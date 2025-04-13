#!/usr/bin/env python3
import sqlite3
import json
import sys

# Connect to the database
conn = sqlite3.connect('instance/physio.db')
conn.row_factory = sqlite3.Row  # This allows accessing columns by name
cursor = conn.cursor()

# SVG viewBox dimensions
VIEW_SVG_WIDTH = 500
VIEW_SVG_HEIGHT = 800

# Define specific body regions with their coordinate ranges
# Format: (min_x, max_x, min_y, max_y)
BODY_REGIONS = {
    # Front view (left side of the viewBox)
    "front_head": (140, 190, 50, 120),
    "front_neck": (140, 190, 120, 150),
    "front_shoulder_left": (100, 140, 150, 180),
    "front_shoulder_right": (190, 230, 150, 180),
    "front_chest": (140, 190, 180, 250),
    "front_abdomen": (140, 190, 250, 350),
    "front_arm_left": (70, 100, 180, 300),
    "front_arm_right": (230, 260, 180, 300),
    "front_hip_left": (120, 140, 350, 400),
    "front_hip_right": (190, 210, 350, 400),
    "front_leg_left": (120, 140, 400, 600),
    "front_leg_right": (190, 210, 400, 600),
    
    # Back view (right side of the viewBox)
    "back_head": (310, 360, 50, 120),
    "back_neck": (310, 360, 120, 150),
    "back_shoulder_left": (270, 310, 150, 180),
    "back_shoulder_right": (360, 400, 150, 180),
    "back_upper_back": (310, 360, 180, 250),
    "back_lower_back": (310, 360, 250, 350),
    "back_arm_left": (240, 270, 180, 300),
    "back_arm_right": (400, 430, 180, 300),
    "back_hip_left": (290, 310, 350, 400),
    "back_hip_right": (360, 380, 350, 400),
    "back_leg_left": (290, 310, 400, 600),
    "back_leg_right": (360, 380, 400, 600),
    "back_gluteal_left": (290, 310, 350, 380),
    "back_gluteal_right": (360, 380, 350, 380)
}

# Helper function to get a region's coordinates
def get_region_coordinates(region_name):
    if region_name in BODY_REGIONS:
        min_x, max_x, min_y, max_y = BODY_REGIONS[region_name]
        # Return center of the region by default
        return (min_x + max_x) / 2, (min_y + max_y) / 2
    else:
        print(f"Region '{region_name}' not found. Available regions:")
        for region in BODY_REGIONS.keys():
            print(f"  - {region}")
        return None, None

