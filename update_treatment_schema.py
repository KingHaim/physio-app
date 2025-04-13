#!/usr/bin/env python3
import sqlite3
import json

# Connect to the database
conn = sqlite3.connect('instance/physio.db')
cursor = conn.cursor()

try:
    # Start transaction
    conn.execute('BEGIN TRANSACTION')
    
    # 1. First, get all the data from the current table
    cursor.execute("SELECT id, patient_id, date, description, progress_notes, next_appointment, status, created_at, pain_level, movement_restriction, evaluation_data FROM treatment")
    treatments = cursor.fetchall()
    
    # 2. Create a new table with the expected schema
    cursor.execute("""
    CREATE TABLE treatment_new (
        id INTEGER NOT NULL, 
        patient_id INTEGER NOT NULL, 
        treatment_type VARCHAR(100) NOT NULL,
        assessment TEXT,
        notes TEXT,
        status VARCHAR(50), 
        provider VARCHAR(100),
        created_at DATETIME,
        updated_at DATETIME,
        body_chart_url VARCHAR(255),
        pain_level INTEGER, 
        movement_restriction VARCHAR(50), 
        evaluation_data JSON, 
        PRIMARY KEY (id), 
        FOREIGN KEY(patient_id) REFERENCES patient (id)
    )
    """)
    
    # 3. Copy the data to the new table with field mapping
    for treatment in treatments:
        id, patient_id, date, description, progress_notes, next_appointment, status, created_at, pain_level, movement_restriction, evaluation_data = treatment
        
        # Use date as created_at if created_at is NULL
        if created_at is None:
            created_at = date
            
        # Insert into new table with mapped fields
        cursor.execute("""
        INSERT INTO treatment_new (
            id, patient_id, treatment_type, assessment, notes, status, provider, 
            created_at, updated_at, body_chart_url, pain_level, movement_restriction, evaluation_data
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            id, patient_id, description, "", progress_notes, status, "", 
            created_at, None, None, pain_level, movement_restriction, evaluation_data
        ))
    
    # 4. Drop the old table
    cursor.execute("DROP TABLE treatment")
    
    # 5. Rename the new table to the old table name
    cursor.execute("ALTER TABLE treatment_new RENAME TO treatment")
    
    # Commit the changes
    conn.commit()
    print("Successfully updated the treatment table schema to match the application model!")
    
except Exception as e:
    # Rollback in case of error
    conn.rollback()
    print(f"Error updating schema: {e}")
finally:
    conn.close() 