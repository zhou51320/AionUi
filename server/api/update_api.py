import os
from flask import Blueprint, request, send_from_directory, current_app
from models import db, AppRelease
from auth import api_response, api_error
from config import Config

update_bp = Blueprint('update_api', __name__, url_prefix='/api/update')

@update_bp.route('/check', methods=['GET'])
def check_update():
    """
    Check for the latest available application update.
    Returns latest release info if available.
    """
    latest_release = AppRelease.query.filter_by(is_active=True).order_by(AppRelease.id.desc()).first()
    if not latest_release:
        return api_response(code=0, message='No updates available', data=None)

    base_url = request.host_url.rstrip('/')
    download_url = f"{base_url}/api/update/download/{latest_release.id}"

    data = {
        'version': latest_release.version,
        'name': latest_release.title or f'AionUi v{latest_release.version}',
        'body': latest_release.changelog or '',
        'pub_date': latest_release.created_at.isoformat() if latest_release.created_at else None,
        'filename': latest_release.filename,
        'file_size': latest_release.file_size,
        'download_url': download_url,
    }
    return api_response(data=data)

@update_bp.route('/download/<int:release_id>', methods=['GET'])
def download_update(release_id):
    """
    Download update package file.
    """
    release = db.session.get(AppRelease, release_id) if hasattr(db.session, 'get') else AppRelease.query.get(release_id)
    if not release or not release.is_active:
        return api_error(code=404, message='更新包不存在或已被下架', status=404)

    release_dir = os.path.join(Config.UPLOAD_FOLDER, 'releases')
    file_path = os.path.join(release_dir, release.stored_name)
    dir_to_send = release_dir
    if not os.path.exists(file_path):
        file_path = os.path.join(Config.UPLOAD_FOLDER, release.stored_name)
        dir_to_send = Config.UPLOAD_FOLDER

    if not os.path.exists(file_path):
        return api_error(code=404, message='更新文件在服务器上丢失', status=404)

    release.download_count += 1
    db.session.commit()

    return send_from_directory(
        dir_to_send,
        release.stored_name,
        as_attachment=True,
        download_name=release.filename
    )
