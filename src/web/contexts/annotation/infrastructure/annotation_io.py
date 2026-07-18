"""处理标注文件、图片上下文和待标注列表的读写。"""

import os

from contexts.dataset.infrastructure.dataset_repository import resolve_project_dataset_root
from contexts.dataset.infrastructure.dataset_layout import (
    build_label_relpath,
    get_dataset_auto_labels_dir,
    get_dataset_images_dir,
    get_dataset_labels_dir,
)
from shared.utils.media_constants import IMAGE_FILE_EXTENSIONS
from shared.utils.path_utils import build_file_items, is_within_path, resolve_storage_path, slice_items
from shared.utils.value_utils import require_present
from shared.utils.yolo_utils import parse_yolo_class_id


def get_dataset_root(project_path, dataset_name):
    """解析并校验标注所属的数据集根目录。"""
    ds_root = resolve_project_dataset_root(project_path, dataset_name=dataset_name)
    if not ds_root:
        raise ValueError("数据集不存在")
    return ds_root


def resolve_dataset_image_context(project_path, dataset_name, split, image_ref):
    """解析图片路径以及对应的人工和自动标签路径。"""
    image_path = resolve_storage_path(image_ref)
    require_present(image_path=image_path)

    ds_root = get_dataset_root(project_path, dataset_name)
    img_dir = get_dataset_images_dir(ds_root, split)
    if not is_within_path(image_path, img_dir):
        raise ValueError("image_path 非法")
    if not os.path.isfile(image_path):
        raise ValueError("图片不存在")

    rel = os.path.relpath(image_path, img_dir)
    rel_noext = os.path.splitext(rel)[0]
    manual_dir = get_dataset_labels_dir(ds_root, split)
    auto_dir = get_dataset_auto_labels_dir(ds_root, split)
    return {
        "dataset_root": ds_root,
        "image_path": image_path,
        "image_dir": img_dir,
        "relative_path": rel,
        "relative_noext": rel_noext,
        "manual_dir": manual_dir,
        "auto_dir": auto_dir,
        "manual_label_path": os.path.join(manual_dir, build_label_relpath(rel_noext)),
        "auto_label_path": os.path.join(auto_dir, build_label_relpath(rel_noext)),
    }


def get_image_size(image_path):
    """读取图片的宽高尺寸。"""
    try:
        from PIL import Image

        with Image.open(image_path) as image:
            return image.size
    except Exception as exc:
        raise ValueError("无法读取图片尺寸") from exc


def get_image_size_fallback(image_path):
    """优先用 PIL、失败后退回 cv2 获取图片尺寸。"""
    try:
        return get_image_size(image_path)
    except Exception:
        try:
            import cv2

            image = cv2.imread(image_path)
            if image is not None and getattr(image, "shape", None) is not None:
                height, width = image.shape[:2]
                return width, height
        except Exception:
            pass
    return 1, 1


def encode_yolo_lines(labels, width, height):
    """把矩形框列表编码为 YOLO 文本行。"""
    lines = []
    for item in labels or []:
        cls = int(item.get("class", 0))
        x1 = float(item["x1"])
        y1 = float(item["y1"])
        x2 = float(item["x2"])
        y2 = float(item["y2"])
        cx = ((x1 + x2) / 2.0) / width
        cy = ((y1 + y2) / 2.0) / height
        ww = (x2 - x1) / width
        hh = (y2 - y1) / height
        lines.append(f"{cls} {cx:.6f} {cy:.6f} {ww:.6f} {hh:.6f}")
    return lines


def decode_yolo_file(label_path, width, height):
    """把 YOLO 标签文件解码为像素坐标框。"""
    boxes = []
    if not os.path.exists(label_path):
        return boxes
    try:
        with open(label_path, "r", encoding="utf-8") as handle:
            for line in handle:
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                cls = parse_yolo_class_id(parts[0])
                cx = float(parts[1]) * width
                cy = float(parts[2]) * height
                ww = float(parts[3]) * width
                hh = float(parts[4]) * height
                x1 = max(0.0, cx - ww / 2)
                y1 = max(0.0, cy - hh / 2)
                x2 = min(float(width), cx + ww / 2)
                y2 = min(float(height), cy + hh / 2)
                boxes.append({"class": cls, "x1": x1, "y1": y1, "x2": x2, "y2": y2})
    except Exception:
        return []
    return boxes
def list_missing_annotations(project_path, dataset_name, split, offset=0, limit=50):
    """列出缺少人工标签或空标签的图片。"""
    ds_root = get_dataset_root(project_path, dataset_name)
    img_dir = get_dataset_images_dir(ds_root, split)
    lbl_dir = get_dataset_labels_dir(ds_root, split)
    missing = []
    for root, _, files in os.walk(img_dir):
        for file_name in files:
            if not file_name.lower().endswith(IMAGE_FILE_EXTENSIONS):
                continue
            image_path = os.path.join(root, file_name)
            rel = os.path.relpath(image_path, img_dir)
            label_path = os.path.join(lbl_dir, build_label_relpath(rel))
            if not os.path.exists(label_path) or os.path.getsize(label_path) == 0:
                missing.append(image_path)
    return slice_items(build_file_items(missing), offset=offset, limit=limit)


def list_pending_auto_annotations(project_path, dataset_name, split, offset=0, limit=50):
    """列出存在自动标签待确认的图片。"""
    ds_root = get_dataset_root(project_path, dataset_name)
    img_dir = get_dataset_images_dir(ds_root, split)
    auto_dir = get_dataset_auto_labels_dir(ds_root, split)
    items = []
    for root, _, files in os.walk(img_dir):
        for file_name in files:
            if not file_name.lower().endswith(IMAGE_FILE_EXTENSIONS):
                continue
            image_path = os.path.join(root, file_name)
            rel = os.path.relpath(image_path, img_dir)
            auto_label_path = os.path.join(auto_dir, build_label_relpath(rel))
            if os.path.exists(auto_label_path):
                items.append(image_path)
    return slice_items(build_file_items(items), offset=offset, limit=limit)
