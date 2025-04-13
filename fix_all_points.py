#!/usr/bin/env python3
import sqlite3
import json
import sys
import os
import math
import time

# Connect to the database
conn = sqlite3.connect('instance/physio.db')
conn.row_factory = sqlite3.Row  # This allows accessing columns by name
cursor = conn.cursor()

# SVG viewBox dimensions
VIEW_SVG_WIDTH = 500
VIEW_SVG_HEIGHT = 800

# Maps of fixed positions based on the coordinates in original data
# Format: (original_x_range, original_y_range) -> (target_x, target_y)
POSITION_MAPPINGS = [
    # Upper back/trapezius area left side
    ((200, 250, 100, 200), (250, 180)),
    # Upper back/trapezius area right side
    ((300, 350, 100, 200), (350, 180)),
    # Mid back left side
    ((200, 250, 200, 300), (250, 250)),
    # Mid back right side
    ((300, 350, 200, 300), (350, 250)),
    # Lower back left side
    ((200, 250, 300, 400), (250, 350)),
    # Lower back right side
    ((300, 350, 300, 400), (350, 350)),
    # Gluteal area left side
    ((200, 250, 350, 450), (250, 400)),
    # Gluteal area right side
    ((300, 350, 350, 450), (350, 400)),
    # Leg left side
    ((200, 250, 450, 600), (250, 500)),
    # Leg right side
    ((300, 350, 450, 600), (350, 500))
]

# Function to determine the best mapping for a point
def get_best_position(x, y):
    # Define specific fixed positions for common anatomical landmarks with WIDER spread
    
    # Use a wider range of x-values to spread points horizontally
    # Center line is around 280
    if x < 230:
        # Far left side
        x_new = 120
    elif x < 280:
        # Center-left side
        x_new = 200
    elif x < 330:
        # Center-right side 
        x_new = 300
    else:
        # Far right side
        x_new = 380
    
    # Spread points vertically with more distinct positions
    if y < 130:  # Head area
        y_new = 120
    elif y < 160:  # Neck area
        y_new = 150
    elif y < 200:  # Upper shoulder area
        y_new = 180
    elif y < 240:  # Upper back
        y_new = 220
    elif y < 280:  # Mid back
        y_new = 260
    elif y < 320:  # Lower back - upper
        y_new = 300
    elif y < 360:  # Lower back - lower
        y_new = 340
    elif y < 400:  # Gluteal/hip area - upper
        y_new = 380
    elif y < 450:  # Gluteal/hip area - lower
        y_new = 420
    elif y < 500:  # Upper leg
        y_new = 460
    else:  # Lower leg
        y_new = 550
    
    # Add a small random offset to avoid perfect alignment (optional)
    # This part ensures points don't stack exactly on top of each other
    # We'll use the original x,y values to derive a consistent offset
    x_offset = (int(x * 10) % 30) - 15  # -15 to +14 pixel offset
    y_offset = (int(y * 10) % 20) - 10  # -10 to +9 pixel offset
    
    # Apply small offset for variety, but ensure we stay in reasonable bounds
    x_new = max(80, min(420, x_new + x_offset))
    y_new = max(80, min(700, y_new + y_offset))
    
    return x_new, y_new

