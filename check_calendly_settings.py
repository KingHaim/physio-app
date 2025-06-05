from flask import Flask
import os, sys

# Add the current directory to the path so we can import the app module
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    users = User.query.all()
    print(f"Total users: {len(users)}")
    
    for user in users:
        print(f"User: {user.email}")
        print(f"  - API Token exists: {bool(user.calendly_api_token)}")
        print(f"  - API Token value: '{user.calendly_api_token}'")
        print(f"  - User URI exists: {bool(user.calendly_user_uri)}")
        print(f"  - User URI value: '{user.calendly_user_uri}'")
        print("-" * 50) 