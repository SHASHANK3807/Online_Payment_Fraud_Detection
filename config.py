import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Database connection string
    # Format: mysql+pymysql://username:password@host/dbname
    
    DB_USERNAME = os.getenv('DB_USERNAME', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    DB_HOST = os.getenv('DB_HOST', 'localhost')
    DB_NAME = os.getenv('DB_NAME', 'fraud_detection_db')
    
    # URL encode password to handle special characters like '@'
    from urllib.parse import quote_plus
    encoded_password = quote_plus(DB_PASSWORD)
    
    SQLALCHEMY_DATABASE_URI = f"mysql+pymysql://{DB_USERNAME}:{encoded_password}@{DB_HOST}/{DB_NAME}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Secret key for session management (optional but good practice)
    SECRET_KEY = os.getenv('SECRET_KEY', 'default_secret_key')

    # Flask-Mail Configuration
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_USERNAME')

