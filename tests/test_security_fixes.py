# tests/test_security_fixes.py
"""Security fixes: removed admin backdoors, treatment ownership, login on pathology APIs, ICD-10 apply."""
import os
import uuid

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-security-fixes")
os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("DISABLE_ENCRYPTION", "true")

from datetime import date, datetime, time, timedelta

from app import create_app, db
from app.models import (
    User,
    Patient,
    Treatment,
    Clinic,
    ClinicMembership,
    UnmatchedCalendlyBooking,
    RecurringAppointment,
    UserConsent,
)


REMOVED_PATHS = ("/make-admin", "/admin/update-treatments", "/admin/fix-calendly-dates")
REMOVED_ENDPOINTS = ("main.make_admin", "main.update_treatments_demo", "main.fix_calendly_dates")
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
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
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


def _create_admin(email_prefix):
    unique_email = f"{email_prefix}_{uuid.uuid4().hex[:8]}@example.com"
    user = User(username=unique_email, email=unique_email, role="admin", is_admin=True)
    user.set_password("password")
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def platform_admin(app):
    """Platform admin who must not see other practitioners' patient data."""
    with app.app_context():
        user = _create_admin("platform_admin")
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
    with app.app_context():
        original = Treatment.query.get(treatment_id)
        original_status = original.status
        original_notes = original.notes
        original_type = original.treatment_type

    login_user_in_session(client, app, other_physio)

    get_response = client.get(f"/treatment/{treatment_id}/edit", follow_redirects=False)
    assert get_response.status_code == 404

    post_response = client.post(
        f"/treatment/{treatment_id}/edit",
        data={"status": "Cancelled", "notes": "hijacked"},
        follow_redirects=False,
    )
    assert post_response.status_code == 404
    with app.app_context():
        treatment = Treatment.query.get(treatment_id)
        assert treatment.status == original_status
        assert treatment.notes == original_notes
        assert treatment.treatment_type == original_type


def test_user_cannot_view_another_users_treatment(client, app, owner_and_treatment, other_physio):
    """User B cannot view user A's treatment record."""
    treatment_id = owner_and_treatment["treatment_id"]
    login_user_in_session(client, app, other_physio)
    response = client.get(f"/treatment/{treatment_id}/view", follow_redirects=False)
    assert response.status_code == 404


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


def _add_clinic_member(clinic_id, email_prefix, role):
    user = _create_physio(email_prefix)
    membership = ClinicMembership(
        user_id=user.id,
        clinic_id=clinic_id,
        role=role,
        is_active=True,
    )
    membership.set_permissions_by_role()
    db.session.add(membership)
    patient = Patient(name=f"{email_prefix}_{uuid.uuid4().hex[:4]}", user_id=user.id)
    db.session.add(patient)
    db.session.commit()
    treatment = Treatment(
        patient_id=patient.id,
        treatment_type="Assessment",
        status="Scheduled",
    )
    db.session.add(treatment)
    db.session.commit()
    return {
        "user_id": user.id,
        "patient_id": patient.id,
        "treatment_id": treatment.id,
    }


@pytest.fixture
def clinic_physios(app):
    """One clinic: manager M, practitioner R, practitioner R2, each with their own patient."""
    with app.app_context():
        clinic = Clinic(name=f"Clinic_{uuid.uuid4().hex[:6]}")
        db.session.add(clinic)
        db.session.commit()
        return {
            "manager": _add_clinic_member(clinic.id, "manager", "admin"),
            "practitioner": _add_clinic_member(clinic.id, "pract", "practitioner"),
            "other_practitioner": _add_clinic_member(clinic.id, "pract2", "practitioner"),
        }


def _assert_forbidden_and_unwritten(client, app, other):
    edit = client.get(f"/treatment/{other['treatment_id']}/edit", follow_redirects=False)
    assert edit.status_code == 404
    treatments = client.get(
        f"/patient/{other['patient_id']}/edit-treatments", follow_redirects=False
    )
    assert treatments.status_code == 404
    cancel = client.post(
        f"/appointments/update/{other['treatment_id']}",
        data={"action": "cancel"},
        follow_redirects=False,
    )
    assert cancel.status_code == 404
    with app.app_context():
        treatment = Treatment.query.get(other["treatment_id"])
        assert treatment.status != "Cancelled"


