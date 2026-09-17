from flask import session, redirect, url_for, request, flash, render_template_string
from flask_admin import Admin, AdminIndexView, expose
from flask_admin.contrib.sqla import ModelView
from werkzeug.security import generate_password_hash
from models import db, User, UserConfig, MarketFile, ClientLog
from crypto_utils import decrypt_api_key

LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>AionUi 管理后台登录</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@3.4.1/dist/css/bootstrap.min.css">
    <style>
        body { background: #f0f2f5; padding-top: 80px; }
        .login-card { max-width: 380px; margin: 0 auto; background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
        .login-title { text-align: center; margin-bottom: 24px; font-weight: 600; color: #1f2329; }
    </style>
</head>
<body>
<div class="container">
    <div class="login-card">
        <h3 class="login-title">AionUi 管理后台</h3>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'danger' if category == 'error' else 'info' }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <form method="post" action="{{ url_for('admin.login') }}">
            <div class="form-group">
                <label>用户名</label>
                <input type="text" name="username" class="form-control" required autofocus placeholder="admin">
            </div>
            <div class="form-group">
                <label>密码</label>
                <input type="password" name="password" class="form-control" required placeholder="admin123">
            </div>
            <button type="submit" class="btn btn-primary btn-block" style="margin-top: 20px;">登 录</button>
        </form>
    </div>
</div>
</body>
</html>
"""

class SecureAdminIndexView(AdminIndexView):
    def is_accessible(self):
        return session.get('is_admin', False)

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('admin.login', next=request.url))

    @expose('/')
    def index(self):
        if not self.is_accessible():
            return redirect(url_for('admin.login', next=request.url))
        user_count = User.query.count()
        file_count = MarketFile.query.count()
        log_count = ClientLog.query.count()
        return self.render('admin/index.html',
                           user_count=user_count,
                           file_count=file_count,
                           log_count=log_count)

    @expose('/login', methods=['GET', 'POST'])
    def login(self):
        if request.method == 'POST':
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '')
            user = User.query.filter_by(username=username).first()
            if user and user.check_password(password):
                if user.role == 'admin' and user.is_active:
                    session['is_admin'] = True
                    session['admin_user_id'] = user.id
                    session['admin_username'] = user.username
                    next_url = request.args.get('next') or url_for('admin.index')
                    return redirect(next_url)
                else:
                    flash('该账号没有管理员权限或已被禁用', 'error')
            else:
                flash('用户名或密码错误', 'error')
        return render_template_string(LOGIN_TEMPLATE)

    @expose('/logout')
    def logout(self):
        session.pop('is_admin', None)
        session.pop('admin_user_id', None)
        session.pop('admin_username', None)
        return redirect(url_for('admin.login'))


class SecureModelView(ModelView):
    def is_accessible(self):
        return session.get('is_admin', False)

    def inaccessible_callback(self, name, **kwargs):
        return redirect(url_for('admin.login', next=request.url))


class UserView(SecureModelView):
    column_list = ['id', 'username', 'role', 'is_active', 'created_at']
    column_searchable_list = ['username']
    column_filters = ['role', 'is_active']
    form_columns = ['username', 'password', 'role', 'is_active']
    column_labels = {
        'id': 'ID',
        'username': '用户名',
        'role': '角色',
        'is_active': '启用状态',
        'created_at': '创建时间',
    }

    def on_model_change(self, form, model, is_created):
        if form.password.data:
            model.password_hash = generate_password_hash(form.password.data)
        elif is_created and not form.password.data:
            model.password_hash = generate_password_hash('123456')


class UserConfigView(SecureModelView):
    column_list = ['id', 'user_id', 'user', 'base_url', 'model_name', 'updated_at']
    column_searchable_list = ['base_url', 'model_name']
    column_labels = {
        'id': 'ID',
        'user_id': '用户ID',
        'user': '关联用户',
        'base_url': 'Base URL',
        'model_name': '默认模型',
        'updated_at': '更新时间',
    }


class MarketFileView(SecureModelView):
    column_list = ['id', 'filename', 'category', 'file_size', 'download_count', 'created_at']
    column_searchable_list = ['filename', 'description']
    column_filters = ['category']
    column_labels = {
        'id': 'ID',
        'filename': '文件名',
        'category': '分类',
        'file_size': '文件大小(字节)',
        'download_count': '下载次数',
        'created_at': '上传时间',
    }


class ClientLogView(SecureModelView):
    can_create = False
    can_edit = False
    column_list = ['id', 'level', 'user', 'client_info', 'message', 'created_at']
    column_searchable_list = ['message', 'client_info']
    column_filters = ['level', 'created_at']
    column_default_sort = ('created_at', True)
    column_labels = {
        'id': 'ID',
        'level': '级别',
        'user': '上报用户',
        'client_info': '客户端信息',
        'message': '日志内容',
        'created_at': '时间',
    }


def init_admin(app):
    admin = Admin(
        app,
        name='AionUi 管理后台',
        index_view=SecureAdminIndexView(name='概览', url='/admin'),
        template_mode='bootstrap3'
    )
    admin.add_view(UserView(User, db.session, name='用户管理'))
    admin.add_view(UserConfigView(UserConfig, db.session, name='模型配置'))
    admin.add_view(MarketFileView(MarketFile, db.session, name='市场文件'))
    admin.add_view(ClientLogView(ClientLog, db.session, name='日志查看'))
    return admin
