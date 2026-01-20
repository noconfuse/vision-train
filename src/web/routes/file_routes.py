from flask import Blueprint, jsonify, request, send_file
import os

bp = Blueprint('file', __name__)

@bp.route('/api/file')
def api_file():
    try:
        p = request.args.get('path')
        if not p or not os.path.exists(p):
            return jsonify({'success': False, 'error': '文件不存在'})
        return send_file(p)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
