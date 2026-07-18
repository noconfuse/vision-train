"""定义标准数据集目录协议及相关路径构造函数。"""

import os

from shared.utils.path_utils import normalize_path_ref
from shared.utils.media_constants import DATASET_SPLITS

DATASET_SPLIT_TRAIN = "train"
DATASET_SPLIT_VAL = "val"
DATASET_SPLIT_TEST = "test"
STANDARD_DATASET_SPLITS = DATASET_SPLITS
DATASET_IMAGES_DIRNAME = "images"
DATASET_LABELS_DIRNAME = "labels"
DATASET_AUTO_LABELS_DIRNAME = "auto_labels"


def get_dataset_split_dir(dataset_root, split):
    """拼接某个 split 的根目录路径。"""
    return os.path.join(dataset_root, str(split))


def normalize_standard_dataset_splits(splits):
    """把 split 参数规范为标准 split 列表。"""
    if splits is None:
        return list(STANDARD_DATASET_SPLITS)
    if isinstance(splits, list):
        normalized = [str(split).strip() for split in splits if str(split).strip()]
        return normalized or list(STANDARD_DATASET_SPLITS)
    raise ValueError("splits 参数无效")


def get_dataset_images_dir(dataset_root, split):
    """返回某个 split 的图片目录。"""
    return os.path.join(get_dataset_split_dir(dataset_root, split), DATASET_IMAGES_DIRNAME)


def get_dataset_labels_dir(dataset_root, split):
    """返回某个 split 的标签目录。"""
    return os.path.join(get_dataset_split_dir(dataset_root, split), DATASET_LABELS_DIRNAME)


def get_dataset_auto_labels_dir(dataset_root, split):
    """返回某个 split 的自动标注目录。"""
    return os.path.join(dataset_root, DATASET_AUTO_LABELS_DIRNAME, str(split))


def get_dataset_root_images_dir(dataset_root):
    """返回旧布局下的根级 images 目录。"""
    return os.path.join(dataset_root, DATASET_IMAGES_DIRNAME)


def get_dataset_root_labels_dir(dataset_root):
    """返回旧布局下的根级 labels 目录。"""
    return os.path.join(dataset_root, DATASET_LABELS_DIRNAME)


def get_dataset_legacy_labels_dir(dataset_root, split):
    """返回兼容旧布局的 split 标签目录。"""
    return os.path.join(get_dataset_root_labels_dir(dataset_root), str(split))


def build_dataset_yaml_image_ref(split):
    """生成写入 dataset.yaml 的图片相对引用。"""
    return f"{split}/{DATASET_IMAGES_DIRNAME}"
def strip_dataset_images_ref(value):
    """去掉图片引用末尾的 images 片段。"""
    normalized = normalize_path_ref(value)
    if normalized.endswith(f"/{DATASET_IMAGES_DIRNAME}"):
        normalized = normalized[: -(len(DATASET_IMAGES_DIRNAME) + 1)]
    elif normalized == DATASET_IMAGES_DIRNAME:
        normalized = ""
    return normalized.strip("/")


def infer_label_path_from_image_path(image_path):
    """根据图片路径推断对应标签路径。"""
    normalized = os.path.normpath(str(image_path or ""))
    if not normalized:
        return ""
    parts = normalized.split(os.sep)
    if DATASET_IMAGES_DIRNAME not in parts:
        return ""
    try:
        image_dir_index = len(parts) - 1 - parts[::-1].index(DATASET_IMAGES_DIRNAME)
    except ValueError:
        return ""
    parts[image_dir_index] = DATASET_LABELS_DIRNAME
    parts[-1] = os.path.splitext(parts[-1])[0] + ".txt"
    return os.sep.join(parts)


def resolve_existing_label_path_for_image(image_path):
    """解析图片已存在的标签文件路径。"""
    candidate = infer_label_path_from_image_path(image_path)
    if candidate and os.path.exists(candidate):
        return candidate
    parent = os.path.dirname(str(image_path or ""))
    grandparent = os.path.dirname(parent)
    if os.path.basename(parent) != DATASET_IMAGES_DIRNAME:
        return ""
    candidate = os.path.join(grandparent, DATASET_LABELS_DIRNAME, os.path.splitext(os.path.basename(str(image_path or "")))[0] + ".txt")
    return candidate if os.path.exists(candidate) else ""


def build_label_relpath(image_relpath):
    """把图片相对路径转换为标签相对路径。"""
    return os.path.splitext(str(image_relpath or ""))[0] + ".txt"
