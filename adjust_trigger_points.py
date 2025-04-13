#!/usr/bin/env python3
import sqlite3
import json
import math
import sys

# Connect to the database
conn = sqlite3.connect('instance/physio.db')
conn.row_factory = sqlite3.Row  # This allows accessing columns by name
cursor = conn.cursor()

# Updated scale factors based on 500x800 viewBox
X_SCALE = 1.0  # Additional scaling factor if needed
Y_SCALE = 1.0  # Additional scaling factor if needed

# Input coordinate ranges - these are the ranges we observed in the data
INPUT_MIN_X = 200
INPUT_MAX_X = 600
INPUT_MIN_Y = 100
INPUT_MAX_Y = 500

# Output coordinate ranges - these are the target ranges for the viewBox
OUTPUT_MIN_X = 120
OUTPUT_MAX_X = 380
OUTPUT_MIN_Y = 100
OUTPUT_MAX_Y = 700

# First, run a SQL update to reset all coordinates to their base values
# This helps us avoid applying scaling multiple times
try:
    # Set all evaluation_data to NULL to force a reset
    conn.execute("UPDATE treatment SET evaluation_data = NULL WHERE evaluation_data IS NOT NULL")
    conn.commit()
    print("Reset all evaluation_data fields to prepare for fresh scaling.")
except Exception as e:
    conn.rollback()
    print(f"Error resetting evaluation data: {e}")

# Get scaling factors from command line if provided
if len(sys.argv) > 2:
    try:
        X_SCALE = float(sys.argv[1])
        Y_SCALE = float(sys.argv[2])
    except ValueError:
        print(f"Invalid scale factors. Using defaults: X={X_SCALE}, Y={Y_SCALE}")

# Get range adjustments if provided
if len(sys.argv) > 6:
    try:
        OUTPUT_MIN_X = float(sys.argv[3])
        OUTPUT_MAX_X = float(sys.argv[4])
        OUTPUT_MIN_Y = float(sys.argv[5])
        OUTPUT_MAX_Y = float(sys.argv[6])
    except ValueError:
        print(f"Invalid output ranges. Using defaults.")

print(f"Adjusting trigger points with scale factors: X={X_SCALE}, Y={Y_SCALE}")
print(f"Input coordinate ranges: X=({INPUT_MIN_X}-{INPUT_MAX_X}), Y=({INPUT_MIN_Y}-{INPUT_MAX_Y})")
print(f"Output coordinate ranges: X=({OUTPUT_MIN_X}-{OUTPUT_MAX_X}), Y=({OUTPUT_MIN_Y}-{OUTPUT_MAX_Y})")

# Calculate the correct viewBox dimensions based on our templates
VIEW_SVG_WIDTH = 500
VIEW_SVG_HEIGHT = 800
EDIT_SVG_WIDTH = 200
EDIT_SVG_HEIGHT = 400

print(f"Target viewBox: 0 0 {VIEW_SVG_WIDTH} {VIEW_SVG_HEIGHT} (view_treatment.html)")
print(f"Edit viewBox: 0 0 {EDIT_SVG_WIDTH} {EDIT_SVG_HEIGHT} (edit_treatment.html)")

