#!/usr/bin/env python3
"""
Migrate from slow PythonAnywhere MySQL to fast local SQLite database.
This will dramatically improve performance by eliminating network database calls.
"""
import os
import sys
import sqlite3
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models import Patient, Treatment, User, Location, TriggerPoint, UnmatchedCalendlyBooking, PatientReport
from sqlalchemy import text


def backup_current_database():
    """Export all data from current MySQL database"""
    print("📦 Backing up current MySQL database...")
    
    app = create_app()
    backup_data = {}
    
    with app.app_context():
        # Export all tables
        try:
            backup_data['users'] = []
            for user in User.query.all():
                user_data = {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'password_hash': user.password_hash,
                    'is_admin': user.is_admin,
                    'created_at': user.created_at.isoformat() if user.created_at else None,
                    'email_verified': user.email_verified,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'date_of_birth': user.date_of_birth.isoformat() if user.date_of_birth else None,
                    'sex': user.sex,
                    'license_number': user.license_number,
                    'college_acronym': user.college_acronym,
                    'clinic_name': user.clinic_name,
                    'clinic_address': user.clinic_address,
                    'clinic_phone': user.clinic_phone,
                    'clinic_email': user.clinic_email,
                    'clinic_website': user.clinic_website,
                    'clinic_description': user.clinic_description,
                    'role': user.role,
                    'language': user.language,
                    'consent_given': user.consent_given,
                    'consent_date': user.consent_date.isoformat() if user.consent_date else None,
                    'oauth_provider': user.oauth_provider,
                    'oauth_id': user.oauth_id,
                    'avatar_url': user.avatar_url,
                    'is_deleted': user.is_deleted,
                    'has_unlimited_access': user.has_unlimited_access,
                    'is_new_user': user.is_new_user,
                }
                backup_data['users'].append(user_data)
            
            print(f"  ✅ Exported {len(backup_data['users'])} users")
            
            backup_data['patients'] = []
            for patient in Patient.query.all():
                patient_data = {
                    'id': patient.id,
                    'user_id': patient.user_id,
                    'portal_user_id': patient.portal_user_id,
                    'name': patient._name,  # Get raw data (plaintext after migration)
                    'email': patient._email,
                    'phone': patient._phone,
                    'notes': patient._notes,
                    'anamnesis': getattr(patient, '_anamnesis', None),
                    'date_of_birth': patient.date_of_birth.isoformat() if patient.date_of_birth else None,
                    'contact': patient.contact,
                    'diagnosis': patient.diagnosis,
                    'treatment_plan': patient.treatment_plan,
                    'status': patient.status,
                    'created_at': patient.created_at.isoformat() if patient.created_at else None,
                    'updated_at': patient.updated_at.isoformat() if patient.updated_at else None,
                    'address_line1': patient.address_line1,
                    'address_line2': patient.address_line2,
                    'city': patient.city,
                    'postcode': patient.postcode,
                    'preferred_location': patient.preferred_location,
                    'ai_suggested_tests': patient.ai_suggested_tests,
                    'ai_red_flags': patient.ai_red_flags,
                    'ai_yellow_flags': patient.ai_yellow_flags,
                    'ai_clinical_notes': patient.ai_clinical_notes,
                    'ai_analysis_date': patient.ai_analysis_date.isoformat() if patient.ai_analysis_date else None,
                }
                backup_data['patients'].append(patient_data)
            
            print(f"  ✅ Exported {len(backup_data['patients'])} patients")
            
            backup_data['treatments'] = []
            for treatment in Treatment.query.all():
                treatment_data = {
                    'id': treatment.id,
                    'patient_id': treatment.patient_id,
                    'treatment_type': treatment.treatment_type,
                    'assessment': treatment.assessment,
                    'notes': treatment._notes,  # Get raw data (plaintext)
                    'status': treatment.status,
                    'provider': treatment.provider,
                    'created_at': treatment.created_at.isoformat() if treatment.created_at else None,
                    'updated_at': treatment.updated_at.isoformat() if treatment.updated_at else None,
                    'body_chart_url': treatment.body_chart_url,
                    'pain_level': treatment.pain_level,
                    'movement_restriction': treatment.movement_restriction,
                    'evaluation_data': treatment.evaluation_data,
                    'location': treatment.location,
                    'location_id': treatment.location_id,
                    'visit_type': treatment.visit_type,
                    'fee_charged': treatment.fee_charged,
                    'payment_method': treatment.payment_method,
                    'calendly_invitee_uri': treatment.calendly_invitee_uri,
                    'google_calendar_event_id': treatment.google_calendar_event_id,
                    'google_calendar_event_summary': treatment.google_calendar_event_summary,
                    'clinic_share': treatment.clinic_share,
                    'therapist_share': treatment.therapist_share,
                }
                backup_data['treatments'].append(treatment_data)
            
            print(f"  ✅ Exported {len(backup_data['treatments'])} treatments")
            
            # Export other tables
            backup_data['locations'] = []
            for location in Location.query.all():
                backup_data['locations'].append({
                    'id': location.id,
                    'user_id': location.user_id,
                    'name': location.name,
                    'address': location.address,
                    'phone': location.phone,
                    'email': location.email,
                    'first_session_fee': location.first_session_fee,
                    'subsequent_session_fee': location.subsequent_session_fee,
                    'fee_percentage': location.fee_percentage,
                    'location_type': location.location_type,
                    'is_active': location.is_active,
                    'created_at': location.created_at.isoformat() if location.created_at else None,
                })
            
            backup_data['trigger_points'] = []
            for tp in TriggerPoint.query.all():
                backup_data['trigger_points'].append({
                    'id': tp.id,
                    'treatment_id': tp.treatment_id,
                    'location_x': tp.location_x,
                    'location_y': tp.location_y,
                    'type': tp.type,
                    'muscle': tp.muscle,
                    'intensity': tp.intensity,
                    'symptoms': tp.symptoms,
                    'referral_pattern': tp.referral_pattern,
                })
            
            print(f"  ✅ Exported {len(backup_data['locations'])} locations")
            print(f"  ✅ Exported {len(backup_data['trigger_points'])} trigger points")
            
        except Exception as e:
            print(f"  ❌ Error during backup: {e}")
            return None
    
    # Save backup
    backup_file = f"mysql_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(backup_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Backup saved to {backup_file}")
    return backup_file, backup_data


