#!/usr/bin/env python3
import sqlite3
import json
import sys
import os
import time
import math
import random

# Connect to the database
conn = sqlite3.connect('instance/physio.db')
conn.row_factory = sqlite3.Row  # This allows accessing columns by name
cursor = conn.cursor()

# SVG viewBox dimensions
VIEW_SVG_WIDTH = 500
VIEW_SVG_HEIGHT = 800

# Wider coordinate range for better spread
SAFE_MIN_X = 100
SAFE_MAX_X = 400
SAFE_MIN_Y = 100
SAFE_MAX_Y = 700

# Function to spread points more widely
def spread_points(points):
    """Take a set of existing points and spread them further apart."""
    if len(points) <= 1:
        return points  # No need to spread a single point
    
    # For very few points, force extreme separation
    if len(points) == 2:
        # Place points at opposite corners of the body chart
        points[0]["x"] = 120  # Far left
        points[0]["y"] = 180  # Upper area
        
        points[1]["x"] = 380  # Far right
        points[1]["y"] = 480  # Lower area
        
        # Add z-index property to ensure the lower point appears on top
        # This will be used when rendering the SVG
        points[1]["z_index"] = 10  # Higher z-index for the lower point
        points[0]["z_index"] = 5   # Lower z-index for the upper point
        
        return points
    
    # For more than 2 points, use extreme spreading and assign z-indices
    
    # Find the bounding box of the original points
    min_x = min(p["x"] for p in points)
    max_x = max(p["x"] for p in points)
    min_y = min(p["y"] for p in points)
    max_y = max(p["y"] for p in points)
    
    # Calculate the center of the points
    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    
    # Calculate scaling factors to spread points (using a MUCH larger scale)
    x_scale = 4.0  # Very high scaling factor
    y_scale = 4.0  # Very high scaling factor
    
    # Apply transformation to spread points from center
    for i, point in enumerate(points):
        # Vector from center to point
        dx = point["x"] - center_x
        dy = point["y"] - center_y
        
        # Scale the vector to increase distance
        new_x = center_x + (dx * x_scale)
        new_y = center_y + (dy * y_scale)
        
        # Ensure we stay within safe bounds
        point["x"] = max(SAFE_MIN_X, min(SAFE_MAX_X, new_x))
        point["y"] = max(SAFE_MIN_Y, min(SAFE_MAX_Y, new_y))
        
        # Assign z-index based on y-position (higher y = higher z-index)
        # This ensures points lower in the image appear on top
        point["z_index"] = int(point["y"] / 10)  # Simple mapping from y to z-index
    
    return points

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

# Function to process a single treatment
def spread_treatment_points(treatment_id, verbose=True):
    try:
        # Get current evaluation_data
        cursor.execute("SELECT evaluation_data FROM treatment WHERE id = ?", (treatment_id,))
        result = cursor.fetchone()
        
        if not result or not result['evaluation_data']:
            if verbose:
                print(f"No evaluation data found for treatment {treatment_id}")
            return False
        
        # Parse the evaluation_data
        points = json.loads(result['evaluation_data'])
        
        if not points:
            if verbose:
                print(f"No points found in evaluation_data for treatment {treatment_id}")
            return False
        
        # Store original positions for reporting
        original_positions = [(p["id"], p["x"], p["y"]) for p in points]
        
        # Spread the points
        spread_points(points)
        
        # Update the treatment
        cursor.execute("""
            UPDATE treatment 
            SET evaluation_data = ? 
            WHERE id = ?
        """, (json.dumps(points), treatment_id))
        
        conn.commit()
        
        if verbose:
            print(f"Successfully spread {len(points)} points for treatment {treatment_id}")
            print("\nPoint transformations:")
            for i, (orig_id, orig_x, orig_y) in enumerate(original_positions):
                print(f"  {orig_id}: ({orig_x:.1f}, {orig_y:.1f}) → ({points[i]['x']:.1f}, {points[i]['y']:.1f})")
        
        return True
    
    except Exception as e:
        conn.rollback()
        if verbose:
            print(f"Error processing treatment {treatment_id}: {e}")
        return False

# Function to process all treatments
def spread_all_treatments(treatment_ids=None):
    try:
        if treatment_ids:
            # Use the provided list of treatment IDs
            treatments = [(id,) for id in treatment_ids]
        else:
            # Get all treatments with evaluation_data
            cursor.execute("""
                SELECT id
                FROM treatment
                WHERE evaluation_data IS NOT NULL
                ORDER BY id
            """)
            treatments = cursor.fetchall()
        
        if not treatments:
            print("No eligible treatments found.")
            return
        
        success_count = 0
        total_count = len(treatments)
        
        print(f"Spreading points for {total_count} treatments...")
        
        for i, (treatment_id,) in enumerate(treatments):
            print(f"\nTreatment {i+1}/{total_count}: ID = {treatment_id}")
            if spread_treatment_points(treatment_id):
                success_count += 1
        
        print(f"\nSummary: Successfully processed {success_count} out of {total_count} treatments")
    
    except Exception as e:
        print(f"Error during batch update: {e}")

# Main function
def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python spread_trigger_points.py single <treatment_id>")
        print("  python spread_trigger_points.py batch [treatment_id1 treatment_id2 ...]")
        print("  python spread_trigger_points.py all")
        return
    
    command = sys.argv[1]
    
    # Create a backup before making changes
    if not backup_database():
        print("Failed to create backup. Aborting.")
        return
    
    if command == "single" and len(sys.argv) > 2:
        treatment_id = int(sys.argv[2])
        spread_treatment_points(treatment_id)
    
    elif command == "batch":
        treatment_ids = [int(id) for id in sys.argv[2:]] if len(sys.argv) > 2 else None
        spread_all_treatments(treatment_ids)
    
    elif command == "all":
        spread_all_treatments()
    
    else:
        print("Invalid command or missing arguments")
        print("Run the script without arguments for usage information")

if __name__ == "__main__":
    try:
        main()
    finally:
        conn.close() 