#!/usr/bin/env python3
import sqlite3
import time
import os
from datetime import datetime

# Constants for fees
FIRST_SESSION_FEE = 80.0
SUBSEQUENT_SESSION_FEE = 70.0
CALENDLY_NOTE_MARKER = "Booked via Calendly"

# --- Database Connection ---
DB_PATH = 'instance/physio.db'

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
    backup_filename = f"physio_backup_fees_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    try:
        # Use VACUUM INTO for an efficient backup
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
def update_missing_fees(conn):
    """Finds treatments with missing fees and updates them based on clinic logic."""
    cursor = conn.cursor()
    updated_count = 0
    skipped_calendly = 0
    updated_treatments_log = [] # To store details of updates

    try:
        # Find treatments where fee_charged is NULL
        cursor.execute("""
            SELECT id, patient_id, created_at, notes
            FROM treatment
            WHERE fee_charged IS NULL
            ORDER BY patient_id, created_at
        """)
        treatments_to_update = cursor.fetchall()

        print(f"Found {len(treatments_to_update)} treatments with missing fees.")

        # Keep track of the first non-Calendly treatment date per patient
        patient_first_session_date = {}

        for treatment in treatments_to_update:
            treatment_id = treatment['id']
            patient_id = treatment['patient_id']
            notes = treatment['notes'] or "" # Handle NULL notes
            created_at_str = treatment['created_at']
            
            # Parse the datetime string
            try:
                # Adjust format string if necessary based on how dates are stored
                treatment_date = datetime.fromisoformat(created_at_str) 
            except (ValueError, TypeError):
                 print(f"Warning: Could not parse date '{created_at_str}' for treatment {treatment_id}. Skipping.")
                 continue


            # Check if it's a Calendly booking
            if CALENDLY_NOTE_MARKER in notes:
                print(f"Skipping Treatment ID {treatment_id} (Patient {patient_id}): Booked via Calendly.")
                skipped_calendly += 1
                continue

            # --- Determine if it's the first non-Calendly session for this patient ---
            
            # If we haven't processed this patient yet, find their first non-Calendly session date
            if patient_id not in patient_first_session_date:
                cursor.execute("""
                    SELECT MIN(created_at) as first_date
                    FROM treatment
                    WHERE patient_id = ? 
                      AND (notes IS NULL OR notes NOT LIKE ?)
                """, (patient_id, f"%{CALENDLY_NOTE_MARKER}%"))
                first_date_result = cursor.fetchone()
                
                if first_date_result and first_date_result['first_date']:
                     try:
                         patient_first_session_date[patient_id] = datetime.fromisoformat(first_date_result['first_date'])
                     except (ValueError, TypeError):
                         print(f"Warning: Could not parse first session date for patient {patient_id}. Logic might be affected.")
                         patient_first_session_date[patient_id] = None # Mark as unable to determine
                else:
                     patient_first_session_date[patient_id] = None # No non-Calendly sessions found yet

            # Determine the fee based on whether it's the first session
            fee_to_apply = None
            first_date_for_patient = patient_first_session_date.get(patient_id)

            # Check if this treatment's date matches the first non-calendly date we found
            # We need to compare just the date part if times might differ slightly
            is_first_session = False
            if first_date_for_patient and treatment_date.date() == first_date_for_patient.date():
                is_first_session = True
                fee_to_apply = FIRST_SESSION_FEE
                print(f"Applying FIRST session fee ({FIRST_SESSION_FEE}€) to Treatment ID {treatment_id} (Patient {patient_id}) on {treatment_date.strftime('%Y-%m-%d')}")
            elif first_date_for_patient: # It's a subsequent session if a first date exists and it's not this one
                fee_to_apply = SUBSEQUENT_SESSION_FEE
                print(f"Applying SUBSEQUENT session fee ({SUBSEQUENT_SESSION_FEE}€) to Treatment ID {treatment_id} (Patient {patient_id}) on {treatment_date.strftime('%Y-%m-%d')}")
            else:
                # This case means no non-Calendly sessions were found for this patient yet (this IS the first)
                # OR dates couldn't be parsed. Assume it's the first.
                is_first_session = True
                fee_to_apply = FIRST_SESSION_FEE
                print(f"Applying FIRST session fee ({FIRST_SESSION_FEE}€) to Treatment ID {treatment_id} (Patient {patient_id}) as no prior non-Calendly sessions found.")


            # Update the treatment record
            if fee_to_apply is not None:
                cursor.execute("""
                    UPDATE treatment
                    SET fee_charged = ?
                    WHERE id = ?
                """, (fee_to_apply, treatment_id))
                updated_count += 1
                updated_treatments_log.append({
                    "id": treatment_id,
                    "patient_id": patient_id,
                    "date": treatment_date.strftime('%Y-%m-%d'),
                    "fee": fee_to_apply,
                    "is_first": is_first_session 
                })
            else:
                 print(f"Error: Could not determine fee for Treatment ID {treatment_id}. Skipping update.")


        # Commit all changes at the end
        conn.commit()
        print("\n--- Update Summary ---")
        print(f"Total treatments checked: {len(treatments_to_update)}")
        print(f"Treatments updated with fee: {updated_count}")
        print(f"Treatments skipped (Calendly): {skipped_calendly}")

        if updated_treatments_log:
             print("\n--- Details of Updates ---")
             print("Treatment ID | Patient ID | Date       | Fee Applied (€) | Is First Session?")
             print("-" * 70)
             for log in updated_treatments_log:
                 print(f"{log['id']:<12} | {log['patient_id']:<10} | {log['date']:<10} | {log['fee']:<15.2f} | {'Yes' if log['is_first'] else 'No'}")
        
        print("\nFee update process completed.")

    except sqlite3.Error as e:
        print(f"An error occurred during fee update: {e}")
        conn.rollback() # Rollback changes on error
    except Exception as e:
         print(f"An unexpected error occurred: {e}")
         conn.rollback()


# --- Main Execution ---
if __name__ == "__main__":
    print("Starting script to update missing treatment fees...")
    conn = connect_db()

    if conn:
        if backup_database(conn):
            update_missing_fees(conn)
        else:
            print("Aborting fee update due to backup failure.")
        
        conn.close()
        print("Database connection closed.")
    else:
        print("Could not connect to the database. Exiting.") 