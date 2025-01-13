import os
from datetime import timedelta

class Config:
    # Generate a good secret key
    SECRET_KEY = os.environ.get('SECRET_KEY') or os.urandom(24)
    
    # Session configuration
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=30)
    SESSION_COOKIE_HTTPONLY = True
    # Disable secure cookie in development
    SESSION_COOKIE_SECURE = False  # Change this to True in production with HTTPS
    
    # CSRF protection
    WTF_CSRF_ENABLED = True
    WTF_CSRF_SECRET_KEY = os.environ.get('WTF_CSRF_SECRET_KEY') or os.urandom(24)
    WTF_CSRF_TIME_LIMIT = None  # Disable CSRF token timeout
    
    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = 'uploads' 