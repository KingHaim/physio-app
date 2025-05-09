# config.py
import os
from dotenv import load_dotenv

# Get the absolute path to the directory containing this file
basedir = os.path.abspath(os.path.dirname(__file__))

load_dotenv()

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-12345")
    # Use absolute path for database
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(basedir, 'instance', 'physio.db')}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Calendly API configuration
    CALENDLY_API_TOKEN = os.environ.get('CALENDLY_API_TOKEN', '')