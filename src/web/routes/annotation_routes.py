from flask import Blueprint, jsonify, request
import os
import sys

# Ensure parent directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from managers.model_manager import ModelManager
from managers.annotation_manager import AnnotationManager

bp = Blueprint('annotation', __name__)

@bp.route('/api/annotation/missing')
def api_annotation_missing():
    try:
        project_path = request.args.get('project_path')
        dataset_name = request.args.get('dataset_name')
        split = request.args.get('split', 'train')
        offset = int(request.args.get('offset', '0'))
        limit = int(request.args.get('limit', '50'))
        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        lbl_dir = os.path.join(ds_root, split, 'labels')
        missing = []
        for root, _, fs in os.walk(img_dir):
            for f in fs:
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    ip = os.path.join(root, f)
                    rel = os.path.relpath(ip, img_dir)
                    lp = os.path.join(lbl_dir, os.path.splitext(rel)[0] + '.txt')
                    if not os.path.exists(lp) or os.path.getsize(lp) == 0:
                        missing.append({'url': f"/api/file?path={ip}", 'path': ip})
        total = len(missing)
        page = missing[offset:offset+limit]
        return jsonify({'success': True, 'images': page, 'total': total})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/auto_annotate', methods=['POST'])
def api_auto_annotate():
    try:
        data = request.get_json()
        project_path = data.get('project_path')
        image_path = data.get('image_path')
        model_path = data.get('model_path') # 可选指定模型路径
        conf = float(data.get('conf', 0.25))
        if not image_path:
             return jsonify({'success': False, 'error': '缺少图片路径'})
        boxes = AnnotationManager.auto_annotate_image(
            project_path=project_path,
            image_path=image_path,
            model_path=model_path,
            conf=conf,
            max_det=200
        )
        return jsonify({'success': True, 'boxes': boxes})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/auto_annotate/batch', methods=['POST'])
