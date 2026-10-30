# tests/test_security_fixes.py
"""Security fixes: removed admin backdoors, treatment ownership, login on pathology APIs, ICD-10 apply."""
import os
import uuid

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-security-fixes")
os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("DISABLE_ENCRYPTION", "true")

from app import create_app, db
from app.models import User, Patient, Treatment, Clinic, ClinicMembership


REMOVED_PATHS = ("/make-admin", "/admin/update-treatments")
REMOVED_ENDPOINTS = ("main.make_admin", "main.update_treatments_demo")
TEST_EDIT_PATH_PREFIX = "/test/edit-treatment"
BULK_UPDATE_DENIED_MESSAGE = "Unable to update treatments."
PATHOLOGY_LOGIN_PATHS = (
    "/api/pathology-guides",
    "/api/pathology-guide/1/stats",
    "/api/diagnosis-templates-with-guides",
)


@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["DISABLE_ENCRYPTION"] = True

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        try:
            db.drop_all()
        except Exception:
            db.session.close()


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


def login_user_in_session(client, app, user_id):
    """Helper function to login a user in the test session."""
    with app.app_context():
        user = User.query.get(user_id)
        if user:
            with client.session_transaction() as sess:
                sess["_user_id"] = str(user.id)
                sess["_fresh"] = True


def _create_physio(email_prefix):
    unique_email = f"{email_prefix}_{uuid.uuid4().hex[:8]}@example.com"
    user = User(username=unique_email, email=unique_email, role="physio")
    user.set_password("password")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def owner_and_treatment(app):
    """Physio A owns a patient and one treatment."""
    with app.app_context():
        owner = _create_physio("owner")
        patient = Patient(name=f"Patient_{uuid.uuid4().hex[:4]}", user_id=owner.id)
        db.session.add(patient)
        db.session.commit()
        treatment = Treatment(
            patient_id=patient.id,
            treatment_type="Assessment",
            status="Completed",
        )
        db.session.add(treatment)
        db.session.commit()
        return {
            "owner_id": owner.id,
            "patient_id": patient.id,
            "treatment_id": treatment.id,
        }


@pytest.fixture
def other_physio(app):
    """Physio B who does not own the other user's records."""
    with app.app_context():
        user = _create_physio("other")
        return user.id


def test_removed_routes_absent_from_url_map(app):
    """The backdoor paths and endpoints must not be registered."""
    paths = {rule.rule for rule in app.url_map.iter_rules()}
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    for path in REMOVED_PATHS:
        assert path not in paths
    for endpoint in REMOVED_ENDPOINTS:
        assert endpoint not in endpoints


@pytest.mark.parametrize("path", REMOVED_PATHS)
def test_removed_routes_404_for_anonymous(client, path):
    """Anonymous visitors must get 404, not a login redirect or 200."""
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 404


@pytest.mark.parametrize("path", REMOVED_PATHS)
def test_removed_routes_404_for_logged_in_non_admin(client, app, other_physio, path):
    """A logged-in non-admin must not be able to hit the old backdoors."""
    login_user_in_session(client, app, other_physio)
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 404


def test_user_cannot_edit_another_users_treatment(client, app, owner_and_treatment, other_physio):
    """User B cannot GET or POST the edit page for user A's treatment."""
    treatment_id = owner_and_treatment["treatment_id"]
    login_user_in_session(client, app, other_physio)

    get_response = client.get(f"/treatment/{treatment_id}/edit", follow_redirects=False)
    assert get_response.status_code in (403, 404)

    post_response = client.post(
        f"/treatment/{treatment_id}/edit",
        data={"status": "Completed", "notes": "hijacked"},
        follow_redirects=False,
    )
    assert post_response.status_code in (403, 404)


def test_user_cannot_view_another_users_treatment(client, app, owner_and_treatment, other_physio):
    """User B cannot view user A's treatment record."""
    treatment_id = owner_and_treatment["treatment_id"]
    login_user_in_session(client, app, other_physio)
    response = client.get(f"/treatment/{treatment_id}/view", follow_redirects=False)
    assert response.status_code != 200
    assert response.status_code in (302, 403, 404)


def test_owner_can_open_own_treatment_edit(client, app, owner_and_treatment):
    """The owning physio is not blocked by the new ownership check."""
    treatment_id = owner_and_treatment["treatment_id"]
    login_user_in_session(client, app, owner_and_treatment["owner_id"])
    response = client.get(f"/treatment/{treatment_id}/edit", follow_redirects=False)
    assert response.status_code != 404
    assert response.status_code != 403


@pytest.mark.parametrize("path", PATHOLOGY_LOGIN_PATHS)
def test_pathology_endpoints_require_login(client, path):
    """Anonymous callers must be sent to login, not given guide data."""
    response = client.get(path, follow_redirects=False)
    assert response.status_code in (302, 401)
    if response.status_code == 302:
        assert "/auth/login" in (response.headers.get("Location") or "")


def test_icd10_template_apply_does_not_crash(client, app, owner_and_treatment):
    """Applying a missing template must 404, not NameError on current_app."""
    login_user_in_session(client, app, owner_and_treatment["owner_id"])
    response = client.post(
        f"/api/template/999999/apply/{owner_and_treatment['patient_id']}",
        json={},
        follow_redirects=False,
    )
    assert response.status_code != 500
    assert response.status_code in (403, 404)


def test_icd10_api_imports_current_app():
    """current_app must be imported so apply_diagnosis_template can log/run."""
    import app.routes.icd10_api as icd10_api

    assert hasattr(icd10_api, "current_app")
    assert "current_app" in icd10_api.apply_diagnosis_template.__globals__


