# config.py
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
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'instance', 'physio.db')}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Calendly API configuration
    CALENDLY_API_TOKEN = os.environ.get('CALENDLY_API_TOKEN', '')

    # Stripe Webhook Signing Secret
    STRIPE_WEBHOOK_SECRET = os.environ.get('STRIPE_WEBHOOK_SECRET')

    # Stripe Publishable Key
    STRIPE_PUBLISHABLE_KEY = os.environ.get('STRIPE_PUBLISHABLE_KEY')

    # Stripe Secret Key
    STRIPE_SECRET_KEY = os.environ.get('STRIPE_SECRET_KEY')
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=30)  # Sessions last 30 days
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # CSRF configuration
    WTF_CSRF_TIME_LIMIT = 3600  # CSRF tokens valid for 1 hour (3600 seconds)
    WTF_CSRF_SSL_STRICT = False  # Allow HTTP in development