#!/usr/bin/env python3
from datetime import datetime
import os
import sqlite3
import getpass
from werkzeug.security import generate_password_hash

# Configuration
# Credentials can be provided via environment variables or entered interactively
username = os.getenv("ADMIN_USERNAME") or input("Admin username: ")
email = os.getenv("ADMIN_EMAIL") or input("Admin email: ")
password = os.getenv("ADMIN_PASSWORD") or getpass.getpass("Admin password: ")
is_admin = os.getenv("ADMIN_IS_ADMIN", "True").lower() in ("1", "true", "yes", "y")

# Generate password hash using Werkzeug's function
password_hash = generate_password_hash(password)

# Connect to the database
conn = sqlite3.connect('instance/physio.db')
cursor = conn.cursor()

try:
    # Check if the user already exists
    cursor.execute("SELECT id FROM user WHERE username=? OR email=?", (username, email))
    existing_user = cursor.fetchone()
    
    
    if existing_user:
        # Update existing user
        cursor.execute(
            "UPDATE user SET username=?, email=?, password_hash=?, is_admin=?, created_at=? WHERE id=?",
            (username, email, password_hash, is_admin, datetime.utcnow(), existing_user[0])
        )
        print(f"Updated existing user (ID: {existing_user[0]}) with new credentials")
    else:
        # Insert new user
        cursor.execute(
            "INSERT INTO user (username, email, password_hash, is_admin, created_at) VALUES (?, ?, ?, ?, ?)",
            (username, email, password_hash, is_admin, datetime.utcnow())
        )
        user_id = cursor.lastrowid
        print(f"Created new admin user with ID: {user_id}")
    
    # Commit the changes
    conn.commit()
    
    print("Successfully set up admin credentials:")
    print(f"Username: {username}")
    print(f"Email: {email}")
    print(f"Admin: {'Yes' if is_admin else 'No'}")
    
except Exception as e:
    conn.rollback()
    print(f"Error creating admin user: {e}")
finally:
    conn.close() 