from datetime import datetime, timedelta
from functools import wraps
import jwt
from flask import g, jsonify, request
from config import Config
from models import User

def api_response(code=0, message='success', data=None, status=200):
    payload = {
        'code': code,
        'message': message,
        'data': data if data is not None else {},
    }
    return jsonify(payload), status

def api_error(code=400, message='error', status=400):
    return api_response(code=code, message=message, data={}, status=status)

def generate_token(user: User) -> str:
    exp = datetime.utcnow() + timedelta(days=Config.JWT_EXPIRATION_DAYS)
    payload = {
        'user_id': user.id,
        'username': user.username,
        'role': user.role,
        'exp': int(exp.timestamp()),
    }
    return jwt.encode(payload, Config.SECRET_KEY, algorithm='HS256')

def decode_token(token: str) -> dict:
    return jwt.decode(token, Config.SECRET_KEY, algorithms=['HS256'])

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        token = auth_header.replace('Bearer ', '').strip()
        if not token:
            return api_error(code=401, message='未登录', status=401)
        try:
            payload = decode_token(token)
            user = User.query.get(payload.get('user_id'))
            if not user or not user.is_active:
                return api_error(code=401, message='用户不存在或已被禁用', status=401)
            g.user = user
            g.token_payload = payload
        except jwt.ExpiredSignatureError:
            return api_error(code=401, message='Token已过期', status=401)
        except jwt.InvalidTokenError:
            return api_error(code=401, message='Token无效', status=401)
        except Exception as e:
            return api_error(code=401, message=f'鉴权失败: {str(e)}', status=401)
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if getattr(g, 'user', None) is None or g.user.role != 'admin':
            return api_error(code=403, message='需要管理员权限', status=403)
        return f(*args, **kwargs)
    return decorated
