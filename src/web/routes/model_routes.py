from flask import Blueprint, jsonify, request
import os
import sys
import threading
from datetime import datetime

# Ensure parent directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from managers.model_manager import ModelManager
from managers.export_manager import ExportManager, export_status
from managers.training_manager import TrainingManager

bp = Blueprint('model', __name__)

@bp.route('/api/models')
def api_models():
    try:
        project_path = request.args.get('project_path')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        models = ModelManager.scan_models(project_path)
        return jsonify({'success': True, 'models': models})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/model/export', methods=['POST'])
def api_model_export():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        training_id = data.get('training_id')
        format_ = data.get('format', 'onnx')
        half = bool(data.get('half_precision'))
        int8 = bool(data.get('int8_quant'))
        imgsz = data.get('imgsz')
        per_class = int(data.get('per_class', 20))
        max_images = int(data.get('max_images', 200))
        weights_path = data.get('weights_path')
        
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
            
        if export_status['is_running']:
            return jsonify({'success': False, 'error': '已有导出任务正在运行'})
            
        export_id = f"export_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        export_status.update({'export_id': export_id, 'is_running': True, 'progress': 0, 'message': '启动导出...'})
        
        th = threading.Thread(target=lambda: ExportManager.export_model(project_path, training_id, format_, half, int8, imgsz, per_class, max_images, weights_path))
        th.daemon = True
        th.start()
        
        return jsonify({'success': True, 'export_id': export_id, 'message': '导出任务已启动'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/model/export/status')
def api_model_export_status():
    st = ExportManager.get_status()
    # 转换 result_path 为 URL
    res = st.copy()
    if res.get('result_path'):
        res['download_url'] = f"/api/file?path={res['result_path']}"
    return jsonify({'success': True, 'status': res})

@bp.route('/api/model/evaluate', methods=['POST'])
def api_model_evaluate():
    try:
        data = request.get_json()
        project_path = data.get('project_path')
        training_id = data.get('training_id')
        split = data.get('split', 'val')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        result = TrainingManager.evaluate_model(project_path, training_id, split)
        # 将本地路径转为可访问URL
        imgs = result.get('images', [])
        result['images'] = [f"/api/file?path={p}" for p in imgs]
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/model/evaluate/start', methods=['POST'])
def api_model_evaluate_start():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        split = data.get('split', 'val')
        if not project_path:
            return jsonify({'success': False, 'error': '缺少项目路径'})
        result = TrainingManager.start_evaluate_async(project_path, split)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/model/evaluate/status')
def api_model_evaluate_status():
    try:
        st = TrainingManager.get_evaluate_status()
        # 将路径转换为可访问 URL
        res = st.copy()
        if res.get('results') and res['results'].get('images'):
            res['results']['images'] = [f"/api/file?path={p}" for p in res['results']['images']]
        return jsonify({'success': True, 'status': res})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
