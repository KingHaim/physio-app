#!/usr/bin/env python3
import sqlite3
import json
from datetime import datetime

# Connect to the database
conn = sqlite3.connect('instance/physio.db')
conn.row_factory = sqlite3.Row  # This allows accessing columns by name
cursor = conn.cursor()

try:
    # 1. Get all treatments
    cursor.execute("SELECT id, evaluation_data FROM treatment")
    treatments = cursor.fetchall()
    
    updated_count = 0
    
    for treatment in treatments:
        treatment_id = treatment['id']
        
        # 2. Get all trigger points for this treatment
        cursor.execute("""
            SELECT id, location_x, location_y, type, muscle, intensity, symptoms, referral_pattern 
            FROM trigger_point 
            WHERE treatment_id = ?
        """, (treatment_id,))
        
        trigger_points = cursor.fetchall()
        
        if trigger_points:
            # 3. Format trigger points as JSON for evaluation_data
            evaluation_data = []
            
            for point in trigger_points:
                point_data = {
                    "id": f"point-{point['id']}",
                    "x": float(point['location_x']),
                    "y": float(point['location_y']),
                    "type": point['type'] or "active",
                    "muscle": point['muscle'] or "",
                    "intensity": point['intensity'] or 5,
                    "symptoms": point['symptoms'] or "",
                    "referral": point['referral_pattern'] or ""
                }
                evaluation_data.append(point_data)
            
            # 4. Update the treatment record
            cursor.execute("""
                UPDATE treatment 
                SET evaluation_data = ? 
                WHERE id = ?
            """, (json.dumps(evaluation_data), treatment_id))
            
            updated_count += 1
    
    # Commit the changes
    conn.commit()
    print(f"Successfully updated evaluation_data for {updated_count} treatments.")
    
    # 5. Verify that trigger points are connected to treatments properly
    cursor.execute("""
        SELECT t.id, t.treatment_type, COUNT(tp.id) as point_count 
        FROM treatment t
        LEFT JOIN trigger_point tp ON t.id = tp.treatment_id
        GROUP BY t.id
        ORDER BY point_count DESC
        LIMIT 10
    """)
    
    results = cursor.fetchall()
    
    print("\nTop 10 treatments by trigger point count:")
    print("Treatment ID | Treatment Type | Trigger Point Count")
    print("-" * 60)
    
    for row in results:
        print(f"{row['id']:12} | {row['treatment_type'][:30]:30} | {row['point_count']}")
    
except Exception as e:
    # Rollback in case of error
    conn.rollback()
    print(f"Error updating trigger points: {e}")
finally:
    conn.close() 