def _assert_own_access(client, actor):
    edit = client.get(f"/treatment/{actor['treatment_id']}/edit", follow_redirects=False)
    assert edit.status_code != 404
    assert edit.status_code != 403
    treatments = client.get(
        f"/patient/{actor['patient_id']}/edit-treatments", follow_redirects=False
    )
    assert treatments.status_code == 200


def test_clinic_manager_cannot_access_practitioner_patient(client, app, clinic_physios):
    """Manager M cannot open or write practitioner R's patient."""
    manager = clinic_physios["manager"]
    practitioner = clinic_physios["practitioner"]
    login_user_in_session(client, app, manager["user_id"])
    _assert_forbidden_and_unwritten(client, app, practitioner)
    _assert_own_access(client, manager)


def test_practitioner_cannot_access_other_practitioner_patient(client, app, clinic_physios):
    """Practitioner R cannot open or write practitioner R2's patient."""
    practitioner = clinic_physios["practitioner"]
    other = clinic_physios["other_practitioner"]
    login_user_in_session(client, app, practitioner["user_id"])
    _assert_forbidden_and_unwritten(client, app, other)
    _assert_own_access(client, practitioner)


def test_practitioner_cannot_access_manager_patient(client, app, clinic_physios):
    """Practitioner R cannot open or write manager M's patient."""
    practitioner = clinic_physios["practitioner"]
    manager = clinic_physios["manager"]
    login_user_in_session(client, app, practitioner["user_id"])
    _assert_forbidden_and_unwritten(client, app, manager)
    _assert_own_access(client, practitioner)


def test_edit_treatments_list_handles_none_notes(client, app, owner_and_treatment):
    """None notes must not 500 the edit-treatments list."""
    login_user_in_session(client, app, owner_and_treatment["owner_id"])
    response = client.get(
        f"/patient/{owner_and_treatment['patient_id']}/edit-treatments",
        follow_redirects=False,
    )
    assert response.status_code == 200


@pytest.mark.parametrize("path", REMOVED_PATHS)
def test_removed_routes_404_for_platform_admin(client, app, platform_admin, path):
    """Removed backdoors stay gone even for a platform admin."""
    login_user_in_session(client, app, platform_admin)
    response = client.get(path, follow_redirects=False)
    assert response.status_code == 404


def test_admin_cannot_get_another_users_treatment(client, app, owner_and_treatment, platform_admin):
    """A platform admin must not read another practitioner's treatment via the API."""
    treatment_id = owner_and_treatment["treatment_id"]
    login_user_in_session(client, app, platform_admin)
    response = client.get(f"/api/treatment/{treatment_id}", follow_redirects=False)
    assert response.status_code == 404
    if response.is_json:
        assert "notes" not in (response.get_json() or {})


def test_admin_cannot_delete_another_users_treatment(client, app, owner_and_treatment, platform_admin):
    """A platform admin must not delete another practitioner's treatment."""
    treatment_id = owner_and_treatment["treatment_id"]
    login_user_in_session(client, app, platform_admin)
    response = client.delete(f"/api/treatment/{treatment_id}", follow_redirects=False)
    assert response.status_code == 404
    with app.app_context():
        assert Treatment.query.get(treatment_id) is not None


def test_non_owner_delete_treatment_returns_404_not_500(
    client, app, owner_and_treatment, other_physio
):
    """A non-owner DELETE must 404; first_or_404 must not become a 500."""
    treatment_id = owner_and_treatment["treatment_id"]
    login_user_in_session(client, app, other_physio)
    response = client.delete(f"/api/treatment/{treatment_id}", follow_redirects=False)
    assert response.status_code == 404
    assert response.status_code != 500
    with app.app_context():
        assert Treatment.query.get(treatment_id) is not None


