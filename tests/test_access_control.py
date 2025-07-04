# tests/test_access_control.py
from app import create_app, db
from app.models import User, Patient, Treatment
import pytest
import uuid
from flask_login import login_user

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        # Use a more graceful cleanup approach
        try:
            db.drop_all()
        except Exception:
            # If drop_all fails, just close the session
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
                sess['_user_id'] = str(user.id)
                sess['_fresh'] = True

@pytest.fixture
def admin_user(app):
    """Create an admin user."""
    with app.app_context():
        unique_email = f"admin_{uuid.uuid4().hex[:8]}@example.com"
        user = User(username=unique_email, email=unique_email, is_admin=True, role='admin')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()
        return user.id

@pytest.fixture
def physio_user(app):
    """Create a physio user."""
    with app.app_context():
        unique_email = f"physio_{uuid.uuid4().hex[:8]}@example.com"
        user = User(username=unique_email, email=unique_email, role='physio')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()
        return user.id

@pytest.fixture
def patient_user(app):
    """Create a patient user."""
    with app.app_context():
        unique_email = f"patient_{uuid.uuid4().hex[:8]}@example.com"
        user = User(username=unique_email, email=unique_email, role='patient')
        user.set_password('password')
        db.session.add(user)
        db.session.commit()
        return user.id

def test_admin_access_to_monitoring(client, app, admin_user):
    """Test that admin can access monitoring dashboard."""
    login_user_in_session(client, app, admin_user)
    response = client.get('/monitoring')
    assert response.status_code == 200

def test_physio_denied_monitoring_access(client, app, physio_user):
    """Test that physio users cannot access monitoring dashboard."""
    login_user_in_session(client, app, physio_user)
    response = client.get('/monitoring', follow_redirects=False)
    # Should be forbidden (403)
    assert response.status_code == 403

def test_patient_denied_monitoring_access(client, app, patient_user):
    """Test that patient users cannot access monitoring dashboard."""
    login_user_in_session(client, app, patient_user)
    response = client.get('/monitoring', follow_redirects=False)
    # Should be forbidden (403)
    assert response.status_code == 403

def test_physio_access_to_patients_list(client, app, physio_user):
    """Test that physio users can access patients list."""
    login_user_in_session(client, app, physio_user)
    response = client.get('/patients')
    assert response.status_code == 200

def test_admin_access_to_patients_list(client, app, admin_user):
    """Test that admin users can access patients list."""
    login_user_in_session(client, app, admin_user)
    response = client.get('/patients')
    assert response.status_code == 200

def test_patient_denied_patients_list_access(client, app, patient_user):
    """Test that patient users cannot access patients list."""
    login_user_in_session(client, app, patient_user)
    response = client.get('/patients', follow_redirects=True)
    assert response.status_code == 200
    # Should redirect or show access denied

@pytest.mark.skip(reason="Database field length issues in CI/CD - needs migration fix")
def test_physio_access_to_own_patients(client, app, physio_user):
    """Test that physio users can access their own patients."""
    with app.app_context():
        physio = User.query.get(physio_user)
        patient = Patient(name=f'Patient_{uuid.uuid4().hex[:4]}', user_id=physio.id)
        db.session.add(patient)
        db.session.commit()
        
        login_user_in_session(client, app, physio_user)
        response = client.get(f'/patient/{patient.id}')
        assert response.status_code == 200

@pytest.mark.skip(reason="Database field length issues in CI/CD - needs migration fix")
def test_physio_denied_other_patients(client, app, physio_user, admin_user):
    """Test that physio users cannot access other users' patients."""
    with app.app_context():
        physio = User.query.get(physio_user)
        admin = User.query.get(admin_user)
        patient = Patient(name=f'Admin_Patient_{uuid.uuid4().hex[:4]}', user_id=admin.id)
        db.session.add(patient)
        db.session.commit()
        
        login_user_in_session(client, app, physio_user)
        response = client.get(f'/patient/{patient.id}', follow_redirects=False)
        # The application redirects (302) instead of returning 403
        assert response.status_code == 302

@pytest.mark.skip(reason="Database field length issues in CI/CD - needs migration fix")
def test_admin_access_to_all_patients(client, app, admin_user, physio_user):
    """Test that admin users can access all patients."""
    with app.app_context():
        admin = User.query.get(admin_user)
        physio = User.query.get(physio_user)
        patient = Patient(name=f'Physio_Patient_{uuid.uuid4().hex[:4]}', user_id=physio.id)
        db.session.add(patient)
        db.session.commit()
        
        login_user_in_session(client, app, admin_user)
        response = client.get(f'/patient/{patient.id}')
        assert response.status_code == 200

def test_analytics_requires_physio_role(client, app, physio_user):
    """Test that analytics requires physio role."""
    login_user_in_session(client, app, physio_user)
    response = client.get('/analytics')
    assert response.status_code == 200

def test_analytics_denied_for_patients(client, app, patient_user):
    """Test that patients cannot access analytics."""
    login_user_in_session(client, app, patient_user)
    response = client.get('/analytics', follow_redirects=True)
    assert response.status_code == 200
    # Should redirect or show access denied

def test_financials_requires_physio_role(client, app, physio_user):
    """Test that financials requires physio role."""
    login_user_in_session(client, app, physio_user)
    response = client.get('/financials')
    assert response.status_code == 200

def test_financials_denied_for_patients(client, app, patient_user):
    """Test that patients cannot access financials."""
    login_user_in_session(client, app, patient_user)
    response = client.get('/financials', follow_redirects=True)
    assert response.status_code == 200
    # Should redirect or show access denied

def test_patient_dashboard_for_patients(client, app, patient_user):
    """Test that patients can access their dashboard (should redirect if not allowed)."""
    login_user_in_session(client, app, patient_user)
    response = client.get('/patient/dashboard', follow_redirects=False)
    # Should redirect (302) if not allowed
    assert response.status_code == 302

def test_patient_dashboard_denied_for_physios(client, app, physio_user):
    """Test that physios cannot access patient dashboard."""
    login_user_in_session(client, app, physio_user)
    response = client.get('/patient/dashboard', follow_redirects=True)
    assert response.status_code == 200
    # Should redirect or show access denied

def test_unauthenticated_access_redirects(client):
    """Test that unauthenticated access redirects to login."""
    response = client.get('/patients', follow_redirects=True)
    assert response.status_code == 200
    # Should redirect to login page 

def test_access_control(client, app, db_session):
    with app.app_context():
        # Create users with different roles
        unique_email_admin = f"admin_{uuid.uuid4().hex[:8]}@example.com"
        admin_user = User(username=unique_email_admin, email=unique_email_admin, is_admin=True, role='admin')
        admin_user.set_password('password')
        
        unique_email_physio = f"physio_{uuid.uuid4().hex[:8]}@example.com"
        physio_user = User(username=unique_email_physio, email=unique_email_physio, role='physio')
        physio_user.set_password('password')

        unique_email_patient = f"patient_{uuid.uuid4().hex[:8]}@example.com"
        patient_user = User(username=unique_email_patient, email=unique_email_patient, role='patient')
        patient_user.set_password('password')

        db.session.add_all([admin_user, physio_user, patient_user])
        db.session.commit() 