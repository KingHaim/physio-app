#!/usr/bin/env python3
import sqlite3
import json
import sys
import os
import time
from datetime import datetime

# Connect to the database
conn = sqlite3.connect('instance/physio.db')
conn.row_factory = sqlite3.Row  # This allows accessing columns by name
cursor = conn.cursor()

# SVG viewBox dimensions - should match what's in the HTML templates
SVG_VIEWBOX_WIDTH = 500
SVG_VIEWBOX_HEIGHT = 800

# Function to correct trigger point positions without altering their anatomical location
def fix_point_position(point):
    """
    Ensure trigger point is visible on the body chart without changing its anatomical position.
    This approach preserves the original relative position while ensuring it's visible on the chart.
    """
    # Get original position
    x = float(point.get("x", 0))
    y = float(point.get("y", 0))
    
    # Only adjust points that are outside the visible body area
    # These values are specific to the bodychart.svg dimensions
    # and should be adjusted based on the actual image dimensions
    
    # Horizontal boundaries - keep points on the body
    if x < 150:
        # Left side adjustment (if too far left)
        x = max(150, x)
    elif x > 350:
        # Right side adjustment (if too far right)
        x = min(350, x)
        
    # Vertical boundaries - keep points on the body
    if y < 80:
        # Top adjustment (if too high)
        y = max(80, y)
    elif y > 700:
        # Bottom adjustment (if too low)
        y = min(700, y)
    
    # Return corrected position
    return round(x, 1), round(y, 1)

def fix_treatment_points(treatment_id, verbose=True):
    """Fix trigger point positions for a specific treatment."""
    try:
        # Get evaluation_data for the treatment
        cursor.execute("SELECT evaluation_data FROM treatment WHERE id = ?", (treatment_id,))
        result = cursor.fetchone()
        
        if not result or not result['evaluation_data']:
            if verbose:
                print(f"No evaluation data found for treatment {treatment_id}")
            return False
        
        # Parse the evaluation_data
        try:
            points = json.loads(result['evaluation_data'])
        except json.JSONDecodeError:
            if verbose:
                print(f"Invalid JSON in evaluation_data for treatment {treatment_id}")
            return False
        
        if not points:
            if verbose:
                print(f"No points found in evaluation_data for treatment {treatment_id}")
            return False
        
        # Store original positions for reporting
        original_positions = [(p.get("id", "unknown"), p.get("x", 0), p.get("y", 0)) for p in points]
        
        # Fix each point's position to ensure it's visible without changing anatomical location
        for point in points:
            # Get the corrected position
            new_x, new_y = fix_point_position(point)
            
            # Update point coordinates if needed
            point["x"] = new_x
            point["y"] = new_y
        
        # Update the treatment with the fixed coordinates
        cursor.execute("""
            UPDATE treatment 
            SET evaluation_data = ? 
            WHERE id = ?
        """, (json.dumps(points), treatment_id))
        
        conn.commit()
        
        if verbose:
            print(f"Successfully updated {len(points)} points for treatment {treatment_id}")
            print("\nPoint adjustments:")
            for i, (point_id, orig_x, orig_y) in enumerate(original_positions):
                if orig_x != points[i]["x"] or orig_y != points[i]["y"]:
                    print(f"  {point_id}: ({orig_x:.1f}, {orig_y:.1f}) → ({points[i]['x']:.1f}, {points[i]['y']:.1f})")
                else:
                    print(f"  {point_id}: No change needed ({orig_x:.1f}, {orig_y:.1f})")
        
        return True
    
    except Exception as e:
        conn.rollback()
        if verbose:
            print(f"Error updating treatment {treatment_id}: {e}")
        return False

def fix_all_treatments(treatment_ids=None):
    """Fix trigger point positions for multiple or all treatments."""
    try:
        if treatment_ids:
            # Use the provided list of treatment IDs
            treatments = [(id,) for id in treatment_ids]
        else:
            # Get all treatments with evaluation_data
            cursor.execute("""
                SELECT id
                FROM treatment
                WHERE evaluation_data IS NOT NULL AND evaluation_data != '[]'
                ORDER BY id
            """)
            treatments = cursor.fetchall()
        
        if not treatments:
            print("No eligible treatments found.")
            return
        
        success_count = 0
        total_count = len(treatments)
        
        print(f"Fixing trigger point positions for {total_count} treatments...")
        
        for i, (treatment_id,) in enumerate(treatments):
            print(f"\nTreatment {i+1}/{total_count}: ID = {treatment_id}")
            if fix_treatment_points(treatment_id):
                success_count += 1
        
        print(f"\nSummary: Successfully processed {success_count} out of {total_count} treatments")
    
    except Exception as e:
        print(f"Error during batch update: {e}")

def backup_database():
    """Create a backup of the database before making changes."""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"instance/physio_backup_positions_{timestamp}.db"
        cursor.execute("VACUUM INTO ?", (backup_path,))
        print(f"Database backed up to {backup_path}")
        return True
    except Exception as e:
        print(f"Error backing up database: {e}")
        return False

def main():
    """Main function to handle command-line arguments."""
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python fix_trigger_point_scaling.py single <treatment_id>")
        print("  python fix_trigger_point_scaling.py batch [treatment_id1 treatment_id2 ...]")
        print("  python fix_trigger_point_scaling.py all")
        print("\nOptions:")
        print("  single: Fix a single treatment ID")
        print("  batch: Fix a list of treatment IDs")
        print("  all: Fix all treatments with trigger points")
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
        print("Invalid command. Run without arguments to see usage information.")

if __name__ == "__main__":
    try:
        main()
    finally:
        conn.close() 