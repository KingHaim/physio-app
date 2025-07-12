#!/usr/bin/env python3
"""
Comprehensive troubleshooting script for email verification 404 issue
"""

import os
import sys
import subprocess
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_step(step_name, func):
    """Helper to run a step and report results"""
    print(f"\n{'='*60}")
    print(f"🔍 STEP: {step_name}")
    print(f"{'='*60}")
    try:
        return func()
    except Exception as e:
        print(f"❌ Error in {step_name}: {e}")
        import traceback
        traceback.print_exc()
        return False

def step_1_check_routes():
    """Check if routes are registered correctly"""
    print("Checking if Flask routes are registered...")
    
    # Set environment to development
    os.environ['FLASK_ENV'] = 'development'
    
    from app import create_app
    app = create_app()
    
    with app.app_context():
        # Find auth routes
        auth_routes = []
        for rule in app.url_map.iter_rules():
            if rule.endpoint.startswith('auth.'):
                auth_routes.append((rule.endpoint, rule.rule))
        
        print(f"✅ Found {len(auth_routes)} auth routes:")
        for endpoint, rule in auth_routes:
            print(f"  - {endpoint}: {rule}")
            
        # Specifically check verify_email
        verify_route = next((r for r in auth_routes if 'verify_email' in r[0]), None)
        if verify_route:
            print(f"✅ verify_email route found: {verify_route[1]}")
            return True
        else:
            print("❌ verify_email route NOT found!")
            return False

def step_2_check_blueprints():
    """Check if blueprints are registered correctly"""
    print("Checking if blueprints are registered...")
    
    from app import create_app
    app = create_app()
    
    with app.app_context():
        blueprints = list(app.blueprints.keys())
        print(f"✅ Found {len(blueprints)} blueprints:")
        for name in blueprints:
            blueprint = app.blueprints[name]
            print(f"  - {name}: {blueprint.url_prefix or '/'}")
            
        if 'auth' in blueprints:
            print("✅ auth blueprint is registered")
            return True
        else:
            print("❌ auth blueprint is NOT registered")
            return False

def step_3_test_url_generation():
    """Test URL generation"""
    print("Testing URL generation...")
    
    from app import create_app
    app = create_app()
    
    with app.app_context():
        from flask import url_for
        
        try:
            login_url = url_for('auth.login')
            print(f"✅ Login URL: {login_url}")
        except Exception as e:
            print(f"❌ Login URL generation failed: {e}")
            return False
            
        try:
            verify_url = url_for('auth.verify_email', token='test-token')
            print(f"✅ Verify URL: {verify_url}")
            return True
        except Exception as e:
            print(f"❌ Verify URL generation failed: {e}")
            return False

def step_4_test_local_access():
    """Test local route access"""
    print("Testing local route access...")
    
    from app import create_app
    app = create_app()
    
    with app.test_client() as client:
        # Test login route
        response = client.get('/auth/login')
        print(f"✅ Login route status: {response.status_code}")
        
        # Test verify route with dummy token
        response = client.get('/auth/verify-email/dummy-token')
        print(f"✅ Verify route status: {response.status_code}")
        
        if response.status_code == 404:
            print("❌ Verify route returns 404 even locally!")
            return False
        else:
            print("✅ Verify route is accessible locally")
            return True

def step_5_check_production_config():
    """Check production configuration"""
    print("Checking production configuration...")
    
    from app import create_app
    from config import ProductionConfig
    
    # Check if production config sets correct domain
    try:
        config = ProductionConfig()
        print(f"✅ Production SERVER_NAME: {config.SERVER_NAME}")
        print(f"✅ Production PREFERRED_URL_SCHEME: {config.PREFERRED_URL_SCHEME}")
        
        # Test URL generation with production config
        os.environ['FLASK_ENV'] = 'production'
        app = create_app(ProductionConfig)
        
        with app.app_context():
            from flask import url_for
            verify_url = url_for('auth.verify_email', token='test-token', _external=True)
            print(f"✅ Production verify URL: {verify_url}")
            
            if 'trxck.tech' in verify_url:
                print("✅ Production URLs point to trxck.tech")
                return True
            else:
                print("❌ Production URLs don't point to trxck.tech")
                return False
                
    except Exception as e:
        print(f"❌ Production config error: {e}")
        return False

def step_6_suggest_solutions():
    """Suggest solutions based on findings"""
    print("Suggesting solutions...")
    
    solutions = [
        "🔧 IMMEDIATE FIXES:",
        "",
        "1. FOR LOCAL TESTING:",
        "   - Run: python debug_routes.py",
        "   - Run: python test_email_verification_locally.py",
        "   - Start local server: python app.py",
        "   - Test locally: http://localhost:5000/auth/verify-email/test-token",
        "",
        "2. FOR PRODUCTION ISSUE:",
        "   - Check if trxck.tech domain is configured properly",
        "   - Verify SSL certificate is installed",
        "   - Check if Flask app is running on trxck.tech",
        "   - Check web server (nginx/apache) configuration",
        "",
        "3. QUICK WORKAROUND:",
        "   - Temporarily change SERVER_NAME in production config",
        "   - Use your actual server IP or domain",
        "   - Test with a development environment first",
        "",
        "4. DEBUGGING STEPS:",
        "   - Check server logs for errors",
        "   - Verify database connection",
        "   - Test direct route access: curl https://trxck.tech/auth/verify-email/test",
        "",
        "5. ALTERNATIVE TESTING:",
        "   - Use ngrok for local testing with external URLs",
        "   - Test with a different domain temporarily",
    ]
    
    for solution in solutions:
        print(solution)
    
    return True

def main():
    """Main troubleshooting function"""
    print("🚀 EMAIL VERIFICATION 404 TROUBLESHOOTING")
    print("=" * 60)
    
    # Run all steps
    steps = [
        ("Check Routes Registration", step_1_check_routes),
        ("Check Blueprints Registration", step_2_check_blueprints),
        ("Test URL Generation", step_3_test_url_generation),
        ("Test Local Route Access", step_4_test_local_access),
        ("Check Production Config", step_5_check_production_config),
        ("Suggest Solutions", step_6_suggest_solutions),
    ]
    
    results = []
    for step_name, step_func in steps:
        result = check_step(step_name, step_func)
        results.append((step_name, result))
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 TROUBLESHOOTING SUMMARY")
    print(f"{'='*60}")
    
    for step_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {step_name}")
    
    print(f"\n{'='*60}")
    print("🎯 NEXT STEPS")
    print(f"{'='*60}")
    
    failed_steps = [name for name, result in results if not result]
    if failed_steps:
        print("❌ Issues found in:")
        for step in failed_steps:
            print(f"  - {step}")
        print("\n🔧 Focus on fixing these issues first!")
    else:
        print("✅ All checks passed!")
        print("🔍 The issue is likely in production deployment/configuration")
        print("🌐 Check if trxck.tech domain is properly configured")

if __name__ == "__main__":
    main() 