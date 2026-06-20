import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists (local development)
load_dotenv()

class Config:
    """Base configuration settings for GeoWatch AI."""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'geowatch-default-fallback-key-replace-in-prod')
    
    # Render provides DATABASE_URL starting with postgres:// which SQLAlchemy 1.4+ does not support.
    # We must rewrite it to postgresql://
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = db_url
    else:
        # Fallback to local SQLite database for quick setup and testing
        SQLALCHEMY_DATABASE_URI = 'sqlite:///geowatch.db'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # API Keys
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    
    # Port configuration (primarily for Gunicorn/Render)
    PORT = int(os.environ.get('PORT', 5000))
    DEBUG = os.environ.get('FLASK_ENV') == 'development'
