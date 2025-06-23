# tests/test_auth.py
from app import create_app, db
from app.models import User
from flask_login import current_user
import pytest
import uuid

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = create_app()
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
    
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
def runner(app):
    """A test runner for the app's Click commands."""
    return app.test_cli_runner()

def test_login_route_exists(client):
    """Test that the login route exists and returns 200."""
    response = client.get("/auth/login")
    assert response.status_code == 200

def test_register_route_exists(client):
    """Test that the register route exists and returns 200."""
    response = client.get("/auth/register")
    assert response.status_code == 200

def test_login_form_submission(client, app):
    """Test login form submission with valid credentials."""
    with app.app_context():
        # Create a test user with unique email
        unique_email = f"testuser_{uuid.uuid4().hex[:8]}@example.com"
        user = User(username=f'testuser_{uuid.uuid4().hex[:8]}', email=unique_email)
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        
        # Test login
        response = client.post('/auth/login', data={
            'email': unique_email,
            'password': 'password123',
            'remember_me': False
        }, follow_redirects=True)
        
        assert response.status_code == 200

def test_login_invalid_credentials(client):
    """Test login with invalid credentials."""
    response = client.post('/auth/login', data={
        'email': 'nonexistent@example.com',
        'password': 'wrongpassword',
        'remember_me': False
    }, follow_redirects=True)
    
    assert response.status_code == 200
    # Should stay on login page or show error

def test_registration(client, app):
    # Test successful registration
    with app.app_context():
        unique_email = f"newuser_{uuid.uuid4().hex[:8]}@example.com"
        response = client.post('/auth/register', data={
            'email': unique_email,
            'password': 'newpassword',
            'confirm_password': 'newpassword',
            'consent_checkbox': 'y'
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b'Registration successful!' in response.data

        # Test registration with existing email
        response = client.post('/auth/register', data={
            'email': unique_email,
            'password': 'anotherpassword',
            'confirm_password': 'anotherpassword',
            'consent_checkbox': 'y'
        }, follow_redirects=True)
        assert b'Email already registered' in response.data

def test_logout_route(client):
    """Test logout functionality."""
    response = client.get('/auth/logout', follow_redirects=True)
    assert response.status_code == 200 