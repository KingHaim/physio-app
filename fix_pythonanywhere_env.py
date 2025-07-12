#!/usr/bin/env python3
"""
Fix PythonAnywhere environment variable loading
"""

import os
import sys
from pathlib import Path

def fix_env_loading():
    """Fix environment variable loading for PythonAnywhere"""
    
    print("🔧 FIXING PYTHONANYWHERE ENVIRONMENT VARIABLES")
    print("=" * 60)
    
    # Get the project root directory
    project_root = Path(__file__).parent
    env_file = project_root / '.env'
    
    print(f"📁 Project root: {project_root}")
    print(f"📄 .env file path: {env_file}")
    
    if not env_file.exists():
        print("❌ .env file not found!")
        return False
    
    # Read .env file
    env_vars = {}
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key] = value
    
    print(f"✅ Found {len(env_vars)} environment variables")
    
    # Set environment variables
    for key, value in env_vars.items():
        os.environ[key] = value
        if 'PASSWORD' in key or 'SECRET' in key:
            print(f"✅ Set {key}: {'*' * 10}")
        else:
            print(f"✅ Set {key}: {value}")
    
    return True

def create_pythonanywhere_wsgi():
    """Create WSGI file for PythonAnywhere that loads environment variables"""
    
    wsgi_content = '''#!/usr/bin/env python3
"""
WSGI file for PythonAnywhere that properly loads environment variables
"""

import sys
import os
from pathlib import Path

# Add your project directory to the sys.path
project_home = '/home/yourusername/trxck-tech'  # CHANGE THIS TO YOUR ACTUAL PATH
if project_home not in sys.path:
    sys.path = [project_home] + sys.path

# Load environment variables from .env file
def load_env_file():
    env_file = Path(project_home) / '.env'
    if env_file.exists():
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key] = value

# Load environment variables before importing the app
load_env_file()

# Now import and create the application
from app import create_app
application = create_app()

if __name__ == "__main__":
    application.run()
'''
    
    try:
        with open('pythonanywhere_wsgi.py', 'w') as f:
            f.write(wsgi_content)
        print("✅ Created pythonanywhere_wsgi.py")
        return True
    except Exception as e:
        print(f"❌ Error creating WSGI file: {e}")
        return False

def create_environment_setup():
    """Create a script to set environment variables in PythonAnywhere console"""
    
    setup_script = '''#!/bin/bash
# Script to set environment variables in PythonAnywhere
# Run this in the PythonAnywhere Bash console

echo "🔧 Setting up environment variables for TRXCK.TECH"

# Flask Environment
export FLASK_ENV=production

# Email Configuration (Brevo SMTP)
export MAIL_SERVER=smtp-relay.brevo.com
export MAIL_PORT=587
export MAIL_USE_TLS=true
export MAIL_USERNAME=YOUR_BREVO_USERNAME
export MAIL_PASSWORD=YOUR_BREVO_PASSWORD
export MAIL_DEFAULT_SENDER=noreply@trxck.tech

# Server Configuration
export SERVER_NAME=trxck.tech
export PREFERRED_URL_SCHEME=https

# Security Keys (REPLACE WITH YOUR ACTUAL VALUES)
export SECRET_KEY=YOUR_SECRET_KEY_HERE
export FERNET_SECRET_KEY=YOUR_FERNET_KEY_HERE

# Database (REPLACE WITH YOUR ACTUAL DATABASE URL)
export DATABASE_URL=YOUR_DATABASE_URL_HERE

# Deepseek API (REPLACE WITH YOUR ACTUAL API KEY)
export DEEPSEEK_API_KEY=YOUR_DEEPSEEK_API_KEY
export DEEPSEEK_API_ENDPOINT=https://api.deepseek.com/v1/chat/completions

# Stripe Configuration (REPLACE WITH YOUR ACTUAL STRIPE KEYS)
export STRIPE_WEBHOOK_SECRET=YOUR_STRIPE_WEBHOOK_SECRET
export STRIPE_PUBLISHABLE_KEY=YOUR_STRIPE_PUBLISHABLE_KEY
export STRIPE_SECRET_KEY=YOUR_STRIPE_SECRET_KEY

echo "✅ Environment variables set successfully!"
echo "🚀 You can now restart your web app in PythonAnywhere dashboard"
'''
    
    try:
        with open('setup_pythonanywhere_env.sh', 'w') as f:
            f.write(setup_script)
        os.chmod('setup_pythonanywhere_env.sh', 0o755)
        print("✅ Created setup_pythonanywhere_env.sh")
        return True
    except Exception as e:
        print(f"❌ Error creating setup script: {e}")
        return False

def test_after_fix():
    """Test if the fix worked"""
    
    print("\n🧪 TESTING AFTER FIX")
    print("=" * 60)
    
    # Test critical variables
    critical_vars = ['FLASK_ENV', 'MAIL_SERVER', 'MAIL_USERNAME', 'MAIL_PASSWORD', 'DATABASE_URL']
    
    all_ok = True
    for var in critical_vars:
        value = os.environ.get(var)
        if value:
            if 'PASSWORD' in var or 'SECRET' in var:
                print(f"✅ {var}: {'*' * 10}")
            else:
                print(f"✅ {var}: {value}")
        else:
            print(f"❌ {var}: NOT SET")
            all_ok = False
    
    if all_ok:
        print("\n✅ All critical variables are now set!")
        
        # Test Flask app creation
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from app import create_app
            from config import ProductionConfig
            
            app = create_app(ProductionConfig)
            with app.app_context():
                from flask import url_for
                test_url = url_for('auth.verify_email', token='test-token', _external=True)
                print(f"🔗 Test URL: {test_url}")
                
                if 'trxck.tech' in test_url:
                    print("✅ URLs point to production domain")
                    return True
                    
        except Exception as e:
            print(f"❌ Flask app test failed: {e}")
    
    return all_ok

def main():
    """Main function"""
    
    print("🚨 PYTHONANYWHERE ENVIRONMENT VARIABLE FIX")
    print("🔧 Solving email verification issues")
    print("=" * 60)
    
    # Step 1: Fix environment loading
    if fix_env_loading():
        print("\n✅ Environment variables loaded from .env file")
    else:
        print("\n❌ Failed to load .env file")
    
    # Step 2: Test if fix worked
    test_after_fix()
    
    # Step 3: Create helper files
    create_pythonanywhere_wsgi()
    create_environment_setup()
    
    print("\n" + "=" * 60)
    print("🎯 PYTHONANYWHERE SETUP INSTRUCTIONS")
    print("=" * 60)
    
    print("""
📋 OPTION 1: Manual Environment Variables (RECOMMENDED)
1. Go to PythonAnywhere Web tab
2. Scroll to "Environment variables" section
3. Add each variable from your .env file manually
4. Reload your web app

📋 OPTION 2: Use WSGI File
1. Replace your WSGI file content with pythonanywhere_wsgi.py
2. Update the project_home path in the WSGI file
3. Reload your web app

📋 OPTION 3: Console Setup
1. Open PythonAnywhere Bash console
2. Run: source setup_pythonanywhere_env.sh
3. Reload your web app

🎯 AFTER SETUP:
1. Check error logs in PythonAnywhere
2. Test user registration
3. Check if emails are being sent
""")

if __name__ == "__main__":
    main() 