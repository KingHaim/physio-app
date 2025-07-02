# app/__init__.py
import os
from flask import Flask, request, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config
import markdown
from markupsafe import Markup
from flask_login import LoginManager
from flask_babel import Babel, get_locale
from flask_wtf.csrf import CSRFProtect
import logging
import stripe # Import stripe
from logging.handlers import RotatingFileHandler

# Sentry SDK for error monitoring
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

db = SQLAlchemy()

# Initialize login manager
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'
login_manager.session_protection = 'basic'

# Initialize CSRF protection
csrf = CSRFProtect()

# Initialize Babel for translations
babel = Babel()

# Import models here *before* Migrate is instantiated
from app import models 

migrate = Migrate()

def setup_logging(app):
    """Configure advanced logging with file rotation and request logging"""
    # Create logs directory if it doesn't exist
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Configure file handler with rotation
    file_handler = RotatingFileHandler(
        'logs/physiotracker.log', 
        maxBytes=10240, 
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] in %(module)s: %(message)s'
    ))
    file_handler.setLevel(logging.INFO)

    # Add file handler to app logger
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('PhysioTracker startup log initialized.')

    # Request logging middleware
    @app.before_request
    def log_request_info():
        """Log all incoming requests for monitoring"""
        # Skip logging for static files and health checks
        if request.path.startswith('/static/') or request.path == '/health':
            return
            
        # Get user info if authenticated
        user_info = "anonymous"
        from flask_login import current_user
        if current_user.is_authenticated:
            user_info = f"user_id:{current_user.id}"
        
        # Log request details
        app.logger.info(
            f"Request: {request.remote_addr} - {user_info} - "
            f"{request.method} {request.path} - "
            f"User-Agent: {request.headers.get('User-Agent', 'Unknown')}"
        )
        
        # Log sensitive endpoints with extra detail
        sensitive_endpoints = [
            '/auth/login', '/auth/register', '/auth/reset_password',
            '/api/', '/webhooks/', '/admin/'
        ]
        
        if any(endpoint in request.path for endpoint in sensitive_endpoints):
            app.logger.warning(
                f"SENSITIVE ACCESS: {request.remote_addr} - {user_info} - "
                f"{request.method} {request.path}"
            )

def setup_sentry(app):
    """Configure Sentry for error monitoring"""
    # Get Sentry DSN from config or environment
    sentry_dsn = app.config.get('SENTRY_DSN') or os.environ.get('SENTRY_DSN')
    
    if sentry_dsn:
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[FlaskIntegration()],
            traces_sample_rate=0.2,  # Sample 20% of transactions
            send_default_pii=True,  # Include user context
            environment=app.config.get('FLASK_ENV', 'development'),
            before_send=lambda event, hint: before_sentry_send(event, hint, app)
        )
        app.logger.info("Sentry error monitoring initialized.")
    else:
        app.logger.warning("Sentry DSN not configured. Error monitoring disabled.")

