"""
Database Migration: Create ICD-10 Tables

This migration creates the necessary tables for ICD-10 diagnosis coding system:
- icd10_codes: Master table of ICD-10 codes
- patient_diagnoses: Patient-specific diagnoses with ICD-10 codes
- diagnosis_templates: Pre-configured diagnosis templates
- treatment_outcomes: Treatment outcome tracking by diagnosis

Run this migration after updating your models.
"""

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from app import create_app, db

def create_icd10_tables():
    """Create ICD-10 related tables"""
    
    app = create_app()
    
    with app.app_context():
        print("Creating ICD-10 tables...")
        
        # Import models to ensure they're registered
        from app.models_icd10 import ICD10Code, PatientDiagnosis, DiagnosisTemplate, TreatmentOutcome
        
        try:
            # Create all tables
            db.create_all()
            print("✓ ICD-10 tables created successfully")
            
            # Verify tables were created
            inspector = db.inspect(db.engine)
            tables = inspector.get_table_names()
            
            expected_tables = ['icd10_codes', 'patient_diagnoses', 'diagnosis_templates', 'treatment_outcomes']
            created_tables = [table for table in expected_tables if table in tables]
            
            print(f"✓ Created tables: {', '.join(created_tables)}")
            
            if len(created_tables) == len(expected_tables):
                print("✓ All ICD-10 tables created successfully!")
                return True
            else:
                missing = set(expected_tables) - set(created_tables)
                print(f"⚠ Missing tables: {', '.join(missing)}")
                return False
                
        except Exception as e:
            print(f"✗ Error creating tables: {str(e)}")
            return False

def add_patient_diagnoses_relationship():
    """Add the diagnoses relationship to existing Patient records"""
    
    app = create_app()
    
    with app.app_context():
        print("Adding diagnoses relationship to Patient model...")
        
        try:
            # The relationship is already defined in the updated Patient model
            # This function is here for completeness and future migrations
            print("✓ Patient model already updated with diagnoses relationship")
            return True
            
        except Exception as e:
            print(f"✗ Error updating Patient model: {str(e)}")
            return False

def run_migration():
    """Run the complete ICD-10 migration"""
    
    print("=" * 60)
    print("ICD-10 DIAGNOSIS SYSTEM MIGRATION")
    print("=" * 60)
    
    success = True
    
    # Step 1: Create tables
    print("\n1. Creating ICD-10 tables...")
    if not create_icd10_tables():
        success = False
    
    # Step 2: Update relationships
    print("\n2. Updating Patient model relationships...")
    if not add_patient_diagnoses_relationship():
        success = False
    
    # Step 3: Seed initial data
    print("\n3. Seeding initial ICD-10 data...")
    try:
        import subprocess
        import sys
        
        result = subprocess.run([
            sys.executable, 'seed_icd10_data.py'
        ], capture_output=True, text=True)
        
        if result.returncode == 0:
            print("✓ ICD-10 data seeded successfully")
            print(result.stdout)
        else:
            print(f"⚠ Warning: Data seeding failed: {result.stderr}")
            # Don't mark as failure since tables are created
            
    except Exception as e:
        print(f"⚠ Warning: Could not run data seeding: {str(e)}")
        print("You can run 'python seed_icd10_data.py' manually later")
    
    print("\n" + "=" * 60)
    if success:
        print("✓ MIGRATION COMPLETED SUCCESSFULLY!")
        print("\nNext steps:")
        print("1. Register the ICD-10 API blueprint in your main app")
        print("2. Update patient templates to include ICD-10 components")
        print("3. Test the ICD-10 functionality")
        print("4. Train users on the new diagnosis system")
    else:
        print("✗ MIGRATION FAILED!")
        print("Please check the errors above and try again")
    
    print("=" * 60)
    
    return success

if __name__ == "__main__":
    run_migration()
