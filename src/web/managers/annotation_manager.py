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
    'message': '',
    'added': 0,
    'pending': 0
}

_openvino_cache = {}

def _pick_openvino_xml(path):
    if not path:
        return None
    if os.path.isfile(path) and path.lower().endswith('.xml'):
        return os.path.abspath(path)
    if os.path.isdir(path):
        cand = os.path.join(path, 'best.xml')
        if os.path.exists(cand):
            return os.path.abspath(cand)
        xmls = []
        for r, _, fs in os.walk(path):
            for f in fs:
                if f.lower().endswith('.xml'):
                    xmls.append(os.path.abspath(os.path.join(r, f)))
        if not xmls:
            return None
        xmls.sort(key=lambda p: (0 if os.path.basename(p) == 'best.xml' else 1, len(p), p))
        return xmls[0]
    return None

def _xywh_to_xyxy(xywh):
    x, y, w, h = xywh
    return (x - w / 2.0, y - h / 2.0, x + w / 2.0, y + h / 2.0)

def _box_iou_xyxy(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    return inter / (area_a + area_b - inter + 1e-6)

def _nms_xyxy(boxes, scores, iou_thresh, max_det):
    if not boxes:
        return []
    order = sorted(range(len(boxes)), key=lambda i: scores[i], reverse=True)
    keep = []
    for i in order:
        if len(keep) >= max_det:
            break
        ok = True
        for ki in keep:
            if _box_iou_xyxy(boxes[i], boxes[ki]) >= iou_thresh:
                ok = False
                break
        if ok:
            keep.append(i)
    return keep

def _parse_openvino_metadata(xml_path):
    try:
        import yaml
    except Exception:
        return {}
    try:
        meta = os.path.join(os.path.dirname(xml_path), 'metadata.yaml')
        if not os.path.exists(meta):
            return {}
        with open(meta, 'r', encoding='utf-8') as f:
            y = yaml.safe_load(f) or {}
        names = y.get('names')
        if isinstance(names, dict):
            nc = len(names)
        elif isinstance(names, list):
            nc = len(names)
        else:
            nc = None
        imgsz = y.get('imgsz')
        if isinstance(imgsz, (list, tuple)) and len(imgsz) == 2:
            ih, iw = int(imgsz[0]), int(imgsz[1])
        else:
            ih, iw = None, None
        return {'nc': nc, 'img_h': ih, 'img_w': iw}
    except Exception:
        return {}

def _load_openvino(xml_path):
    key = os.path.abspath(xml_path)
    cached = _openvino_cache.get(key)
    if cached:
        return cached
    try:
        from openvino.runtime import Core
    except Exception as e:
        raise RuntimeError("OpenVINO 运行时不可用，请安装 openvino 包") from e
    core = Core()
    ov_model = core.read_model(model=key)
    compiled = core.compile_model(model=ov_model, device_name="CPU")
    meta = _parse_openvino_metadata(key)
    _openvino_cache[key] = (compiled, meta)
    return compiled, meta

def _letterbox_pil(im, new_w, new_h, color=114):
    from PIL import Image
    w0, h0 = im.size
    r = min(new_w / w0, new_h / h0)
    rw = int(round(w0 * r))
    rh = int(round(h0 * r))
    resized = im.resize((rw, rh), Image.BILINEAR)
    canvas = Image.new('RGB', (new_w, new_h), (color, color, color))
    pad_w = (new_w - rw) // 2
    pad_h = (new_h - rh) // 2
    canvas.paste(resized, (pad_w, pad_h))
    return canvas, r, pad_w, pad_h, w0, h0

def _openvino_predict_boxes(xml_path, image_paths, conf, max_det, nms_iou=0.45):
    import numpy as np
    from PIL import Image

    compiled, meta = _load_openvino(xml_path)
    nc = meta.get('nc')

    inp = compiled.inputs[0]
    try:
        in_shape = list(inp.shape)
    except Exception:
        in_shape = []
    if len(in_shape) == 4:
        try:
            bdim = int(in_shape[0])
        except Exception:
            bdim = None
        if bdim == 1 and len(image_paths) > 1:
            out = []
            for p in image_paths:
                out.extend(_openvino_predict_boxes(xml_path, [p], conf=conf, max_det=max_det, nms_iou=nms_iou))
            return out
    in_h = None
    in_w = None
    if len(in_shape) == 4:
        in_h = int(in_shape[2]) if str(in_shape[2]).isdigit() else None
        in_w = int(in_shape[3]) if str(in_shape[3]).isdigit() else None
    if not in_h or not in_w:
        in_h = int(meta.get('img_h') or 640)
        in_w = int(meta.get('img_w') or 640)

    batch = []
    infos = []
    for p in image_paths:
        with Image.open(p) as im:
            im = im.convert('RGB')
            lb, r, pad_w, pad_h, w0, h0 = _letterbox_pil(im, in_w, in_h)
            arr = np.asarray(lb, dtype=np.float32) / 255.0
            arr = np.transpose(arr, (2, 0, 1))
            batch.append(arr)
            infos.append((r, pad_w, pad_h, w0, h0))
    input_data = np.stack(batch, axis=0)

    req = compiled.create_infer_request()
    try:
        req.infer({compiled.inputs[0]: input_data})
    except Exception:
        req.infer({0: input_data})

    outs = []
    for oi in range(len(compiled.outputs)):
        try:
            outs.append(np.array(req.get_output_tensor(oi).data))
        except Exception:
            try:
                outs.append(np.array(req.get_tensor(compiled.outputs[oi]).data))
            except Exception:
                pass
    if not outs:
        raise RuntimeError("OpenVINO 推理未返回输出")

    pred = outs[0]
    if pred.ndim == 2:
        pred = pred[None, ...]

    if pred.ndim == 3:
        b, d1, d2 = pred.shape
        if d1 <= 256 and d2 > d1:
            pred = np.transpose(pred, (0, 2, 1))
    else:
        raise RuntimeError(f"OpenVINO 输出维度不支持: {pred.shape}")

    results = []
    for bi in range(pred.shape[0]):
        p = pred[bi]
        r, pad_w, pad_h, w0, h0 = infos[bi]

        attrs = p.shape[1]
        if nc is None:
            nc_guess_1 = attrs - 4
            nc_guess_2 = attrs - 5
            if nc_guess_2 > 0 and nc_guess_2 < 200:
                nc = nc_guess_2
            elif nc_guess_1 > 0 and nc_guess_1 < 200:
                nc = nc_guess_1
            else:
                nc = max(1, attrs - 4)

        if attrs == nc + 4:
            cls_scores = p[:, 4:]
            cls_ids = np.argmax(cls_scores, axis=1)
            cls_confs = cls_scores[np.arange(len(p)), cls_ids]
            scores = cls_confs
            xywh = p[:, :4]
        elif attrs == nc + 5:
            obj = p[:, 4]
            cls_scores = p[:, 5:]
            cls_ids = np.argmax(cls_scores, axis=1)
            cls_confs = cls_scores[np.arange(len(p)), cls_ids]
            scores = obj * cls_confs
            xywh = p[:, :4]
        else:
            cls_scores = p[:, 4:]
            cls_ids = np.argmax(cls_scores, axis=1)
            cls_confs = cls_scores[np.arange(len(p)), cls_ids]
            scores = cls_confs
            xywh = p[:, :4]

        keep_mask = scores >= float(conf)
        if not np.any(keep_mask):
            results.append([])
            continue
        xywh = xywh[keep_mask]
        cls_ids = cls_ids[keep_mask]
        scores = scores[keep_mask]

        m = float(np.max(xywh)) if xywh.size else 0.0
        if m <= 1.5:
            xywh = xywh.copy()
            xywh[:, 0] *= in_w
            xywh[:, 1] *= in_h
            xywh[:, 2] *= in_w
            xywh[:, 3] *= in_h

        boxes_xyxy = np.stack([np.array(_xywh_to_xyxy(v), dtype=np.float32) for v in xywh], axis=0)
        boxes_xyxy[:, [0, 2]] -= float(pad_w)
        boxes_xyxy[:, [1, 3]] -= float(pad_h)
        boxes_xyxy /= float(r)
        boxes_xyxy[:, [0, 2]] = np.clip(boxes_xyxy[:, [0, 2]], 0.0, float(w0))
        boxes_xyxy[:, [1, 3]] = np.clip(boxes_xyxy[:, [1, 3]], 0.0, float(h0))

        out_boxes = []
        for cls in np.unique(cls_ids):
            idxs = np.where(cls_ids == cls)[0]
            cls_boxes = [tuple(map(float, boxes_xyxy[j])) for j in idxs]
            cls_scores = [float(scores[j]) for j in idxs]
            keep = _nms_xyxy(cls_boxes, cls_scores, float(nms_iou), int(max_det))
            for k in keep:
                bx = cls_boxes[k]
                out_boxes.append({
                    'class': int(cls),
                    'x1': float(bx[0]),
                    'y1': float(bx[1]),
                    'x2': float(bx[2]),
                    'y2': float(bx[3]),
                    'conf': float(cls_scores[k])
                })
        out_boxes.sort(key=lambda b: b.get('conf', 0.0), reverse=True)
        results.append(out_boxes[: int(max_det)])
    return results

class AnnotationManager:
    """标注任务管理器"""
    
    @staticmethod
    def get_batch_status():
        return batch_status

    @staticmethod
    def auto_annotate_image(project_path, image_path, model_path=None, conf=0.25, max_det=200):
        ov_xml = _pick_openvino_xml(model_path) if model_path else None
        if ov_xml:
            res = _openvino_predict_boxes(ov_xml, [image_path], conf=float(conf), max_det=int(max_det))
            return res[0] if res else []
        from ultralytics import YOLO
        if model_path:
            model = YOLO(model_path)
        else:
            model = ModelManager.get_auto_annotate_model(project_path, prefer_project_best=True)
        if model is None:
            raise ValueError('模型不可用')
        results = model.predict(image_path, conf=float(conf), max_det=int(max_det), verbose=False)
        boxes = []
        for r in results:
            for b in r.boxes:
                xyxy = b.xyxy[0].tolist()
                cls = int(b.cls.item()) if hasattr(b, 'cls') else 0
                boxes.append({'class': cls, 'x1': xyxy[0], 'y1': xyxy[1], 'x2': xyxy[2], 'y2': xyxy[3]})
        return boxes

    @staticmethod
    def start_batch_annotation(project_path, dataset_name, split, model_path, conf, max_det, batch_size, iou_thresh):
        """启动批量自动标注"""
        if batch_status['is_running']:
            return {'success': False, 'error': '已有批量标注任务正在运行'}
            
        batch_status.update({
            'is_running': True, 
            'progress': 0, 
            'message': '初始化...',
            'added': 0,
            'pending': 0
        })
        
        def run_batch():
            try:
                model = None
                ov_xml = _pick_openvino_xml(model_path) if model_path else None
                use_openvino = bool(ov_xml)
                if not use_openvino:
                    from ultralytics import YOLO
                    if model_path:
                        model = YOLO(model_path)
                    else:
                        model = ModelManager.get_auto_annotate_model(project_path, prefer_project_best=True)
                    
                if model is None:
                    if use_openvino:
                        _load_openvino(ov_xml)
                    else:
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
                    if use_openvino:
                        results = _openvino_predict_boxes(ov_xml, batch, conf=conf, max_det=max_det)
                    else:
                        try:
                            results = model.predict(batch, conf=conf, max_det=max_det, verbose=False)
                        except Exception as e:
                            batch_status.update({'is_running': False, 'message': f'出错: {str(e)}'})
                            return
                        
                    for bi, res in enumerate(results):
                        img_path = batch[bi]
                        auto_lbl_path = to_lbl(img_path)
                        boxes = []
                        if use_openvino:
                            try:
                                boxes = [
                                    {'class': int(b.get('class', 0)), 'x1': float(b['x1']), 'y1': float(b['y1']), 'x2': float(b['x2']), 'y2': float(b['y2'])}
                                    for b in (res or [])
                                    if all(k in b for k in ('x1', 'y1', 'x2', 'y2'))
                                ]
                            except Exception:
                                boxes = []
                        else:
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
                    batch_status.update({'added': added, 'pending': pending})
                    
                batch_status.update({
                    'is_running': False, 
                    'message': '完成',
                    'added': added,
                    'pending': pending
                })
                
            except Exception as e:
                batch_status.update({'is_running': False, 'message': f'出错: {str(e)}'})
                print(f"Batch annotation error: {e}")

        thread = threading.Thread(target=run_batch)
        thread.daemon = True
        thread.start()
        
        return {'success': True, 'message': '批量自动标注已启动'}
