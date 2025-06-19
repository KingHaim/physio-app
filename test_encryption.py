#!/usr/bin/env python3
"""
Test script to verify encryption is working correctly.
"""

import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Patient, Treatment
from app.crypto_utils import encrypt_text, decrypt_text

def test_encryption_utils():
    """Test the basic encryption utilities"""
    print("Testing encryption utilities...")
    
    test_text = "Aaron Ganancia"
    print(f"Original text: {test_text}")
    
    # Test encryption
    encrypted = encrypt_text(test_text)
    print(f"Encrypted: {encrypted}")
    
    # Test decryption
    decrypted = decrypt_text(encrypted)
    print(f"Decrypted: {decrypted}")
    
    # Verify they match
    assert test_text == decrypted, "Encryption/decryption failed!"
    print("✅ Encryption utilities working correctly!")

def test_patient_encryption():
    """Test patient model encryption"""
    print("\nTesting patient model encryption...")
    
    # Create a test patient
    patient = Patient()
    patient.name = "Aaron Ganancia"
    patient.email = "aaron@example.com"
    patient.phone = "+1234567890"
    patient.notes = "Sensitive health information"
    
    print(f"Patient name: {patient.name}")
    print(f"Patient email: {patient.email}")
    print(f"Patient phone: {patient.phone}")
    print(f"Patient notes: {patient.notes}")
    
    # Check that the underlying database columns are encrypted
    print(f"Encrypted name in DB: {patient._name}")
    print(f"Encrypted email in DB: {patient._email}")
    print(f"Encrypted phone in DB: {patient._phone}")
    print(f"Encrypted notes in DB: {patient._notes}")
    
    # Verify the encrypted data is different from plain text
    assert patient._name != "Aaron Ganancia", "Name was not encrypted!"
    assert patient._email != "aaron@example.com", "Email was not encrypted!"
    assert patient._phone != "+1234567890", "Phone was not encrypted!"
    assert patient._notes != "Sensitive health information", "Notes were not encrypted!"
    
    print("✅ Patient model encryption working correctly!")

def test_treatment_encryption():
    """Test treatment model encryption"""
    print("\nTesting treatment model encryption...")
    
    # Create a test treatment
    treatment = Treatment()
    treatment.notes = "Patient reported severe back pain during session"
    
    print(f"Treatment notes: {treatment.notes}")
    print(f"Encrypted notes in DB: {treatment._notes}")
    
    # Verify the encrypted data is different from plain text
    assert treatment._notes != "Patient reported severe back pain during session", "Notes were not encrypted!"
    
    print("✅ Treatment model encryption working correctly!")

def test_round_trip():
    """Test that data can be saved and retrieved correctly"""
    print("\nTesting round-trip encryption...")
    
    # Create test data
    original_name = "John Doe"
    original_email = "john.doe@example.com"
    original_phone = "+9876543210"
    original_notes = "Patient has chronic condition"
    
    # Create patient and set data
    patient = Patient()
    patient.name = original_name
    patient.email = original_email
    patient.phone = original_phone
    patient.notes = original_notes
    
    # Retrieve data and verify it matches
    retrieved_name = patient.name
    retrieved_email = patient.email
    retrieved_phone = patient.phone
    retrieved_notes = patient.notes
    
    assert retrieved_name == original_name, f"Name mismatch: {retrieved_name} != {original_name}"
    assert retrieved_email == original_email, f"Email mismatch: {retrieved_email} != {original_email}"
    assert retrieved_phone == original_phone, f"Phone mismatch: {retrieved_phone} != {original_phone}"
    assert retrieved_notes == original_notes, f"Notes mismatch: {retrieved_notes} != {original_notes}"
    
    print("✅ Round-trip encryption working correctly!")

def main():
    """Main test function"""
    print("=== Encryption System Test ===")
    
    # Check if FERNET_SECRET_KEY is set
    if not os.environ.get('FERNET_SECRET_KEY'):
        print("FERNET_SECRET_KEY not found in environment variables!")
        print("Please set it before running this test.")
        print("You can generate a new key using:")
        print("python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
        return
    
    try:
        # Create Flask app context
        app = create_app()
        
        with app.app_context():
            # Run tests
            test_encryption_utils()
            test_patient_encryption()
            test_treatment_encryption()
            test_round_trip()
            
            print("\n=== All tests passed! ===")
            print("Encryption system is working correctly.")
            
    except Exception as e:
        print(f"Test failed: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main() 