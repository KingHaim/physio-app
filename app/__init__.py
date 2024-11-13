# app/__init__.py
import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from config import Config  # This will work now as config.py is at root level

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Ensure the instance folder exists
    os.makedirs(os.path.join(app.root_path, '..', 'instance'), exist_ok=True)
    
    db.init_app(app)
    migrate.init_app(app, db)

    from . import routes
    app.register_blueprint(routes.main)

    # Create all tables
    with app.app_context():
        db.create_all()
        
    return app