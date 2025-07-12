#!/usr/bin/env python3
"""
Debug script to diagnose 404 error in email verification
"""

import os
import sys
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_local_routes():
    """Test routes locally"""
    print("🔍 TESTING LOCAL ROUTES")
    print("=" * 50)
    
    try:
        # Import the Flask app
        from app import create_app
        
        app = create_app()
        
        with app.test_client() as client:
            # Test basic routes
            test_routes = [
                '/auth/login',
                '/auth/register',
                '/auth/verify_email/test-token',
                '/auth/resend-verification'
            ]
            
            for route in test_routes:
                try:
                    response = client.get(route)
                    if response.status_code == 404:
                        print(f"❌ {route} → 404 NOT FOUND")
                    else:
                        print(f"✅ {route} → {response.status_code}")
                except Exception as e:
                    print(f"❌ {route} → ERROR: {e}")
        
        # List all registered routes
        print("\n📋 ALL REGISTERED ROUTES:")
        print("-" * 30)
        for rule in app.url_map.iter_rules():
            if '/auth/' in rule.rule:
                print(f"✅ {rule.rule} → {rule.endpoint}")
                
    except Exception as e:
        print(f"❌ LOCAL TEST FAILED: {e}")
        return False
    
    return True

def test_production_routes():
    """Test routes in production"""
    print("\n🌐 TESTING PRODUCTION ROUTES")
    print("=" * 50)
    
    production_urls = [
        'https://trxck.tech/auth/login',
        'https://trxck.tech/auth/register', 
        'https://trxck.tech/auth/verify_email/test-token',
        'https://trxck.tech/auth/resend-verification'
    ]
    
    for url in production_urls:
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 404:
                print(f"❌ {url} → 404 NOT FOUND")
            else:
                print(f"✅ {url} → {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ {url} → ERROR: {e}")

def check_environment_config():
    """Check environment configuration"""
    print("\n⚙️  CHECKING ENVIRONMENT CONFIG")
    print("=" * 50)
    
    env_vars = [
        'FLASK_ENV',
        'SERVER_NAME', 
        'PREFERRED_URL_SCHEME',
        'MAIL_SERVER',
        'DATABASE_URL',
        'SECRET_KEY'
    ]
    
    for var in env_vars:
        value = os.getenv(var)
        if value:
            if 'SECRET' in var or 'PASSWORD' in var:
                print(f"✅ {var}: {'*' * 10}")
            else:
                print(f"✅ {var}: {value}")
        else:
            print(f"❌ {var}: NOT SET")

def check_url_generation():
    """Check URL generation"""
    print("\n🔗 CHECKING URL GENERATION")
    print("=" * 50)
    
    try:
        from app import create_app
        from flask import url_for
        
        app = create_app()
        
        with app.app_context():
            # Test URL generation
            try:
                verify_url = url_for('auth.verify_email', token='test-token', _external=True)
                print(f"✅ verify_email URL: {verify_url}")
                
                # Check if it's generating the correct URL
                if 'verify_email' in verify_url:
                    print("✅ URL generation is correct")
                else:
                    print("❌ URL generation might be wrong")
                    
            except Exception as e:
                print(f"❌ URL generation failed: {e}")
                
    except Exception as e:
        print(f"❌ URL generation test failed: {e}")

def check_blueprint_registration():
    """Check if auth blueprint is properly registered"""
    print("\n📝 CHECKING BLUEPRINT REGISTRATION")
    print("=" * 50)
    
    try:
        from app import create_app
        
        app = create_app()
        
        # Check if auth blueprint is registered
        auth_routes = []
        for rule in app.url_map.iter_rules():
            if rule.endpoint and rule.endpoint.startswith('auth.'):
                auth_routes.append(rule.rule)
        
        print(f"✅ Found {len(auth_routes)} auth routes:")
        for route in sorted(auth_routes):
            print(f"   {route}")
            
        # Specifically check for verify_email route
        verify_routes = [r for r in auth_routes if 'verify' in r]
        if verify_routes:
            print(f"\n✅ Verify email routes found: {verify_routes}")
        else:
            print("\n❌ No verify email routes found!")
            
    except Exception as e:
        print(f"❌ Blueprint check failed: {e}")

def main():
    """Main diagnostic function"""
    print("🚨 EMAIL VERIFICATION 404 DIAGNOSTIC")
    print("🔧 Investigating the issue...")
    print("=" * 60)
    
    # Run all diagnostics
    check_environment_config()
    check_blueprint_registration()
    check_url_generation()
    test_local_routes()
    test_production_routes()
    
    print("\n" + "=" * 60)
    print("🎯 DIAGNOSTIC COMPLETE")
    print("=" * 60)
    
    print("""
📋 NEXT STEPS:
1. If local routes work but production doesn't → Deploy changes to PythonAnywhere
2. If URL generation is wrong → Check email_utils.py
3. If blueprint not registered → Check __init__.py
4. If environment vars missing → Set them in PythonAnywhere

🚀 DEPLOYMENT REMINDER:
- Make sure you've pushed changes to git
- Pull latest changes in PythonAnywhere
- Reload your web app in PythonAnywhere
- Check PythonAnywhere error logs
""")

if __name__ == "__main__":
    main() 