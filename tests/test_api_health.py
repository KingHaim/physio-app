# tests/test_api_health.py
import requests
import pytest
from app import app

def test_health_check():
    """Test the health check endpoint returns 200 and expected data structure."""
    with app.test_client() as client:
        response = client.get('/health')
        assert response.status_code == 200
        
        # Parse JSON response
        data = response.get_json()
        
        # Check expected fields
        assert 'status' in data
        assert 'timestamp' in data
        assert 'database' in data
        assert 'version' in data
        
        # Check status is healthy
        assert data['status'] == 'healthy'
        assert data['database'] == 'connected'
        
        # Check numeric fields exist
        assert 'total_users' in data
        assert 'total_patients' in data
        assert 'total_treatments' in data
        
        # Verify these are integers
        assert isinstance(data['total_users'], int)
        assert isinstance(data['total_patients'], int)
        assert isinstance(data['total_treatments'], int) 