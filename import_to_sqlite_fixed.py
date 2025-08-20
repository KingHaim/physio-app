#!/usr/bin/env python3
"""
Import data from MySQL backup into SQLite database.
Fixed version that properly handles the migration.
"""
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set SQLite database URL before importing app
sqlite_path = "/home/kinghaim/physio-app/instance/physio_sqlite_fast.db"
os.environ["DATABASE_URL"] = f"sqlite:///{sqlite_path}"
os.environ["DISABLE_ENCRYPTION"] = "true"

from app import create_app, db
from app.models import Patient, Treatment, User, Location, TriggerPoint


def import_data():
    """Import all data from backup into SQLite"""
    print("📥 Importing data into SQLite...")
    
    app = create_app()
    
    with app.app_context():
        # Create all tables
        print("Creating database tables...")
        db.create_all()
        
        # Find the most recent backup file
        import glob
        backup_files = glob.glob("mysql_backup_*.json")
        if not backup_files:
            print("❌ No backup file found! Run migrate_to_sqlite.py first")
            return
        
        backup_file = sorted(backup_files)[-1]  # Get most recent
        print(f"Using backup file: {backup_file}")
        
        # Load backup data
        with open(backup_file, 'r') as f:
            data = json.load(f)
        
        # Import users first (foreign key dependency)
        print("Importing users...")
        for user_data in data['users']:
            user = User()
            for key, value in user_data.items():
                if key in ['created_at', 'date_of_birth', 'consent_date'] and value:
                    try:
                        setattr(user, key, datetime.fromisoformat(value))
                    except:
                        setattr(user, key, None)
                else:
                    setattr(user, key, value)
            db.session.add(user)
        
        try:
            db.session.commit()
            print(f"✅ Imported {len(data['users'])} users")
        except Exception as e:
            print(f"❌ Error importing users: {e}")
            db.session.rollback()
        
        # Import patients
        print("Importing patients...")
        for patient_data in data['patients']:
            patient = Patient()
            for key, value in patient_data.items():
                if key in ['date_of_birth', 'created_at', 'updated_at', 'ai_analysis_date'] and value:
                    try:
                        setattr(patient, key, datetime.fromisoformat(value))
                    except:
                        setattr(patient, key, None)
                elif key == 'name':
                    patient._name = value
                elif key == 'email':
                    patient._email = value
                elif key == 'phone':
                    patient._phone = value
                elif key == 'notes':
                    patient._notes = value
                elif key == 'anamnesis':
                    patient._anamnesis = value
                else:
                    setattr(patient, key, value)
            db.session.add(patient)
        
        try:
            db.session.commit()
            print(f"✅ Imported {len(data['patients'])} patients")
        except Exception as e:
            print(f"❌ Error importing patients: {e}")
            db.session.rollback()
        
        # Import treatments
        print("Importing treatments...")
        for treatment_data in data['treatments']:
            treatment = Treatment()
            for key, value in treatment_data.items():
                if key in ['created_at', 'updated_at'] and value:
                    try:
                        setattr(treatment, key, datetime.fromisoformat(value))
                    except:
                        setattr(treatment, key, None)
                elif key == 'notes':
                    treatment._notes = value
                else:
                    setattr(treatment, key, value)
            db.session.add(treatment)
        
        try:
            db.session.commit()
            print(f"✅ Imported {len(data['treatments'])} treatments")
        except Exception as e:
            print(f"❌ Error importing treatments: {e}")
            db.session.rollback()
        
        # Import locations
        if 'locations' in data and data['locations']:
            print("Importing locations...")
            for location_data in data['locations']:
                location = Location()
                for key, value in location_data.items():
                    if key == 'created_at' and value:
                        try:
                            setattr(location, key, datetime.fromisoformat(value))
                        except:
                            setattr(location, key, None)
                    else:
                        setattr(location, key, value)
                db.session.add(location)
            
            try:
                db.session.commit()
                print(f"✅ Imported {len(data['locations'])} locations")
            except Exception as e:
                print(f"❌ Error importing locations: {e}")
                db.session.rollback()
        
        # Import trigger points
        if 'trigger_points' in data and data['trigger_points']:
            print("Importing trigger points...")
            for tp_data in data['trigger_points']:
                tp = TriggerPoint()
                for key, value in tp_data.items():
                    setattr(tp, key, value)
                db.session.add(tp)
            
            try:
                db.session.commit()
                print(f"✅ Imported {len(data['trigger_points'])} trigger points")
            except Exception as e:
                print(f"❌ Error importing trigger points: {e}")
                db.session.rollback()
        
        print("\n🎉 Data migration to SQLite completed successfully!")
        print(f"Database location: {sqlite_path}")
        print("Next steps:")
        print("1. Update config.py to use SQLite")
        print("2. Set DATABASE_URL environment variable")
        print("3. Restart web app")


if __name__ == "__main__":
    import_data() 