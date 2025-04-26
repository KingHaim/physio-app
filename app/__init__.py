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
    
    # Ensure the instance folder exists
    os.makedirs(os.path.join(app.root_path, '..', 'instance'), exist_ok=True)
    
    db.init_app(app)
    
    # Models are already imported above
    # from app import models 
    
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)  # Initialize CSRF protection

    # Import and register blueprints
    from app.routes.main import main
    app.register_blueprint(main)

    from app.routes.api import api
    app.register_blueprint(api)

    from app.routes.auth import auth
    app.register_blueprint(auth)

    # Create all tables
    # with app.app_context():
    #     db.create_all()
        
    # Add this after creating the app
    def markdown_filter(text):
        return Markup(markdown.markdown(text))

    app.jinja_env.filters['markdown'] = markdown_filter

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
        return User.query.get(int(user_id))

    def get_pending_review_count():
        from app.models import Patient
        return Patient.query.filter_by(status='Pending Review').count()

    app.jinja_env.globals.update(get_pending_review_count=get_pending_review_count)

    return app