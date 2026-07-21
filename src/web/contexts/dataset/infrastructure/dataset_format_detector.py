"""负责识别外部数据集的输入格式。"""

import glob
import os

from constants.media import IMAGE_FILE_EXTENSIONS, ROBOFLOW_CONFIG_FILENAMES
from contexts.dataset.infrastructure.dataset_schema import find_dataset_config
from protocols.vision_task_type import VISION_TASK_TYPE_CLASSIFY, VISION_TASK_TYPE_SET


def _has_glob(root, pattern):
    """判断目录下是否存在匹配的文件模式。"""
    return len(glob.glob(os.path.join(root, pattern))) > 0


def _list_meaningful_entries(root):
    """列出参与协议识别的可见目录项，过滤系统噪音文件。"""
    if not os.path.isdir(root):
        return []
    return [
        entry
        for entry in sorted(os.listdir(root))
        if not entry.startswith("__MACOSX") and not entry.startswith(".")
    ]


def _list_meaningful_dirs(root):
    """列出参与协议识别的可见子目录。"""
    return [entry for entry in _list_meaningful_entries(root) if os.path.isdir(os.path.join(root, entry))]


def _dir_has_images(root):
    """判断目录中是否存在图片文件。"""
    if not os.path.isdir(root):
        return False
    for _, _, files in os.walk(root):
        for filename in files:
            if filename.lower().endswith(IMAGE_FILE_EXTENSIONS):
                return True
    return False


def normalize_import_split_name(name):
    """把外部常见 split 名统一归一为 train/val/test。"""
    text = str(name or "").strip().lower()
    if text in {"train", "training"}:
        return "train"
    if text in {"val", "valid", "validation", "dev"}:
        return "val"
    if text in {"test", "testing"}:
        return "test"
    return ""


def resolve_imagefolder_split_roots(root):
    """识别 `train|val|test/class/*` 形式的分类目录根。"""
    split_dirs = {}
    for entry in _list_meaningful_dirs(root):
        split_name = normalize_import_split_name(entry)
        if not split_name:
            continue
        split_root = os.path.join(root, entry)
        class_dirs = [name for name in _list_meaningful_dirs(split_root) if _dir_has_images(os.path.join(split_root, name))]
        if len(class_dirs) >= 2:
            split_dirs[split_name] = split_root
    return split_dirs if split_dirs else None


def resolve_imagefolder_class_names(root):
    """识别 `class/*` 形式的分类目录根，并返回类别目录名列表。"""
    class_dirs = [name for name in _list_meaningful_dirs(root) if _dir_has_images(os.path.join(root, name))]
    if len(class_dirs) < 2:
        return None
    reserved = {"train", "training", "val", "valid", "validation", "dev", "test", "testing", "images", "labels", "annotations"}
    if any(str(name).strip().lower() in reserved for name in class_dirs):
        return None
    return sorted(class_dirs)


def detect_dataset_format(root, vision_task_type):
    """根据目录协议识别输入数据集格式。"""
    if not os.path.isdir(root):
        return "unknown"
    if vision_task_type not in VISION_TASK_TYPE_SET:
        raise ValueError("vision_task_type 不合法")
    if vision_task_type == VISION_TASK_TYPE_CLASSIFY:
        if resolve_imagefolder_split_roots(root) or resolve_imagefolder_class_names(root):
            return "classification_imagefolder"
    if find_dataset_config(root) is not None:
        return "yolo"
    for rf_name in ROBOFLOW_CONFIG_FILENAMES:
        if os.path.isfile(os.path.join(root, rf_name)):
            return "roboflow"
    if os.path.isdir(os.path.join(root, "annotations")) and _has_glob(root, "annotations/instances_*.json"):
        return "coco"
    if os.path.isdir(os.path.join(root, "Annotations")) and os.path.isdir(os.path.join(root, "JPEGImages")) and _has_glob(root, "Annotations/*.xml"):
        return "voc"
    return "unknown"
