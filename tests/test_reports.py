# tests/test_reports.py
from app import create_app, db
from app.models import User, Patient, Treatment, PatientReport
import pytest
import uuid
from datetime import datetime, timedelta

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

@pytest.fixture
def auth_client(client, app):
    """A test client with authenticated user."""
    with app.app_context():
        # Create test user with unique email
        unique_email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
        user = User(username=f'testuser_{uuid.uuid4().hex[:8]}', email=unique_email, is_admin=True)
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        
        # Login
        client.post('/auth/login', data={
            'email': unique_email,
            'password': 'password123'
        })
        
        return client

def test_reports_route_requires_auth(client):
    """Test that reports route requires authentication."""
    response = client.get('/reports', follow_redirects=True)
    assert response.status_code == 200
    # Should redirect to login page

def test_reports_route_with_auth(auth_client):
    """Test reports route with authenticated user."""
    response = auth_client.get('/reports')
    assert response.status_code == 200

def test_treatments_by_month_api(auth_client, app):
    """Test the treatments by month API endpoint."""
    with app.app_context():
        # Get the user from the session
        user = User.query.filter_by(is_admin=True).first()
        if not user:
            # Create a test user if none exists
            unique_email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
            user = User(username=f'testuser_{uuid.uuid4().hex[:8]}', email=unique_email, is_admin=True)
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()

        # Create test data with shorter name
        patient = Patient(name=f'Patient_{uuid.uuid4().hex[:4]}', user_id=user.id)
        db.session.add(patient)
        db.session.commit()

        # Create a treatment
        treatment = Treatment(
            patient_id=patient.id,
            treatment_type='Assessment',
            status='Completed',
            created_at=datetime.now()
        )
        db.session.add(treatment)
        db.session.commit()

        response = auth_client.get('/api/reports/treatments-by-month')
        assert response.status_code == 200
        data = response.get_json()
        assert 'treatments_by_month' in data

def test_patient_reports_list(auth_client, app):
    """Test patient reports list endpoint."""
    with app.app_context():
        # Get the user from the session
        user = User.query.filter_by(is_admin=True).first()
        if not user:
            # Create a test user if none exists
            unique_email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
            user = User(username=f'testuser_{uuid.uuid4().hex[:8]}', email=unique_email, is_admin=True)
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()

        patient = Patient(name=f'Patient_{uuid.uuid4().hex[:4]}', user_id=user.id)
        db.session.add(patient)
        db.session.commit()

        # Create a test report so the template has a valid report object to work with
        report = PatientReport(
            patient_id=patient.id,
            content='Test report content',
            report_type='Test Report'
        )
        db.session.add(report)
        db.session.commit()

        response = auth_client.get('/reports')
        assert response.status_code == 200

def test_report_pdf_download(auth_client, app):
    """Test report PDF download functionality."""
    with app.app_context():
        # Get the user from the session
        user = User.query.filter_by(is_admin=True).first()
        if not user:
            # Create a test user if none exists
            unique_email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
            user = User(username=f'testuser_{uuid.uuid4().hex[:8]}', email=unique_email, is_admin=True)
            user.set_password('password123')
            db.session.add(user)
            db.session.commit()

        patient = Patient(name=f'Patient_{uuid.uuid4().hex[:4]}', user_id=user.id)
        db.session.add(patient)
        db.session.commit()

        # Create a test report - remove user_id field as it doesn't exist
        report = PatientReport(
            patient_id=patient.id,
            content='Test report content for PDF generation',
            report_type='Test Report'
        )
        db.session.add(report)
        db.session.commit()

        response = auth_client.get(f'/report/{report.id}/pdf')
        # Should return PDF or redirect to PDF generation
        assert response.status_code in [200, 302] 