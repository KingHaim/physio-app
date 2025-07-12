#!/usr/bin/env python3
"""
Diagnostic script specifically for PythonAnywhere deployment
"""

import os
import sys
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def check_env_variables():
    """Check if environment variables are loaded correctly"""
    
    print("🔍 CHECKING ENVIRONMENT VARIABLES IN PYTHONANYWHERE")
    print("=" * 60)
    
    # Expected variables from .env file
    expected_vars = {
        'FLASK_ENV': 'production',
        'MAIL_SERVER': 'smtp-relay.brevo.com',
        'MAIL_PORT': '587',
        'MAIL_USE_TLS': 'true',
        'MAIL_USERNAME': '918347001@smtp-brevo.com',
        'MAIL_PASSWORD': '8caQAZJ6CbRBstjk',
        'MAIL_DEFAULT_SENDER': 'noreply@trxck.tech',
        'SERVER_NAME': 'trxck.tech',
        'PREFERRED_URL_SCHEME': 'https',
        'SECRET_KEY': 'cc731212552fcd66f4f2b62111b7a1a1b495417a3395512c',
        'DATABASE_URL': 'postgresql://postgres.cyjtlvrektrkxnuebvuq:***@aws-0-eu-central-1.pooler.supabase.com:5432/postgres'
    }
    
    missing_vars = []
    incorrect_vars = []
    
    for var, expected in expected_vars.items():
        current = os.environ.get(var)
        if current:
            if var == 'MAIL_PASSWORD' or var == 'SECRET_KEY' or 'DATABASE_URL' in var:
                print(f"✅ {var}: {'*' * 10} (set)")
            else:
                print(f"✅ {var}: {current}")
                if current != expected:
                    incorrect_vars.append(f"{var} (expected: {expected}, got: {current})")
        else:
            print(f"❌ {var}: NOT SET")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n❌ MISSING VARIABLES: {', '.join(missing_vars)}")
    if incorrect_vars:
        print(f"\n⚠️  INCORRECT VARIABLES: {', '.join(incorrect_vars)}")
    
    if not missing_vars and not incorrect_vars:
        print("\n✅ ALL ENVIRONMENT VARIABLES ARE CORRECTLY SET")
        return True
    else:
        return False

def test_dotenv_loading():
    """Test if .env file is being loaded correctly"""
    
    print("\n🔍 TESTING .ENV FILE LOADING")
    print("=" * 60)
    
    try:
        from dotenv import load_dotenv
        
        # Try to load .env file
        result = load_dotenv()
        print(f"✅ load_dotenv() result: {result}")
        
        # Check if .env file exists
        if os.path.exists('.env'):
            print("✅ .env file exists")
            
            # Read .env file content
            with open('.env', 'r') as f:
                content = f.read()
                lines = content.strip().split('\n')
                print(f"✅ .env file has {len(lines)} lines")
                
                # Check for key variables
                if 'MAIL_SERVER' in content:
                    print("✅ MAIL_SERVER found in .env")
                if 'FLASK_ENV' in content:
                    print("✅ FLASK_ENV found in .env")
                    
        else:
            print("❌ .env file not found")
            return False
            
    except ImportError:
        print("❌ python-dotenv not installed")
        return False
    except Exception as e:
        print(f"❌ Error loading .env: {e}")
        return False
    
    return True

def test_smtp_connection():
    """Test SMTP connection directly"""
    
    print("\n🔍 TESTING SMTP CONNECTION")
    print("=" * 60)
    
    mail_server = os.environ.get('MAIL_SERVER')
    mail_port = int(os.environ.get('MAIL_PORT', 587))
    mail_username = os.environ.get('MAIL_USERNAME')
    mail_password = os.environ.get('MAIL_PASSWORD')
    mail_use_tls = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    
    if not all([mail_server, mail_username, mail_password]):
        print("❌ Email configuration incomplete")
        return False
    
    try:
        print(f"📧 Connecting to {mail_server}:{mail_port}")
        
        # Create SMTP connection
        server = smtplib.SMTP(mail_server, mail_port)
        server.set_debuglevel(1)  # Enable debug output
        
        if mail_use_tls:
            print("🔒 Starting TLS...")
            server.starttls()
        
        print("🔑 Authenticating...")
        server.login(mail_username, mail_password)
        
        print("✅ SMTP connection successful!")
        
        # Test sending a simple email
        print("\n📤 Testing email sending...")
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Test Email from PythonAnywhere'
        msg['From'] = os.environ.get('MAIL_DEFAULT_SENDER', mail_username)
        msg['To'] = mail_username  # Send to self
        
        text_body = "This is a test email from PythonAnywhere SMTP configuration."
        html_body = "<h1>Test Email</h1><p>This is a test email from PythonAnywhere SMTP configuration.</p>"
        
        msg.attach(MIMEText(text_body, 'plain'))
        msg.attach(MIMEText(html_body, 'html'))
        
        server.sendmail(mail_username, [mail_username], msg.as_string())
        server.quit()
        
        print("✅ Test email sent successfully!")
        return True
        
    except Exception as e:
        print(f"❌ SMTP connection failed: {e}")
        return False