def test_unknown_role_cannot_get_another_users_treatment(
    client, app, owner_and_treatment
):
    """Roles outside patient/physio/admin must not read another user's treatment JSON."""
    with app.app_context():
        unique_email = f"assistant_{uuid.uuid4().hex[:8]}@example.com"
        assistant = User(
            username=unique_email,
            email=unique_email,
            role="assistant",
            is_admin=False,
        )
        assistant.set_password("password")
        db.session.add(assistant)
        db.session.commit()
        assistant_id = assistant.id

    treatment_id = owner_and_treatment["treatment_id"]
    login_user_in_session(client, app, assistant_id)
    response = client.get(f"/api/treatment/{treatment_id}", follow_redirects=False)
    assert response.status_code == 404
    if response.is_json:
        body = response.get_json() or {}
        assert "notes" not in body
        assert "patient_name" not in body


def test_non_owner_get_treatment_is_404_for_every_role(
    client, app, owner_and_treatment, other_physio, platform_admin
):
    """Non-owner GET /api/treatment/<id> is 404 for physio, admin, assistant, and portal."""
    treatment_id = owner_and_treatment["treatment_id"]
    with app.app_context():
        unique_email = f"portal_{uuid.uuid4().hex[:8]}@example.com"
        portal = User(
            username=unique_email,
            email=unique_email,
            role="patient",
            is_admin=False,
        )
        portal.set_password("password")
        db.session.add(portal)
        db.session.commit()
        portal_id = portal.id

    for user_id in (other_physio, platform_admin, portal_id):
        login_user_in_session(client, app, user_id)
        response = client.get(f"/api/treatment/{treatment_id}", follow_redirects=False)
        assert response.status_code == 404
        if response.is_json:
            body = response.get_json() or {}
            assert "notes" not in body
            assert "patient_name" not in body


def test_non_owner_patient_and_treatment_pages_are_404(
    client, app, owner_and_treatment, other_physio
):
    """HTML patient/treatment pages 404 for another practitioner."""
    login_user_in_session(client, app, other_physio)
    patient_page = client.get(
        f"/patient/{owner_and_treatment['patient_id']}", follow_redirects=False
    )
    assert patient_page.status_code == 404
    treatment_page = client.get(
        f"/treatment/{owner_and_treatment['treatment_id']}/view",
        follow_redirects=False,
    )
    assert treatment_page.status_code == 404


def test_admin_cannot_delete_another_users_patient(client, app, owner_and_treatment, platform_admin):
    """A platform admin must not delete another practitioner's patient."""
    patient_id = owner_and_treatment["patient_id"]
    login_user_in_session(client, app, platform_admin)
    response = client.post(f"/patient/{patient_id}/delete", follow_redirects=False)
    assert response.status_code == 404
    with app.app_context():
        assert Patient.query.get(patient_id) is not None


def test_admin_cannot_see_another_users_patient_on_calendar(
    client, app, owner_and_treatment, platform_admin
):
    """Calendar HTML and events must not include another practitioner's patients."""
    with app.app_context():
        patient = Patient.query.get(owner_and_treatment["patient_id"])
        patient_name = patient.name
        treatment = Treatment.query.get(owner_and_treatment["treatment_id"])
        treatment.status = "Scheduled"
        db.session.commit()

    login_user_in_session(client, app, platform_admin)
    calendar_page = client.get("/calendar", follow_redirects=False)
    assert calendar_page.status_code == 200
    assert patient_name.encode() not in calendar_page.data

    events = client.get(
        "/api/calendar-appointments?start=2000-01-01T00:00:00&end=2100-01-01T00:00:00",
        follow_redirects=False,
    )
    assert events.status_code == 200
    payload = events.get_json()
    assert isinstance(payload, list)
    assert payload == []


