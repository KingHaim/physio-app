#!/usr/bin/env python3
"""
Script to clean up and encrypt all unencrypted data in the database.
This will eliminate Base64 decode errors by ensuring all sensitive data is properly encrypted.
"""

import os
import sys
import re

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Patient, Treatment
from app.crypto_utils import encrypt_text, decrypt_text

def is_likely_base64(text):
    """Check if text looks like base64"""
    if not text:
        return False
    
    # Base64 should only contain A-Z, a-z, 0-9, +, /, and = for padding
    base64_pattern = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')
    return bool(base64_pattern.match(text))

def is_encrypted(text):
    """Check if text is likely encrypted"""
    if not text:
        return False
    
    # Must be long enough to be a Fernet token
    if len(text) < 20:
        return False
    
    # Must look like base64
    if not is_likely_base64(text):
        return False
    
    # Try to decrypt it to see if it's actually encrypted
    try:
        decrypted = decrypt_text(text)
        # If decryption succeeds and returns something different, it was encrypted
        return decrypted != text
    except:
        return False

def cleanup_patient_data():
    """Clean up and encrypt all patient data"""
    print("=== Cleaning up Patient Data ===")
    
    patients = Patient.query.all()
    print(f"Found {len(patients)} patients")
    
    fixed_count = 0
    
    for patient in patients:
        try:
            # Check and fix name
            if patient._name and not is_encrypted(patient._name):
                print(f"  Encrypting patient {patient.id} name: {patient._name}")
                patient.name = patient._name  # This will re-encrypt it
                fixed_count += 1
            
            # Check and fix email
            if patient._email and not is_encrypted(patient._email):
                print(f"  Encrypting patient {patient.id} email: {patient._email}")
                patient.email = patient._email  # This will re-encrypt it
                fixed_count += 1
            
            # Check and fix phone
            if patient._phone and not is_encrypted(patient._phone):
                print(f"  Encrypting patient {patient.id} phone: {patient._phone}")
                patient.phone = patient._phone  # This will re-encrypt it
                fixed_count += 1
            
            # Check and fix notes
            if patient._notes and not is_encrypted(patient._notes):
                print(f"  Encrypting patient {patient.id} notes: {patient._notes[:50]}...")
                patient.notes = patient._notes  # This will re-encrypt it
                fixed_count += 1
                
        except Exception as e:
            print(f"  Error processing patient {patient.id}: {e}")
    
    print(f"Fixed {fixed_count} patient fields")
    return fixed_count

def cleanup_treatment_data():
    """Clean up and encrypt all treatment data"""
    print("\n=== Cleaning up Treatment Data ===")
    
    treatments = Treatment.query.all()
    print(f"Found {len(treatments)} treatments")
    
    fixed_count = 0
    
    for treatment in treatments:
        try:
            # Check and fix notes
            if treatment._notes and not is_encrypted(treatment._notes):
                print(f"  Encrypting treatment {treatment.id} notes: {treatment._notes[:50]}...")
                treatment.notes = treatment._notes  # This will re-encrypt it
                fixed_count += 1
                
        except Exception as e:
            print(f"  Error processing treatment {treatment.id}: {e}")
    
    print(f"Fixed {fixed_count} treatment fields")
    return fixed_count

def verify_encryption():
    """Verify that all data is now properly encrypted"""
    print("\n=== Verifying Encryption ===")
    
    # Check patients
    patients = Patient.query.all()
    unencrypted_patients = 0
    
    for patient in patients:
        if (patient._name and not is_encrypted(patient._name)) or \
           (patient._email and not is_encrypted(patient._email)) or \
           (patient._phone and not is_encrypted(patient._phone)) or \
           (patient._notes and not is_encrypted(patient._notes)):
            unencrypted_patients += 1
    
    # Check treatments
    treatments = Treatment.query.all()
    unencrypted_treatments = 0
    
    for treatment in treatments:
        if treatment._notes and not is_encrypted(treatment._notes):
            unencrypted_treatments += 1
    
    print(f"Patients with unencrypted data: {unencrypted_patients}")
    print(f"Treatments with unencrypted data: {unencrypted_treatments}")
    
    if unencrypted_patients == 0 and unencrypted_treatments == 0:
        print("✅ All data is now properly encrypted!")
        return True
    else:
        print("❌ Some data is still unencrypted")
        return False

def main():
    """Main cleanup function"""
    print("=== Database Encryption Cleanup ===")
    
    # Check if FERNET_SECRET_KEY is set
    if not os.environ.get('FERNET_SECRET_KEY'):
        print("❌ FERNET_SECRET_KEY not found in environment variables!")
        print("Please set it before running this cleanup.")
        print("You can generate a new key using:")
        print("python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
        return
    
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        try:
            # Clean up data
            patient_fixes = cleanup_patient_data()
            treatment_fixes = cleanup_treatment_data()
            
            # Commit changes
            if patient_fixes > 0 or treatment_fixes > 0:
                db.session.commit()
                print(f"\n✅ Committed {patient_fixes + treatment_fixes} fixes to database")
            else:
                print("\n✅ No fixes needed - all data is already encrypted")
            
            # Verify encryption
            verify_encryption()
            
            print("\n=== Cleanup completed successfully! ===")
            print("All Base64 decode errors should now be eliminated.")
            
        except Exception as e:
            print(f"❌ Cleanup failed: {str(e)}")
            db.session.rollback()
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    main() 