def create_sqlite_database():
    """Create new SQLite database with optimized settings"""
    print("🔧 Creating optimized SQLite database...")
    
    # SQLite database path
    sqlite_path = "/home/kinghaim/physio-app/instance/physio_sqlite_fast.db"
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(sqlite_path), exist_ok=True)
    
    # Create SQLite connection with performance optimizations
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.cursor()
    
    # Apply SQLite performance optimizations
    optimizations = [
        "PRAGMA journal_mode = WAL;",      # Write-Ahead Logging for better concurrency
        "PRAGMA synchronous = NORMAL;",    # Balance between speed and safety
        "PRAGMA cache_size = 10000;",      # 10MB cache
        "PRAGMA temp_store = MEMORY;",     # Store temp tables in memory
        "PRAGMA mmap_size = 268435456;",   # 256MB memory-mapped I/O
    ]
    
    for pragma in optimizations:
        cursor.execute(pragma)
        print(f"  ✅ Applied: {pragma}")
    
    conn.commit()
    conn.close()
    
    print(f"✅ SQLite database created at {sqlite_path}")
    return sqlite_path


def update_config_for_sqlite(sqlite_path):
    """Update config to use SQLite instead of MySQL"""
    print("⚙️ Updating configuration for SQLite...")
    
    config_update = f'''
# Update your config.py DATABASE_URL:
# Change from MySQL to SQLite:

# OLD (slow MySQL):
# SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "mysql://...")

# NEW (fast SQLite):
SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///{sqlite_path}")

# Also update engine options for SQLite:
SQLALCHEMY_ENGINE_OPTIONS = {{
    'pool_size': 20,
    'pool_recycle': -1,        # SQLite doesn't need connection recycling
    'pool_pre_ping': False,    # Not needed for SQLite
    'max_overflow': 0,         # SQLite is single-threaded
    'pool_timeout': 30,
    'echo': False,
}}
'''
    
    with open('sqlite_config_update.txt', 'w') as f:
        f.write(config_update)
    
    print("✅ Configuration update saved to sqlite_config_update.txt")