def test_admin_cannot_access_another_users_calendly_booking(
    client, app, owner_and_treatment, platform_admin
):
    """Calendly review and match must stay scoped to the current user."""
    with app.app_context():
        booking = UnmatchedCalendlyBooking(
            user_id=owner_and_treatment["owner_id"],
            name="OtherClinic Invitee",
            email="invitee@example.com",
            event_type="Initial consult",
            status="Pending",
        )
        db.session.add(booking)
        db.session.commit()
        booking_id = booking.id

    login_user_in_session(client, app, platform_admin)
    review = client.get("/calendly/review", follow_redirects=False)
    assert review.status_code == 200
    assert b"OtherClinic Invitee" not in review.data

    match = client.get(f"/calendly/match_booking/{booking_id}", follow_redirects=False)
    assert match.status_code == 404


def test_admin_can_read_and_delete_own_treatment(client, app, platform_admin):
    """An admin who is also a practitioner still manages only their own records."""
    with app.app_context():
        admin = User.query.get(platform_admin)
        patient = Patient(name=f"AdminOwn_{uuid.uuid4().hex[:4]}", user_id=admin.id)
        db.session.add(patient)
        db.session.commit()
        treatment = Treatment(
            patient_id=patient.id,
            treatment_type="Assessment",
            status="Completed",
        )
        db.session.add(treatment)
        db.session.commit()
        treatment_id = treatment.id
        patient_id = patient.id

    login_user_in_session(client, app, platform_admin)
    get_response = client.get(f"/api/treatment/{treatment_id}", follow_redirects=False)
    assert get_response.status_code == 200
    assert get_response.get_json()["id"] == treatment_id

    delete_response = client.delete(f"/api/treatment/{treatment_id}", follow_redirects=False)
    assert delete_response.status_code == 200
    with app.app_context():
        assert Treatment.query.get(treatment_id) is None
        assert Patient.query.get(patient_id) is not None


def test_admin_only_pages_still_work(client, app, platform_admin):
    """Legitimate admin-only pages stay available."""
    login_user_in_session(client, app, platform_admin)
    response = client.get("/monitoring", follow_redirects=False)
    assert response.status_code == 200


def test_user_cannot_delete_another_users_recurring_appointment(
    client, app, owner_and_treatment, other_physio
):
    """User B gets 404 on A's recurring delete and the rule stays."""
    with app.app_context():
        rule = RecurringAppointment(
            patient_id=owner_and_treatment["patient_id"],
            start_date=date.today(),
            recurrence_type="weekly",
            time_of_day=time(10, 0),
            treatment_type="Standard Session",
        )
        db.session.add(rule)
        db.session.commit()
        rule_id = rule.id

    login_user_in_session(client, app, other_physio)
    response = client.post(f"/recurring/{rule_id}/delete", follow_redirects=False)
    assert response.status_code == 404
    with app.app_context():
        assert RecurringAppointment.query.get(rule_id) is not None


def test_user_cannot_create_or_view_consent_for_another_users_patient(
    client, app, owner_and_treatment, other_physio
):
    """User B cannot create a consent or load the template for user A's patient."""
    patient_id = owner_and_treatment["patient_id"]
    with app.app_context():
        patient = Patient.query.get(patient_id)
        patient_name = patient.name

    login_user_in_session(client, app, other_physio)
    create = client.post(
        "/api/consent/create",
        json={
            "consent_type": "fisioterapia_general",
            "patient_id": patient_id,
            "lang": "es",
        },
        follow_redirects=False,
    )
    assert create.status_code == 404
    with app.app_context():
        assert UserConsent.query.filter_by(patient_id=patient_id).count() == 0

    template = client.get(
        f"/api/consent_template?type=fisioterapia_general&lang=es&patient_id={patient_id}",
        follow_redirects=False,
    )
    assert template.status_code == 404
    assert patient_name.encode() not in template.data


