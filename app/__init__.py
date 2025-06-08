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

db = SQLAlchemy()

# Initialize login manager
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

# Initialize CSRF protection
csrf = CSRFProtect()

# Initialize Babel for translations
babel = Babel()

# Import models here *before* Migrate is instantiated
from app import models 

migrate = Migrate()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(Config)

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

    from app.routes.auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint, url_prefix='/auth')

    from app.routes.webhooks import webhook_bp
    app.register_blueprint(webhook_bp)

    # Create all tables
    # with app.app_context():
    #     db.create_all()
        
    # Add this after creating the app
    def markdown_filter(text):
        return Markup(markdown.markdown(text))

    app.jinja_env.filters['markdown'] = markdown_filter

    # Make csrf_token available in templates
    # from flask_wtf.csrf import generate_csrf # This is fine, but already imported above
    # app.jinja_env.globals['csrf_token'] = generate_csrf # THIS IS THE LINE OF INTEREST

    # Register CLI commands
    from app.cli import register_commands
    register_commands(app)

    # Add user loader
    from app.models import User
    
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

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