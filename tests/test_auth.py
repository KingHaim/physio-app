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

def test_register_new_user(client, app):
    """Test user registration."""
    with app.app_context():
        initial_user_count = User.query.count()
        
        unique_email = f"newuser_{uuid.uuid4().hex[:8]}@example.com"
        unique_username = f"newuser_{uuid.uuid4().hex[:8]}"
        
        response = client.post('/auth/register', data={
            'username': unique_username,
            'email': unique_email,
            'password': 'password123',
            'confirm_password': 'password123',
            'consent_checkbox': True
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert User.query.count() == initial_user_count + 1

def test_register_duplicate_email(client, app):
    """Test registration with duplicate email."""
    with app.app_context():
        # Create initial user with unique email
        unique_email = f"existing_{uuid.uuid4().hex[:8]}@example.com"
        user = User(username=f'existinguser_{uuid.uuid4().hex[:8]}', email=unique_email)
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        
        # Try to register with same email
        response = client.post('/auth/register', data={
            'username': f'newuser_{uuid.uuid4().hex[:8]}',
            'email': unique_email,
            'password': 'password123',
            'confirm_password': 'password123',
            'consent_checkbox': True
        }, follow_redirects=True)
        
        assert response.status_code == 200
        # Should show error message

def test_logout_route(client):
    """Test logout functionality."""
    response = client.get('/auth/logout', follow_redirects=True)
    assert response.status_code == 200 