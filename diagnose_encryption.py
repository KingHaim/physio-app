#!/usr/bin/env python3
"""
Diagnostic script to understand the current state of data and encryption.
"""

import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Patient, Treatment
from app.crypto_utils import decrypt_text

def check_fernet_key():
    """Check if FERNET_SECRET_KEY is properly set"""
    print("=== Checking FERNET_SECRET_KEY ===")
    
    key = os.environ.get('FERNET_SECRET_KEY')
    if not key:
        print("❌ FERNET_SECRET_KEY not found in environment variables!")
        return False
    
    print(f"✅ FERNET_SECRET_KEY is set (length: {len(key)})")
    
    # Test if it's a valid Fernet key
    try:
        from cryptography.fernet import Fernet
        Fernet(key.encode())
        print("✅ FERNET_SECRET_KEY is valid")
        return True
    except Exception as e:
        print(f"❌ FERNET_SECRET_KEY is invalid: {e}")
        return False

def sample_patient_data():
    """Show sample patient data to understand the current state"""
    print("\n=== Sample Patient Data ===")
    
    patients = Patient.query.limit(5).all()
    
    for i, patient in enumerate(patients, 1):
        print(f"\nPatient {i} (ID: {patient.id}):")
        
        # Raw database values
        print(f"  Raw _name: {patient._name}")
        print(f"  Raw _email: {patient._email}")
        print(f"  Raw _phone: {patient._phone}")
        print(f"  Raw _notes: {patient._notes}")
        
        # Decrypted values (using our safe decrypt function)
        print(f"  Decrypted name: {decrypt_text(patient._name)}")
        print(f"  Decrypted email: {decrypt_text(patient._email)}")
        print(f"  Decrypted phone: {decrypt_text(patient._phone)}")
        print(f"  Decrypted notes: {decrypt_text(patient._notes)}")
        
        # Property access (should work with our updated decrypt function)
        try:
            print(f"  Property name: {patient.name}")
        except Exception as e:
            print(f"  Property name error: {e}")
        
        try:
            print(f"  Property email: {patient.email}")
        except Exception as e:
            print(f"  Property email error: {e}")

def sample_treatment_data():
    """Show sample treatment data to understand the current state"""
    print("\n=== Sample Treatment Data ===")
    
    treatments = Treatment.query.limit(3).all()
    
    for i, treatment in enumerate(treatments, 1):
        print(f"\nTreatment {i} (ID: {treatment.id}):")
        
        # Raw database values
        print(f"  Raw _notes: {treatment._notes}")
        
        # Decrypted values
        print(f"  Decrypted notes: {decrypt_text(treatment._notes)}")
        
        # Property access
        try:
            print(f"  Property notes: {treatment.notes}")
        except Exception as e:
            print(f"  Property notes error: {e}")

def test_encryption_flow():
    """Test the complete encryption/decryption flow"""
    print("\n=== Testing Encryption Flow ===")
    
    from app.crypto_utils import encrypt_text
    
    test_data = [
        "John Doe",
        "jane@example.com", 
        "+1234567890",
        "Patient has chronic back pain"
    ]
    
    for original in test_data:
        print(f"\nTesting: {original}")
        
        # Encrypt
        encrypted = encrypt_text(original)
        print(f"  Encrypted: {encrypted}")
        
        # Decrypt
        decrypted = decrypt_text(encrypted)
        print(f"  Decrypted: {decrypted}")
        
        # Verify
        if original == decrypted:
            print("  ✅ Encryption/decryption working correctly")
        else:
            print("  ❌ Encryption/decryption failed")

def main():
    """Main diagnostic function"""
    print("=== Encryption Diagnostic ===")
    
    # Check Fernet key
    if not check_fernet_key():
        return
    
    app = create_app()
    
    with app.app_context():
        try:
            # Sample data
            sample_patient_data()
            sample_treatment_data()
            
            # Test encryption flow
            test_encryption_flow()
            
            print("\n=== Diagnostic Complete ===")
            print("If you see errors in the property access, run fix_data_issues.py")
            
        except Exception as e:
            print(f"Error during diagnostic: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    main() 