from flask import Blueprint, request, g
from models import db, ClientLog
from auth import api_response, api_error, login_required, admin_required

log_bp = Blueprint('log_api', __name__, url_prefix='/api/logs')

@log_bp.route('', methods=['POST'])
@login_required
def report_log():
    data = request.get_json(silent=True) or {}
    level = (data.get('level') or 'INFO').upper()
    message = (data.get('message') or '').strip()
    client_info = (data.get('client_info') or '').strip()

    if not message:
        return api_error(code=400, message='日志内容不能为空', status=400)

    log_entry = ClientLog(
        user_id=g.user.id if getattr(g, 'user', None) else None,
        level=level,
        message=message,
        client_info=client_info,
    )
    db.session.add(log_entry)
    db.session.commit()

    return api_response(message='日志已上报', data={'id': log_entry.id}, status=201)

@log_bp.route('', methods=['GET'])
@admin_required
def query_logs():
    level = request.args.get('level', '').strip().upper()
    page = request.args.get('page', 1, type=int)
    size = request.args.get('size', 20, type=int)

    query = ClientLog.query
    if level:
        query = query.filter_by(level=level)

    total = query.count()
    items = (
        query.order_by(ClientLog.created_at.desc())
        .offset((page - 1) * size)
        .limit(size)
        .all()
    )

    return api_response(data={
        'total': total,
        'page': page,
        'size': size,
        'items': [item.to_dict() for item in items],
    })