def test_user_cannot_cancel_another_users_appointment(client, app, owner_and_treatment, other_physio):
    """User B cannot cancel user A's treatment via /appointments/update/<id>."""
    treatment_id = owner_and_treatment["treatment_id"]
    login_user_in_session(client, app, other_physio)
    response = client.post(
        f"/appointments/update/{treatment_id}",
        data={"action": "cancel"},
        follow_redirects=False,
    )
    assert response.status_code in (403, 404)
    with app.app_context():
        treatment = Treatment.query.get(treatment_id)
        assert treatment.status != "Cancelled"


def test_owner_can_cancel_own_appointment(client, app, owner_and_treatment):
    """The owning physio can still cancel their own appointment."""
    treatment_id = owner_and_treatment["treatment_id"]
    login_user_in_session(client, app, owner_and_treatment["owner_id"])
    response = client.post(
        f"/appointments/update/{treatment_id}",
        data={"action": "cancel"},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert response.get_json()["success"] is True
    with app.app_context():
        treatment = Treatment.query.get(treatment_id)
        assert treatment.status == "Cancelled"


def test_test_edit_treatment_route_removed(app, client, owner_and_treatment, other_physio):
    """Leftover /test/edit-treatment/<id> must be gone for everyone."""
    paths = {rule.rule for rule in app.url_map.iter_rules()}
    endpoints = {rule.endpoint for rule in app.url_map.iter_rules()}
    assert not any(rule.startswith(TEST_EDIT_PATH_PREFIX) or TEST_EDIT_PATH_PREFIX in rule for rule in paths)
    assert "main.test_edit_treatment" not in endpoints

    treatment_id = owner_and_treatment["treatment_id"]
    anon = client.get(f"{TEST_EDIT_PATH_PREFIX}/{treatment_id}", follow_redirects=False)
    assert anon.status_code == 404

    login_user_in_session(client, app, other_physio)
    other = client.get(f"{TEST_EDIT_PATH_PREFIX}/{treatment_id}", follow_redirects=False)
    assert other.status_code == 404


def test_bulk_update_filters_before_reference_and_hides_id_existence(
    client, app, owner_and_treatment, other_physio
):
    """Foreign ids first must not block own updates, and errors must be uniform."""
    with app.app_context():
        other = User.query.get(other_physio)
        other_patient = Patient(name=f"Other_{uuid.uuid4().hex[:4]}", user_id=other.id)
        db.session.add(other_patient)
        db.session.commit()
        other_treatment = Treatment(
            patient_id=other_patient.id,
            treatment_type="Assessment",
            status="Completed",
        )
        db.session.add(other_treatment)
        db.session.commit()
        other_treatment_id = other_treatment.id

    own_id = owner_and_treatment["treatment_id"]
    login_user_in_session(client, app, owner_and_treatment["owner_id"])

    mixed = client.post(
        "/api/treatments/bulk-update",
        json={
            "treatment_ids": [other_treatment_id, own_id],
            "field": "payment_method",
            "value": "Cash",
        },
        follow_redirects=False,
    )
    assert mixed.status_code == 200
    assert mixed.get_json()["success"] is True
    with app.app_context():
        own = Treatment.query.get(own_id)
        foreign = Treatment.query.get(other_treatment_id)
        assert own.payment_method == "Cash"
        assert foreign.payment_method != "Cash"

    foreign_only = client.post(
        "/api/treatments/bulk-update",
        json={
            "treatment_ids": [other_treatment_id],
            "field": "payment_method",
            "value": "Card",
        },
        follow_redirects=False,
    )
    missing = client.post(
        "/api/treatments/bulk-update",
        json={
            "treatment_ids": [999999],
            "field": "payment_method",
            "value": "Card",
        },
        follow_redirects=False,
    )
    assert foreign_only.status_code == missing.status_code == 400
    assert foreign_only.get_json()["message"] == missing.get_json()["message"] == BULK_UPDATE_DENIED_MESSAGE


def test_clinic_manager_can_edit_member_patient_treatment(client, app):
    """Clinic managers who can manage clinic patients keep access to members' records."""
    with app.app_context():
        clinic = Clinic(name=f"Clinic_{uuid.uuid4().hex[:6]}")
        db.session.add(clinic)
        db.session.commit()

        manager = _create_physio("manager")
        member = _create_physio("member")

        manager_membership = ClinicMembership(
            user_id=manager.id,
            clinic_id=clinic.id,
            role="admin",
            is_active=True,
        )
        manager_membership.set_permissions_by_role()
        member_membership = ClinicMembership(
            user_id=member.id,
            clinic_id=clinic.id,
            role="practitioner",
            is_active=True,
        )
        member_membership.set_permissions_by_role()
        db.session.add_all([manager_membership, member_membership])

        patient = Patient(name=f"MemberPatient_{uuid.uuid4().hex[:4]}", user_id=member.id)
        db.session.add(patient)
        db.session.commit()
        treatment = Treatment(
            patient_id=patient.id,
            treatment_type="Assessment",
            status="Scheduled",
        )
        db.session.add(treatment)
        db.session.commit()

        manager_id = manager.id
        treatment_id = treatment.id
        patient_id = patient.id

    login_user_in_session(client, app, manager_id)
    manager_edit = client.get(f"/treatment/{treatment_id}/edit", follow_redirects=False)
    assert manager_edit.status_code != 404
    assert manager_edit.status_code != 403

    manager_list = client.get(f"/patient/{patient_id}/edit-treatments", follow_redirects=False)
    assert manager_list.status_code == 200


def test_edit_treatments_list_handles_none_notes(client, app, owner_and_treatment):
    """None notes must not 500 the edit-treatments list."""
    login_user_in_session(client, app, owner_and_treatment["owner_id"])
    response = client.get(
        f"/patient/{owner_and_treatment['patient_id']}/edit-treatments",
        follow_redirects=False,
    )
    assert response.status_code == 200
