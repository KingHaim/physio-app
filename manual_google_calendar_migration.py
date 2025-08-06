#!/usr/bin/env python3
"""
Manual migration script to add Google Calendar fields to the database
Run this script to add the required columns for Google Calendar integration
"""

import sqlite3
import os
from datetime import datetime

def add_google_calendar_fields():
    """Add Google Calendar fields to the database"""
    
    # Database path
    db_path = 'instance/physio-2.db'
    if not os.path.exists(db_path):
        print("Database file not found. Make sure you're in the project root directory.")
        return False
    
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("Adding Google Calendar fields to User table...")
        
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(user)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Add Google Calendar fields to User table
        fields_to_add = [
            ("google_calendar_token_encrypted", "TEXT"),
            ("google_calendar_refresh_token_encrypted", "TEXT"),
            ("google_calendar_enabled", "BOOLEAN DEFAULT 0"),
            ("google_calendar_primary_calendar_id", "VARCHAR(255)"),
            ("google_calendar_last_sync", "DATETIME")
        ]
        
        for field_name, field_type in fields_to_add:
            if field_name not in columns:
                sql = f"ALTER TABLE user ADD COLUMN {field_name} {field_type}"
                cursor.execute(sql)
                print(f"✓ Added column: {field_name}")
            else:
                print(f"⚠ Column already exists: {field_name}")
        
        print("\nAdding Google Calendar fields to Treatment table...")
        
        # Check Treatment table columns
        cursor.execute("PRAGMA table_info(treatment)")
        treatment_columns = [col[1] for col in cursor.fetchall()]
        
        # Add Google Calendar fields to Treatment table
        treatment_fields = [
            ("google_calendar_event_id", "VARCHAR(255)"),
            ("google_calendar_event_summary", "VARCHAR(255)")
        ]
        
        for field_name, field_type in treatment_fields:
            if field_name not in treatment_columns:
                sql = f"ALTER TABLE treatment ADD COLUMN {field_name} {field_type}"
                cursor.execute(sql)
                print(f"✓ Added column: {field_name}")
            else:
                print(f"⚠ Column already exists: {field_name}")
        
        # Create indexes for better performance
        indexes = [
            ("idx_treatment_google_calendar_event_id", "treatment", "google_calendar_event_id"),
        ]
        
        for index_name, table_name, column_name in indexes:
            try:
                sql = f"CREATE INDEX {index_name} ON {table_name} ({column_name})"
                cursor.execute(sql)
                print(f"✓ Created index: {index_name}")
            except sqlite3.OperationalError as e:
                if "already exists" in str(e):
                    print(f"⚠ Index already exists: {index_name}")
                else:
                    print(f"✗ Error creating index {index_name}: {e}")
        
        # Commit changes
        conn.commit()
        print("\n✓ Google Calendar fields added successfully!")
        
        return True
        
    except Exception as e:
        print(f"✗ Error adding Google Calendar fields: {e}")
        return False
    finally:
        if conn:
            conn.close()

def verify_fields():
    """Verify that the fields were added correctly"""
    
    db_path = 'instance/physio-2.db'
    if not os.path.exists(db_path):
        print("Database file not found.")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("\nVerifying Google Calendar fields...")
        
        # Check User table
        cursor.execute("PRAGMA table_info(user)")
        user_columns = [col[1] for col in cursor.fetchall()]
        
        expected_user_fields = [
            "google_calendar_token_encrypted",
            "google_calendar_refresh_token_encrypted", 
            "google_calendar_enabled",
            "google_calendar_primary_calendar_id",
            "google_calendar_last_sync"
        ]
        
        print("User table fields:")
        for field in expected_user_fields:
            if field in user_columns:
                print(f"  ✓ {field}")
            else:
                print(f"  ✗ {field} - MISSING")
        
        # Check Treatment table
        cursor.execute("PRAGMA table_info(treatment)")
        treatment_columns = [col[1] for col in cursor.fetchall()]
        
        expected_treatment_fields = [
            "google_calendar_event_id",
            "google_calendar_event_summary"
        ]
        
        print("\nTreatment table fields:")
        for field in expected_treatment_fields:
            if field in treatment_columns:
                print(f"  ✓ {field}")
            else:
                print(f"  ✗ {field} - MISSING")
        
        return True
        
    except Exception as e:
        print(f"✗ Error verifying fields: {e}")
        return False
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("Google Calendar Database Migration")
    print("=" * 40)
    
    # Add the fields
    if add_google_calendar_fields():
        # Verify the fields were added
        verify_fields()
        print("\n🎉 Migration completed successfully!")
        print("\nNext steps:")
        print("1. Set up Google Cloud Console project")
        print("2. Configure environment variables:")
        print("   - GOOGLE_CLIENT_ID")
        print("   - GOOGLE_CLIENT_SECRET")
        print("   - GOOGLE_REDIRECT_URI")
        print("3. Restart your Flask application")
    else:
        print("\n❌ Migration failed!") 