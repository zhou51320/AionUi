import os
import sys
from flask import Flask, jsonify
from flask_cors import CORS
from config import Config
from models import db, User, UserConfig
from api import auth_bp, config_bp, market_bp, log_bp
from admin_views import init_admin

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Enable CORS for desktop/web clients
    CORS(app, supports_credentials=True, resources={r"/api/*": {"origins": "*"}})

    # Initialize extensions
    db.init_app(app)
    init_admin(app)

    # Register API blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(market_bp)
    app.register_blueprint(log_bp)

    @app.route('/')
    def root():
        return jsonify({
            'name': 'AionUi Self-Hosted Server',
            'version': '1.0.0',
            'status': 'running',
            'compatibility': 'Windows 7 / Linux / macOS',
        })

    @app.errorhandler(404)
    def handle_404(e):
        return jsonify({'code': 404, 'message': 'Endpoint not found', 'data': {}}), 404

    @app.errorhandler(500)
    def handle_500(e):
        return jsonify({'code': 500, 'message': 'Internal server error', 'data': {}}), 500

    return app

def init_database(app):
    with app.app_context():
        db.create_all()
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

        # Check or create default admin
        admin_user = User.query.filter_by(username='admin').first()
        if not admin_user:
            admin_user = User(username='admin', role='admin', is_active=True)
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.flush()

            # Create default config for admin
            admin_config = UserConfig(
                user_id=admin_user.id,
                base_url='https://api.openai.com/v1',
                model_name='gpt-4o',
                extra_config='{}'
            )
            admin_config.set_api_key('')
            db.session.add(admin_config)

        # Create default regular user
        normal_user = User.query.filter_by(username='user').first()
        if not normal_user:
            normal_user = User(username='user', role='user', is_active=True)
            normal_user.set_password('user123')
            db.session.add(normal_user)
            db.session.flush()

            user_config = UserConfig(
                user_id=normal_user.id,
                base_url='https://api.openai.com/v1',
                model_name='gpt-4o-mini',
                extra_config='{}'
            )
            user_config.set_api_key('')
            db.session.add(user_config)

        db.session.commit()
        print('====================================================')
        print('AionUi 自托管服务器数据库初始化完成！')
        print('默认管理员账号: admin / admin123')
        print('默认普通用户账号: user  / user123')
        print('管理后台地址:     http://127.0.0.1:5000/admin')
        print('====================================================')

if __name__ == '__main__':
    app = create_app()

    if '--init' in sys.argv:
        init_database(app)
        sys.exit(0)

    # Ensure database tables exist at start if not yet initialized
    with app.app_context():
        db.create_all()
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        if not User.query.filter_by(username='admin').first():
            init_database(app)

    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '0.0.0.0')
    print(f'Starting AionUi Self-Hosted Server on {host}:{port}...')
    app.run(host=host, port=port, debug=False)
