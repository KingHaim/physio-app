#!/usr/bin/env python3
"""
Temporary fix script to modify production configuration for email verification testing
"""

import os
import sys
import shutil
from datetime import datetime

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def backup_config():
    """Create backup of config.py"""
    try:
        shutil.copy('config.py', 'config.py.backup')
        print("✅ Created backup: config.py.backup")
        return True
    except Exception as e:
        print(f"❌ Error creating backup: {e}")
        return False

def restore_config():
    """Restore original config.py"""
    try:
        if os.path.exists('config.py.backup'):
            shutil.copy('config.py.backup', 'config.py')
            print("✅ Restored original config.py")
            return True
        else:
            print("❌ No backup found")
            return False
    except Exception as e:
        print(f"❌ Error restoring config: {e}")
        return False

def modify_config_for_testing(domain='localhost:5000'):
    """Modify config.py to use a different domain for testing"""
    
    config_content = '''# config.py
import os
from dotenv import load_dotenv
from datetime import timedelta

# Get the absolute path to the directory containing this file
basedir = os.path.abspath(os.path.dirname(__file__))

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY environment variable is required")
    
    # Encryption key for sensitive data
    FERNET_SECRET_KEY = os.getenv("FERNET_SECRET_KEY")
    if not FERNET_SECRET_KEY:
        raise RuntimeError("FERNET_SECRET_KEY environment variable is required for data encryption")
    
    # Use absolute path for database
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///" + os.path.join(basedir, 'instance', 'physio-2.db'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Database connection pool settings
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'max_overflow': 20
    }
    
    # Server configuration for email URL generation (overridden in subclasses)
    SERVER_NAME = 'localhost:5000'  # Default for development
    PREFERRED_URL_SCHEME = 'http'
    
    # Email configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'noreply@trxcker.com'
    MAIL_SUBJECT_PREFIX = '[TRXCKER] '
    
    # ... rest of configuration ...
    # (keeping all other settings the same)
    
    # Calendly API configuration
    CALENDLY_API_TOKEN = os.environ.get('CALENDLY_API_TOKEN', '')

    # Stripe Webhook Signing Secret
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

    # Stripe Publishable Key
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')

    # Stripe Secret Key
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    
    # DeepSeek AI API Key for clinical suggestions
    DEEPSEEK_API_KEY = os.environ.get('DEEPSEEK_API_KEY')
    
    # Sentry DSN for error monitoring
    SENTRY_DSN = os.environ.get('SENTRY_DSN')
    
    # Google OAuth configuration
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET')
    
    # OAuth configuration
    OAUTH_CREDENTIALS = {
        'google': {
            'id': os.environ.get('GOOGLE_CLIENT_ID'),
            'secret': os.environ.get('GOOGLE_CLIENT_SECRET')
        }
    }
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # CSRF configuration
    WTF_CSRF_TIME_LIMIT = 3600
    WTF_CSRF_SSL_STRICT = False

    # File upload configuration
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(basedir, 'uploads')
    
    # Logging configuration
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Security headers
    SECURITY_HEADERS = {
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'SAMEORIGIN',
        'X-XSS-Protection': '1; mode=block',
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains'
    }

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = True
    
    # Override server name for local development
    SERVER_NAME = 'localhost:5000'
    PREFERRED_URL_SCHEME = 'http'

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_ECHO = False
    
    # TEMPORARILY MODIFIED FOR TESTING - Use localhost instead of trxck.tech
    SERVER_NAME = '''' + domain + ''''
    PREFERRED_URL_SCHEME = 'http'  # Changed from https to http for testing
    
    # Production-specific settings - only check at runtime, not import time
    def __init__(self):
        super().__init__()
        # Comment out DATABASE_URL requirement for testing
        # if not os.getenv("DATABASE_URL"):
        #     raise RuntimeError("DATABASE_URL environment variable is required for production")

class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    
    # Use test database URL if provided, otherwise use SQLite
    TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
    if TEST_DATABASE_URL:
        SQLALCHEMY_DATABASE_URI = TEST_DATABASE_URL
    else:
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(basedir, 'instance', 'test_physio.db')
    
    # Optimize for testing - reduce connection pool size
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 5,
        'pool_recycle': 300,
        'pool_pre_ping': True,
        'max_overflow': 10
    }
    
    # Disable encryption for testing to avoid length issues
    DISABLE_ENCRYPTION = True
    
    # Use simpler session configuration for testing
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestConfig,
    'default': DevelopmentConfig
}
'''
    
    try:
        with open('config.py', 'w') as f:
            f.write(config_content)
        print(f"✅ Modified config.py to use domain: {domain}")
        return True
    except Exception as e:
        print(f"❌ Error modifying config: {e}")
        return False

def main():
    """Main function"""
    print("🔧 TEMPORARY EMAIL VERIFICATION CONFIG FIX")
    print("=" * 60)
    
    if len(sys.argv) > 1:
        action = sys.argv[1]
    else:
        print("Usage:")
        print("  python temp_fix_config.py backup     - Create backup of config.py")
        print("  python temp_fix_config.py modify     - Modify config for localhost testing")
        print("  python temp_fix_config.py restore    - Restore original config.py")
        print("  python temp_fix_config.py modify [domain] - Modify config for specific domain")
        return
    
    if action == 'backup':
        if backup_config():
            print("🎉 Backup created successfully")
        else:
            print("❌ Failed to create backup")
    
    elif action == 'modify':
        domain = sys.argv[2] if len(sys.argv) > 2 else 'localhost:5000'
        print(f"📝 Modifying config to use domain: {domain}")
        
        # Create backup first
        if backup_config():
            if modify_config_for_testing(domain):
                print("🎉 Config modified successfully")
                print(f"📧 Email verification URLs will now use: {domain}")
                print("⚠️  Remember to run 'python temp_fix_config.py restore' when done testing")
            else:
                print("❌ Failed to modify config")
        else:
            print("❌ Failed to create backup, aborting")
    
    elif action == 'restore':
        if restore_config():
            print("🎉 Config restored successfully")
        else:
            print("❌ Failed to restore config")
    
    else:
        print(f"❌ Unknown action: {action}")

if __name__ == "__main__":
    main() 