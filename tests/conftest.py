import pytest
import uuid
from flask import Flask
from app import create_app, db
from app.models import User, Patient, Treatment, PatientReport, Plan, UserSubscription
from sqlalchemy import text
from config import TestConfig


@pytest.fixture(scope='session')
def app():
    """Create and configure a new app instance for each test session."""
    app = create_app()
    app.config.from_object(TestConfig)
    app.config['STRIPE_WEBHOOK_SECRET'] = 'whsec_test_secret'
    
    return app


@pytest.fixture(scope='function')
def client(app):
    """Create a test client for the app."""
    with app.test_client() as client:
        yield client


@pytest.fixture(scope='function')
def auth_client(client, app):
    """Create an authenticated test client."""
    with app.app_context():
        # Create a test admin user
        unique_email = f"admin_{uuid.uuid4().hex[:8]}@example.com"
        user = User(username=f'admin_{uuid.uuid4().hex[:8]}', email=unique_email, is_admin=True)
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        
        # Login the user
        response = client.post('/auth/login', data={
            'email': unique_email,
            'password': 'password123'
        }, follow_redirects=True)
        
        yield client
        
        # Cleanup
        try:
            db.session.delete(user)
            db.session.commit()
        except:
            db.session.rollback()


@pytest.fixture(scope='function')
def app_context(app):
    """Create an application context for tests."""
    with app.app_context():
        yield app


@pytest.fixture(scope='function', autouse=True)
def cleanup_database(app):
    """Clean up the database after each test."""
    with app.app_context():
        # Start a transaction
        connection = db.engine.connect()
        transaction = connection.begin()
        
        # Set up the session to use the transaction
        db.session.configure(bind=connection)
        
        yield
        
        # Rollback the transaction to undo all changes
        transaction.rollback()
        connection.close()
        
        # Close any remaining connections
        db.session.remove()
        db.engine.dispose()


@pytest.fixture(scope='function')
def sample_user(app):
    """Create a sample user for testing."""
    with app.app_context():
        unique_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
        user = User(username=f'user_{uuid.uuid4().hex[:8]}', email=unique_email)
        user.set_password('password123')
        db.session.add(user)
        db.session.commit()
        
        yield user
        
        # Cleanup is handled by cleanup_database fixture


@pytest.fixture(scope='function')
def sample_patient(app, sample_user):
    """Create a sample patient for testing."""
    with app.app_context():
        patient = Patient(
            name=f'Patient_{uuid.uuid4().hex[:6]}',
            user_id=sample_user.id
        )
        db.session.add(patient)
        db.session.commit()
        
        yield patient
        
        # Cleanup is handled by cleanup_database fixture


@pytest.fixture(scope='function')
def sample_treatment(app, sample_patient):
    """Create a sample treatment for testing."""
    with app.app_context():
        treatment = Treatment(
            patient_id=sample_patient.id,
            treatment_type='Assessment',
            status='Completed'
        )
        db.session.add(treatment)
        db.session.commit()
        
        yield treatment
        
        # Cleanup is handled by cleanup_database fixture


def pytest_configure(config):
    """Configure pytest to handle database connections properly."""
    # Set up any global test configuration here
    pass


def pytest_unconfigure(config):
    """Clean up after all tests are done."""
    # Ensure all database connections are closed
    pass 