def api_auto_annotate_batch():
    try:
        data = request.get_json()
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        split = data.get('split', 'train')
        model_path = data.get('model_path')
        conf = float(data.get('conf', 0.25))
        max_det = int(data.get('max_det', 200))
        batch_size = int(data.get('batch_size', 1))
        iou_thresh = float(data.get('iou_thresh', 0.5))
        
        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
            
        AnnotationManager.start_batch_annotation(
            project_path, dataset_name, split, model_path, conf, max_det, batch_size, iou_thresh
        )
        
        return jsonify({'success': True, 'message': '任务已启动'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/auto_annotate/batch/status')
def api_auto_annotate_batch_status():
    return jsonify({'success': True, 'status': AnnotationManager.get_batch_status()})

@bp.route('/api/annotation/pending')
def api_annotation_pending():
    try:
        project_path = request.args.get('project_path')
        dataset_name = request.args.get('dataset_name')
        split = request.args.get('split', 'train')
        offset = int(request.args.get('offset', '0'))
        limit = int(request.args.get('limit', '50'))
        if not project_path or not dataset_name:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        lbl_dir = os.path.join(ds_root, 'auto_labels', split)
        items = []
        for root, _, fs in os.walk(img_dir):
            for f in fs:
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    ip = os.path.join(root, f)
                    rel = os.path.relpath(ip, img_dir)
                    lp = os.path.join(lbl_dir, os.path.splitext(rel)[0] + '.txt')
                    if os.path.exists(lp):
                        items.append({'url': f"/api/file?path={ip}", 'path': ip})
        total = len(items)
        page = items[offset:offset+limit]
        return jsonify({'success': True, 'images': page, 'total': total})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/annotation/save', methods=['POST'])
def api_annotation_save():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        split = data.get('split', 'train')
        image_path = data.get('image_path')
        labels = data.get('labels') or []
        if not project_path or not dataset_name or not image_path:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        # 获取尺寸
        try:
            from PIL import Image
            with Image.open(image_path) as im:
                w, h = im.size
        except Exception:
            return jsonify({'success': False, 'error': '无法读取图片尺寸'})
        # 写入 YOLO 文本
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        lbl_dir = os.path.join(ds_root, split, 'labels')
        auto_dir = os.path.join(ds_root, 'auto_labels', split)
        os.makedirs(lbl_dir, exist_ok=True)
        rel = os.path.relpath(image_path, img_dir)
        rel_noext = os.path.splitext(rel)[0]
        lbl_path = os.path.join(lbl_dir, rel_noext + '.txt')
        auto_path = os.path.join(auto_dir, rel_noext + '.txt')
        lines = []
        for l in labels:
            cls = int(l.get('class', 0))
            x1, y1, x2, y2 = float(l['x1']), float(l['y1']), float(l['x2']), float(l['y2'])
            cx = ((x1 + x2) / 2.0) / w
            cy = ((y1 + y2) / 2.0) / h
            ww = (x2 - x1) / w
            hh = (y2 - y1) / h
            lines.append(f"{cls} {cx:.6f} {cy:.6f} {ww:.6f} {hh:.6f}")
        with open(lbl_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        # 保存后若存在对应 auto_labels，则删除以完成合并效果
        try:
            if os.path.exists(auto_path):
                os.remove(auto_path)
        except Exception:
            pass
        return jsonify({'success': True, 'label_path': lbl_path})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/annotation/get')
def api_annotation_get():
    try:
        project_path = request.args.get('project_path')
        dataset_name = request.args.get('dataset_name')
        split = request.args.get('split', 'train')
        image_path = request.args.get('image_path')
        if not project_path or not dataset_name or not image_path:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        lbl_dir = os.path.join(ds_root, split, 'labels')
        auto_dir = os.path.join(ds_root, 'auto_labels', split)
        rel = os.path.relpath(image_path, img_dir)
        lbl_path = os.path.join(lbl_dir, os.path.splitext(rel)[0] + '.txt')
        auto_path = os.path.join(auto_dir, os.path.splitext(rel)[0] + '.txt')
        boxes = []
        auto_boxes = []
        from PIL import Image
        with Image.open(image_path) as im:
            w, h = im.size
        if os.path.exists(lbl_path):
            try:
                with open(lbl_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            cls = int(float(parts[0]))
                            cx = float(parts[1]) * w
                            cy = float(parts[2]) * h
                            ww = float(parts[3]) * w
                            hh = float(parts[4]) * h
                            x1 = max(0.0, cx - ww/2)
                            y1 = max(0.0, cy - hh/2)
                            x2 = min(float(w), cx + ww/2)
                            y2 = min(float(h), cy + hh/2)
                            boxes.append({'class': cls, 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})
            except Exception:
                boxes = []
        if os.path.exists(auto_path):
            try:
                with open(auto_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 5:
                            cls = int(float(parts[0]))
                            cx = float(parts[1]) * w
                            cy = float(parts[2]) * h
                            ww = float(parts[3]) * w
                            hh = float(parts[4]) * h
                            x1 = max(0.0, cx - ww/2)
                            y1 = max(0.0, cy - hh/2)
                            x2 = min(float(w), cx + ww/2)
                            y2 = min(float(h), cy + hh/2)
                            auto_boxes.append({'class': cls, 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})
            except Exception:
                auto_boxes = []
        return jsonify({'success': True, 'boxes': boxes, 'auto_boxes': auto_boxes, 'width': w, 'height': h})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/annotation/commit', methods=['POST'])
def api_annotation_commit():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        split = data.get('split', 'train')
        image_path = data.get('image_path')
        if not project_path or not dataset_name or not image_path:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        manual_dir = os.path.join(ds_root, 'labels', split)
        auto_dir = os.path.join(ds_root, 'auto_labels', split)
        os.makedirs(manual_dir, exist_ok=True)
        os.makedirs(auto_dir, exist_ok=True)
        rel = os.path.relpath(image_path, img_dir)
        manual_lbl = os.path.join(manual_dir, os.path.splitext(rel)[0] + '.txt')
        auto_lbl = os.path.join(auto_dir, os.path.splitext(rel)[0] + '.txt')
        lines_manual = []
        lines_auto = []
        if os.path.exists(manual_lbl):
            try:
                with open(manual_lbl, 'r', encoding='utf-8') as f:
                    lines_manual = [ln.strip() for ln in f if ln.strip()]
            except Exception:
                lines_manual = []
        if os.path.exists(auto_lbl):
            try:
                with open(auto_lbl, 'r', encoding='utf-8') as f:
                    lines_auto = [ln.strip() for ln in f if ln.strip()]
            except Exception:
                lines_auto = []
        # 合并策略：人工优先，简单追加 auto 行（复核后提交）
        merged = lines_manual + lines_auto
        with open(manual_lbl, 'w', encoding='utf-8') as f:
            f.write('\n'.join(merged))
        # 提交后删除 auto 文件
        try:
            if os.path.exists(auto_lbl):
                os.remove(auto_lbl)
        except Exception:
            pass
        return jsonify({'success': True, 'label_path': manual_lbl})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@bp.route('/api/annotation/save_auto', methods=['POST'])
def api_annotation_save_auto():
    try:
        data = request.get_json() or {}
        project_path = data.get('project_path')
        dataset_name = data.get('dataset_name')
        split = data.get('split', 'train')
        image_path = data.get('image_path')
        labels = data.get('labels') or []
        if not project_path or not dataset_name or not image_path:
            return jsonify({'success': False, 'error': '缺少必要参数'})
        try:
            from PIL import Image
            with Image.open(image_path) as im:
                w, h = im.size
        except Exception:
            return jsonify({'success': False, 'error': '无法读取图片尺寸'})
        ds_root = os.path.join(project_path, 'training', dataset_name)
        img_dir = os.path.join(ds_root, split, 'images')
        auto_dir = os.path.join(ds_root, 'auto_labels', split)
        os.makedirs(auto_dir, exist_ok=True)
        rel = os.path.relpath(image_path, img_dir)
        lbl_path = os.path.join(auto_dir, os.path.splitext(rel)[0] + '.txt')
        lines = []
        for l in labels:
            cls = int(l.get('class', 0))
            x1, y1, x2, y2 = float(l['x1']), float(l['y1']), float(l['x2']), float(l['y2'])
            cx = ((x1 + x2) / 2.0) / w
            cy = ((y1 + y2) / 2.0) / h
            ww = (x2 - x1) / w
            hh = (y2 - y1) / h
            lines.append(f"{cls} {cx:.6f} {cy:.6f} {ww:.6f} {hh:.6f}")
        with open(lbl_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        return jsonify({'success': True, 'label_path': lbl_path})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
