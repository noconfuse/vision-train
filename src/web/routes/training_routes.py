from flask import Blueprint, jsonify, request
import os
import sys

# Ensure parent directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from managers.training_manager import TrainingManager, training_status

bp = Blueprint('training', __name__)

@bp.route('/api/training/start', methods=['POST'])
def api_start_training():
    try:
        data = request.get_json()
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        model_name = data.get('model_name')
        training_config = data.get('training_config', {})
        dataset_path = data.get('dataset_path')
        
        if not project_path or not dataset_name or not model_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
            
        result = TrainingManager.start_training(project_path, dataset_name, model_name, training_config, dataset_path)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/training/stop', methods=['POST'])
def api_stop_training():
    try:
        result = TrainingManager.stop_training()
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/training/status')
def api_training_status():
    # Convert deque to list for JSON serialization
    status = dict(training_status)
    status['log'] = list(status['log'])
    return jsonify({'success': True, 'status': status, 'log': status['log']})

@bp.route('/api/training/history')
def api_training_history():
    try:
        project_path = request.args.get('project_path')
        dataset_name = request.args.get('dataset_name')
        
        if not project_path:
            # Fallback to current log if no project path (legacy behavior)
            return jsonify({'success': True, 'history': list(training_status['log'])})

        runs = TrainingManager.list_training_runs(project_path)
        
        # Filter by dataset if provided
        if dataset_name:
            runs = [r for r in runs if r.get('dataset') == dataset_name]
            
        return jsonify({'success': True, 'history': runs})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/training/runs')
def api_training_runs():
    try:
        project_path = request.args.get('project_path')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        runs = TrainingManager.list_training_runs(project_path)
        return jsonify({'success': True, 'runs': runs})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/training/continue', methods=['POST'])
def api_training_continue():
    try:
        data = request.get_json()
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name', 'training')
        use_best = data.get('use_best', False)
        training_config = data.get('training_config', {})
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        result = TrainingManager.start_training_from_artifact(project_path, dataset_name, use_best, training_config)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/training/resume', methods=['POST'])
def api_training_resume():
    try:
        data = request.get_json()
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name', 'training')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        result = TrainingManager.resume_last_run(project_path, dataset_name)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/training/artifacts')
def api_training_artifacts():
    try:
        project_path = request.args.get('project_path')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        artifacts = TrainingManager.get_latest_artifacts(project_path)
        
        # 将本地路径转为可访问 URL
        res = {}
        for k, v in artifacts.items():
            if v and isinstance(v, str) and os.path.exists(v):
                res[k] = f"/api/file?path={v}"
            else:
                res[k] = v
        return jsonify({'success': True, 'artifacts': res})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
