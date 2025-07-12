#!/usr/bin/env python3
"""
Run Flask server on port 5001 with correct configuration for email verification testing
"""

import os
import sys
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def run_server_port_5001():
    """Run Flask server on port 5001 with correct configuration"""
    
    # Set environment to development
    os.environ['FLASK_ENV'] = 'development'
    
    # Clear email configuration to force console output for testing
    if 'MAIL_SERVER' in os.environ:
        del os.environ['MAIL_SERVER']
    if 'MAIL_USERNAME' in os.environ:
        del os.environ['MAIL_USERNAME']
    if 'MAIL_PASSWORD' in os.environ:
        del os.environ['MAIL_PASSWORD']
    
    print("🚀 Starting Flask Server on Port 5001")
    print("📧 Email configuration cleared - emails will be displayed in console")
    print("=" * 60)
    
    try:
        from app import create_app
        from config import DevelopmentConfig
        
        # Create a custom config class for port 5001
        class DevelopmentConfig5001(DevelopmentConfig):
            DEBUG = True
            SQLALCHEMY_ECHO = True
            
            # Override server name for port 5001
            SERVER_NAME = 'localhost:5001'
            PREFERRED_URL_SCHEME = 'http'
            
            # Clear email configuration to force console output
            MAIL_SERVER = None
            MAIL_USERNAME = None
            MAIL_PASSWORD = None
        
        # Create app with the custom config
        app = create_app(DevelopmentConfig5001)
        
        print("✅ Flask app created successfully")
        print("🌐 Server will start on: http://localhost:5001")
        print("📧 Email verification URLs will use: http://localhost:5001")
        print("✅ SERVER_NAME configured correctly for port 5001")
        print("📧 Email configuration disabled - content will show in console")
        print("\n📋 Test Instructions:")
        print("1. Register a new user at: http://localhost:5001/auth/register")
        print("2. Check the console for the verification email content")
        print("3. Copy the verification URL from the console")
        print("4. Test the URL in your browser")
        print("5. Verify that the route works locally")
        print("\n🔍 Common test URLs:")
        print("- Registration: http://localhost:5001/auth/register")
        print("- Login: http://localhost:5001/auth/login")
        print("- Test route: http://localhost:5001/auth/verify_email/test-token")
        print("\n⚠️  IMPORTANT: Look for the email content in the console after registration!")
        print("=" * 60)
        print("🎯 Press Ctrl+C to stop the server")
        print("=" * 60)
        
        # Run the Flask app
        app.run(
            host='0.0.0.0',
            port=5001,
            debug=True
        )
        
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_server_port_5001() 