# Function to update a treatment's trigger points
def fix_treatment_points(treatment_id, verbose=True):
    try:
        # Get existing trigger points
        cursor.execute("""
            SELECT id, location_x, location_y, type, muscle, intensity, symptoms, referral_pattern 
            FROM trigger_point 
            WHERE treatment_id = ?
        """, (treatment_id,))
        
        points = cursor.fetchall()
        
        if not points:
            if verbose:
                print(f"No trigger points found for treatment {treatment_id}")
            return False
        
        # Prepare evaluation_data with new coordinates
        evaluation_data = []
        point_mappings = []
        
        for point in points:
            # Get original coordinates
            orig_x = float(point['location_x'])
            orig_y = float(point['location_y'])
            
            # Determine the correct placement based on the original position
            new_x, new_y = get_best_position(orig_x, orig_y)
            
            # Store the mapping for logging
            point_mappings.append((point['id'], orig_x, orig_y, new_x, new_y))
            
            # Create point data
            point_json = {
                "id": f"point-{point['id']}",
                "x": round(new_x, 1),
                "y": round(new_y, 1),
                "type": point['type'] or "active",
                "muscle": point['muscle'] or "",
                "intensity": point['intensity'] or 5,
                "symptoms": point['symptoms'] or "",
                "referral": point['referral_pattern'] or ""
            }
            
            evaluation_data.append(point_json)
        
        # Update the treatment
        if evaluation_data:
            cursor.execute("""
                UPDATE treatment 
                SET evaluation_data = ? 
                WHERE id = ?
            """, (json.dumps(evaluation_data), treatment_id))
            
            conn.commit()
            
            if verbose:
                print(f"Successfully updated {len(evaluation_data)} points for treatment {treatment_id}")
                print("\nPoint mappings:")
                for point_id, orig_x, orig_y, new_x, new_y in point_mappings:
                    print(f"  Point {point_id}: ({orig_x:.1f}, {orig_y:.1f}) → ({new_x:.1f}, {new_y:.1f})")
            
            return True
        else:
            if verbose:
                print(f"No valid points to update for treatment {treatment_id}")
            return False
    
    except Exception as e:
        conn.rollback()
        if verbose:
            print(f"Error updating treatment {treatment_id}: {e}")
        return False

# Function to fix all treatments
def fix_all_treatments(treatment_ids=None):
    try:
        if treatment_ids:
            # Use the provided list of treatment IDs
            treatments = [(id,) for id in treatment_ids]
        else:
            # Get all treatments with trigger points
            cursor.execute("""
                SELECT DISTINCT t.id
                FROM treatment t
                JOIN trigger_point tp ON t.id = tp.treatment_id
                ORDER BY t.id
            """)
            treatments = cursor.fetchall()
        
        success_count = 0
        total_count = len(treatments)
        
        print(f"Fixing trigger points for {total_count} treatments...")
        
        for i, (treatment_id,) in enumerate(treatments):
            print(f"\nTreatment {i+1}/{total_count}: ID = {treatment_id}")
            if fix_treatment_points(treatment_id):
                success_count += 1
        
        print(f"\nSummary: Successfully updated {success_count} out of {total_count} treatments")
    
    except Exception as e:
        print(f"Error during batch update: {e}")

# Function to backup the database
def backup_database():
    try:
        timestamp = int(time.time())
        backup_path = f"instance/physio_backup_{timestamp}.db"
        cursor.execute("VACUUM INTO ?", (backup_path,))
        print(f"Database backed up to {backup_path}")
        return True
    except Exception as e:
        print(f"Error backing up database: {e}")
        return False

# Main function
def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python fix_all_points.py single <treatment_id>")
        print("  python fix_all_points.py batch [treatment_id1 treatment_id2 ...]")
        print("  python fix_all_points.py all")
        print("\nIf no treatment IDs are provided with 'batch', all treatments will be processed.")
        return
    
    command = sys.argv[1]
    
    # Create a backup before making changes
    if not backup_database():
        print("Failed to create backup. Aborting.")
        return
    
    if command == "single" and len(sys.argv) > 2:
        treatment_id = int(sys.argv[2])
        fix_treatment_points(treatment_id)
    
    elif command == "batch":
        treatment_ids = [int(id) for id in sys.argv[2:]] if len(sys.argv) > 2 else None
        fix_all_treatments(treatment_ids)
    
    elif command == "all":
        fix_all_treatments()
    
    else:
        print("Invalid command or missing arguments")
        print("Run the script without arguments for usage information")

if __name__ == "__main__":
    try:
        main()
    finally:
        conn.close() 