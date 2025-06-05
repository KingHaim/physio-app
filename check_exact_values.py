from flask import Flask
import os, sys

# Add the current directory to the path so we can import the app module
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from app import create_app, db
from app.models import User

app = create_app()

with app.app_context():
    # Find your currently logged in user
    haim_user = User.query.filter(User.username == 'haim').first()
    if not haim_user:
        print("Could not find user with username 'haim'")
        exit(1)
    
    print(f"User: {haim_user.email} (username: {haim_user.username})")
    
    # Check the token
    token = haim_user.calendly_api_token
    print(f"Token type: {type(token)}")
    print(f"Token length: {len(token) if token else 0}")
    print(f"Token repr: {repr(token)}")
    print(f"Token bool value: {bool(token)}")
    
    # Check the URI
    uri = haim_user.calendly_user_uri
    print(f"URI type: {type(uri)}")
    print(f"URI length: {len(uri) if uri else 0}")
    print(f"URI repr: {repr(uri)}")
    print(f"URI bool value: {bool(uri)}")
    
    # Check the literal condition used in the template
    is_condition_true = bool(haim_user.calendly_api_token and haim_user.calendly_user_uri)
    print(f"\nTemplate condition result: {is_condition_true}")
    
    # Test with some forced proper values
    haim_user.calendly_api_token = "test_token" 
    haim_user.calendly_user_uri = "https://api.calendly.com/users/test"
    
    # Check the condition again
    is_condition_true_after_update = bool(haim_user.calendly_api_token and haim_user.calendly_user_uri)
    print(f"Template condition after update: {is_condition_true_after_update}")
    
    # Don't commit the test changes
    db.session.rollback() 