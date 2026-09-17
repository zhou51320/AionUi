from datetime import datetime
import json
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from crypto_utils import decrypt_api_key, encrypt_api_key

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(16), nullable=False, default='user')  # 'admin' | 'user'
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    config = db.relationship('UserConfig', backref='user', uselist=False, cascade='all, delete-orphan')
    logs = db.relationship('ClientLog', backref='user', lazy='dynamic')
    uploaded_files = db.relationship('MarketFile', backref='uploader', lazy='dynamic')

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<User {self.username}>'


class UserConfig(db.Model):
    __tablename__ = 'user_configs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    api_key = db.Column(db.Text, nullable=True)  # Fernet encrypted
    base_url = db.Column(db.String(256), nullable=True)
    model_name = db.Column(db.String(128), nullable=True)
    extra_config = db.Column(db.Text, nullable=True, default='{}')  # JSON string
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def set_api_key(self, plain_key: str):
        self.api_key = encrypt_api_key(plain_key)

    def get_api_key(self) -> str:
        return decrypt_api_key(self.api_key)

    def to_dict(self, decrypt=True):
        extra = {}
        if self.extra_config:
            try:
                extra = json.loads(self.extra_config)
            except Exception:
                extra = {}
        return {
            'api_key': self.get_api_key() if decrypt else self.api_key,
            'base_url': self.base_url or '',
            'model_name': self.model_name or '',
            'extra_config': extra,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<UserConfig user_id={self.user_id}>'


class MarketFile(db.Model):
    __tablename__ = 'market_files'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    filename = db.Column(db.String(256), nullable=False)
    stored_name = db.Column(db.String(256), nullable=False, unique=True)
    category = db.Column(db.String(32), nullable=False)  # 'assistant' | 'plugin' | 'skill'
    description = db.Column(db.Text, nullable=True)
    file_size = db.Column(db.Integer, nullable=False, default=0)
    uploader_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    download_count = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'filename': self.filename,
            'category': self.category,
            'description': self.description or '',
            'file_size': self.file_size,
            'download_count': self.download_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<MarketFile {self.filename}>'


class ClientLog(db.Model):
    __tablename__ = 'client_logs'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    level = db.Column(db.String(16), default='INFO', nullable=False)
    message = db.Column(db.Text, nullable=False)
    client_info = db.Column(db.String(256), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.user.username if self.user else None,
            'level': self.level,
            'message': self.message,
            'client_info': self.client_info,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<ClientLog {self.level}: {self.message[:30]}>'
