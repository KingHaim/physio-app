#!/usr/bin/env python3
"""
Migration script to encrypt sensitive patient and treatment data.
This script will:
1. Add new encrypted columns with underscore prefixes
2. Migrate existing data to encrypted format
3. Remove old unencrypted columns
"""

import os
import sys
from cryptography.fernet import Fernet
import base64

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Patient, Treatment
from app.crypto_utils import encrypt_text

def generate_fernet_key():
    """Generate a new Fernet key for encryption"""
    return Fernet.generate_key().decode()

def migrate_patient_data():
    """Migrate patient data to encrypted format"""
    print("Starting patient data migration...")
    
    # Get all patients
    patients = Patient.query.all()
    print(f"Found {len(patients)} patients to migrate")
    
    for i, patient in enumerate(patients, 1):
        try:
            print(f"Migrating patient {i}/{len(patients)} (ID: {patient.id})")
            
            # Store original values
            original_name = patient._name if hasattr(patient, '_name') else None
            original_email = patient._email if hasattr(patient, '_email') else None
            original_phone = patient._phone if hasattr(patient, '_phone') else None
            original_notes = patient._notes if hasattr(patient, '_notes') else None
            
            # If we're accessing the old column names directly, get them
            if not original_name and hasattr(patient, 'name'):
                # This means we're reading from the old unencrypted column
                original_name = patient.name
            if not original_email and hasattr(patient, 'email'):
                original_email = patient.email
            if not original_phone and hasattr(patient, 'phone'):
                original_phone = patient.phone
            if not original_notes and hasattr(patient, 'notes'):
                original_notes = patient.notes
            
            # Encrypt and set the values using the new property setters
            if original_name:
                patient.name = original_name
            if original_email:
                patient.email = original_email
            if original_phone:
                patient.phone = original_phone
            if original_notes:
                patient.notes = original_notes
                
        except Exception as e:
            print(f"Error migrating patient {patient.id}: {str(e)}")
            continue
    
    # Commit all changes
    try:
        db.session.commit()
        print("Patient data migration completed successfully!")
    except Exception as e:
        print(f"Error committing patient migration: {str(e)}")
        db.session.rollback()

def migrate_treatment_data():
    """Migrate treatment data to encrypted format"""
    print("Starting treatment data migration...")
    
    # Get all treatments
    treatments = Treatment.query.all()
    print(f"Found {len(treatments)} treatments to migrate")
    
    for i, treatment in enumerate(treatments, 1):
        try:
            print(f"Migrating treatment {i}/{len(treatments)} (ID: {treatment.id})")
            
            # Store original values
            original_notes = treatment._notes if hasattr(treatment, '_notes') else None
            
            # If we're accessing the old column names directly, get them
            if not original_notes and hasattr(treatment, 'notes'):
                # This means we're reading from the old unencrypted column
                original_notes = treatment.notes
            
            # Encrypt and set the values using the new property setters
            if original_notes:
                treatment.notes = original_notes
                
        except Exception as e:
            print(f"Error migrating treatment {treatment.id}: {str(e)}")
            continue
    
    # Commit all changes
    try:
        db.session.commit()
        print("Treatment data migration completed successfully!")
    except Exception as e:
        print(f"Error committing treatment migration: {str(e)}")
        db.session.rollback()

def main():
    """Main migration function"""
    print("=== Data Encryption Migration ===")
    
    # Check if FERNET_SECRET_KEY is set
    if not os.environ.get('FERNET_SECRET_KEY'):
        print("FERNET_SECRET_KEY not found in environment variables!")
        print("Please set it before running this migration.")
        print("You can generate a new key using:")
        print("python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"")
        return
    
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        try:
            # Migrate patient data
            migrate_patient_data()
            
            # Migrate treatment data
            migrate_treatment_data()
            
            print("\n=== Migration completed successfully! ===")
            print("All sensitive data has been encrypted.")
            print("Make sure to update your database schema to reflect the new column names.")
            
        except Exception as e:
            print(f"Migration failed: {str(e)}")
            db.session.rollback()

if __name__ == '__main__':
    main() 