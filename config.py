# config.py
import os
from dotenv import load_dotenv
from datetime import timedelta

# Get the absolute path to the directory containing this file
basedir = os.path.abspath(os.path.dirname(__file__))

# Public defaults first (.flaskenv), then .env. Neither overrides a real env var.
load_dotenv(os.path.join(basedir, '.flaskenv'))
load_dotenv()

VALID_ENVIRONMENTS = frozenset({'development', 'production', 'testing'})


def resolve_config_name():
    """Return development|production|testing. Unset defaults to production.

    FLASK_ENV is preferred; APP_ENV is an optional alias. Values are stripped
    and lowercased. Unknown values raise so a typo cannot silently use insecure
    development settings.
    """
    raw = os.environ.get('FLASK_ENV')
    if raw is None or str(raw).strip() == '':
        raw = os.environ.get('APP_ENV')
    if raw is None or str(raw).strip() == '':
        return 'production'
    name = str(raw).strip().lower()
    if name not in VALID_ENVIRONMENTS:
        raise RuntimeError(
            f"Unknown environment {name!r}. "
            "Set FLASK_ENV or APP_ENV to 'development', 'production', or 'testing'."
        )
    return name

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY environment variable is required")
    
    # Encryption control: disabled by default
    DISABLE_ENCRYPTION = os.getenv("DISABLE_ENCRYPTION", "true").lower() in ["true", "1", "yes", "on"]
    
    # Encryption key for sensitive data (optional when DISABLE_ENCRYPTION is true)
    FERNET_SECRET_KEY = os.getenv("FERNET_SECRET_KEY")
    
    # Use absolute path for database - optimized SQLite
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///" + os.path.join(basedir, 'instance', 'physio-2.db'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Database connection pool settings - optimized for SQLite
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 1,            # SQLite is single-threaded
        'pool_recycle': -1,        # No connection recycling needed for SQLite
        'pool_pre_ping': False,    # Not needed for SQLite file access
        'max_overflow': 0,         # No overflow for SQLite
        'pool_timeout': 30,        # Keep timeout
        'echo': False,             # Disable SQL logging in production
    }
    
    # Server configuration for email URL generation (overridden in subclasses)
    # SERVER_NAME = 'localhost:5000'  # Commented out to allow flexible host access in development
    PREFERRED_URL_SCHEME = 'http'
    
    # Email configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER') or 'smtp.gmail.com'
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 587)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER') or 'noreply@trxcker.com'
    MAIL_SUBJECT_PREFIX = '[TRXCKER] '
    
    # Calendly API configuration
    CALENDLY_API_TOKEN = os.environ.get('CALENDLY_API_TOKEN', '')

    # STRIPE PAYMENTS TEMPORARILY DISABLED FOR SYSTEM UPGRADES
    # Stripe Webhook Signing Secret
    STRIPE_WEBHOOK_SECRET = None  # DISABLED: os.environ.get('STRIPE_WEBHOOK_SECRET')

    # Stripe Publishable Key
    STRIPE_PUBLISHABLE_KEY = None  # DISABLED: os.environ.get('STRIPE_PUBLISHABLE_KEY')

    # Stripe Secret Key
    STRIPE_SECRET_KEY = None  # DISABLED: os.environ.get('STRIPE_SECRET_KEY')
    
    # Payment processing status flag
    PAYMENTS_ENABLED = False
    
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
    
    # Session configuration (HTTP-safe defaults for local development)
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = False
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    SESSION_PROTECTION = 'basic'
    
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
    
    # Remove SERVER_NAME restriction for development to work with both localhost and 127.0.0.1
    # SERVER_NAME = 'localhost:5000'  # Commented out to allow flexible host access
    PREFERRED_URL_SCHEME = 'http'
    # Keep cookies sendable over local HTTP
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_ECHO = False
    
    # Use production domain from environment or default
    SERVER_NAME = os.environ.get('SERVER_NAME') or 'trxck.tech'
    PREFERRED_URL_SCHEME = 'https'

    # HTTPS-only cookies. SameSite=Lax (not Strict) so top-level GET
    # returns from Google OAuth, Calendly, and Stripe still carry the session.
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=12)
    # 'basic' (not 'strong'): 'strong' logs users out on any IP change,
    # including X-Forwarded-For that a client can spoof, and clears remember-me.
    SESSION_PROTECTION = 'basic'
    WTF_CSRF_SSL_STRICT = True
    
    # Production-specific settings - only check at runtime, not import time
    def __init__(self):
        super().__init__()
        if not os.getenv("DATABASE_URL"):
            raise RuntimeError("DATABASE_URL environment variable is required for production")

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
    
    # Use simpler session configuration for testing (HTTP, no Secure flag)
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_SECURE = False
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = 'Lax'
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False

# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestConfig,
    'default': ProductionConfig,
}