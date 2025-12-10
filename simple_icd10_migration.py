#!/usr/bin/env python3
"""
Simplified ICD-10 Migration Script
Creates tables and seeds data without Flask dependencies
"""

import os
import sqlite3
from datetime import datetime

def get_db_path():
    """Get the database path"""
    # Try to find the database file
    possible_paths = [
        'instance/app.db',
        'app.db',
        'instance/database.db',
        'database.db'
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return path
    
    # Default to instance/app.db
    os.makedirs('instance', exist_ok=True)
    return 'instance/app.db'

def create_icd10_tables():
    """Create ICD-10 tables using direct SQLite"""
    
    db_path = get_db_path()
    print(f"Using database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        print("Creating ICD-10 tables...")
        
        # Create icd10_codes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS icd10_codes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code VARCHAR(10) UNIQUE NOT NULL,
                description VARCHAR(500) NOT NULL,
                short_description VARCHAR(200),
                category VARCHAR(100),
                subcategory VARCHAR(100),
                is_active BOOLEAN DEFAULT 1,
                is_physiotherapy_relevant BOOLEAN DEFAULT 1
            )
        ''')
        
        # Create patient_diagnoses table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS patient_diagnoses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id INTEGER NOT NULL,
                icd10_code_id INTEGER NOT NULL,
                diagnosis_type VARCHAR(20) DEFAULT 'primary',
                status VARCHAR(20) DEFAULT 'active',
                confidence_level VARCHAR(20),
                clinical_notes TEXT,
                severity VARCHAR(20),
                onset_date DATE,
                diagnosis_date DATE DEFAULT CURRENT_DATE,
                resolved_date DATE,
                diagnosed_by_user_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (patient_id) REFERENCES patient (id),
                FOREIGN KEY (icd10_code_id) REFERENCES icd10_codes (id),
                FOREIGN KEY (diagnosed_by_user_id) REFERENCES user (id)
            )
        ''')
        
        # Create diagnosis_templates table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS diagnosis_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(200) NOT NULL,
                description TEXT,
                primary_icd10_code_id INTEGER NOT NULL,
                default_severity VARCHAR(20) DEFAULT 'moderate',
                typical_duration_days INTEGER,
                common_symptoms TEXT,
                treatment_guidelines TEXT,
                usage_count INTEGER DEFAULT 0,
                created_by_user_id INTEGER,
                is_active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (primary_icd10_code_id) REFERENCES icd10_codes (id),
                FOREIGN KEY (created_by_user_id) REFERENCES user (id)
            )
        ''')
        
        # Create treatment_outcomes table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS treatment_outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_diagnosis_id INTEGER NOT NULL,
                treatment_id INTEGER NOT NULL,
                pain_level_before INTEGER,
                pain_level_after INTEGER,
                functional_improvement VARCHAR(20),
                patient_satisfaction INTEGER,
                objective_improvement TEXT,
                treatment_effectiveness VARCHAR(20),
                follow_up_required BOOLEAN DEFAULT 0,
                discharge_status VARCHAR(50),
                recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                recorded_by_user_id INTEGER,
                FOREIGN KEY (patient_diagnosis_id) REFERENCES patient_diagnoses (id),
                FOREIGN KEY (treatment_id) REFERENCES treatment (id),
                FOREIGN KEY (recorded_by_user_id) REFERENCES user (id)
            )
        ''')
        
        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_icd10_code ON icd10_codes (code)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_icd10_search ON icd10_codes (description)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_patient_diagnoses_patient ON patient_diagnoses (patient_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_patient_diagnoses_status ON patient_diagnoses (status)')
        
        conn.commit()
        print("✓ ICD-10 tables created successfully")
        
        # Verify tables were created
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND (name LIKE '%icd10%' OR name LIKE '%diagnos%' OR name LIKE '%outcome%')")
        tables = [row[0] for row in cursor.fetchall()]
        
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
    finally:
        conn.close()

def seed_basic_data():
    """Seed basic ICD-10 codes"""
    
    db_path = get_db_path()
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if data already exists
        cursor.execute("SELECT COUNT(*) FROM icd10_codes")
        count = cursor.fetchone()[0]
        
        if count > 0:
            print(f"✓ Found {count} existing ICD-10 codes, skipping seeding")
            return True
        
        print("Seeding basic ICD-10 codes...")
        
        # Basic ICD-10 codes for physiotherapy
        basic_codes = [
            ("M54.5", "Low back pain", "Low back pain", "Musculoskeletal", "Back pain"),
            ("M54.2", "Cervicalgia", "Neck pain", "Musculoskeletal", "Neck disorders"),
            ("M54.6", "Pain in thoracic spine", "Mid-back pain", "Musculoskeletal", "Back pain"),
            ("M54.3", "Sciatica", "Sciatica", "Musculoskeletal", "Back pain"),
            ("M75.1", "Rotator cuff tear or rupture, not specified as traumatic", "Rotator cuff tear", "Musculoskeletal", "Shoulder disorders"),
            ("M75.0", "Adhesive capsulitis of shoulder", "Frozen shoulder", "Musculoskeletal", "Shoulder disorders"),
            ("M77.1", "Lateral epicondylitis", "Tennis elbow", "Musculoskeletal", "Elbow disorders"),
            ("M77.0", "Medial epicondylitis", "Golfer's elbow", "Musculoskeletal", "Elbow disorders"),
            ("M76.6", "Achilles tendinitis", "Achilles tendinitis", "Musculoskeletal", "Tendon disorders"),
            ("S93.4", "Sprain and strain of ankle", "Ankle sprain", "Injury", "Ankle injuries"),
            ("S83.5", "Sprain and strain of cruciate ligament of knee", "Knee ligament sprain", "Injury", "Knee injuries"),
            ("S43.4", "Sprain and strain of shoulder joint", "Shoulder sprain", "Injury", "Shoulder injuries"),
            ("S13.4", "Sprain and strain of cervical spine", "Neck strain/whiplash", "Injury", "Neck injuries"),
            ("G56.0", "Carpal tunnel syndrome", "Carpal tunnel syndrome", "Neurological", "Nerve entrapment"),
            ("R52", "Pain, unspecified", "General pain", "Symptoms", "Pain")
        ]
        
        for code, desc, short_desc, category, subcategory in basic_codes:
            cursor.execute('''
                INSERT INTO icd10_codes (code, description, short_description, category, subcategory, is_active, is_physiotherapy_relevant)
                VALUES (?, ?, ?, ?, ?, 1, 1)
            ''', (code, desc, short_desc, category, subcategory))
        
        # Create basic templates
        templates = [
            ("Acute Lower Back Pain", "Common acute lower back pain presentation", "M54.5", "moderate", 14),
            ("Neck Pain/Cervicalgia", "General neck pain condition", "M54.2", "moderate", 10),
            ("Frozen Shoulder", "Adhesive capsulitis of shoulder", "M75.0", "severe", 180),
            ("Tennis Elbow", "Lateral epicondylitis", "M77.1", "moderate", 42),
            ("Ankle Sprain", "Acute ankle ligament injury", "S93.4", "moderate", 21)
        ]
        
        for name, desc, code, severity, duration in templates:
            # Get the ICD-10 code ID
            cursor.execute("SELECT id FROM icd10_codes WHERE code = ?", (code,))
            result = cursor.fetchone()
            if result:
                code_id = result[0]
                
                cursor.execute('''
                    INSERT INTO diagnosis_templates (name, description, primary_icd10_code_id, default_severity, typical_duration_days)
                    VALUES (?, ?, ?, ?, ?)
                ''', (name, desc, code_id, severity, duration))
        
        conn.commit()
        print(f"✓ Seeded {len(basic_codes)} ICD-10 codes and {len(templates)} templates")
        return True
        
    except Exception as e:
        conn.rollback()
        print(f"✗ Error seeding data: {str(e)}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("SIMPLIFIED ICD-10 MIGRATION")
    print("=" * 60)
    
    success = True
    
    if create_icd10_tables():
        print("\n✓ Tables created successfully")
    else:
        success = False
    
    if seed_basic_data():
        print("✓ Basic data seeded successfully")
    else:
        print("⚠ Data seeding had issues")
    
    print("\n" + "=" * 60)
    if success:
        print("✓ MIGRATION COMPLETED!")
        print("\nNext steps:")
        print("1. Refresh your patient detail page")
        print("2. Try adding an ICD-10 diagnosis")
        print("3. Check the browser console for any errors")
    else:
        print("✗ MIGRATION FAILED!")
    print("=" * 60)
