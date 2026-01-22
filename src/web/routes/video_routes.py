from flask import Blueprint, jsonify, request, send_file, Response
import sys
import os
import threading
import mimetypes

# Ensure parent directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from managers.video_manager import VideoManager

bp = Blueprint('video', __name__)

@bp.route('/api/videos')
def get_videos():
    project_path = request.args.get('project_path')
    if not project_path:
        return jsonify({'success': False, 'error': 'Missing project_path'})
    videos = VideoManager.scan_videos(project_path)
    # Add URL fields
    for v in videos:
        v['thumbnail_url'] = f"/api/video/thumbnail?project_path={project_path}&video_name={v['name']}"
        v['stream_url'] = f"/api/video/stream?project_path={project_path}&video_name={v['name']}"
        
    return jsonify({'success': True, 'videos': videos})

@bp.route('/api/video/thumbnail')
def get_thumbnail():
    project_path = request.args.get('project_path')
    video_name = request.args.get('video_name')
    if not project_path or not video_name:
        return "Missing parameters", 400
        
    thumb_path = os.path.join(project_path, 'videos', '.thumbnails', f"{video_name}.jpg")
    if os.path.exists(thumb_path):
        return send_file(thumb_path, mimetype='image/jpeg')
    else:
        return "Thumbnail not found", 404

@bp.route('/api/video/stream')
def stream_video():
    project_path = request.args.get('project_path')
    video_name = request.args.get('video_name')
    if not project_path or not video_name:
        return "Missing parameters", 400
        
    video_path = os.path.join(project_path, 'videos', video_name)
    if not os.path.exists(video_path):
        return "Video not found", 404
        
    return send_file(video_path)

@bp.route('/api/video/extract', methods=['POST'])
def extract_video():
    data = request.get_json()
    project_path = data.get('project_path')
    video_name = data.get('video_name')
    strategy = data.get('strategy', 'interval') # interval | count
    value = data.get('value', 1.0) 
    
    if not all([project_path, video_name]):
        return jsonify({'success': False, 'error': 'Missing parameters'})
        
    try:
        task_id = VideoManager.start_extraction_task(project_path, video_name, strategy, value)
        return jsonify({'success': True, 'task_id': task_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/video/tasks')
def get_tasks():
    project_path = request.args.get('project_path')
    if not project_path:
        return jsonify({'success': False, 'error': 'Missing project_path'})
    tasks = VideoManager.get_tasks(project_path)
    return jsonify({'success': True, 'tasks': tasks})

@bp.route('/api/video/task/images')
def get_task_images():
    project_path = request.args.get('project_path')
    task_id = request.args.get('task_id')
    if not project_path or not task_id:
        return jsonify({'success': False, 'error': 'Missing parameters'})
    images = VideoManager.get_task_images(project_path, task_id)
    # Add URLs
    image_list = []
    for img in images:
        image_list.append({
            'name': img,
            'url': f"/api/video/task/image_file?project_path={project_path}&task_id={task_id}&image_name={img}"
        })
    return jsonify({'success': True, 'images': image_list})

@bp.route('/api/video/task/image_file')
def get_task_image_file():
    project_path = request.args.get('project_path')
    task_id = request.args.get('task_id')
    image_name = request.args.get('image_name')
    
    if not all([project_path, task_id, image_name]):
        return "Missing parameters", 400
        
    # Manually construct path since VideoManager helper is private/internal logic
    # Actually we can reuse _get_task_dir logic if we exposed it, but for now just replicate
    img_path = os.path.join(project_path, 'temp_tasks', task_id, 'images', image_name)
    
    if os.path.exists(img_path):
        return send_file(img_path, mimetype='image/jpeg')
    else:
        return "Image not found", 404

@bp.route('/api/video/task/import', methods=['POST'])
def import_task_images():
    data = request.get_json()
    project_path = data.get('project_path')
    task_id = data.get('task_id')
    dataset_name = data.get('dataset_name')
    selected_images = data.get('selected_images') # List of filenames (optional, empty means all)
    
    if not all([project_path, task_id, dataset_name]):
        return jsonify({'success': False, 'error': 'Missing parameters'})
        
    try:
        count = VideoManager.add_frames_to_dataset(project_path, task_id, dataset_name, selected_images)
        return jsonify({'success': True, 'imported_count': count})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/video/task/batch_delete', methods=['POST'])
def batch_delete_task_images():
    data = request.get_json() or {}
    project_path = data.get('project_path')
    task_id = data.get('task_id')
    selected_images = data.get('selected_images') or []

    if not project_path or not task_id:
        return jsonify({'success': False, 'error': 'Missing parameters'})
    if not isinstance(selected_images, list) or len(selected_images) == 0:
        return jsonify({'success': False, 'error': 'Missing parameters'})

    try:
        deleted = VideoManager.delete_task_images(project_path, task_id, selected_images)
        return jsonify({'success': True, 'deleted_count': len(deleted), 'deleted_images': deleted})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/video/task/delete', methods=['POST'])
def delete_task():
    data = request.get_json()
    project_path = data.get('project_path')
    task_id = data.get('task_id')
    
    if not all([project_path, task_id]):
        return jsonify({'success': False, 'error': 'Missing parameters'})
        
    try:
        VideoManager.delete_task(project_path, task_id)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
