"""处理标注协议共用的文件编解码与图片上下文解析。"""

import os

from contexts.dataset.infrastructure.dataset_repository import resolve_project_dataset_root
from contexts.dataset.infrastructure.dataset_layout import (
    extract_classification_class_name,
    build_label_relpath,
    get_dataset_auto_labels_dir,
    get_dataset_labels_dir,
    get_dataset_split_dir,
    get_dataset_split_content_dir,
    get_dataset_unlabeled_dir,
)
from contexts.dataset.infrastructure.dataset_schema import load_dataset_names
from contexts.dataset.infrastructure.dataset_task_type import load_dataset_vision_task_type
from protocols.vision_task_type import VISION_TASK_TYPE_CLASSIFY
from shared.utils.path_utils import is_within_path, resolve_storage_path
from shared.utils.value_utils import require_present
from shared.utils.yolo_utils import parse_yolo_class_id


def get_dataset_root(project_path, dataset_name):
    """解析并校验标注所属的数据集根目录。"""
    ds_root = resolve_project_dataset_root(project_path, dataset_name=dataset_name)
    if not ds_root:
        raise ValueError("数据集不存在")
    return ds_root


def resolve_dataset_image_context(project_path, dataset_name, split, image_ref):
    """解析图片路径、标签路径以及分类目录上下文。"""
    image_path = resolve_storage_path(image_ref)
    require_present(image_path=image_path)

    ds_root = get_dataset_root(project_path, dataset_name)
    return build_dataset_image_context(ds_root, split, image_path)


def build_dataset_image_context(dataset_root, split, image_path):
    """基于已知数据集根目录和图片路径解析标注上下文。"""
    image_path = resolve_storage_path(image_path)
    require_present(image_path=image_path)
    vision_task_type = load_dataset_vision_task_type(dataset_root)
    if not os.path.isfile(image_path):
        raise ValueError("图片不存在")

    split_dir = get_dataset_split_dir(dataset_root, split)
    unlabeled_dir = get_dataset_unlabeled_dir(dataset_root, split)
    auto_dir = get_dataset_auto_labels_dir(dataset_root, split)
    manual_dir = get_dataset_labels_dir(dataset_root, split)
    img_dir = get_dataset_split_content_dir(dataset_root, split, vision_task_type)
    class_names = load_dataset_names(dataset_root)

    if vision_task_type == VISION_TASK_TYPE_CLASSIFY:
        is_unlabeled = is_within_path(image_path, unlabeled_dir)
        if is_unlabeled:
            rel = os.path.relpath(image_path, unlabeled_dir)
            rel_noext = os.path.splitext(rel)[0]
            class_name = ""
            sample_relative_path = rel
            auto_label_path = os.path.join(auto_dir, "unlabeled", build_label_relpath(rel_noext))
        else:
            if not is_within_path(image_path, split_dir):
                raise ValueError("image_path 非法")
            rel = os.path.relpath(image_path, split_dir)
            rel_noext = os.path.splitext(rel)[0]
            class_name = extract_classification_class_name(rel)
            sample_relative_path = rel.split(os.sep, 1)[1] if class_name and os.sep in rel else os.path.basename(image_path)
            auto_label_path = ""
        return {
            "dataset_root": dataset_root,
            "split": split,
            "vision_task_type": vision_task_type,
            "image_path": image_path,
            "image_dir": unlabeled_dir if is_unlabeled else split_dir,
            "relative_path": rel,
            "relative_noext": rel_noext,
            "sample_relative_path": sample_relative_path,
            "manual_dir": manual_dir,
            "auto_dir": auto_dir,
            "manual_label_path": "",
            "auto_label_path": auto_label_path,
            "class_names": class_names,
            "class_name": class_name,
            "is_unlabeled": is_unlabeled,
            "split_dir": split_dir,
            "unlabeled_dir": unlabeled_dir,
        }

    if not is_within_path(image_path, img_dir):
        raise ValueError("image_path 非法")
    if not os.path.isfile(image_path):
        raise ValueError("图片不存在")

    rel = os.path.relpath(image_path, img_dir)
    rel_noext = os.path.splitext(rel)[0]
    return {
        "dataset_root": dataset_root,
        "split": split,
        "vision_task_type": vision_task_type,
        "image_path": image_path,
        "image_dir": img_dir,
        "relative_path": rel,
        "relative_noext": rel_noext,
        "manual_dir": manual_dir,
        "auto_dir": auto_dir,
        "manual_label_path": os.path.join(manual_dir, build_label_relpath(rel_noext)),
        "auto_label_path": os.path.join(auto_dir, build_label_relpath(rel_noext)),
        "class_names": class_names,
        "class_name": extract_classification_class_name(rel),
        "is_unlabeled": False,
        "split_dir": split_dir,
        "unlabeled_dir": unlabeled_dir,
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


def encode_detect_lines(labels, width, height):
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


def decode_detect_file(label_path, width, height):
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


def decode_classification_file(label_path):
    """把分类标签文件解码为单个类别 id。"""
    if not os.path.exists(label_path):
        return None
    try:
        with open(label_path, "r", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                return parse_yolo_class_id(text.split()[0])
    except Exception:
        return None
    return None


def encode_classification_lines(annotation):
    """把图像级分类标注编码为单行类别 id。"""
    class_id = annotation.get("class_id") if isinstance(annotation, dict) else None
    if class_id is None or class_id == "":
        return []
    return [str(int(class_id))]


def resolve_classification_class_id(context):
    """从分类样本当前目录推导类别 id。"""
    class_name = context.get("class_name") or ""
    class_names = context.get("class_names") or []
    try:
        return next(index for index, name in enumerate(class_names) if str(name) == class_name)
    except StopIteration:
        return None
