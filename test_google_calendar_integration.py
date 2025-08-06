#!/usr/bin/env python3
"""
Test script for Google Calendar integration
This script verifies that all components are working correctly
"""

import os
import sys
from pathlib import Path

def test_imports():
    """Test that all required modules can be imported"""
    print("🧪 Testing imports...")
    
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import Flow
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        print("  ✅ Google API libraries imported successfully")
    except ImportError as e:
        print(f"  ❌ Error importing Google libraries: {e}")
        return False
    
    try:
        # Test Flask app imports
        sys.path.insert(0, str(Path(__file__).parent))
        from app.google_calendar_service import google_calendar_service
        from app.models import User, Treatment
        print("  ✅ App modules imported successfully")
    except ImportError as e:
        print(f"  ❌ Error importing app modules: {e}")
        return False
    
    return True

def test_environment_variables():
    """Test that environment variables are configured"""
    print("\n🧪 Testing environment variables...")
    
    required_vars = [
        'GOOGLE_CLIENT_ID',
        'GOOGLE_CLIENT_SECRET', 
        'GOOGLE_REDIRECT_URI'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        print(f"  ❌ Missing environment variables: {', '.join(missing_vars)}")
        print("  📝 Add these to your .env file:")
        for var in missing_vars:
            print(f"     {var}=your_value_here")
        return False
    else:
        print("  ✅ All required environment variables are set")
        return True

def test_database_fields():
    """Test that database fields exist"""
    print("\n🧪 Testing database fields...")
    
    try:
        import sqlite3
        
        # Check if database exists
        db_path = 'instance/physio-2.db'
        if not os.path.exists(db_path):
            print(f"  ❌ Database not found at {db_path}")
            return False
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check User table fields
        cursor.execute("PRAGMA table_info(user)")
        user_columns = [col[1] for col in cursor.fetchall()]
        
        required_user_fields = [
            'google_calendar_token_encrypted',
            'google_calendar_refresh_token_encrypted',
            'google_calendar_enabled',
            'google_calendar_primary_calendar_id',
            'google_calendar_last_sync'
        ]
        
        missing_user_fields = [field for field in required_user_fields if field not in user_columns]
        
        if missing_user_fields:
            print(f"  ❌ Missing User table fields: {', '.join(missing_user_fields)}")
            print("  📝 Run migration: python3 -m flask db upgrade")
            return False
        
        # Check Treatment table fields
        cursor.execute("PRAGMA table_info(treatment)")
        treatment_columns = [col[1] for col in cursor.fetchall()]
        
        required_treatment_fields = [
            'google_calendar_event_id',
            'google_calendar_event_summary'
        ]
        
        missing_treatment_fields = [field for field in required_treatment_fields if field not in treatment_columns]
        
        if missing_treatment_fields:
            print(f"  ❌ Missing Treatment table fields: {', '.join(missing_treatment_fields)}")
            print("  📝 Run migration: python3 -m flask db upgrade")
            return False
        
        print("  ✅ All database fields are present")
        conn.close()
        return True
        
    except Exception as e:
        print(f"  ❌ Error checking database: {e}")
        return False

def test_routes():
    """Test that routes are registered"""
    print("\n🧪 Testing routes...")
    
    try:
        from app import create_app
        app = create_app()
        
        # Check if Google Calendar routes are registered
        google_routes = [rule for rule in app.url_map.iter_rules() if 'google-calendar' in rule.rule]
        
        expected_routes = [
            '/google-calendar/connect',
            '/google-calendar/callback',
            '/google-calendar/sync',
            '/google-calendar/status',
            '/google-calendar/disconnect'
        ]
        
        registered_routes = [rule.rule for rule in google_routes]
        missing_routes = [route for route in expected_routes if route not in registered_routes]
        
        if missing_routes:
            print(f"  ❌ Missing routes: {', '.join(missing_routes)}")
            return False
        
        print(f"  ✅ All {len(google_routes)} Google Calendar routes are registered")
        return True
        
    except Exception as e:
        print(f"  ❌ Error testing routes: {e}")
        return False

def test_templates():
    """Test that templates have been updated"""
    print("\n🧪 Testing templates...")
    
    try:
        # Check user_settings.html for Google Calendar integration
        with open('app/templates/user_settings.html', 'r') as f:
            content = f.read()
        
        required_elements = [
            'enable_google_calendar',
            'google-calendar-config',
            'toggleGoogleCalendarConfig',
            'syncGoogleCalendar'
        ]
        
        missing_elements = [elem for elem in required_elements if elem not in content]
        
        if missing_elements:
            print(f"  ❌ Missing template elements: {', '.join(missing_elements)}")
            return False
        
        print("  ✅ Template has been updated with Google Calendar integration")
        return True
        
    except Exception as e:
        print(f"  ❌ Error checking templates: {e}")
        return False

def show_next_steps():
    """Show next steps for configuration"""
    print("\n📋 Next steps to complete setup:")
    print("1. Set up Google Cloud Console project:")
    print("   - Go to https://console.cloud.google.com/")
    print("   - Create new project or select existing")
    print("   - Enable Google Calendar API")
    print("   - Configure OAuth consent screen")
    print("   - Create OAuth2 credentials")
    print("")
    print("2. Configure environment variables in .env:")
    print("   GOOGLE_CLIENT_ID=your_client_id_here")
    print("   GOOGLE_CLIENT_SECRET=your_client_secret_here")
    print("   GOOGLE_REDIRECT_URI=http://localhost:5000/google-calendar/callback")
    print("")
    print("3. Apply database migration:")
    print("   python3 -m flask db upgrade")
    print("")
    print("4. Restart Flask application")
    print("")
    print("5. Go to User Settings > API Integrations to connect Google Calendar")
    print("")
    print("📖 See GOOGLE_CALENDAR_SETUP.md for detailed instructions")

def main():
    """Run all tests"""
    print("🚀 Google Calendar Integration Test")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_environment_variables,
        test_database_fields,
        test_routes,
        test_templates
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Google Calendar integration is ready.")
        print("💡 Configure your Google Cloud Console credentials to start using it.")
    else:
        print("⚠️  Some tests failed. Please fix the issues above.")
        
    show_next_steps()

if __name__ == "__main__":
    main() 