def test_consent_apis_deny_when_consent_owner_does_not_own_patient(
    client, app, owner_and_treatment, other_physio
):
    """An A-owned consent attached to B's patient is still denied for A."""
    with app.app_context():
        other = User.query.get(other_physio)
        b_patient = Patient(
            name=f"BPatient_{uuid.uuid4().hex[:4]}",
            user_id=other.id,
            diagnosis="BOwnDiagnosis",
        )
        db.session.add(b_patient)
        db.session.commit()
        mixed = UserConsent(
            user_id=owner_and_treatment["owner_id"],
            patient_id=b_patient.id,
            purpose="fisioterapia_general",
            given_at=datetime.utcnow(),
            is_active=True,
        )
        db.session.add(mixed)
        db.session.commit()
        consent_id = mixed.id
        b_patient_id = b_patient.id
        b_patient_name = b_patient.name

    login_user_in_session(client, app, owner_and_treatment["owner_id"])
    create = client.post(
        "/api/consent/create",
        json={
            "consent_type": "fisioterapia_general",
            "patient_id": b_patient_id,
            "lang": "es",
        },
        follow_redirects=False,
    )
    assert create.status_code == 404

    template = client.get(
        f"/api/consent_template?type=fisioterapia_general&lang=es&patient_id={b_patient_id}",
        follow_redirects=False,
    )
    assert template.status_code == 404
    assert b_patient_name.encode() not in template.data

    revoke = client.post(f"/api/consent/{consent_id}/revoke", follow_redirects=False)
    assert revoke.status_code == 404

    delete = client.post(f"/api/consent/{consent_id}/delete", follow_redirects=False)
    assert delete.status_code == 404

    with app.app_context():
        consent = UserConsent.query.get(consent_id)
        assert consent is not None
        assert consent.is_active is True
        assert UserConsent.query.filter_by(patient_id=b_patient_id).count() == 1


def test_patient_portal_cannot_use_consent_apis(client, app, owner_and_treatment):
    """Patient-portal role is denied on both consent APIs."""
    with app.app_context():
        unique_email = f"portal_{uuid.uuid4().hex[:8]}@example.com"
        portal = User(
            username=unique_email,
            email=unique_email,
            role="patient",
            is_admin=False,
        )
        portal.set_password("password")
        db.session.add(portal)
        db.session.commit()
        portal_id = portal.id

    patient_id = owner_and_treatment["patient_id"]
    login_user_in_session(client, app, portal_id)

    create = client.post(
        "/api/consent/create",
        json={
            "consent_type": "fisioterapia_general",
            "patient_id": patient_id,
            "lang": "es",
        },
        follow_redirects=False,
    )
    assert create.status_code in (403, 404)

    template = client.get(
        f"/api/consent_template?type=fisioterapia_general&lang=es&patient_id={patient_id}",
        follow_redirects=False,
    )
    assert template.status_code in (403, 404)


def test_reports_and_treatments_by_month_are_own_only(
    client, app, owner_and_treatment, other_physio
):
    """Reports and monthly counts include only the caller's patients."""
    leak_diagnosis = f"LeakDiag{uuid.uuid4().hex[:6]}"
    own_diagnosis = f"OwnDiag{uuid.uuid4().hex[:6]}"
    with app.app_context():
        owner_patient = Patient.query.get(owner_and_treatment["patient_id"])
        owner_patient.diagnosis = leak_diagnosis
        extra_a = Patient(
            name=f"LeakExtra_{uuid.uuid4().hex[:4]}",
            user_id=owner_and_treatment["owner_id"],
            diagnosis=leak_diagnosis,
        )
        extra_a2 = Patient(
            name=f"LeakExtra2_{uuid.uuid4().hex[:4]}",
            user_id=owner_and_treatment["owner_id"],
            diagnosis=leak_diagnosis,
        )
        other = User.query.get(other_physio)
        b_patient = Patient(
            name=f"OwnOnly_{uuid.uuid4().hex[:4]}",
            user_id=other.id,
            diagnosis=own_diagnosis,
        )
        db.session.add_all([extra_a, extra_a2, b_patient])
        db.session.commit()
        for patient_id in (extra_a.id, extra_a2.id):
            db.session.add(
                Treatment(
                    patient_id=patient_id,
                    treatment_type="Assessment",
                    status="Completed",
                )
            )
        db.session.add(
            Treatment(
                patient_id=b_patient.id,
                treatment_type="Assessment",
                status="Completed",
            )
        )
        db.session.commit()

    login_user_in_session(client, app, other_physio)
    reports = client.get("/reports", follow_redirects=False)
    assert reports.status_code == 200
    assert leak_diagnosis.encode() not in reports.data
    assert own_diagnosis.encode() in reports.data
    assert b">3</h2>" not in reports.data
    assert b">1</h2>" in reports.data

    monthly = client.get("/api/reports/treatments-by-month", follow_redirects=False)
    assert monthly.status_code == 200
    payload = monthly.get_json()["treatments_by_month"]
    assert sum(payload["data"]) == 1