# Function to update a treatment's trigger points
def update_treatment_points(treatment_id, points_data):
    """
    Update a treatment's trigger points with manually specified coordinates
    
    points_data format: [
        {"id": 123, "region": "back_shoulder_left", "x_offset": 0, "y_offset": 5},
        {"id": 124, "region": "back_gluteal_right", "x_offset": -5, "y_offset": 0}
    ]
    
    If x and y are directly provided instead of region, those coordinates will be used.
    """
    try:
        # Get existing trigger points
        cursor.execute("""
            SELECT id, type, muscle, intensity, symptoms, referral_pattern 
            FROM trigger_point 
            WHERE treatment_id = ?
        """, (treatment_id,))
        
        db_points = cursor.fetchall()
        point_dict = {point['id']: point for point in db_points}
        
        # Prepare evaluation_data with new coordinates
        evaluation_data = []
        
        for point_data in points_data:
            point_id = point_data.get("id")
            
            if point_id not in point_dict:
                print(f"Warning: Point ID {point_id} not found in treatment {treatment_id}")
                continue
                
            db_point = point_dict[point_id]
            
            # Get coordinates
            if "region" in point_data:
                # Get region center coordinates
                base_x, base_y = get_region_coordinates(point_data["region"])
                if base_x is None:
                    continue
                
                # Apply offsets if provided
                x_offset = point_data.get("x_offset", 0)
                y_offset = point_data.get("y_offset", 0)
                
                x = base_x + x_offset
                y = base_y + y_offset
            elif "x" in point_data and "y" in point_data:
                # Use directly provided coordinates
                x = point_data["x"]
                y = point_data["y"]
            else:
                print(f"Error: Point {point_id} has no valid coordinates")
                continue
            
            # Ensure coordinates stay within the viewBox bounds
            x = max(5, min(x, VIEW_SVG_WIDTH - 5))
            y = max(5, min(y, VIEW_SVG_HEIGHT - 5))
            
            # Create point data
            point_json = {
                "id": f"point-{point_id}",
                "x": round(x, 1),
                "y": round(y, 1),
                "type": db_point["type"] or "active",
                "muscle": db_point["muscle"] or "",
                "intensity": db_point["intensity"] or 5,
                "symptoms": db_point["symptoms"] or "",
                "referral": db_point["referral_pattern"] or ""
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
            print(f"Successfully updated {len(evaluation_data)} points for treatment {treatment_id}")
            
            # Show the updated points
            print("\nUpdated points:")
            for point in evaluation_data:
                print(f"  ID: {point['id']}, Position: ({point['x']}, {point['y']}), Type: {point['type']}")
        else:
            print(f"No valid points to update for treatment {treatment_id}")
    
    except Exception as e:
        conn.rollback()
        print(f"Error updating treatment {treatment_id}: {e}")

# List available body regions
def list_regions():
    print("\nAvailable body regions:")
    
    # Group by front/back
    front_regions = [r for r in BODY_REGIONS.keys() if r.startswith('front_')]
    back_regions = [r for r in BODY_REGIONS.keys() if r.startswith('back_')]
    
    print("\nFront body regions:")
    for region in sorted(front_regions):
        min_x, max_x, min_y, max_y = BODY_REGIONS[region]
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        print(f"  - {region}: center at ({center_x:.1f}, {center_y:.1f})")
    
    print("\nBack body regions:")
    for region in sorted(back_regions):
        min_x, max_x, min_y, max_y = BODY_REGIONS[region]
        center_x = (min_x + max_x) / 2
        center_y = (min_y + max_y) / 2
        print(f"  - {region}: center at ({center_x:.1f}, {center_y:.1f})")

# List all treatments with trigger points
def list_treatments():
    try:
        cursor.execute("""
            SELECT t.id, t.treatment_type, COUNT(tp.id) as point_count 
            FROM treatment t
            JOIN trigger_point tp ON t.id = tp.treatment_id
            GROUP BY t.id
            HAVING point_count > 0
            ORDER BY t.id DESC
        """)
        
        treatments = cursor.fetchall()
        
        print("\nTreatments with trigger points:")
        for t in treatments:
            print(f"  - Treatment ID: {t['id']}, Type: {t['treatment_type']}, Points: {t['point_count']}")
    
    except Exception as e:
        print(f"Error listing treatments: {e}")

# List trigger points for a specific treatment
def list_treatment_points(treatment_id):
    try:
        cursor.execute("""
            SELECT tp.id, tp.location_x, tp.location_y, tp.type, tp.muscle
            FROM trigger_point tp
            WHERE tp.treatment_id = ?
            ORDER BY tp.id
        """, (treatment_id,))
        
        points = cursor.fetchall()
        
        print(f"\nTrigger points for treatment {treatment_id}:")
        for p in points:
            print(f"  - Point ID: {p['id']}, Position: ({p['location_x']:.1f}, {p['location_y']:.1f}), " +
                  f"Type: {p['type'] or 'active'}, Muscle: {p['muscle'] or 'Unknown'}")
    
    except Exception as e:
        print(f"Error listing points: {e}")

# Main function
def main():
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python manual_point_placement.py list_regions")
        print("  python manual_point_placement.py list_treatments")
        print("  python manual_point_placement.py list_points <treatment_id>")
        print("  python manual_point_placement.py update_treatment <treatment_id> <points_file.json>")
        print("\nExample points file content:")
        print('''{
  "points": [
    {"id": 88, "region": "back_shoulder_left", "x_offset": 0, "y_offset": 0},
    {"id": 89, "region": "back_gluteal_right", "x_offset": -5, "y_offset": 0},
    {"id": 90, "x": 250, "y": 300}
  ]
}''')
        return
    
    command = sys.argv[1]
    
    if command == "list_regions":
        list_regions()
    
    elif command == "list_treatments":
        list_treatments()
    
    elif command == "list_points" and len(sys.argv) > 2:
        treatment_id = int(sys.argv[2])
        list_treatment_points(treatment_id)
    
    elif command == "update_treatment" and len(sys.argv) > 3:
        treatment_id = int(sys.argv[2])
        points_file = sys.argv[3]
        
        try:
            with open(points_file, 'r') as f:
                data = json.load(f)
                points_data = data.get("points", [])
                
                if points_data:
                    update_treatment_points(treatment_id, points_data)
                else:
                    print("Error: No points found in the JSON file")
        
        except FileNotFoundError:
            print(f"Error: File {points_file} not found")
        except json.JSONDecodeError:
            print(f"Error: Invalid JSON in {points_file}")
        except Exception as e:
            print(f"Error: {e}")
    
    else:
        print("Invalid command or missing arguments")
        print("Run the script without arguments for usage information")

if __name__ == "__main__":
    try:
        main()
    finally:
        conn.close() 