# app/__init__.py
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config
import markdown
from markupsafe import Markup
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
import logging
import stripe # Import stripe

db = SQLAlchemy()

# Initialize login manager
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message_category = 'info'

# Initialize CSRF protection
csrf = CSRFProtect()

# Import models here *before* Migrate is instantiated
from app import models 

migrate = Migrate()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Configure basic logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]')
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
    from app.routes.main import main
    app.register_blueprint(main)

    from app.routes.api import api
    app.register_blueprint(api)

    from app.routes.auth import auth
    app.register_blueprint(auth)

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

    return app