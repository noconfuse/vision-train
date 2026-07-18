"""提供批量自动标注过程中的路径、框结果和标签追加辅助逻辑。"""

import os

from contexts.annotation.infrastructure.annotation_io import decode_yolo_file, encode_yolo_lines
from shared.utils.media_constants import IMAGE_FILE_EXTENSIONS
from shared.utils.path_utils import is_within_path
from shared.utils.yolo_utils import read_yolo_lines, write_yolo_lines


def list_batch_image_paths(img_dir, image_paths=None):
    """列出批量任务要处理的图片路径。"""
    images = []
    if isinstance(image_paths, list) and image_paths:
        for path in image_paths:
            if not isinstance(path, str) or not path:
                continue
            absolute_path = os.path.realpath(path)
            if not os.path.isfile(absolute_path):
                continue
            if not is_within_path(absolute_path, img_dir):
                continue
            if not absolute_path.lower().endswith(IMAGE_FILE_EXTENSIONS):
                continue
            images.append(absolute_path)
    else:
        for root, _, files in os.walk(img_dir):
            for file_name in files:
                if file_name.lower().endswith(IMAGE_FILE_EXTENSIONS):
                    images.append(os.path.join(root, file_name))
    images.sort()
    return images


def build_auto_label_path(img_dir, auto_label_dir, image_path):
    """根据图片路径推导自动标签文件路径。"""
    rel = os.path.relpath(image_path, img_dir)
    return os.path.join(auto_label_dir, os.path.splitext(rel)[0] + ".txt")


def extract_prediction_boxes(prediction, use_openvino):
    """把不同推理后端的输出统一成框列表。"""
    boxes = []
    if use_openvino:
        try:
            return [
                {
                    "class": int(box.get("class", 0)),
                    "x1": float(box["x1"]),
                    "y1": float(box["y1"]),
                    "x2": float(box["x2"]),
                    "y2": float(box["y2"]),
                }
                for box in (prediction or [])
                if all(key in box for key in ("x1", "y1", "x2", "y2"))
            ]
        except Exception:
            return []

    try:
        for box in prediction.boxes:
            xyxy = box.xyxy[0].tolist()
            cls = int(box.cls.item()) if hasattr(box, "cls") else 0
            boxes.append({"class": cls, "x1": xyxy[0], "y1": xyxy[1], "x2": xyxy[2], "y2": xyxy[3]})
    except Exception:
        return []
    return boxes


def load_existing_manual_boxes(ds_root, split, rel_noext, width, height):
    """读取一张图片已有的人工标注框。"""
    manual_candidates = [
        os.path.join(ds_root, split, "labels", rel_noext + ".txt"),
        os.path.join(ds_root, "labels", split, rel_noext + ".txt"),
    ]
    for candidate in manual_candidates:
        if os.path.exists(candidate):
            return decode_yolo_file(candidate, width, height)
    return []


def append_auto_label_boxes(auto_label_path, boxes, width, height):
    """把新框追加写入自动标签文件。"""
    lines = read_yolo_lines(auto_label_path)
    lines.extend(encode_yolo_lines(boxes, width, height))
    write_yolo_lines(auto_label_path, lines)
    return len(lines)