def test_flask_app_creation():
    """Test Flask app creation with production config"""
    
    print("\n🔍 TESTING FLASK APP CREATION")
    print("=" * 60)
    
    try:
        # Add project root to path
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        from app import create_app
        from config import ProductionConfig
        
        app = create_app(ProductionConfig)
        
        with app.app_context():
            print("✅ Flask app created successfully")
            
            # Check configuration
            print(f"📧 MAIL_SERVER: {app.config.get('MAIL_SERVER')}")
            print(f"📧 MAIL_USERNAME: {app.config.get('MAIL_USERNAME')}")
            print(f"📧 MAIL_PASSWORD: {'*' * 10 if app.config.get('MAIL_PASSWORD') else 'NOT SET'}")
            print(f"🌐 SERVER_NAME: {app.config.get('SERVER_NAME')}")
            print(f"🔒 PREFERRED_URL_SCHEME: {app.config.get('PREFERRED_URL_SCHEME')}")
            
            # Test URL generation
            from flask import url_for
            test_url = url_for('auth.verify_email', token='test-token', _external=True)
            print(f"🔗 Test verification URL: {test_url}")
            
            return True
            
    except Exception as e:
        print(f"❌ Flask app creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_email_utils():
    """Test email utilities directly"""
    
    print("\n🔍 TESTING EMAIL UTILITIES")
    print("=" * 60)
    
    try:
        # Add project root to path
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
        from app import create_app
        from app.email_utils import send_email
        from config import ProductionConfig
        
        app = create_app(ProductionConfig)
        
        with app.app_context():
            print("✅ Email utilities imported successfully")
            
            # Test email sending
            result = send_email(
                to_email="test@example.com",
                subject="Test Email Verification",
                html_body="<h1>Test</h1><p>This is a test email.</p>",
                text_body="This is a test email."
            )
            
            print(f"📧 Email send result: {result}")
            
            return result
            
    except Exception as e:
        print(f"❌ Email utilities test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def pythonanywhere_specific_checks():
    """PythonAnywhere specific checks"""
    
    print("\n🔍 PYTHONANYWHERE SPECIFIC CHECKS")
    print("=" * 60)
    
    # Check Python version
    print(f"🐍 Python version: {sys.version}")
    
    # Check working directory
    print(f"📁 Working directory: {os.getcwd()}")
    
    # Check if running on PythonAnywhere
    hostname = os.environ.get('HOSTNAME', 'unknown')
    print(f"🖥️  Hostname: {hostname}")
    
    if 'pythonanywhere' in hostname.lower():
        print("✅ Running on PythonAnywhere")
    else:
        print("⚠️  Not detected as PythonAnywhere environment")
    
    # Check file permissions
    try:
        test_file = 'test_write_permissions.txt'
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        print("✅ File write permissions OK")
    except Exception as e:
        print(f"❌ File write permissions issue: {e}")
    
    # Check if .env file is readable
    try:
        with open('.env', 'r') as f:
            content = f.read()
        print("✅ .env file is readable")
    except Exception as e:
        print(f"❌ .env file read error: {e}")

def main():
    """Main diagnostic function"""
    
    print("🚨 PYTHONANYWHERE EMAIL DIAGNOSTIC")
    print("🔧 Diagnosing email verification issues")
    print("=" * 60)
    
    # Run all checks
    checks = [
        ("Environment Variables", check_env_variables),
        (".env File Loading", test_dotenv_loading),
        ("SMTP Connection", test_smtp_connection),
        ("Flask App Creation", test_flask_app_creation),
        ("Email Utilities", test_email_utils),
        ("PythonAnywhere Specific", pythonanywhere_specific_checks)
    ]
    
    results = {}
    for name, check_func in checks:
        print(f"\n{'='*60}")
        print(f"🔍 {name}")
        print(f"{'='*60}")
        try:
            results[name] = check_func()
        except Exception as e:
            print(f"❌ {name} failed with error: {e}")
            results[name] = False
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 DIAGNOSTIC SUMMARY")
    print(f"{'='*60}")
    
    passed = sum(1 for result in results.values() if result)
    total = len(results)
    
    for name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {name}")
    
    print(f"\n🎯 OVERALL: {passed}/{total} checks passed")
    
    if passed == total:
        print("✅ All checks passed - email should be working!")
    else:
        print("❌ Some checks failed - see details above")
        
    print("\n🔧 NEXT STEPS:")
    print("1. If SMTP connection fails, check PythonAnywhere email restrictions")
    print("2. If .env loading fails, ensure the file is in the correct location")
    print("3. Check PythonAnywhere error logs for detailed error messages")
    print("4. Consider using PythonAnywhere's email service if external SMTP is blocked")

if __name__ == "__main__":
    main() 