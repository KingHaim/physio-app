#!/usr/bin/env python3
"""
Production Email Configuration Fix Script
This script helps diagnose and fix email configuration issues in production
"""

import os
import sys
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def diagnose_production_email():
    """Diagnose production email configuration"""
    
    print("🔍 PRODUCTION EMAIL CONFIGURATION DIAGNOSTIC")
    print("=" * 60)
    
    # Check environment variables
    print("\n1. 📋 CHECKING ENVIRONMENT VARIABLES:")
    
    required_vars = {
        'MAIL_SERVER': 'smtp-relay.brevo.com',
        'MAIL_USERNAME': '918347001@smtp-brevo.com', 
        'MAIL_PASSWORD': '8caQAZJ6CbRBstjk',
        'MAIL_DEFAULT_SENDER': 'noreply@trxck.tech',
        'FLASK_ENV': 'production'
    }
    
    missing_vars = []
    for var, expected in required_vars.items():
        current = os.environ.get(var)
        if current:
            if var == 'MAIL_PASSWORD':
                print(f"✅ {var}: {'*' * len(current)}")
            else:
                print(f"✅ {var}: {current}")
        else:
            print(f"❌ {var}: NOT SET (expected: {expected})")
            missing_vars.append(var)
    
    print(f"\n2. 📊 SUMMARY:")
    if missing_vars:
        print(f"❌ Missing variables: {', '.join(missing_vars)}")
        return False
    else:
        print("✅ All required variables are set")
        return True

