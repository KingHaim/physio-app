#!/usr/bin/env python3
"""
Migration script to add is_deleted field to User table
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app import create_app, db
from sqlalchemy import text

def add_is_deleted_field():
    app = create_app()
    with app.app_context():
        try:
            db.session.execute(text('ALTER TABLE "user" ADD COLUMN is_deleted BOOLEAN DEFAULT FALSE'))
            db.session.commit()
            print('✅ Successfully added is_deleted column to User table')
        except Exception as e:
            print(f'❌ Error adding is_deleted field: {e}')
            db.session.rollback()
            return False
    return True

if __name__ == '__main__':
    print('🔄 Adding is_deleted field to User table...')
    success = add_is_deleted_field()
    if success:
        print('✅ Migration completed successfully!')
    else:
        print('❌ Migration failed!')
        sys.exit(1) 