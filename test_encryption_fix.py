#!/usr/bin/env python3
"""
Test script to verify that the encryption fixes are working correctly.
"""

import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Patient, Treatment
from app.crypto_utils import encrypt_text, decrypt_text

def test_basic_encryption():
    """Test basic encryption/decryption"""
    print("Testing basic encryption...")
    
    test_text = "John Doe"
    encrypted = encrypt_text(test_text)
    decrypted = decrypt_text(encrypted)
    
    print(f"Original: {test_text}")
    print(f"Encrypted: {encrypted}")
    print(f"Decrypted: {decrypted}")
    
    assert test_text == decrypted, "Basic encryption/decryption failed!"
    print("✅ Basic encryption working!")

def test_patient_model():
    """Test patient model with encryption"""
    print("\nTesting patient model...")
    
    # Create a test patient
    patient = Patient()
    patient.name = "Jane Smith"
    patient.email = "jane@example.com"
    patient.phone = "+1234567890"
    patient.notes = "Test patient notes"
    
    # Check that the properties work
    print(f"Patient name: {patient.name}")
    print(f"Patient email: {patient.email}")
    print(f"Patient phone: {patient.phone}")
    print(f"Patient notes: {patient.notes}")
    
    # Check that the database columns are encrypted
    print(f"Encrypted name in DB: {patient._name}")
    print(f"Encrypted email in DB: {patient._email}")
    print(f"Encrypted phone in DB: {patient._phone}")
    print(f"Encrypted notes in DB: {patient._notes}")
    
    # Verify encryption
    assert patient._name != "Jane Smith", "Name was not encrypted!"
    assert patient._email != "jane@example.com", "Email was not encrypted!"
    assert patient._phone != "+1234567890", "Phone was not encrypted!"
    assert patient._notes != "Test patient notes", "Notes were not encrypted!"
    
    print("✅ Patient model encryption working!")

def test_treatment_model():
    """Test treatment model with encryption"""
    print("\nTesting treatment model...")
    
    # Create a test treatment
    treatment = Treatment()
    treatment.notes = "Patient reported back pain"
    
    print(f"Treatment notes: {treatment.notes}")
    print(f"Encrypted notes in DB: {treatment._notes}")
    
    # Verify encryption
    assert treatment._notes != "Patient reported back pain", "Notes were not encrypted!"
    
    print("✅ Treatment model encryption working!")

def test_database_queries():
    """Test that database queries work with encrypted columns"""
    print("\nTesting database queries...")
    
    app = create_app()
    
    with app.app_context():
        # Test that we can query by encrypted column
        try:
            # This should work now that we've fixed the queries
            patients = Patient.query.limit(5).all()
            patients.sort(key=lambda p: p.name.lower() if p.name else '')
            print(f"✅ Successfully queried {len(patients)} patients and sorted by name")
        except Exception as e:
            print(f"❌ Query failed: {e}")
            return False
        
        # Test search functionality
        try:
            # This should work with the fixed search
            search_results = Patient.query.filter(
                Patient._name.ilike('%test%')
            ).limit(5).all()
            print(f"✅ Successfully searched patients using Patient._name")
        except Exception as e:
            print(f"❌ Search failed: {e}")
            return False
    
    print("✅ Database queries working!")

def main():
    """Main test function"""
    print("=== Encryption Fix Test ===")
    
    # Check if FERNET_SECRET_KEY is set
    if not os.environ.get('FERNET_SECRET_KEY'):
        print("FERNET_SECRET_KEY not found in environment variables!")
        print("Please set it before running this test.")
        return False
    
    try:
        # Run tests
        test_basic_encryption()
        test_patient_model()
        test_treatment_model()
        test_database_queries()
        
        print("\n=== All tests passed! ===")
        print("Encryption fixes are working correctly.")
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1) 