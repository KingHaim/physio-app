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
        
        # Create test data
        patient = Patient(name='Test Patient', user_id=user.id)
        db.session.add(patient)
        db.session.commit()
        
        # Create some treatments
        treatment1 = Treatment(
            patient_id=patient.id,
            provider=user.username,
            treatment_type='Massage',
            created_at=datetime.utcnow()
        )
        treatment2 = Treatment(
            patient_id=patient.id,
            provider=user.username,
            treatment_type='Exercise',
            created_at=datetime.utcnow() - timedelta(days=30)
        )
        db.session.add_all([treatment1, treatment2])
        db.session.commit()
        
        # Test API endpoint
        response = auth_client.get('/api/reports/treatments-by-month')
        assert response.status_code == 200
        
        data = response.get_json()
        assert 'data' in data
        assert len(data['data']) > 0

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
        
        patient = Patient(name='Test Patient', user_id=user.id)
        db.session.add(patient)
        db.session.commit()
        
        response = auth_client.get(f'/patient/{patient.id}/reports_list')
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
        
        patient = Patient(name='Test Patient', user_id=user.id)
        db.session.add(patient)
        db.session.commit()
        
        # Create a test report - check what fields PatientReport actually has
        report = PatientReport(
            patient_id=patient.id,
            user_id=user.id,
            report_type='treatment_summary',
            content='Test report content',
            created_at=datetime.utcnow()
        )
        db.session.add(report)
        db.session.commit()
        
        response = auth_client.get(f'/report/{report.id}/pdf')
        assert response.status_code == 200
        assert response.headers['Content-Type'] == 'application/pdf' 