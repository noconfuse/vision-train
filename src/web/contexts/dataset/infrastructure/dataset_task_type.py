"""维护数据集任务类型的项目内部元数据。"""

import os

from shared.utils.json_utils import load_json_file, save_json_file
from protocols.vision_task_type import VISION_TASK_TYPE_SET

DATASET_TASK_META_FILENAME = ".vision-train.meta.json"


def get_dataset_task_meta_path(dataset_root):
    """返回数据集任务元数据文件路径。"""
    return os.path.join(dataset_root, DATASET_TASK_META_FILENAME)


def require_dataset_vision_task_type(value):
    """校验并返回数据集内部记录的任务类型。"""
    if value not in VISION_TASK_TYPE_SET:
        raise ValueError("数据集缺少合法的 vision_task_type")
    return value


def load_dataset_vision_task_type(dataset_root):
    """从项目内部元数据读取数据集任务类型。"""
    data = load_json_file(get_dataset_task_meta_path(dataset_root), default={}) or {}
    if not isinstance(data, dict):
        raise ValueError("数据集任务元数据格式错误")
    return require_dataset_vision_task_type(data.get("vision_task_type"))


def save_dataset_vision_task_type(dataset_root, vision_task_type):
    """把数据集任务类型写入项目内部元数据。"""
    os.makedirs(dataset_root, exist_ok=True)
    return save_json_file(
        get_dataset_task_meta_path(dataset_root),
        {"vision_task_type": require_dataset_vision_task_type(vision_task_type)},
    )