try:
    # 1. Get treatments with trigger points directly from the trigger_point table
    cursor.execute("""
        SELECT t.id, COUNT(tp.id) as point_count 
        FROM treatment t
        JOIN trigger_point tp ON t.id = tp.treatment_id
        GROUP BY t.id
        HAVING point_count > 0
        ORDER BY point_count DESC
    """)
    
    treatments = cursor.fetchall()
    
    if not treatments:
        print("No treatments with trigger points found.")
        sys.exit(0)
    
    adjusted_count = 0
    
    for treatment in treatments:
        treatment_id = treatment['id']
        
        try:
            # Get trigger points directly from database
            cursor.execute("""
                SELECT id, location_x, location_y, type, muscle, intensity, symptoms, referral_pattern 
                FROM trigger_point 
                WHERE treatment_id = ?
            """, (treatment_id,))
            
            trigger_points = cursor.fetchall()
            
            if not trigger_points:
                continue
                
            # Format trigger points as JSON
            evaluation_data = []
            for point in trigger_points:
                # Get raw values for x and y
                x = float(point['location_x'])
                y = float(point['location_y'])
                
                # Apply direct linear mapping from input ranges to output ranges
                
                # Clamp input values to input ranges
                x = max(INPUT_MIN_X, min(x, INPUT_MAX_X))
                y = max(INPUT_MIN_Y, min(y, INPUT_MAX_Y))
                
                # Calculate the normalized position within input range (0-1)
                norm_x = (x - INPUT_MIN_X) / (INPUT_MAX_X - INPUT_MIN_X)
                norm_y = (y - INPUT_MIN_Y) / (INPUT_MAX_Y - INPUT_MIN_Y)
                
                # Map to output range
                final_x = round(OUTPUT_MIN_X + norm_x * (OUTPUT_MAX_X - OUTPUT_MIN_X), 1)
                final_y = round(OUTPUT_MIN_Y + norm_y * (OUTPUT_MAX_Y - OUTPUT_MIN_Y), 1)
                
                # Apply additional scaling if needed
                final_x = round(final_x * X_SCALE, 1)
                final_y = round(final_y * Y_SCALE, 1)
                
                # Ensure coordinates stay within the viewBox bounds
                final_x = max(5, min(final_x, VIEW_SVG_WIDTH - 5))
                final_y = max(5, min(final_y, VIEW_SVG_HEIGHT - 5))
                
                point_data = {
                    "id": f"point-{point['id']}",
                    "x": final_x,
                    "y": final_y,
                    "type": point['type'] or "active",
                    "muscle": point['muscle'] or "",
                    "intensity": point['intensity'] or 5,
                    "symptoms": point['symptoms'] or "",
                    "referral": point['referral_pattern'] or ""
                }
                evaluation_data.append(point_data)
            
            # Update the treatment record
            cursor.execute("""
                UPDATE treatment 
                SET evaluation_data = ? 
                WHERE id = ?
            """, (json.dumps(evaluation_data), treatment_id))
            
            adjusted_count += 1
            
            # Print debug info for the first treatment
            if adjusted_count == 1:
                print(f"\nExample transformation for treatment {treatment_id}:")
                for i, point in enumerate(evaluation_data):
                    orig_x = float(trigger_points[i]['location_x'])
                    orig_y = float(trigger_points[i]['location_y'])
                    
                    # Calculate the intermediate values for debugging
                    clamped_x = max(INPUT_MIN_X, min(orig_x, INPUT_MAX_X))
                    clamped_y = max(INPUT_MIN_Y, min(orig_y, INPUT_MAX_Y))
                    
                    norm_x = (clamped_x - INPUT_MIN_X) / (INPUT_MAX_X - INPUT_MIN_X)
                    norm_y = (clamped_y - INPUT_MIN_Y) / (INPUT_MAX_Y - INPUT_MIN_Y)
                    
                    mapped_x = OUTPUT_MIN_X + norm_x * (OUTPUT_MAX_X - OUTPUT_MIN_X)
                    mapped_y = OUTPUT_MIN_Y + norm_y * (OUTPUT_MAX_Y - OUTPUT_MIN_Y)
                    
                    print(f"Point {i+1}: ({orig_x:.1f}, {orig_y:.1f}) → ({point['x']:.1f}, {point['y']:.1f})")
                    print(f"  Transformation steps:")
                    print(f"  1. Raw coordinates: ({orig_x:.1f}, {orig_y:.1f})")
                    print(f"  2. Clamped to input range: ({clamped_x:.1f}, {clamped_y:.1f})")
                    print(f"  3. Normalized (0-1): ({norm_x:.3f}, {norm_y:.3f})")
                    print(f"  4. Mapped to output range: ({mapped_x:.1f}, {mapped_y:.1f})")
                    print(f"  5. Final: ({point['x']:.1f}, {point['y']:.1f})")
            
        except (ValueError, TypeError) as e:
            print(f"Error processing treatment {treatment_id}: {e}")
            continue
    
    # Commit the changes
    conn.commit()
    print(f"Successfully adjusted scaling for {adjusted_count} treatments.")
    
    # Find the maximum values to help with calibration
    cursor.execute("""
        SELECT t.id, t.evaluation_data
        FROM treatment t
        WHERE t.evaluation_data IS NOT NULL
        ORDER BY t.id DESC
        LIMIT 10
    """)
    recent_treatments = cursor.fetchall()
    
    max_x, max_y = 0, 0
    min_x, min_y = float('inf'), float('inf')
    
    for treatment in recent_treatments:
        if treatment['evaluation_data']:
            try:
                points = json.loads(treatment['evaluation_data'])
                for point in points:
                    max_x = max(max_x, float(point["x"]))
                    max_y = max(max_y, float(point["y"]))
                    min_x = min(min_x, float(point["x"]))
                    min_y = min(min_y, float(point["y"]))
            except:
                continue
    
    print(f"\nAfter scaling, coordinate ranges:")
    print(f"X: {min_x:.1f} to {max_x:.1f}")
    print(f"Y: {min_y:.1f} to {max_y:.1f}")
    print("\nIdeal ranges for 500x800 viewBox:")
    print("X: 50 to 450 (centered in viewBox width)")
    print("Y: 50 to 750 (centered in viewBox height)")
    
    # Show a few sample points to verify
    if adjusted_count > 0:
        treatment_id = treatments[0]['id']
        cursor.execute("SELECT evaluation_data FROM treatment WHERE id = ?", (treatment_id,))
        sample = cursor.fetchone()
        
        if sample and sample['evaluation_data']:
            print("\nSample adjusted trigger points for treatment", treatment_id)
            print(json.dumps(json.loads(sample['evaluation_data']), indent=2))
    
except Exception as e:
    # Rollback in case of error
    conn.rollback()
    print(f"Error adjusting trigger points: {e}")
finally:
    conn.close()
    
print("\nTo try different scaling factors, run:")
print(f"python3 {sys.argv[0]} <x_scale> <y_scale>")
print("Example: python3 adjust_trigger_points.py 0.5 0.7")