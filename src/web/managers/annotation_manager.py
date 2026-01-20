import os
import sys
import threading
import json

# Ensure parent directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from managers.model_manager import ModelManager

batch_status = {
    'is_running': False,
    'progress': 0,
    'message': ''
}

class AnnotationManager:
    """标注任务管理器"""
    
    @staticmethod
    def get_batch_status():
        return batch_status

    @staticmethod
    def start_batch_annotation(project_path, dataset_name, split, model_path, conf, max_det, batch_size, iou_thresh):
        """启动批量自动标注"""
        if batch_status['is_running']:
            return {'success': False, 'error': '已有批量标注任务正在运行'}
            
        batch_status.update({'is_running': True, 'progress': 0, 'message': '初始化...'})
        
        def run_batch():
            try:
                from ultralytics import YOLO
                # 获取模型
                if model_path:
                    model = YOLO(model_path)
                else:
                    model = ModelManager.get_auto_annotate_model(project_path, prefer_project_best=True)
                    
                if model is None:
                    raise ValueError('模型不可用')

                ds_root = os.path.join(project_path, 'training', dataset_name)
                img_dir = os.path.join(ds_root, split, 'images')
                lbl_dir = os.path.join(ds_root, 'auto_labels', split)
                os.makedirs(lbl_dir, exist_ok=True)
                
                images = []
                for root, _, fs in os.walk(img_dir):
                    for f in fs:
                        if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                            images.append(os.path.join(root, f))
                images.sort()
                
                total = len(images)
                batch_status.update({'is_running': True, 'progress': 0, 'message': '执行批量自动标注...'})
                
                added = 0
                pending = 0
                
                def to_lbl(p):
                    rel = os.path.relpath(p, img_dir)
                    return os.path.join(lbl_dir, os.path.splitext(rel)[0] + '.txt')
                    
                # 批量推理
                for i in range(0, len(images), batch_size):
                    batch = images[i:i+batch_size]
                    try:
                        results = model.predict(batch, conf=conf, max_det=max_det, verbose=False)
                    except Exception:
                        continue
                        
                    for bi, res in enumerate(results):
                        img_path = batch[bi]
                        auto_lbl_path = to_lbl(img_path)
                        boxes = []
                        try:
                            for b in res.boxes:
                                xyxy = b.xyxy[0].tolist()
                                cls = int(b.cls.item()) if hasattr(b, 'cls') else 0
                                boxes.append({'class': cls, 'x1': xyxy[0], 'y1': xyxy[1], 'x2': xyxy[2], 'y2': xyxy[3]})
                        except Exception:
                            boxes = []
                            
                        if not boxes:
                            continue
                            
                        # 写入到 auto_labels（不修改人工 labels）
                        try:
                            from PIL import Image
                            with Image.open(img_path) as im:
                                w, h = im.size
                        except Exception:
                            w, h = 1, 1
                            
                        # 读取已有人工与自动标签用于去重
                        def _read_yolo(file_path):
                            arr = []
                            if not os.path.exists(file_path):
                                return arr
                            try:
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    for ln in f:
                                        parts = ln.strip().split()
                                        if len(parts) >= 5:
                                            cid = int(float(parts[0]))
                                            cx = float(parts[1]) * w
                                            cy = float(parts[2]) * h
                                            ww = float(parts[3]) * w
                                            hh = float(parts[4]) * h
                                            x1 = max(0.0, cx - ww/2)
                                            y1 = max(0.0, cy - hh/2)
                                            x2 = min(float(w), cx + ww/2)
                                            y2 = min(float(h), cy + hh/2)
                                            arr.append({'class': cid, 'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2})
                            except Exception:
                                return arr
                            return arr
                            
                        manual_lbl = os.path.join(ds_root, 'labels', split, os.path.splitext(os.path.relpath(img_path, img_dir))[0] + '.txt')
                        exist_manual = _read_yolo(manual_lbl)
                        exist_auto = _read_yolo(auto_lbl_path)
                        
                        def _iou(a, b):
                            ix1 = max(a['x1'], b['x1']); iy1 = max(a['y1'], b['y1'])
                            ix2 = min(a['x2'], b['x2']); iy2 = min(a['y2'], b['y2'])
                            iw = max(0.0, ix2 - ix1); ih = max(0.0, iy2 - iy1)
                            inter = iw * ih
                            area_a = max(0.0, (a['x2']-a['x1'])) * max(0.0, (a['y2']-a['y1']))
                            area_b = max(0.0, (b['x2']-b['x1'])) * max(0.0, (b['y2']-b['y1']))
                            union = area_a + area_b - inter + 1e-6
                            return inter / union
                            
                        filtered = []
                        for l in boxes:
                            dup = False
                            for e in exist_manual:
                                if e['class'] == l['class'] and _iou(e, l) >= iou_thresh:
                                    dup = True; break
                            if not dup:
                                for e in exist_auto:
                                    if e['class'] == l['class'] and _iou(e, l) >= iou_thresh:
                                        dup = True; break
                            if not dup:
                                filtered.append(l)
                                
                        if not filtered:
                            continue
                            
                        lines = []
                        # 读取已有 auto 标签（允许追加）
                        if os.path.exists(auto_lbl_path):
                            try:
                                with open(auto_lbl_path, 'r', encoding='utf-8') as f:
                                    lines = [ln.strip() for ln in f if ln.strip()]
                            except Exception:
                                lines = []
                                
                        # 追加自动标注
                        for l in filtered:
                            cx = ((l['x1'] + l['x2']) / 2.0) / w
                            cy = ((l['y1'] + l['y2']) / 2.0) / h
                            ww = (l['x2'] - l['x1']) / w
                            hh = (l['y2'] - l['y1']) / h
                            lines.append(f"{l['class']} {cx:.6f} {cy:.6f} {ww:.6f} {hh:.6f}")
                            
                        os.makedirs(os.path.dirname(auto_lbl_path), exist_ok=True)
                        try:
                            with open(auto_lbl_path, 'w', encoding='utf-8') as f:
                                f.write('\n'.join(lines))
                            added += len(filtered)
                            pending += 1
                        except Exception:
                            pass
                            
                    batch_status['progress'] = int((i + len(batch)) / total * 100) if total else 100
                    
                batch_status.update({'is_running': False, 'message': '完成'})
                
            except Exception as e:
                batch_status.update({'is_running': False, 'message': f'出错: {str(e)}'})
                print(f"Batch annotation error: {e}")

        thread = threading.Thread(target=run_batch)
        thread.daemon = True
        thread.start()
        
        return {'success': True, 'message': '批量自动标注已启动'}
