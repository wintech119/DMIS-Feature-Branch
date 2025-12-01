import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

def get_secret_key():
    """Get SECRET_KEY from environment with secure fallback for development/testing only."""
    secret_key = os.environ.get('SECRET_KEY')
    if secret_key:
        return secret_key
    is_dev = os.environ.get('FLASK_DEBUG', '1') == '1'
    is_test = os.environ.get('TESTING', 'False').lower() == 'true'
    is_allow_dev_key = os.environ.get('ALLOW_DEV_SECRET_KEY', 'False').lower() == 'true'
    if is_dev or is_test or is_allow_dev_key:
        import secrets
        return secrets.token_hex(32)
    raise ValueError("SECRET_KEY environment variable must be set in production")

class Config:
    SECRET_KEY = get_secret_key()
    DATABASE_URL = os.environ.get('DATABASE_URL')
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    WORKFLOW_MODE = os.environ.get('WORKFLOW_MODE', 'AIDMGMT')
    
    DEBUG = os.environ.get('FLASK_DEBUG', '1') == '1'
    TESTING = os.environ.get('TESTING', 'False').lower() == 'true'
    
    TIMEZONE = 'America/Jamaica'
    TIMEZONE_OFFSET = -5
    
    GOJ_GREEN = '#006B3E'
    GOJ_GOLD = '#FFD100'
    
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    
    UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER') or os.path.join(BASE_DIR, 'uploads', 'donations')
    ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg'}
    
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    LOG_TO_STDOUT = os.environ.get('LOG_TO_STDOUT', 'False').lower() == 'true'
