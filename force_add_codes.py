#!/usr/bin/env python3
"""
Force add the new ICD-10 codes directly to the database
"""

import sqlite3
import os

def force_add_codes():
    """Directly add codes to the database"""
    
    db_path = 'instance/app.db'
    if not os.path.exists(db_path):
        print("❌ Database file not found!")
        return False
    
    print(f"📁 Using database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # First, let's see what's currently in the database
        cursor.execute("SELECT code, short_description FROM icd10_codes LIMIT 5")
        existing = cursor.fetchall()
        print(f"📋 Current codes in database:")
        for code, desc in existing:
            print(f"  - {code}: {desc}")
        
        # TMJ codes
        tmj_codes = [
            ("M26.60", "Temporomandibular joint disorder, unspecified", "TMJ Dysfunction", "Musculoskeletal", "Head/Face disorders"),
            ("M26.62", "Arthralgia of temporomandibular joint", "Jaw joint pain", "Musculoskeletal", "Head/Face disorders"),
            ("M26.61", "Adhesions and ankylosis of temporomandibular joint", "Stiff jaw/TMJ", "Musculoskeletal", "Head/Face disorders"),
            ("M26.69", "Other specified temporomandibular joint disorders", "Clicking jaw/TMJ", "Musculoskeletal", "Head/Face disorders"),
        ]
        
        # Other new codes
        other_codes = [
            ("Z98.890", "Other specified postprocedural states", "Post-operative status", "Post-surgical", "Post-operative"),
            ("H81.10", "Benign paroxysmal positional vertigo, unspecified ear", "BPPV/Vertigo", "Neurological", "Vestibular disorders"),
            ("Z96.651", "Presence of right artificial knee joint", "Total knee replacement", "Post-surgical", "Joint replacement"),
            ("M92.5", "Juvenile osteochondrosis of tibia and fibula", "Osgood-Schlatter disease", "Musculoskeletal", "Pediatric conditions"),
        ]
        
        all_new_codes = tmj_codes + other_codes
        
        print(f"\n🔄 Adding {len(all_new_codes)} new codes...")
        
        added_count = 0
        for code, desc, short_desc, category, subcategory in all_new_codes:
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO icd10_codes (code, description, short_description, category, subcategory, is_active, is_physiotherapy_relevant)
                    VALUES (?, ?, ?, ?, ?, 1, 1)
                ''', (code, desc, short_desc, category, subcategory))
                print(f"  ✅ Added: {code} - {short_desc}")
                added_count += 1
            except Exception as e:
                print(f"  ❌ Failed to add {code}: {e}")
        
        # Add new templates
        templates = [
            ("Post-Op ACL Reconstruction", "Post-operative rehabilitation following ACL reconstruction", "Z98.890", "severe", 270),
            ("BPPV (Vertigo)", "Benign Paroxysmal Positional Vertigo - Posterior Canal", "H81.10", "severe", 3),
            ("Total Knee Arthroplasty (TKA)", "Rehabilitation following total knee replacement", "Z96.651", "moderate", 90),
            ("Osgood-Schlatter Disease", "Tibial tuberosity traction apophysitis in adolescents", "M92.5", "mild", 60),
        ]
        
        print(f"\n🔄 Adding {len(templates)} new templates...")
        
        template_count = 0
        for name, desc, code, severity, duration in templates:
            # Get the ICD-10 code ID
            cursor.execute("SELECT id FROM icd10_codes WHERE code = ?", (code,))
            result = cursor.fetchone()
            if result:
                code_id = result[0]
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO diagnosis_templates (name, description, primary_icd10_code_id, default_severity, typical_duration_days)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (name, desc, code_id, severity, duration))
                    print(f"  ✅ Added template: {name}")
                    template_count += 1
                except Exception as e:
                    print(f"  ❌ Failed to add template {name}: {e}")
            else:
                print(f"  ⚠️  Code {code} not found for template {name}")
        
        conn.commit()
        
        # Verify the additions
        cursor.execute("SELECT COUNT(*) FROM icd10_codes")
        total_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM diagnosis_templates")
        template_total = cursor.fetchone()[0]
        
        print(f"\n✅ SUCCESS!")
        print(f"  Added {added_count} new ICD-10 codes")
        print(f"  Added {template_count} new templates")
        print(f"  Total codes in database: {total_count}")
        print(f"  Total templates in database: {template_total}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
        conn.close()
        return False

if __name__ == "__main__":
    force_add_codes()
