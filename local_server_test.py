#!/usr/bin/env python3
"""
Simple script to run Flask app locally for email verification testing
"""

import os
import sys
import subprocess
import socket
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def find_free_port():
    """Find a free port to use"""
    ports_to_try = [5001, 5002, 5003, 8000, 8001, 8080, 3000]
    
    for port in ports_to_try:
        try:
            # Try to connect to the port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            
            if result != 0:  # Port is free
                return port
        except:
            continue
    
    return 5001  # Default fallback

def run_local_server():
    """Run Flask app locally for testing"""
    
    # Set environment to development
    os.environ['FLASK_ENV'] = 'development'
    
    # Find a free port
    port = find_free_port()
    
    print("🚀 Starting Local Flask Server for Email Verification Testing")
    print("=" * 70)
    
    try:
        from app import create_app
        
        app = create_app()
        
        print("✅ Flask app created successfully")
        print(f"🌐 Server will start on: http://localhost:{port}")
        print(f"📧 Email verification URLs will use: http://localhost:{port}")
        print("\n📋 Test Instructions:")
        print(f"1. Register a new user at: http://localhost:{port}/auth/register")
        print("2. Check the console for the verification email content")
        print("3. Copy the verification URL from the console")
        print("4. Test the URL in your browser")
        print("5. Verify that the route works locally")
        print("\n🔍 Common test URLs:")
        print(f"- Registration: http://localhost:{port}/auth/register")
        print(f"- Login: http://localhost:{port}/auth/login")
        print(f"- Test route: http://localhost:{port}/auth/verify_email/test-token")
        print("\n" + "=" * 70)
        print("🎯 Press Ctrl+C to stop the server")
        print("=" * 70)
        
        # Run the Flask app
        app.run(
            host='0.0.0.0',
            port=port,
            debug=True
        )
        
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    run_local_server() 