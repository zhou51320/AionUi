from flask import Blueprint, request, g
from models import db, User
from auth import api_response, api_error, generate_token, login_required

auth_bp = Blueprint('auth_api', __name__, url_prefix='/api/auth')

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return api_error(code=400, message='用户名和密码不能为空', status=400)

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return api_error(code=401, message='用户名或密码错误', status=401)

    if not user.is_active:
        return api_error(code=403, message='账号已被禁用，请联系管理员', status=403)

    token = generate_token(user)
    return api_response(data={
        'token': token,
        'user': {
            'id': user.id,
            'username': user.username,
            'role': user.role,
        }
    })

@auth_bp.route('/logout', methods=['POST'])
def logout():
    return api_response(message='登出成功')

@auth_bp.route('/me', methods=['GET'])
@login_required
def get_current_user():
    return api_response(data={
        'id': g.user.id,
        'username': g.user.username,
        'role': g.user.role,
    })
