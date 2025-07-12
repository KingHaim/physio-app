#!/usr/bin/env python3
"""
Test production email configuration remotely
"""

import os
import sys
import requests
from datetime import datetime

def test_production_registration():
    """Test production email by registering a test user"""
    
    print("🧪 TESTING PRODUCTION EMAIL VERIFICATION")
    print("=" * 50)
    
    # Test data
    test_email = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}@example.com"
    test_data = {
        'email': test_email,
        'password': 'TestPassword123!',
        'confirm_password': 'TestPassword123!',
        'consent_given': True
    }
    
    print(f"📧 Testing with email: {test_email}")
    print(f"🌐 Testing URL: https://trxck.tech/auth/register")
    
    try:
        # Get the registration page first to get CSRF token
        print("\n1. 🔄 Getting registration page...")
        
        session = requests.Session()
        response = session.get('https://trxck.tech/auth/register')
        
        if response.status_code == 200:
            print("✅ Registration page loaded successfully")
            
            # Extract CSRF token from the page
            # This is a simple approach - you might need to parse HTML properly
            if 'csrf_token' in response.text:
                print("✅ CSRF token found in page")
            else:
                print("⚠️  CSRF token not found - this might cause issues")
            
            # Try to submit registration
            print("\n2. 📝 Submitting registration...")
            
            # Set proper headers
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Referer': 'https://trxck.tech/auth/register'
            }
            
            post_response = session.post(
                'https://trxck.tech/auth/register',
                data=test_data,
                headers=headers,
                allow_redirects=False
            )
            
            print(f"📊 Response status: {post_response.status_code}")
            
            if post_response.status_code == 302:
                print("✅ Registration submitted successfully (redirected)")
                print("📧 If email is configured correctly, verification email should be sent")
            elif post_response.status_code == 200:
                print("⚠️  Registration page returned (might have validation errors)")
                if 'error' in post_response.text.lower():
                    print("❌ Registration contained errors")
                else:
                    print("✅ Registration might be successful")
            else:
                print(f"❌ Unexpected response: {post_response.status_code}")
                
        else:
            print(f"❌ Could not load registration page: {response.status_code}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Connection error: {e}")
        print("🔍 This might indicate server issues or domain problems")
    
    print("\n" + "=" * 50)
    print("🎯 NEXT STEPS:")
    print("1. Check your server logs for email sending status")
    print("2. Check if the test email was sent")
    print("3. Verify all environment variables are set correctly")
    print("4. Restart your application if needed")

def test_production_connectivity():
    """Test basic connectivity to production server"""
    
    print("\n🔍 TESTING PRODUCTION CONNECTIVITY")
    print("=" * 50)
    
    endpoints = [
        'https://trxck.tech',
        'https://trxck.tech/auth/register',
        'https://trxck.tech/auth/login',
        'https://trxck.tech/auth/verify_email/test-token'
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(endpoint, timeout=10)
            if response.status_code == 200:
                print(f"✅ {endpoint} - OK")
            elif response.status_code == 404:
                print(f"❌ {endpoint} - NOT FOUND")
            else:
                print(f"⚠️  {endpoint} - {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ {endpoint} - CONNECTION ERROR: {e}")

def main():
    """Main function"""
    
    print("🚨 TRXCK.TECH PRODUCTION EMAIL TEST")
    print("⚠️  Testing email verification in production")
    print("=" * 50)
    
    # Test basic connectivity first
    test_production_connectivity()
    
    # Test email registration
    test_production_registration()
    
    print("\n" + "=" * 50)
    print("🎯 REMEMBER:")
    print("- Check your server logs for detailed error messages")
    print("- Verify that FLASK_ENV=production is set")
    print("- Ensure all email variables are configured")
    print("- Restart your application after setting variables")

if __name__ == "__main__":
    main() 