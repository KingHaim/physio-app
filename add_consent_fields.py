#!/usr/bin/env python3
"""
Migration script to add consent fields to User table
"""
import sys
import os

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app import create_app, db
from app.models import User
from datetime import datetime
from sqlalchemy import text

def add_consent_fields():
    """Add consent_given and consent_date fields to User table"""
    app = create_app()
    
    with app.app_context():
        try:
            # Add the new columns
            db.session.execute(text("""
                ALTER TABLE "user" 
                ADD COLUMN consent_given BOOLEAN DEFAULT FALSE
            """))
            
            db.session.execute(text("""
                ALTER TABLE "user" 
                ADD COLUMN consent_date TIMESTAMP NULL
            """))
            
            print("✅ Successfully added consent_given and consent_date columns to User table")
            
            # Update existing users to have consent_given = True and consent_date = created_at
            # This assumes existing users implicitly consented when they registered
            db.session.execute(text("""
                UPDATE "user" 
                SET consent_given = TRUE, consent_date = created_at 
                WHERE consent_given IS NULL OR consent_given = FALSE
            """))
            
            db.session.commit()
            print("✅ Updated existing users with consent information")
            
        except Exception as e:
            print(f"❌ Error adding consent fields: {e}")
            db.session.rollback()
            return False
    
    return True

if __name__ == '__main__':
    print("🔄 Adding consent fields to User table...")
    success = add_consent_fields()
    if success:
        print("✅ Migration completed successfully!")
    else:
        print("❌ Migration failed!")
        sys.exit(1) 