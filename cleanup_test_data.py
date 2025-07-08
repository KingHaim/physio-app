#!/usr/bin/env python3
"""
Script to clean up test data that was accidentally left in the production database.
This will remove patient records with Admin_Patient naming pattern.
"""

import os
import sys
import re

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Patient, Treatment

def identify_test_patients():
    """Identify patients that appear to be test data"""
    print("=== Identifying Test Data ===")
    
    # Pattern for test patient names: Admin_Patient_[hex] or just "Admin Patient"
    test_patterns = [
        r'^Admin_Patient_[a-f0-9]+$',  # Admin_Patient_0951d6 format
        r'^Admin Patient$',            # Simple "Admin Patient"
    ]
    
    test_patients = []
    
    for patient in Patient.query.all():
        if patient.name:
            for pattern in test_patterns:
                if re.match(pattern, patient.name):
                    test_patients.append(patient)
                    break
    
    print(f"Found {len(test_patients)} test patients:")
    for patient in test_patients:
        print(f"  - ID {patient.id}: {patient.name}")
    
    return test_patients

def cleanup_test_data(confirm=False):
    """Clean up test data from the database"""
    test_patients = identify_test_patients()
    
    if not test_patients:
        print("✅ No test data found to clean up!")
        return
    
    if not confirm:
        print(f"\nFound {len(test_patients)} test patients to remove.")
        print("Run with confirm=True to actually delete them.")
        return
    
    print(f"\n=== Cleaning up {len(test_patients)} test patients ===")
    
    removed_count = 0
    for patient in test_patients:
        try:
            # First, check if this patient has any treatments
            treatments = Treatment.query.filter_by(patient_id=patient.id).all()
            treatment_count = len(treatments)
            
            print(f"Removing patient {patient.id}: {patient.name} ({treatment_count} treatments)")
            
            # Remove treatments first
            for treatment in treatments:
                db.session.delete(treatment)
            
            # Remove patient
            db.session.delete(patient)
            removed_count += 1
            
        except Exception as e:
            print(f"❌ Error removing patient {patient.id}: {e}")
    
    try:
        db.session.commit()
        print(f"✅ Successfully removed {removed_count} test patients and their treatments")
    except Exception as e:
        db.session.rollback()
        print(f"❌ Error committing changes: {e}")

def main():
    """Main cleanup function"""
    print("=== Test Data Cleanup ===")
    
    # Create Flask app context
    app = create_app()
    
    with app.app_context():
        try:
            # First, just identify without deleting
            print("Step 1: Identifying test data...")
            test_patients = identify_test_patients()
            
            if test_patients:
                print(f"\nFound {len(test_patients)} test patients.")
                response = input("Do you want to delete these test patients? (yes/no): ").lower().strip()
                
                if response in ['yes', 'y']:
                    cleanup_test_data(confirm=True)
                else:
                    print("Cleanup cancelled.")
            else:
                print("No test data found.")
                
        except Exception as e:
            print(f"❌ Cleanup failed: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == '__main__':
    main() 