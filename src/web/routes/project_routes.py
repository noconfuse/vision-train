from flask import Blueprint, jsonify, request
import os
import sys

# Ensure parent directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from managers.project_manager import ProjectManager

bp = Blueprint('project', __name__)

@bp.route('/api/projects')
def api_projects():
    try:
        projects = ProjectManager.scan_projects()
        return jsonify({'success': True, 'projects': projects})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/project/create', methods=['POST'])
def api_create_project():
    try:
        data = request.get_json()
        name = data.get('name')
        desc = data.get('description', '')
        if not name:
            return jsonify({'success': False, 'error': '项目名称不能为空'})
        
        info = ProjectManager.create_project(name, desc)
        return jsonify({'success': True, 'project': info})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
