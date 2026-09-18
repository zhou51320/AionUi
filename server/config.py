import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'aionui-win7-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL',
        f"sqlite:///{os.path.join(BASE_DIR, 'aionui.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.environ.get(
        'UPLOAD_FOLDER',
        os.path.join(BASE_DIR, 'uploads')
    )
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB max file upload
    JWT_EXPIRATION_DAYS = 7
    FLASK_ADMIN_SWATCH = 'cerulean'
