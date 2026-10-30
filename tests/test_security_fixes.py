# tests/test_security_fixes.py
"""Security fixes: removed admin backdoors, treatment ownership, login on pathology APIs, ICD-10 apply."""
import os
import uuid

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-security-fixes")
os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("DISABLE_ENCRYPTION", "true")

from app import create_app, db
from app.models import User, Patient, Treatment


REMOVED_PATHS = ("/make-admin", "/admin/update-treatments")
REMOVED_ENDPOINTS = ("main.make_admin", "main.update_treatments_demo")
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
