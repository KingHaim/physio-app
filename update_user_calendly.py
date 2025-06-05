from flask import Flask
import os, sys

# Add the current directory to the path so we can import the app module
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    # Find the admin user which has the credentials
    admin_user = User.query.filter_by(email='admin@example.com').first()
    if not admin_user:
        print("Admin user not found")
        exit(1)
        
    print(f"Admin user found: {admin_user.email}")
    print(f"Admin Calendly token: {bool(admin_user.calendly_api_token)}")
    print(f"Admin Calendly URI: {bool(admin_user.calendly_user_uri)}")
    
    # Find your currently logged in user
    current_user = User.query.filter(User.username.like('%haim%')).first()
    if not current_user:
        # Try with email
        current_user = User.query.filter(User.email.like('%haim%')).first()
    
    if not current_user:
        print("Could not find a user with 'haim' in username or email")
        exit(1)
    
    print(f"\nFound your user: {current_user.email} (username: {current_user.username})")
    print(f"Current Calendly token: {bool(current_user.calendly_api_token)}")
    print(f"Current Calendly URI: {bool(current_user.calendly_user_uri)}")
    
    # Copy the credentials from admin to your user
    current_user.calendly_api_token = admin_user.calendly_api_token
    current_user.calendly_user_uri = admin_user.calendly_user_uri
    db.session.commit()
    
    print("\nUpdated your user with admin's Calendly credentials")
    print(f"New Calendly token: {bool(current_user.calendly_api_token)}")
    print(f"New Calendly URI: {bool(current_user.calendly_user_uri)}")
    print("\nYou should now be able to use the Sync button!") 