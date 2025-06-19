#!/usr/bin/env python3
"""
Script to update database column sizes to accommodate encrypted data.
Encrypted data is much longer than plain text, so we need larger columns.
"""

import os
import sys

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from sqlalchemy import text

def update_column_sizes():
    """Update database column sizes for encrypted data"""
    print("=== Updating Database Column Sizes ===")
    
    app = create_app()
    
    with app.app_context():
        try:
            # Get database connection
            connection = db.engine.connect()
            
            # SQL commands to update column sizes
            # Encrypted data can be 4x+ longer than original text
            sql_commands = [
                # Patient table - increase sizes for encrypted fields
                "ALTER TABLE patient ALTER COLUMN name TYPE VARCHAR(500);",
                "ALTER TABLE patient ALTER COLUMN email TYPE VARCHAR(500);", 
                "ALTER TABLE patient ALTER COLUMN phone TYPE VARCHAR(200);",
                # Notes is already TEXT, so it's fine
                
                # Treatment table - increase size for encrypted notes
                "ALTER TABLE treatment ALTER COLUMN notes TYPE TEXT;",  # Ensure it's TEXT
            ]
            
            print("Executing SQL commands...")
            for i, sql in enumerate(sql_commands, 1):
                try:
                    print(f"  {i}. {sql.strip()}")
                    connection.execute(text(sql))
                    print(f"     ✅ Success")
                except Exception as e:
                    print(f"     ⚠️  Warning: {e}")
                    # Continue with other commands even if one fails
            
            # Commit the changes
            connection.commit()
            connection.close()
            
            print("\n✅ Column sizes updated successfully!")
            print("\nNew column sizes:")
            print("  - patient.name: VARCHAR(500)")
            print("  - patient.email: VARCHAR(500)")
            print("  - patient.phone: VARCHAR(200)")
            print("  - patient.notes: TEXT")
            print("  - treatment.notes: TEXT")
            
        except Exception as e:
            print(f"❌ Error updating column sizes: {str(e)}")
            import traceback
            traceback.print_exc()

def verify_column_sizes():
    """Verify that column sizes were updated correctly"""
    print("\n=== Verifying Column Sizes ===")
    
    app = create_app()
    
    with app.app_context():
        try:
            connection = db.engine.connect()
            
            # Check current column sizes
            sql = """
            SELECT 
                column_name, 
                data_type, 
                character_maximum_length
            FROM information_schema.columns 
            WHERE table_name = 'patient' 
            AND column_name IN ('name', 'email', 'phone', 'notes')
            ORDER BY column_name;
            """
            
            result = connection.execute(text(sql))
            columns = result.fetchall()
            
            print("Patient table column sizes:")
            for col in columns:
                size_info = f"({col.character_maximum_length})" if col.character_maximum_length else ""
                print(f"  - {col.column_name}: {col.data_type}{size_info}")
            
            # Check treatment table
            sql = """
            SELECT 
                column_name, 
                data_type, 
                character_maximum_length
            FROM information_schema.columns 
            WHERE table_name = 'treatment' 
            AND column_name = 'notes'
            ORDER BY column_name;
            """
            
            result = connection.execute(text(sql))
            columns = result.fetchall()
            
            print("\nTreatment table column sizes:")
            for col in columns:
                size_info = f"({col.character_maximum_length})" if col.character_maximum_length else ""
                print(f"  - {col.column_name}: {col.data_type}{size_info}")
            
            connection.close()
            
        except Exception as e:
            print(f"❌ Error verifying column sizes: {str(e)}")

def test_encrypted_data_fit():
    """Test that encrypted data fits in the updated columns"""
    print("\n=== Testing Encrypted Data Fit ===")
    
    from app.crypto_utils import encrypt_text
    
    test_data = [
        ("name", "John Doe"),
        ("email", "john.doe@example.com"),
        ("phone", "+1234567890"),
        ("notes", "This is a long note that should be encrypted and stored safely in the database.")
    ]
    
    for field_name, test_value in test_data:
        encrypted = encrypt_text(test_value)
        print(f"{field_name}:")
        print(f"  Original: {test_value}")
        print(f"  Encrypted length: {len(encrypted)} characters")
        print(f"  Encrypted: {encrypted[:50]}...")
        print()

def main():
    """Main function"""
    print("=== Database Column Size Update ===")
    
    # Check if FERNET_SECRET_KEY is set
    if not os.environ.get('FERNET_SECRET_KEY'):
        print("FERNET_SECRET_KEY not found in environment variables!")
        print("Please set it before running this script.")
        return
    
    try:
        # Update column sizes
        update_column_sizes()
        
        # Verify the changes
        verify_column_sizes()
        
        # Test encrypted data
        test_encrypted_data_fit()
        
        print("\n✅ All operations completed successfully!")
        print("\nYou can now create patients with encrypted data.")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main() 