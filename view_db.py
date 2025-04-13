#!/usr/bin/env python3
import sqlite3
import json
from datetime import datetime

def format_value(value):
    """Format datetime and JSON values for better readability"""
    if value is None:
        return "NULL"
    elif isinstance(value, str) and value.startswith("{") and value.endswith("}"):
        try:
            # Try to format JSON data
            parsed = json.loads(value)
            return json.dumps(parsed, indent=2)
        except:
            return value
    return value

def print_table(conn, table_name):
    """Print all rows from a table in a formatted way"""
    print(f"\n{'=' * 80}")
    print(f"TABLE: {table_name}")
    print(f"{'=' * 80}")
    
    # Get column names
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    
    # Get data
    cursor = conn.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    
    if not rows:
        print("No data in this table")
        return
    
    # Print column headers
    header = " | ".join(columns)
    print(header)
    print("-" * len(header))
    
    # Print rows
    for row in rows:
        formatted_row = [str(format_value(val)) for val in row]
        print(" | ".join(formatted_row))

def main():
    try:
        # Connect to the database
        conn = sqlite3.connect('instance/physio.db')
        
        # Get all table names
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        print(f"Found {len(tables)} tables: {', '.join(tables)}")
        
        # Print each table
        for table in tables:
            print_table(conn, table)
            
        conn.close()
        print("\nDatabase information displayed successfully!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main() 