def create_migration_script(backup_file, sqlite_path):
    """Create script to import data into SQLite"""
    print("📝 Creating data migration script...")
    
    migration_script = f'''#!/usr/bin/env python3
"""
Import data from MySQL backup into SQLite database.
Run this after updating config.py to use SQLite.
"""
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set SQLite database URL before importing app
os.environ["DATABASE_URL"] = "sqlite:///{sqlite_path}"
os.environ["DISABLE_ENCRYPTION"] = "true"

from app import create_app, db
from app.models import Patient, Treatment, User, Location, TriggerPoint

def import_data():
    """Import all data from backup into SQLite"""
    print("📥 Importing data into SQLite...")
    
    app = create_app()
    
    with app.app_context():
        # Create all tables
        db.create_all()
        
        # Load backup data
        with open('{backup_file}', 'r') as f:
            data = json.load(f)
        
        # Import users first (foreign key dependency)
        print("Importing users...")
        for user_data in data['users']:
            user = User()
            for key, value in user_data.items():
                if key in ['created_at', 'date_of_birth', 'consent_date'] and value:
                    setattr(user, key, datetime.fromisoformat(value))
                else:
                    setattr(user, key, value)
            db.session.add(user)
        
        db.session.commit()
        print(f"✅ Imported {{len(data['users'])}} users")
        
        # Import patients
        print("Importing patients...")
        for patient_data in data['patients']:
            patient = Patient()
            for key, value in patient_data.items():
                if key in ['date_of_birth', 'created_at', 'updated_at', 'ai_analysis_date'] and value:
                    setattr(patient, key, datetime.fromisoformat(value))
                elif key in ['name', 'email', 'phone', 'notes', 'anamnesis']:
                    # Store as plaintext in _name, _email, etc.
                    setattr(patient, f'_{key}', value)
                else:
                    setattr(patient, key, value)
            db.session.add(patient)
        
        db.session.commit()
        print(f"✅ Imported {{len(data['patients'])}} patients")
        
        # Import treatments
        print("Importing treatments...")
        for treatment_data in data['treatments']:
            treatment = Treatment()
            for key, value in treatment_data.items():
                if key in ['created_at', 'updated_at'] and value:
                    setattr(treatment, key, datetime.fromisoformat(value))
                elif key == 'notes':
                    # Store as plaintext in _notes
                    setattr(treatment, '_notes', value)
                else:
                    setattr(treatment, key, value)
            db.session.add(treatment)
        
        db.session.commit()
        print(f"✅ Imported {{len(data['treatments'])}} treatments")
        
        # Import other tables
        if 'locations' in data:
            for location_data in data['locations']:
                location = Location()
                for key, value in location_data.items():
                    if key == 'created_at' and value:
                        setattr(location, key, datetime.fromisoformat(value))
                    else:
                        setattr(location, key, value)
                db.session.add(location)
            db.session.commit()
            print(f"✅ Imported {{len(data['locations'])}} locations")
        
        if 'trigger_points' in data:
            for tp_data in data['trigger_points']:
                tp = TriggerPoint()
                for key, value in tp_data.items():
                    setattr(tp, key, value)
                db.session.add(tp)
            db.session.commit()
            print(f"✅ Imported {{len(data['trigger_points'])}} trigger points")
        
        print("🎉 Data migration completed successfully!")

if __name__ == "__main__":
    import_data()
'''
    
    with open('import_to_sqlite.py', 'w') as f:
        f.write(migration_script)
    
    print("✅ Migration script saved as import_to_sqlite.py")


def main():
    print("🚀 MIGRATE TO FAST LOCAL SQLITE DATABASE")
    print("=" * 50)
    
    print("This will:")
    print("1. Backup your current MySQL data")
    print("2. Create optimized SQLite database")
    print("3. Generate migration scripts")
    print("4. Update configuration")
    print("\nBenefit: 10-100x faster database performance!")
    
    # Step 1: Backup current data
    backup_file, backup_data = backup_current_database()
    if not backup_file:
        print("❌ Backup failed - stopping migration")
        return
    
    # Step 2: Create SQLite database
    sqlite_path = create_sqlite_database()
    
    # Step 3: Update config
    update_config_for_sqlite(sqlite_path)
    
    # Step 4: Create migration script
    create_migration_script(backup_file, sqlite_path)
    
    print("\n" + "=" * 50)
    print("🎯 NEXT STEPS:")
    print("1. Update config.py with SQLite settings (see sqlite_config_update.txt)")
    print("2. Run: python3 import_to_sqlite.py")
    print("3. Update environment variable: export DATABASE_URL='sqlite:///...'")
    print("4. Restart your PythonAnywhere web app")
    print("\n✅ Expected result: 10-100x faster database performance!")


if __name__ == "__main__":
    main() 