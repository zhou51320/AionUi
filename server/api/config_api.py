import json
from flask import Blueprint, request, g
from models import db, UserConfig
from auth import api_response, api_error, login_required

config_bp = Blueprint('config_api', __name__, url_prefix='/api/config')

@config_bp.route('', methods=['GET'])
@login_required
def get_config():
    user_config = UserConfig.query.filter_by(user_id=g.user.id).first()
    if not user_config:
        # Create empty user config
        user_config = UserConfig(user_id=g.user.id, base_url='', model_name='', extra_config='{}')
        db.session.add(user_config)
        db.session.commit()
    return api_response(data=user_config.to_dict(decrypt=True))

@config_bp.route('', methods=['PUT'])
@login_required
def update_config():
    data = request.get_json(silent=True) or {}
    user_config = UserConfig.query.filter_by(user_id=g.user.id).first()
    if not user_config:
        user_config = UserConfig(user_id=g.user.id)
        db.session.add(user_config)

    if 'api_key' in data:
        user_config.set_api_key(data['api_key'] or '')
    if 'base_url' in data:
        user_config.base_url = (data['base_url'] or '').strip()
    if 'model_name' in data:
        user_config.model_name = (data['model_name'] or '').strip()

    extra = {}
    if user_config.extra_config:
        try:
            extra = json.loads(user_config.extra_config)
        except Exception:
            extra = {}

    for k in ['platform', 'provider_name', 'models', 'model_protocol', 'image_input', 'openai_api_mode', 'thought_level', 'context_limit']:
        if k in data:
            extra[k] = data[k]

    if 'extra_config' in data:
        if isinstance(data['extra_config'], dict):
            extra.update(data['extra_config'])
        elif isinstance(data['extra_config'], str):
            try:
                extra.update(json.loads(data['extra_config']))
            except Exception:
                pass

    user_config.extra_config = json.dumps(extra, ensure_ascii=False)

    db.session.commit()
    return api_response(message='配置已更新', data=user_config.to_dict(decrypt=True))
