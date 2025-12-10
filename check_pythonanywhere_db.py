#!/usr/bin/env python3
"""
PythonAnywhere Database Diagnostic Script
Checks what ICD-10 and pathology guide data exists
"""

from app import create_app
from app.models_icd10 import PathologyGuide, ICD10Code, PatientDiagnosis, DiagnosisTemplate
from sqlalchemy import inspect
from app import db

def check_database_status():
    """Check the current status of the database"""
    app = create_app()
    
    with app.app_context():
        print("🔍 PythonAnywhere Database Status Check")
        print("=" * 50)
        
        # Check if tables exist
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        required_tables = {
            'pathology_guides': 'Pathology guide content',
            'icd10_codes': 'ICD-10 medical codes', 
            'patient_diagnoses': 'Patient diagnosis records',
            'diagnosis_templates': 'Diagnosis templates'
        }
        
        print("\n📋 Table Status:")
        missing_tables = []
        for table, description in required_tables.items():
            exists = table in tables
            status = "✅ EXISTS" if exists else "❌ MISSING"
            print(f"  {table}: {status} - {description}")
            if not exists:
                missing_tables.append(table)
        
        if missing_tables:
            print(f"\n⚠️  Missing tables: {', '.join(missing_tables)}")
            print("   → Need to run database migration")
            return False
        
        # Check data counts
        print("\n📊 Data Counts:")
        try:
            guides_count = PathologyGuide.query.count()
            codes_count = ICD10Code.query.count()
            diagnoses_count = PatientDiagnosis.query.count()
            templates_count = DiagnosisTemplate.query.count()
            
            print(f"  Pathology guides: {guides_count}")
            print(f"  ICD-10 codes: {codes_count}")
            print(f"  Patient diagnoses: {diagnoses_count}")
            print(f"  Diagnosis templates: {templates_count}")
            
            # Check specific pathology guides
            if guides_count > 0:
                print("\n📚 Available Pathology Guides:")
                guides = PathologyGuide.query.all()
                for guide in guides:
                    print(f"  - {guide.name}")
            
            # Check patients with diagnoses
            if diagnoses_count > 0:
                print("\n👥 Patients with Diagnoses:")
                patients_with_diagnoses = db.session.query(PatientDiagnosis.patient_id).distinct().all()
                for (patient_id,) in patients_with_diagnoses:
                    patient_diagnoses = PatientDiagnosis.query.filter_by(patient_id=patient_id).count()
                    print(f"  Patient {patient_id}: {patient_diagnoses} diagnoses")
            
            # Recommendations
            print("\n🎯 Recommendations:")
            if codes_count == 0:
                print("  ❌ No ICD-10 codes found - need to seed ICD-10 data")
            if guides_count == 0:
                print("  ❌ No pathology guides found - need to seed pathology guide content")
            if templates_count == 0:
                print("  ❌ No diagnosis templates found - need to seed templates")
            if diagnoses_count == 0:
                print("  ❌ No patient diagnoses found - need to add test diagnoses")
            
            if all([codes_count > 0, guides_count > 0, templates_count > 0, diagnoses_count > 0]):
                print("  ✅ Database appears to be fully set up!")
                return True
            else:
                print("  ⚠️  Database needs additional setup")
                return False
                
        except Exception as e:
            print(f"\n❌ Error checking data: {str(e)}")
            print("   → Tables exist but may be empty or have schema issues")
            return False

if __name__ == "__main__":
    check_database_status()
