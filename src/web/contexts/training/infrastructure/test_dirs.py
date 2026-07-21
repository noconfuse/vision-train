"""枚举数据集中可用于测试推理的评估目录。"""

import os

from contexts.dataset.infrastructure.dataset_repository import resolve_project_dataset_root
from constants.media import EVAL_SPLITS, IMAGE_FILE_EXTENSIONS
from shared.utils.value_utils import require_present


def _count_split_images(split_root):
    """统计一个 split 目录下可推理的图片数量。"""
    for candidate in (os.path.join(split_root, "images"), split_root):
        if os.path.isdir(candidate):
            return sum(1 for name in os.listdir(candidate) if name.lower().endswith(IMAGE_FILE_EXTENSIONS))
    return 0


def list_training_test_dirs(project_path, dataset_name):
    """列出数据集可用的测试评估子目录。"""
    require_present(project_path=project_path, dataset_name=dataset_name)
    base = resolve_project_dataset_root(project_path, dataset_name=dataset_name)
    result = []
    if not os.path.isdir(base):
        return result
    for split_name in EVAL_SPLITS:
        split_root = os.path.join(base, split_name)
        if os.path.isdir(split_root):
            result.append({"subdir": split_name, "name": split_name, "image_count": _count_split_images(split_root)})
    return result
