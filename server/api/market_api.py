import os
import uuid
from flask import Blueprint, request, g, send_file
from werkzeug.utils import secure_filename
from config import Config
from models import db, MarketFile
from auth import api_response, api_error, login_required, admin_required

market_bp = Blueprint('market_api', __name__, url_prefix='/api/market')

ALLOWED_CATEGORIES = {'assistant', 'plugin', 'skill', 'mcp'}
CATEGORY_LABELS = {
    'assistant': '智能体助手',
    'plugin': '功能插件',
    'mcp': 'MCP扩展',
    'skill': 'Skill技能',
}
ALLOWED_EXTENSIONS = {'zip', 'json', 'yaml', 'yml', 'tar', 'gz'}

def allowed_file(filename: str) -> bool:
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_EXTENSIONS

@market_bp.route('/files', methods=['GET'])
@login_required
def list_files():
    category = request.args.get('category', '').strip()
    query = MarketFile.query
    if category and category in ALLOWED_CATEGORIES:
        query = query.filter_by(category=category)
    files = query.order_by(MarketFile.created_at.desc()).all()
    
    result = []
    for f in files:
        item = f.to_dict()
        item['category_label'] = CATEGORY_LABELS.get(f.category, f.category)
        item['uploader_username'] = f.uploader.username if f.uploader else 'admin'
        result.append(item)
    return api_response(data=result)

@market_bp.route('/download/<int:file_id>', methods=['GET'])
@login_required
def download_file(file_id: int):
    market_file = MarketFile.query.get(file_id)
    if not market_file:
        return api_error(code=404, message='文件不存在', status=404)

    file_path = os.path.join(Config.UPLOAD_FOLDER, market_file.stored_name)
    if not os.path.exists(file_path):
        return api_error(code=404, message='物理文件缺失', status=404)

    market_file.download_count += 1
    db.session.commit()

    mimetype = 'application/zip'
    if market_file.filename.endswith('.json'):
        mimetype = 'application/json'
    elif market_file.filename.endswith(('.yaml', '.yml')):
        mimetype = 'text/yaml'

    return send_file(
        file_path,
        as_attachment=True,
        download_name=market_file.filename,
        mimetype=mimetype
    )

@market_bp.route('/upload', methods=['POST'])
@admin_required
def upload_file():
    if 'file' not in request.files:
        return api_error(code=400, message='缺少文件字段', status=400)

    file = request.files['file']
    category = request.form.get('category', 'assistant').strip().lower()
    description = request.form.get('description', '').strip()

    if not file or not file.filename:
        return api_error(code=400, message='未选择文件', status=400)

    raw_filename = os.path.basename(file.filename.strip())
    if not allowed_file(raw_filename):
        return api_error(code=400, message=f'不支持的文件类型，仅支持: {", ".join(sorted(ALLOWED_EXTENSIONS))}', status=400)

    if category not in ALLOWED_CATEGORIES:
        return api_error(code=400, message=f'无效的分类，可选分类: {", ".join(ALLOWED_CATEGORIES)}', status=400)

    os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)

    # 保持原有文件名（去除路径遍历风险），生成唯一物理存储名
    original_filename = raw_filename.replace('/', '').replace('\\', '').strip() or f'package-{uuid.uuid4().hex[:8]}.zip'
    ext = original_filename.rsplit('.', 1)[1].lower() if '.' in original_filename else 'zip'
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(Config.UPLOAD_FOLDER, stored_name)

    file.save(file_path)
    file_size = os.path.getsize(file_path)

    market_file = MarketFile(
        filename=original_filename,
        stored_name=stored_name,
        category=category,
        description=description,
        file_size=file_size,
        uploader_id=g.user.id if getattr(g, 'user', None) else None,
    )
    db.session.add(market_file)
    db.session.commit()

    item = market_file.to_dict()
    item['category_label'] = CATEGORY_LABELS.get(market_file.category, market_file.category)
    item['uploader_username'] = g.user.username if getattr(g, 'user', None) else 'admin'

    return api_response(message='上传成功', data=item, status=201)

@market_bp.route('/files/<int:file_id>', methods=['DELETE'])
@admin_required
def delete_file(file_id: int):
    market_file = MarketFile.query.get(file_id)
    if not market_file:
        return api_error(code=404, message='文件不存在', status=404)

    file_path = os.path.join(Config.UPLOAD_FOLDER, market_file.stored_name)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError as e:
            # Continue removing from db even if disk removal has issue
            pass

    db.session.delete(market_file)
    db.session.commit()

    return api_response(message='删除成功')
