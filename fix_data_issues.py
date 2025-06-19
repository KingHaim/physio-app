#!/usr/bin/env python3
"""
Script to identify and fix data issues with mixed encrypted/unencrypted data.
"""

import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Patient, Treatment
from app.crypto_utils import encrypt_text, decrypt_text

def analyze_patient_data():
    """Analyze patient data to identify encryption issues"""
    print("=== Analyzing Patient Data ===")
    
    patients = Patient.query.all()
    print(f"Found {len(patients)} patients")
    
    issues = {
        'short_names': [],
        'non_base64_names': [],
        'short_emails': [],
        'non_base64_emails': [],
        'short_phones': [],
        'non_base64_phones': [],
        'short_notes': [],
        'non_base64_notes': []
    }
    
    for patient in patients:
        # Check name
        if patient._name:
            if len(patient._name) < 20:
                issues['short_names'].append((patient.id, patient._name))
            elif not is_likely_base64(patient._name):
                issues['non_base64_names'].append((patient.id, patient._name))
        
        # Check email
        if patient._email:
            if len(patient._email) < 20:
                issues['short_emails'].append((patient.id, patient._email))
            elif not is_likely_base64(patient._email):
                issues['non_base64_emails'].append((patient.id, patient._email))
        
        # Check phone
        if patient._phone:
            if len(patient._phone) < 20:
                issues['short_phones'].append((patient.id, patient._phone))
            elif not is_likely_base64(patient._phone):
                issues['non_base64_phones'].append((patient.id, patient._phone))
        
        # Check notes
        if patient._notes:
            if len(patient._notes) < 20:
                issues['short_notes'].append((patient.id, patient._notes))
            elif not is_likely_base64(patient._notes):
                issues['non_base64_notes'].append((patient.id, patient._notes))
    
    # Report issues
    for issue_type, items in issues.items():
        if items:
            print(f"\n{issue_type.upper()}: {len(items)} items")
            for patient_id, value in items[:5]:  # Show first 5
                print(f"  Patient {patient_id}: {value}")
            if len(items) > 5:
                print(f"  ... and {len(items) - 5} more")
    
    return issues

def analyze_treatment_data():
    """Analyze treatment data to identify encryption issues"""
    print("\n=== Analyzing Treatment Data ===")
    
    treatments = Treatment.query.all()
    print(f"Found {len(treatments)} treatments")
    
    issues = {
        'short_notes': [],
        'non_base64_notes': []
    }
    
    for treatment in treatments:
        # Check notes
        if treatment._notes:
            if len(treatment._notes) < 20:
                issues['short_notes'].append((treatment.id, treatment._notes))
            elif not is_likely_base64(treatment._notes):
                issues['non_base64_notes'].append((treatment.id, treatment._notes))
    
    # Report issues
    for issue_type, items in issues.items():
        if items:
            print(f"\n{issue_type.upper()}: {len(items)} items")
            for treatment_id, value in items[:5]:  # Show first 5
                print(f"  Treatment {treatment_id}: {value}")
            if len(items) > 5:
                print(f"  ... and {len(items) - 5} more")
    
    return issues

def is_likely_base64(text):
    """Check if text looks like base64"""
    if not text:
        return False
    
    # Base64 should only contain A-Z, a-z, 0-9, +, /, and = for padding
    import re
    base64_pattern = re.compile(r'^[A-Za-z0-9+/]*={0,2}$')
    return bool(base64_pattern.match(text))

def fix_patient_data(issues):
    """Fix patient data issues by encrypting unencrypted values"""
    print("\n=== Fixing Patient Data ===")
    
    fixed_count = 0
    
    # Fix names
    for patient_id, value in issues['short_names'] + issues['non_base64_names']:
        try:
            patient = Patient.query.get(patient_id)
            if patient:
                # Re-encrypt the value
                patient.name = value
                fixed_count += 1
                print(f"Fixed patient {patient_id} name")
        except Exception as e:
            print(f"Error fixing patient {patient_id} name: {e}")
    
    # Fix emails
    for patient_id, value in issues['short_emails'] + issues['non_base64_emails']:
        try:
            patient = Patient.query.get(patient_id)
            if patient:
                patient.email = value
                fixed_count += 1
                print(f"Fixed patient {patient_id} email")
        except Exception as e:
            print(f"Error fixing patient {patient_id} email: {e}")
    
    # Fix phones
    for patient_id, value in issues['short_phones'] + issues['non_base64_phones']:
        try:
            patient = Patient.query.get(patient_id)
            if patient:
                patient.phone = value
                fixed_count += 1
                print(f"Fixed patient {patient_id} phone")
        except Exception as e:
            print(f"Error fixing patient {patient_id} phone: {e}")
    
    # Fix notes
    for patient_id, value in issues['short_notes'] + issues['non_base64_notes']:
        try:
            patient = Patient.query.get(patient_id)
            if patient:
                patient.notes = value
                fixed_count += 1
                print(f"Fixed patient {patient_id} notes")
        except Exception as e:
            print(f"Error fixing patient {patient_id} notes: {e}")
    
    return fixed_count

def fix_treatment_data(issues):
    """Fix treatment data issues by encrypting unencrypted values"""
    print("\n=== Fixing Treatment Data ===")
    
    fixed_count = 0
    
    # Fix notes
    for treatment_id, value in issues['short_notes'] + issues['non_base64_notes']:
        try:
            treatment = Treatment.query.get(treatment_id)
            if treatment:
                treatment.notes = value
                fixed_count += 1
                print(f"Fixed treatment {treatment_id} notes")
        except Exception as e:
            print(f"Error fixing treatment {treatment_id} notes: {e}")
    
    return fixed_count

def main():
    """Main function"""
    print("=== Data Issue Analysis and Fix ===")
    
    # Check if FERNET_SECRET_KEY is set
    if not os.environ.get('FERNET_SECRET_KEY'):
        print("FERNET_SECRET_KEY not found in environment variables!")
        print("Please set it before running this script.")
        return
    
    app = create_app()
    
    with app.app_context():
        try:
            # Analyze data
            patient_issues = analyze_patient_data()
            treatment_issues = analyze_treatment_data()
            
            # Ask user if they want to fix issues
            total_issues = sum(len(items) for items in patient_issues.values()) + \
                          sum(len(items) for items in treatment_issues.values())
            
            if total_issues == 0:
                print("\n✅ No data issues found!")
                return
            
            print(f"\nFound {total_issues} potential data issues.")
            response = input("Do you want to fix these issues? (y/N): ")
            
            if response.lower() in ['y', 'yes']:
                # Fix issues
                patient_fixed = fix_patient_data(patient_issues)
                treatment_fixed = fix_treatment_data(treatment_issues)
                
                # Commit changes
                db.session.commit()
                
                print(f"\n✅ Fixed {patient_fixed} patient records and {treatment_fixed} treatment records!")
                print("Data has been properly encrypted.")
            else:
                print("Skipping fixes. Data remains unchanged.")
                
        except Exception as e:
            print(f"Error: {str(e)}")
            db.session.rollback()

if __name__ == '__main__':
    main() 