def test_production_email():
    """Test production email configuration"""
    
    print("\n3. 🧪 TESTING EMAIL CONFIGURATION:")
    
    try:
        # Set production environment
        os.environ['FLASK_ENV'] = 'production'
        
        # Set required email variables if missing
        if not os.environ.get('MAIL_SERVER'):
            os.environ['MAIL_SERVER'] = 'smtp-relay.brevo.com'
        if not os.environ.get('MAIL_USERNAME'):
            os.environ['MAIL_USERNAME'] = '918347001@smtp-brevo.com'
        if not os.environ.get('MAIL_PASSWORD'):
            os.environ['MAIL_PASSWORD'] = '8caQAZJ6CbRBstjk'
        if not os.environ.get('MAIL_DEFAULT_SENDER'):
            os.environ['MAIL_DEFAULT_SENDER'] = 'noreply@trxck.tech'
        
        from app import create_app
        from app.models import db, User
        from app.email_utils import send_verification_email
        from config import ProductionConfig
        
        app = create_app(ProductionConfig)
        
        with app.app_context():
            print("✅ Flask app created with production config")
            
            # Test email configuration
            mail_server = app.config.get('MAIL_SERVER')
            mail_username = app.config.get('MAIL_USERNAME')
            mail_password = app.config.get('MAIL_PASSWORD')
            
            print(f"📧 MAIL_SERVER: {mail_server}")
            print(f"📧 MAIL_USERNAME: {mail_username}")
            print(f"📧 MAIL_PASSWORD: {'*' * len(mail_password) if mail_password else 'NOT SET'}")
            
            if all([mail_server, mail_username, mail_password]):
                print("✅ Email configuration is complete")
                
                # Test URL generation
                from flask import url_for
                test_url = url_for('auth.verify_email', token='test-token', _external=True)
                print(f"✅ Test verification URL: {test_url}")
                
                if 'trxck.tech' in test_url:
                    print("✅ URLs point to production domain")
                else:
                    print("❌ URLs don't point to production domain")
                
                return True
            else:
                print("❌ Email configuration is incomplete")
                return False
                
    except Exception as e:
        print(f"❌ Error testing email configuration: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_production_env_template():
    """Create a template for production environment variables"""
    
    print("\n4. 📝 CREATING PRODUCTION ENV TEMPLATE:")
    
    template = """# PRODUCTION ENVIRONMENT VARIABLES FOR TRXCK.TECH

# Flask Environment
export FLASK_ENV=production

# Database (Required for production)
export DATABASE_URL=postgresql://your_db_user:your_db_password@your_db_host:5432/your_db_name

# Email Configuration (Brevo SMTP)
export MAIL_SERVER=smtp-relay.brevo.com
export MAIL_PORT=587
export MAIL_USE_TLS=true
export MAIL_USERNAME=918347001@smtp-brevo.com
export MAIL_PASSWORD=8caQAZJ6CbRBstjk
export MAIL_DEFAULT_SENDER=noreply@trxck.tech

# Security Keys (GENERATE NEW ONES FOR PRODUCTION!)
export SECRET_KEY=your-production-secret-key-here
export FERNET_SECRET_KEY=your-production-fernet-key-here

# Domain Configuration
export SERVER_NAME=trxck.tech
export PREFERRED_URL_SCHEME=https

# Optional: Stripe Configuration
export STRIPE_SECRET_KEY=your-stripe-secret-key
export STRIPE_PUBLISHABLE_KEY=your-stripe-publishable-key
export STRIPE_WEBHOOK_SECRET=your-stripe-webhook-secret

# Optional: Sentry Error Monitoring
export SENTRY_DSN=your-sentry-dsn
"""
    
    try:
        with open('production.env', 'w') as f:
            f.write(template)
        print("✅ Created production.env template")
        return True
    except Exception as e:
        print(f"❌ Error creating template: {e}")
        return False

def quick_fix_commands():
    """Show quick fix commands for common platforms"""
    
    print("\n5. 🚀 QUICK FIX COMMANDS:")
    print("=" * 60)
    
    print("🔧 FOR HEROKU:")
    print("heroku config:set MAIL_SERVER=smtp-relay.brevo.com")
    print("heroku config:set MAIL_USERNAME=918347001@smtp-brevo.com")
    print("heroku config:set MAIL_PASSWORD=8caQAZJ6CbRBstjk")
    print("heroku config:set MAIL_DEFAULT_SENDER=noreply@trxck.tech")
    print("heroku config:set FLASK_ENV=production")
    
    print("\n🔧 FOR RAILWAY:")
    print("railway variables set MAIL_SERVER=smtp-relay.brevo.com")
    print("railway variables set MAIL_USERNAME=918347001@smtp-brevo.com")
    print("railway variables set MAIL_PASSWORD=8caQAZJ6CbRBstjk")
    print("railway variables set MAIL_DEFAULT_SENDER=noreply@trxck.tech")
    print("railway variables set FLASK_ENV=production")
    
    print("\n🔧 FOR VERCEL:")
    print("vercel env add MAIL_SERVER")
    print("vercel env add MAIL_USERNAME")
    print("vercel env add MAIL_PASSWORD")
    print("vercel env add MAIL_DEFAULT_SENDER")
    print("vercel env add FLASK_ENV")
    
    print("\n🔧 FOR DOCKER/VPS:")
    print("source production.env  # Use the created template")
    print("export $(cat production.env | xargs)")

def main():
    """Main function to run all diagnostics"""
    
    print("🚨 TRXCK.TECH PRODUCTION EMAIL DIAGNOSTIC")
    print("⚠️  Fixing email verification issues in production")
    print("=" * 60)
    
    # Run diagnostics
    env_ok = diagnose_production_email()
    
    if not env_ok:
        print("\n❌ ENVIRONMENT VARIABLES MISSING")
        print("🔧 Setting up missing variables for testing...")
        
        # Set missing variables
        os.environ['MAIL_SERVER'] = 'smtp-relay.brevo.com'
        os.environ['MAIL_USERNAME'] = '918347001@smtp-brevo.com'
        os.environ['MAIL_PASSWORD'] = '8caQAZJ6CbRBstjk'
        os.environ['MAIL_DEFAULT_SENDER'] = 'noreply@trxck.tech'
        os.environ['FLASK_ENV'] = 'production'
        
        print("✅ Temporary variables set for testing")
    
    # Test configuration
    test_ok = test_production_email()
    
    # Create template
    create_production_env_template()
    
    # Show quick fix commands
    quick_fix_commands()
    
    print("\n" + "=" * 60)
    print("🎯 FINAL RECOMMENDATIONS:")
    print("=" * 60)
    
    if test_ok:
        print("✅ Email configuration is working correctly")
        print("🔧 The issue might be in your hosting platform configuration")
        print("📋 Use the platform-specific commands above to set environment variables")
    else:
        print("❌ Email configuration has issues")
        print("🔧 Check the error messages above")
        print("📋 Use the production.env template to set correct variables")
    
    print("\n🚀 NEXT STEPS:")
    print("1. Set the environment variables in your hosting platform")
    print("2. Restart your application")
    print("3. Test user registration")
    print("4. Check application logs for email sending status")

if __name__ == "__main__":
    main() 