#!/usr/bin/env python3
"""
Quick script to check if ICD-10 tables exist and have data
"""

import os
import sqlite3

def check_database():
    """Check if ICD-10 tables exist and have data"""
    
    # Find database file
    possible_paths = [
        'instance/app.db',
        'app.db',
        'instance/database.db',
        'database.db'
    ]
    
    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        print("❌ No database file found!")
        print("Checked paths:", possible_paths)
        return False
    
    print(f"✅ Found database: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if ICD-10 tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%icd10%' OR name LIKE '%diagnos%'")
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"\n📋 ICD-10 related tables found: {len(tables)}")
        for table in tables:
            print(f"  - {table}")
            
            # Check row count
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"    └─ {count} rows")
        
        # Check if we have the expected tables
        expected_tables = ['icd10_codes', 'patient_diagnoses', 'diagnosis_templates', 'treatment_outcomes']
        missing_tables = [table for table in expected_tables if table not in tables]
        
        if missing_tables:
            print(f"\n⚠️  Missing tables: {', '.join(missing_tables)}")
            print("You need to run the migration script!")
            return False
        else:
            print("\n✅ All ICD-10 tables exist!")
            
            # Check if we have ICD-10 codes
            cursor.execute("SELECT COUNT(*) FROM icd10_codes")
            code_count = cursor.fetchone()[0]
            
            if code_count == 0:
                print("⚠️  No ICD-10 codes found - you need to seed data!")
                return False
            else:
                print(f"✅ Found {code_count} ICD-10 codes")
                
                # Show a few sample codes
                cursor.execute("SELECT code, short_description FROM icd10_codes LIMIT 5")
                samples = cursor.fetchall()
                print("\n📝 Sample codes:")
                for code, desc in samples:
                    print(f"  - {code}: {desc}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        return False

if __name__ == "__main__":
    print("🔍 Checking ICD-10 database status...")
    print("=" * 50)
    
    if check_database():
        print("\n✅ Database is ready for ICD-10!")
    else:
        print("\n❌ Database needs setup. Run:")
        print("   python simple_icd10_migration.py")
