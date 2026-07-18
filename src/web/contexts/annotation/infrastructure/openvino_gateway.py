"""封装 OpenVINO 模型解析、预处理与推理后处理。"""

import os

from contexts.annotation.domain.services import box_iou_xyxy
from contexts.model.infrastructure.model_catalog import load_openvino_metadata

_openvino_cache = {}
def _xywh_to_xyxy(xywh):
    """把中心点格式框转换为角点格式框。"""
    x, y, w, h = xywh
    return (x - w / 2.0, y - h / 2.0, x + w / 2.0, y + h / 2.0)


def _nms_xyxy(boxes, scores, iou_thresh, max_det):
    """对同类候选框执行朴素 NMS。"""
    if not boxes:
        return []
    order = sorted(range(len(boxes)), key=lambda index: scores[index], reverse=True)
    keep = []
    for index in order:
        if len(keep) >= max_det:
            break
        if all(box_iou_xyxy(boxes[index], boxes[kept]) < iou_thresh for kept in keep):
            keep.append(index)
    return keep


def _parse_openvino_metadata(xml_path):
    """读取模型旁路 metadata.yaml 中的推理元信息。"""
    try:
        content = load_openvino_metadata(xml_path)
        names = content.get("names")
        if isinstance(names, dict):
            nc = len(names)
        elif isinstance(names, list):
            nc = len(names)
        else:
            nc = None
        imgsz = content.get("imgsz")
        if isinstance(imgsz, (list, tuple)) and len(imgsz) == 2:
            image_h, image_w = int(imgsz[0]), int(imgsz[1])
        else:
            image_h, image_w = None, None
        return {"nc": nc, "img_h": image_h, "img_w": image_w}
    except Exception:
        return {}


def _load_openvino(xml_path):
    """加载并缓存编译后的 OpenVINO 模型。"""
    key = os.path.abspath(xml_path)
    cached = _openvino_cache.get(key)
    if cached:
        return cached
    try:
        from openvino.runtime import Core
    except Exception as exc:
        raise RuntimeError("OpenVINO 运行时不可用，请安装 openvino 包") from exc
    core = Core()
    ov_model = core.read_model(model=key)
    compiled = core.compile_model(model=ov_model, device_name="CPU")
    meta = _parse_openvino_metadata(key)
    _openvino_cache[key] = (compiled, meta)
    return compiled, meta


def _letterbox_pil(image, new_w, new_h, color=114):
    """按目标尺寸对图片执行 letterbox 预处理。"""
    from PIL import Image

    width, height = image.size
    ratio = min(new_w / width, new_h / height)
    resized_w = int(round(width * ratio))
    resized_h = int(round(height * ratio))
    resized = image.resize((resized_w, resized_h), Image.BILINEAR)
    canvas = Image.new("RGB", (new_w, new_h), (color, color, color))
    pad_w = (new_w - resized_w) // 2
    pad_h = (new_h - resized_h) // 2
    canvas.paste(resized, (pad_w, pad_h))
    return canvas, ratio, pad_w, pad_h, width, height


