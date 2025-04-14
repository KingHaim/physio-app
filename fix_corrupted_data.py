#!/usr/bin/env python3
import sqlite3
import os
from datetime import datetime

# --- Database Connection ---
DB_PATH = 'instance/physio.db'
CORRUPTED_STRING = '[{' # The specific invalid string we found

def connect_db():
    """Connects to the SQLite database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return None

# --- Backup Function ---
def backup_database(conn):
    """Creates a timestamped backup of the database."""
    backup_dir = os.path.dirname(DB_PATH)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"physio_backup_fix_corrupt_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    try:
        conn.execute("VACUUM INTO ?", (backup_path,))
        print(f"Database successfully backed up to: {backup_path}")
        return True
    except sqlite3.Error as e:
        print(f"Error backing up database: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred during backup: {e}")
        return False

# --- Main Logic ---
def fix_data(conn):
    """Finds and fixes treatment 61 if its evaluation_data is causing issues."""
    cursor = conn.cursor()
    fixed_count = 0
    target_treatment_id = 61
    
    try:
        # Check the current value for the target treatment (optional, for logging)
        cursor.execute("SELECT evaluation_data FROM treatment WHERE id = ?", (target_treatment_id,))
        current_data = cursor.fetchone()
        
        if current_data:
            print(f"Current evaluation_data for treatment {target_treatment_id}: {current_data['evaluation_data']}")
            
            # Update treatment 61 specifically to set evaluation_data to NULL
            print(f"Attempting to set evaluation_data to NULL for treatment ID {target_treatment_id}...")
            cursor.execute("UPDATE treatment SET evaluation_data = NULL WHERE id = ?", (target_treatment_id,))
            fixed_count = cursor.rowcount
            
            conn.commit()
            
            if fixed_count > 0:
                print(f"Successfully set evaluation_data to NULL for treatment ID {target_treatment_id}.")
            else:
                print(f"Did not update treatment ID {target_treatment_id} (perhaps already NULL or ID not found?).")
        else:
            print(f"Treatment ID {target_treatment_id} not found.")

    except sqlite3.Error as e:
        print(f"An error occurred during data fix for treatment {target_treatment_id}: {e}")
        conn.rollback() # Rollback changes on error
    except Exception as e:
         print(f"An unexpected error occurred: {e}")
         conn.rollback()

# --- Main Execution ---
if __name__ == "__main__":
    print("Starting script to fix corrupted evaluation_data...")
    conn = connect_db()

    if conn:
        if backup_database(conn):
            fix_data(conn)
        else:
            print("Aborting data fix due to backup failure.")
        
        conn.close()
        print("Database connection closed.")
    else:
        print("Could not connect to the database. Exiting.") 