def before_sentry_send(event, hint, app):
    """Filter sensitive data before sending to Sentry"""
    # Remove sensitive headers
    if 'request' in event and 'headers' in event['request']:
        sensitive_headers = ['authorization', 'cookie', 'x-api-key']
        for header in sensitive_headers:
            if header in event['request']['headers']:
                event['request']['headers'][header] = '[REDACTED]'
    
    # Add custom context
    from flask_login import current_user
    if current_user.is_authenticated:
        event.setdefault('user', {})
        event['user']['id'] = current_user.id
        event['user']['email'] = current_user.email
    
    return event

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(Config)

    # Configure session
    app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # Setup logging and monitoring
    setup_logging(app)
    setup_sentry(app)

    # This function needs to be defined before being passed to babel.init_app
    def get_user_locale():
        # Add logging for debugging
        app.logger.debug(f"Attempting to determine locale. Session lang: {session.get('lang')}")
        
        # 1. Check for language in session first
        if 'lang' in session:
            lang = session['lang']
            app.logger.debug(f"Found lang '{lang}' in session.")
            return lang
        
        # 2. Check for user's preference
        from flask_login import current_user
        if current_user.is_authenticated and current_user.language:
            lang = current_user.language
            app.logger.debug(f"Found lang '{lang}' in user preferences.")
            return lang
            
        # 3. Fallback to browser's accept_languages header
        lang = request.accept_languages.best_match(app.config['BABEL_SUPPORTED_LOCALES'])
        app.logger.debug(f"Falling back to browser lang: '{lang}'.")
        return lang

    # Configure Babel and pass the selector function during initialization
    app.config.setdefault('BABEL_DEFAULT_LOCALE', 'en')
    app.config.setdefault('BABEL_SUPPORTED_LOCALES', ['en', 'es', 'fr', 'it'])
    babel.init_app(app, locale_selector=get_user_locale)

    # Configure basic logging
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
    app.logger.setLevel(logging.DEBUG)  # Set Flask's logger level
    app.logger.info("Flask app created and logging configured.")
    
    # Set Stripe API Key from config
    stripe.api_key = app.config.get('STRIPE_SECRET_KEY')
    if not stripe.api_key:
        app.logger.warning("Stripe API Secret Key (STRIPE_SECRET_KEY) is not set. Stripe integration will not work.")
    else:
        app.logger.info("Stripe API Key configured.")
    
    # Ensure the instance folder exists
    os.makedirs(os.path.join(app.root_path, '..', 'instance'), exist_ok=True)
    
    db.init_app(app)
    
    # Models are already imported above
    # from app import models 
    
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)  # Initialize CSRF protection

    # TEMPORARY DEBUGGING for Stripe Webhook 403 - REMOVING THIS SECTION
    # from flask import request as flask_request 
    # @app.before_request
    # def very_early_debug_webhook():
    #     # This will print for ALL requests, remove after debugging
    #     print(f"FLASK APP VERY_EARLY_DEBUG: Path = {flask_request.path}, Method = {flask_request.method}")
    #     if flask_request.path == '/webhooks/stripe' and flask_request.method == 'POST':
    #         print("FLASK APP VERY_EARLY_DEBUG: Stripe webhook path and method MATCHED!")

    # Import and register blueprints
    from app.routes.main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    from app.routes.api import api as api_blueprint
    app.register_blueprint(api_blueprint, url_prefix='/api')

    from app.routes.auth import auth as auth_blueprint, init_oauth
    app.register_blueprint(auth_blueprint, url_prefix='/auth')
    
    # Initialize OAuth
    if app.config.get('GOOGLE_CLIENT_ID') and app.config.get('GOOGLE_CLIENT_SECRET'):
        init_oauth(app)
        app.logger.info("Google OAuth initialized successfully.")
    else:
        app.logger.warning("Google OAuth not configured - GOOGLE_CLIENT_ID or GOOGLE_CLIENT_SECRET missing.")

    from app.routes.webhooks import webhook_bp
    app.register_blueprint(webhook_bp)

    from app.routes.user_data import user_data as user_data_blueprint
    app.register_blueprint(user_data_blueprint)

    from app.routes.legal import legal as legal_blueprint
    app.register_blueprint(legal_blueprint)

    from app.routes.locations import locations as locations_blueprint
    app.register_blueprint(locations_blueprint)

    from app.routes.onboarding import onboarding as onboarding_blueprint
    app.register_blueprint(onboarding_blueprint)

    # Create all tables
    # with app.app_context():
    #     db.create_all()
        
    # Add this after creating the app
    def markdown_filter(text):
        return Markup(markdown.markdown(text))

    app.jinja_env.filters['markdown'] = markdown_filter
    
    # Add from_json filter for parsing JSON in templates
    import json
    def from_json_filter(text):
        if not text:
            return []
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return []
    
    app.jinja_env.filters['from_json'] = from_json_filter

    # Make csrf_token available in templates
    from flask_wtf.csrf import generate_csrf
    app.jinja_env.globals['csrf_token'] = generate_csrf

    # Register CLI commands
    from app.cli import register_commands
    register_commands(app)

    # Add user loader
    from app.models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        app.logger.info(f"user_loader called with user_id: {user_id}")
        user = User.query.get(int(user_id))
        if user:
            app.logger.info(f"user_loader found user: {user.email} (ID: {user.id})")
        else:
            app.logger.warning(f"user_loader could not find user with ID: {user_id}")
        return user

    @app.context_processor
    def inject_pending_review_count():
        from flask_login import current_user
        from app.models import UnmatchedCalendlyBooking
        
        count = 0
        if current_user.is_authenticated:
            if current_user.is_admin:
                count = UnmatchedCalendlyBooking.query.filter_by(status='Pending').count()
            elif current_user.role == 'physio': # Non-admin physio
                if current_user.calendly_api_token and current_user.calendly_user_uri:
                    count = UnmatchedCalendlyBooking.query.filter_by(
                        status='Pending',
                        user_id=current_user.id
                    ).count()
                # Else, count remains 0 if Calendly not configured for non-admin physio
        return dict(pending_review_count=count)

    @app.context_processor
    def inject_conf_var():
        return dict(
            BABEL_SUPPORTED_LOCALES=app.config['BABEL_SUPPORTED_LOCALES'],
            get_locale=get_locale,
            get_locale_display_name=get_locale_display_name
        )

    return app

# --- Helper function to replace get_locale_display_name ---
def get_locale_display_name(locale_identifier):
    """
    Returns the display name for a given locale identifier.
    This is a workaround for older Flask-Babel versions.
    """
    # Simple mapping for the languages you use
    display_names = {
        'en': 'English',
        'es': 'Español',
        'fr': 'Français',
        'it': 'Italiano'
    }
    return display_names.get(str(locale_identifier), str(locale_identifier))
# ---------------------------------------------------------

# Create the app instance
app = create_app()