def predict_openvino_boxes(xml_path, image_paths, conf, max_det, nms_iou=0.45):
    """对图片批次执行 OpenVINO 推理并还原检测框。"""
    import numpy as np
    from PIL import Image

    compiled, meta = _load_openvino(xml_path)
    nc = meta.get("nc")

    inp = compiled.inputs[0]
    try:
        in_shape = list(inp.shape)
    except Exception:
        in_shape = []
    if len(in_shape) == 4:
        try:
            batch_dim = int(in_shape[0])
        except Exception:
            batch_dim = None
        if batch_dim == 1 and len(image_paths) > 1:
            outputs = []
            for image_path in image_paths:
                outputs.extend(predict_openvino_boxes(xml_path, [image_path], conf=conf, max_det=max_det, nms_iou=nms_iou))
            return outputs
    image_h = int(in_shape[2]) if len(in_shape) == 4 and str(in_shape[2]).isdigit() else None
    image_w = int(in_shape[3]) if len(in_shape) == 4 and str(in_shape[3]).isdigit() else None
    if not image_h or not image_w:
        image_h = int(meta.get("img_h") or 640)
        image_w = int(meta.get("img_w") or 640)

    batch = []
    infos = []
    for image_path in image_paths:
        with Image.open(image_path) as image:
            image = image.convert("RGB")
            lb, ratio, pad_w, pad_h, width, height = _letterbox_pil(image, image_w, image_h)
            arr = np.asarray(lb, dtype=np.float32) / 255.0
            arr = np.transpose(arr, (2, 0, 1))
            batch.append(arr)
            infos.append((ratio, pad_w, pad_h, width, height))
    input_data = np.stack(batch, axis=0)

    request = compiled.create_infer_request()
    try:
        request.infer({compiled.inputs[0]: input_data})
    except Exception:
        request.infer({0: input_data})

    outs = []
    for output_index in range(len(compiled.outputs)):
        try:
            outs.append(np.array(request.get_output_tensor(output_index).data))
        except Exception:
            try:
                outs.append(np.array(request.get_tensor(compiled.outputs[output_index]).data))
            except Exception:
                pass
    if not outs:
        raise RuntimeError("OpenVINO 推理未返回输出")

    prediction = outs[0]
    if prediction.ndim == 2:
        prediction = prediction[None, ...]
    if prediction.ndim == 3:
        _, dim1, dim2 = prediction.shape
        if dim1 <= 256 and dim2 > dim1:
            prediction = np.transpose(prediction, (0, 2, 1))
    else:
        raise RuntimeError(f"OpenVINO 输出维度不支持: {prediction.shape}")

    results = []
    for batch_index in range(prediction.shape[0]):
        pred = prediction[batch_index]
        ratio, pad_w, pad_h, width, height = infos[batch_index]

        attrs = pred.shape[1]
        if nc is None:
            nc_guess_1 = attrs - 4
            nc_guess_2 = attrs - 5
            if 0 < nc_guess_2 < 200:
                nc = nc_guess_2
            elif 0 < nc_guess_1 < 200:
                nc = nc_guess_1
            else:
                nc = max(1, attrs - 4)

        if attrs == nc + 4:
            cls_scores = pred[:, 4:]
            cls_ids = np.argmax(cls_scores, axis=1)
            cls_confs = cls_scores[np.arange(len(pred)), cls_ids]
            scores = cls_confs
            xywh = pred[:, :4]
        elif attrs == nc + 5:
            obj = pred[:, 4]
            cls_scores = pred[:, 5:]
            cls_ids = np.argmax(cls_scores, axis=1)
            cls_confs = cls_scores[np.arange(len(pred)), cls_ids]
            scores = obj * cls_confs
            xywh = pred[:, :4]
        else:
            cls_scores = pred[:, 4:]
            cls_ids = np.argmax(cls_scores, axis=1)
            cls_confs = cls_scores[np.arange(len(pred)), cls_ids]
            scores = cls_confs
            xywh = pred[:, :4]

        keep_mask = scores >= float(conf)
        if not np.any(keep_mask):
            results.append([])
            continue
        xywh = xywh[keep_mask]
        cls_ids = cls_ids[keep_mask]
        scores = scores[keep_mask]

        if float(np.max(xywh)) <= 1.5 if xywh.size else False:
            xywh = xywh.copy()
            xywh[:, 0] *= image_w
            xywh[:, 1] *= image_h
            xywh[:, 2] *= image_w
            xywh[:, 3] *= image_h

        boxes_xyxy = np.stack([np.array(_xywh_to_xyxy(value), dtype=np.float32) for value in xywh], axis=0)
        boxes_xyxy[:, [0, 2]] -= float(pad_w)
        boxes_xyxy[:, [1, 3]] -= float(pad_h)
        boxes_xyxy /= float(ratio)
        boxes_xyxy[:, [0, 2]] = np.clip(boxes_xyxy[:, [0, 2]], 0.0, float(width))
        boxes_xyxy[:, [1, 3]] = np.clip(boxes_xyxy[:, [1, 3]], 0.0, float(height))

        out_boxes = []
        for cls in np.unique(cls_ids):
            indices = np.where(cls_ids == cls)[0]
            cls_boxes = [tuple(map(float, boxes_xyxy[index])) for index in indices]
            cls_scores = [float(scores[index]) for index in indices]
            keep = _nms_xyxy(cls_boxes, cls_scores, float(nms_iou), int(max_det))
            for keep_index in keep:
                box = cls_boxes[keep_index]
                out_boxes.append(
                    {
                        "class": int(cls),
                        "x1": float(box[0]),
                        "y1": float(box[1]),
                        "x2": float(box[2]),
                        "y2": float(box[3]),
                        "conf": float(cls_scores[keep_index]),
                    }
                )
        results.append(out_boxes[: int(max_det)])
    return results
