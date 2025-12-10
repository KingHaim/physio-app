#!/usr/bin/env python3
"""
Verify TMJ and other new codes are in the database
"""

import sqlite3
import os

def verify_codes():
    """Check if specific codes are in the database"""
    
    db_path = 'instance/app.db'
    if not os.path.exists(db_path):
        print("❌ Database file not found!")
        return False
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check total count
        cursor.execute("SELECT COUNT(*) FROM icd10_codes")
        total_count = cursor.fetchone()[0]
        print(f"📊 Total ICD-10 codes in database: {total_count}")
        
        # Check for TMJ codes specifically
        tmj_codes = ["M26.60", "M26.62", "M26.61", "M26.69"]
        print(f"\n🔍 Checking for TMJ codes:")
        
        found_tmj = []
        for code in tmj_codes:
            cursor.execute("SELECT code, short_description FROM icd10_codes WHERE code = ?", (code,))
            result = cursor.fetchone()
            if result:
                print(f"  ✅ {result[0]}: {result[1]}")
                found_tmj.append(code)
            else:
                print(f"  ❌ {code}: NOT FOUND")
        
        # Check for other new codes
        new_codes = ["Z98.890", "H81.10", "Z96.651", "M92.5"]
        print(f"\n🔍 Checking for other new codes:")
        
        found_new = []
        for code in new_codes:
            cursor.execute("SELECT code, short_description FROM icd10_codes WHERE code = ?", (code,))
            result = cursor.fetchone()
            if result:
                print(f"  ✅ {result[0]}: {result[1]}")
                found_new.append(code)
            else:
                print(f"  ❌ {code}: NOT FOUND")
        
        # Check templates
        cursor.execute("SELECT COUNT(*) FROM diagnosis_templates")
        template_count = cursor.fetchone()[0]
        print(f"\n📋 Total diagnosis templates: {template_count}")
        
        # Check for new templates
        new_templates = ["Post-Op ACL Reconstruction", "BPPV (Vertigo)", "Total Knee Arthroplasty (TKA)", "Osgood-Schlatter Disease"]
        print(f"\n🔍 Checking for new templates:")
        
        found_templates = []
        for template in new_templates:
            cursor.execute("SELECT name FROM diagnosis_templates WHERE name = ?", (template,))
            result = cursor.fetchone()
            if result:
                print(f"  ✅ {result[0]}")
                found_templates.append(template)
            else:
                print(f"  ❌ {template}: NOT FOUND")
        
        # Search functionality test
        print(f"\n🔍 Testing search for 'TMJ':")
        cursor.execute("SELECT code, short_description FROM icd10_codes WHERE description LIKE '%TMJ%' OR short_description LIKE '%TMJ%' OR code LIKE '%M26%'")
        tmj_search_results = cursor.fetchall()
        
        if tmj_search_results:
            for code, desc in tmj_search_results:
                print(f"  ✅ {code}: {desc}")
        else:
            print("  ❌ No TMJ codes found in search")
        
        conn.close()
        
        # Summary
        print(f"\n" + "="*50)
        print(f"📊 SUMMARY:")
        print(f"  Total codes: {total_count}")
        print(f"  TMJ codes found: {len(found_tmj)}/{len(tmj_codes)}")
        print(f"  New codes found: {len(found_new)}/{len(new_codes)}")
        print(f"  New templates found: {len(found_templates)}/{len(new_templates)}")
        
        if len(found_tmj) == len(tmj_codes) and len(found_new) == len(new_codes):
            print(f"✅ All new codes successfully deployed!")
            return True
        else:
            print(f"⚠️  Some codes may be missing")
            return False
            
    except Exception as e:
        print(f"❌ Error checking database: {e}")
        return False

if __name__ == "__main__":
    verify_codes()