def test_review_payments_does_not_complete_other_users_treatments(
    client, app, owner_and_treatment, other_physio
):
    """User B visiting review-payments must not flip user A's past Scheduled rows."""
    with app.app_context():
        past_treatment = Treatment(
            patient_id=owner_and_treatment["patient_id"],
            treatment_type="Assessment",
            status="Scheduled",
            created_at=datetime.now() - timedelta(days=3),
        )
        db.session.add(past_treatment)
        db.session.commit()
        past_id = past_treatment.id

    login_user_in_session(client, app, other_physio)
    response = client.get("/review-payments", follow_redirects=False)
    assert response.status_code == 200
    with app.app_context():
        still_scheduled = Treatment.query.get(past_id)
        assert still_scheduled.status == "Scheduled"


def test_match_booking_cannot_reassign_another_tenants_treatment(
    client, app, owner_and_treatment, other_physio
):
    """A colliding Calendly invitee id must not move user A's treatment onto B's patient."""
    invitee_id = f"invitee-{uuid.uuid4().hex}"
    with app.app_context():
        a_treatment = Treatment.query.get(owner_and_treatment["treatment_id"])
        a_treatment.calendly_invitee_uri = invitee_id
        a_patient_id = a_treatment.patient_id

        other = User.query.get(other_physio)
        b_patient = Patient(name=f"BMatch_{uuid.uuid4().hex[:4]}", user_id=other.id)
        db.session.add(b_patient)
        db.session.commit()

        booking = UnmatchedCalendlyBooking(
            user_id=other.id,
            name="Collision Invitee",
            email="collision@example.com",
            event_type="Initial consult",
            status="Pending",
            calendly_invitee_id=invitee_id,
            start_time=datetime.utcnow(),
        )
        db.session.add(booking)
        db.session.commit()
        booking_id = booking.id
        b_patient_id = b_patient.id
        a_treatment_id = a_treatment.id

    login_user_in_session(client, app, other_physio)
    foreign_patient = client.post(
        "/api/calendly/match-booking",
        json={
            "booking_id": booking_id,
            "patient_id": a_patient_id,
        },
        follow_redirects=False,
    )
    assert foreign_patient.status_code == 404
    with app.app_context():
        assert Treatment.query.get(a_treatment_id).patient_id == a_patient_id

    match_own = client.post(
        "/api/calendly/match-booking",
        json={
            "booking_id": booking_id,
            "patient_id": b_patient_id,
        },
        follow_redirects=False,
    )
    assert match_own.status_code == 200
    assert match_own.get_json()["success"] is True
    with app.app_context():
        a_treatment = Treatment.query.get(a_treatment_id)
        assert a_treatment.patient_id == a_patient_id
        b_treatments = Treatment.query.filter_by(patient_id=b_patient_id).all()
        assert len(b_treatments) == 1
        assert b_treatments[0].id != a_treatment_id


def test_first_registered_user_is_not_admin(client, app):
    """The first sign-up is a physio, not an admin. Admin is CLI-only."""
    unique_email = f"first_{uuid.uuid4().hex[:8]}@example.com"
    with app.app_context():
        assert User.query.count() == 0

    response = client.post(
        "/auth/register",
        data={
            "email": unique_email,
            "password": "newpassword",
            "confirm_password": "newpassword",
            "consent_checkbox": "y",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        user = User.query.filter_by(email=unique_email).first()
        assert user is not None
        assert user.is_admin is False
        assert user.role == "physio"
