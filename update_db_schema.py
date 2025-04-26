import sqlite3
import os
from pathlib import Path

# Get the database file path
basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'instance', 'physio.db')

# Make sure the database exists
if not Path(db_path).exists():
    print(f"Database file not found at: {db_path}")
    exit(1)

# Connect to the database
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if columns already exist to avoid errors
def column_exists(table, column):
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    return column in columns

# Add new columns to the Patient table
new_columns = [
    ("email", "VARCHAR(100)"),
    ("phone", "VARCHAR(20)"),
    ("address_line1", "VARCHAR(100)"),
    ("address_line2", "VARCHAR(100)"),
    ("city", "VARCHAR(50)"),
    ("postcode", "VARCHAR(20)"),
    ("preferred_location", "VARCHAR(50) DEFAULT 'Clinic'")
]

# Add each column if it doesn't exist
for column_name, column_type in new_columns:
    if not column_exists('patient', column_name):
        print(f"Adding column {column_name} to patient table")
        cursor.execute(f"ALTER TABLE patient ADD COLUMN {column_name} {column_type}")
    else:
        print(f"Column {column_name} already exists in patient table")

# Commit the changes
conn.commit()

# Close the connection
conn.close()

print("Database schema updated successfully") 