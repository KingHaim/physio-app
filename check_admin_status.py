from flask import Flask
import os, sys

# Add the current directory to the path so we can import the app module
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    # Find the user with username 'haim'
    haim_user = User.query.filter(User.username == 'haim').first()
    if not haim_user:
        print("Could not find user with username 'haim'")
        exit(1)
    
    print(f"User: {haim_user.email} (username: {haim_user.username})")
    print(f"Is Admin: {haim_user.is_admin}")
    print(f"Role: {haim_user.role}")
    
    # Check if the is_admin flag is False but should be True
    if not haim_user.is_admin and haim_user.role == 'admin':
        print("\nIssue found: Your user has role 'admin' but the is_admin flag is False.")
        print("Would you like to fix this? (y/n)")
        response = input().strip().lower()
        if response == 'y':
            haim_user.is_admin = True
            db.session.commit()
            print("Fixed: Set is_admin flag to True.")
        else:
            print("No changes made.")
    elif not haim_user.is_admin:
        print("\nYour user account is not marked as an admin. This might explain why calendly_configured_for_user is False.")
        print("Would you like to set your account as admin? (y/n)")
        response = input().strip().lower()
        if response == 'y':
            haim_user.is_admin = True
            db.session.commit()
            print("Set is_admin flag to True.")
        else:
            print("No changes made.")
    else:
        print("\nYour user is correctly marked as an admin.") 