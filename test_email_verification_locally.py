#!/usr/bin/env python3
"""
Script to test email verification locally
This temporarily overrides the production configuration to use localhost
"""

import os
import sys
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_email_verification():
    """Test email verification functionality locally"""
    
    # Set environment to development to use localhost URLs
    os.environ['FLASK_ENV'] = 'development'
    
    try:
        from app import create_app
        from app.models import db, User
        from app.email_utils import send_verification_email
        
        app = create_app()
        
        with app.app_context():
            print("🔧 Testing Email Verification System...")
            print("=" * 50)
            
            # Check if we can generate a verification URL
            test_user = User(
                email='test@example.com',
                username='test@example.com',
                first_name='Test',
                last_name='User',
                email_verified=False
            )
            test_user.set_password('testpass123')
            
            # Add to session (don't commit to avoid creating actual user)
            db.session.add(test_user)
            db.session.flush()  # Get an ID without committing
            
            # Test token generation
            token = test_user.generate_email_verification_token()
            print(f"✅ Token generated: {token[:20]}...")
            
            # Test URL generation
            from flask import url_for
            verification_url = url_for('auth.verify_email', token=token, _external=True)
            print(f"✅ Verification URL: {verification_url}")
            
            # Test email sending (will log to console)
            print("\n📧 Testing email sending...")
            result = send_verification_email(test_user)
            print(f"✅ Email send result: {result}")
            
            # Test route accessibility
            print("\n🌐 Testing route accessibility...")
            with app.test_client() as client:
                response = client.get(f'/auth/verify_email/{token}')
                print(f"✅ Route response status: {response.status_code}")
                if response.status_code != 404:
                    print("✅ Route is accessible!")
                else:
                    print("❌ Route returned 404!")
                    
            # Rollback the transaction
            db.session.rollback()
            
            print("\n🎉 Test completed!")
            print("=" * 50)
            
            # Show next steps
            print("\n📋 Next Steps:")
            print("1. If route test passed, the issue is in production deployment")
            print("2. Start your app locally: python app.py")
            print("3. Register a new user and check the console for the verification URL")
            print("4. Test the URL in your browser locally")
            print("5. For production, ensure trxck.tech is properly configured and deployed")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_email_verification() 