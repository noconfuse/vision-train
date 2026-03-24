import os
import sys
import threading
from datetime import datetime
from typing import List, Dict, Any
from PIL import Image, ImageDraw, ImageFont

# Ensure parent directory is in sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from managers.model_manager import ModelManager

infer_status = {
    'is_running': False,
    'progress': 0,
    'message': '',
    'total': 0,
    'done': 0,
    'results': [],
    'output_dir': None,
    'error': None
}

def _collect_images(root_dir: str) -> List[str]:
    images = []
    for r, _, fs in os.walk(root_dir):
        for f in fs:
            lf = f.lower()
            if lf.endswith(('.jpg', '.jpeg', '.png', '.bmp', '.webp')):
                images.append(os.path.join(r, f))
    images.sort()
    return images

def _draw_predictions(img_path: str, boxes: List[Dict[str, Any]], class_names: Dict[int, str], save_path: str):
    try:
        with Image.open(img_path) as im:
            im = im.convert('RGB')
            draw = ImageDraw.Draw(im)
            try:
                font = ImageFont.truetype("DejaVuSans.ttf", 16)
            except Exception:
                font = ImageFont.load_default()
            palette = [
                (255, 99, 71), (56, 189, 248), (234, 179, 8), (34, 197, 94),
                (168, 85, 247), (244, 63, 94), (59, 130, 246), (16, 185, 129),
                (245, 158, 11), (239, 68, 68)
            ]
            for b in boxes:
                try:
                    x1 = float(b.get('x1', 0))
                    y1 = float(b.get('y1', 0))
                    x2 = float(b.get('x2', 0))
                    y2 = float(b.get('y2', 0))
                    cls_id = int(b.get('class', 0))
                    conf = float(b.get('conf', 0.0))
                    name = class_names.get(cls_id, str(cls_id))
                    base_color = palette[cls_id % len(palette)]
                    color = (base_color[0], base_color[1], base_color[2])
                    draw.rectangle([(x1, y1), (x2, y2)], outline=color, width=3)
                    label = f"{name} {conf:.2f}"
                    try:
                        # Pillow >=8: textbbox
                        bbox = draw.textbbox((0, 0), label, font=font)
                        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                    except Exception:
                        # Fallback
                        tw, th = draw.textsize(label, font=font)
                    bx = max(0, x1)
                    by = max(0, y1 - th - 2)
                    draw.rectangle([(bx, by), (bx + tw + 6, by + th + 4)], fill=(0, 0, 0), outline=color)
                    draw.text((bx + 3, by + 2), label, fill=(255, 255, 255), font=font)
                except Exception:
                    # Keep going even if one box fails to draw
                    continue
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            im.save(save_path, quality=90)
    except Exception:
        # If something goes wrong, try saving original image to keep pipeline going
        try:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with Image.open(img_path) as im:
                im.convert('RGB').save(save_path, quality=90)
        except Exception:
            pass

class InferenceManager:
    @staticmethod
    def get_status():
        return infer_status

    @staticmethod
    def start(project_path: str, test_subdir: str = None, weights_path: str = None, training_dataset: str = None, training_id: str = None, conf: float = 0.25, max_det: int = 200):
        if infer_status['is_running']:
            return {'success': False, 'error': '已有推理任务正在运行'}
        infer_status.update({
            'is_running': True,
            'progress': 0,
            'message': '初始化推理任务...',
            'total': 0,
            'done': 0,
            'results': [],
            'output_dir': None,
            'error': None
        })
        def run_job():
            try:
                base_test = os.path.join(project_path, 'test')
                src_dir = os.path.join(base_test, test_subdir) if test_subdir else base_test
                images = _collect_images(src_dir)
                infer_status['total'] = len(images)
                ts = datetime.now().strftime('%Y%m%d_%H%M%S')
                out_dir = os.path.join(project_path, 'test_infer_outputs', ts)
                infer_status['output_dir'] = out_dir
                # Resolve model
                model = None
                if weights_path and os.path.exists(weights_path):
                    from ultralytics import YOLO
                    model = YOLO(weights_path)
                elif training_dataset and training_id:
                    from managers.training_manager import TrainingManager
                    arts = TrainingManager.get_run_artifacts(project_path, training_dataset, training_id)
                    cands = arts.get('weights') or []
                    choose = None
                    for p in cands:
                        if os.path.basename(p) == 'best.pt':
                            choose = p; break
                    if not choose and cands:
                        choose = cands[0]
                    if choose and os.path.exists(choose):
                        from ultralytics import YOLO
                        model = YOLO(choose)
                if model is None:
                    # fallback: latest project best
                    model = ModelManager.get_auto_annotate_model(project_path, prefer_project_best=True)
                if model is None:
                    infer_status.update({'is_running': False, 'error': '模型不可用', 'message': '模型不可用'})
                    return
                names = {}
                try:
                    names = {int(k): v for k, v in getattr(model, 'names', {}).items()}
                except Exception:
                    names = {}
                # Predict
                for idx, img_path in enumerate(images):
                    try:
                        res = model.predict(img_path, conf=float(conf), max_det=int(max_det), verbose=False)
                        boxes = []
                        for r in res:
                            if getattr(r, 'boxes', None) is not None:
                                for b in r.boxes:
                                    xyxy = b.xyxy[0].tolist()
                                    cls = int(b.cls.item()) if hasattr(b, 'cls') else 0
                                    cf = float(b.conf.item()) if hasattr(b, 'conf') else 0.0
                                    boxes.append({'class': cls, 'x1': float(xyxy[0]), 'y1': float(xyxy[1]), 'x2': float(xyxy[2]), 'y2': float(xyxy[3]), 'conf': cf})
                        rel = os.path.relpath(img_path, src_dir)
                        save_path = os.path.join(out_dir, os.path.splitext(rel)[0] + '_pred.jpg')
                        _draw_predictions(img_path, boxes, names, save_path)
                        infer_status['results'].append({
                            'image': img_path,
                            'pred_image': save_path if os.path.exists(save_path) else None,
                            'boxes': boxes
                        })
                    except Exception as e:
                        infer_status['results'].append({'image': img_path, 'error': str(e), 'boxes': []})
                    finally:
                        infer_status['done'] = idx + 1
                        infer_status['progress'] = int((idx + 1) / max(1, infer_status['total']) * 100)
                        infer_status['message'] = f'推理中 {infer_status["done"]}/{infer_status["total"]}'
                infer_status.update({'is_running': False, 'message': '推理完成'})
            except Exception as e:
                infer_status.update({'is_running': False, 'error': str(e), 'message': '推理出错'})
        th = threading.Thread(target=run_job)
        th.daemon = True
        th.start()
        return {'success': True, 'message': '推理任务已启动'}

    @staticmethod
    def list_test_dirs(project_path: str):
        base_test = os.path.join(project_path, 'test')
        result = []
        if not os.path.isdir(base_test):
            return []
        # Include root as empty subdir
        root_images = _collect_images(base_test)
        result.append({
            'name': '(test 根目录)',
            'subdir': '',
            'image_count': len(root_images)
        })
        for name in sorted(os.listdir(base_test)):
            p = os.path.join(base_test, name)
            if os.path.isdir(p):
                cnt = len(_collect_images(p))
                result.append({'name': name, 'subdir': name, 'image_count': cnt})
        return result
