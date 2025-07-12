#!/usr/bin/env python3
"""
Script to get the actual verification link for testing
"""

import os
import sys
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def get_verification_link():
    """Get the verification link for the last created user"""
    
    # Set environment to development
    os.environ['FLASK_ENV'] = 'development'
    
    # Clear email configuration to force console output
    if 'MAIL_SERVER' in os.environ:
        del os.environ['MAIL_SERVER']
    if 'MAIL_USERNAME' in os.environ:
        del os.environ['MAIL_USERNAME']
    if 'MAIL_PASSWORD' in os.environ:
        del os.environ['MAIL_PASSWORD']
    
    print("🔧 Getting Verification Link for Testing")
    print("=" * 50)
    
    try:
        from app import create_app
        from app.models import db, User
        from flask import url_for
        
        # Create custom config for port 5001
        app = create_app()
        app.config['SERVER_NAME'] = 'localhost:5001'
        
        with app.app_context():
            # Find the user we just created
            user = User.query.filter_by(email='test2@example.com').first()
            
            if not user:
                print("❌ User test2@example.com not found")
                return
                
            print(f"✅ Found user: {user.email}")
            print(f"📧 Email verified: {user.email_verified}")
            print(f"🔑 Has verification token: {bool(user.email_verification_token)}")
            
            if not user.email_verification_token:
                print("⚠️  No verification token found. Generating new one...")
                token = user.generate_email_verification_token()
                db.session.commit()
                print(f"✅ New token generated")
            else:
                print("⚠️  User has hashed token in database.")
                print("🔧 Generating new token for testing...")
                token = user.generate_email_verification_token()
                db.session.commit()
            
            # Generate the verification URL
            verification_url = url_for('auth.verify_email', token=token, _external=True)
            
            print("\n" + "=" * 60)
            print("🎯 VERIFICATION LINK READY!")
            print("=" * 60)
            print(f"📧 Email: {user.email}")
            print(f"🔗 Verification URL: {verification_url}")
            print("=" * 60)
            print("\n📋 STEPS TO TEST:")
            print("1. Copy the URL above")
            print("2. Open it in your browser")
            print("3. Should verify the email and redirect to login")
            print("\n🚀 Or click here to test automatically:")
            print(f"   open '{verification_url}'")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    get_verification_link() 