"""维护数据集任务类型与稳定身份的项目内部元数据。"""

import os
import uuid

from shared.utils.json_utils import load_json_file, save_json_file
from shared.utils.time_utils import now_iso
from protocols.vision_task_type import VISION_TASK_TYPE_SET

DATASET_TASK_META_FILENAME = ".vision-train.meta.json"


def get_dataset_task_meta_path(dataset_root):
    """返回数据集任务元数据文件路径。"""
    return os.path.join(dataset_root, DATASET_TASK_META_FILENAME)


def new_dataset_id():
    """生成短格式数据集稳定身份标识。"""
    return uuid.uuid4().hex[:12]


def require_dataset_vision_task_type(value):
    """校验并返回数据集内部记录的任务类型。"""
    if value not in VISION_TASK_TYPE_SET:
        raise ValueError("数据集缺少合法的 vision_task_type")
    return value


def load_dataset_task_meta(dataset_root):
    """读取数据集内部元数据。"""
    data = load_json_file(get_dataset_task_meta_path(dataset_root), default={}) or {}
    if not isinstance(data, dict):
        raise ValueError("数据集任务元数据格式错误")
    return data


def save_dataset_task_meta(dataset_root, data):
    """回写数据集内部元数据。"""
    os.makedirs(dataset_root, exist_ok=True)
    payload = dict(data or {})
    payload["vision_task_type"] = require_dataset_vision_task_type(payload.get("vision_task_type"))
    if not str(payload.get("dataset_id") or "").strip():
        raise ValueError("数据集缺少稳定 dataset_id")
    payload.setdefault("created_at", now_iso())
    payload["updated_at"] = now_iso()
    return save_json_file(get_dataset_task_meta_path(dataset_root), payload)


def load_dataset_vision_task_type(dataset_root):
    """从项目内部元数据读取数据集任务类型。"""
    data = load_dataset_task_meta(dataset_root)
    return require_dataset_vision_task_type(data.get("vision_task_type"))


def save_dataset_vision_task_type(dataset_root, vision_task_type):
    """把数据集任务类型写入项目内部元数据。"""
    meta = load_dataset_task_meta(dataset_root)
    meta["vision_task_type"] = require_dataset_vision_task_type(vision_task_type)
    meta["dataset_id"] = str(meta.get("dataset_id") or "").strip() or new_dataset_id()
    meta.setdefault("created_at", now_iso())
    return save_dataset_task_meta(dataset_root, meta)


def ensure_dataset_task_identity(dataset_root, vision_task_type=None):
    """确保数据集具备稳定身份与任务类型元数据。"""
    meta = load_dataset_task_meta(dataset_root)
    normalized_meta = dict(meta)
    resolved_vision_task_type = vision_task_type if vision_task_type is not None else normalized_meta.get("vision_task_type")
    normalized_meta["vision_task_type"] = require_dataset_vision_task_type(resolved_vision_task_type)
    normalized_meta["dataset_id"] = str(normalized_meta.get("dataset_id") or "").strip() or new_dataset_id()
    normalized_meta["created_at"] = normalized_meta.get("created_at") or now_iso()
    if normalized_meta != meta:
        save_dataset_task_meta(dataset_root, normalized_meta)
        return normalized_meta
    return normalized_meta


def load_dataset_identity_meta(dataset_root):
    """读取数据集稳定身份元数据。"""
    meta = load_dataset_task_meta(dataset_root)
    dataset_id = str(meta.get("dataset_id") or "").strip()
    if not dataset_id:
        raise ValueError("数据集缺少稳定 dataset_id")
    return {
        "dataset_id": dataset_id,
        "current_version_id": str(meta.get("current_version_id") or "").strip() or None,
        "created_at": meta.get("created_at"),
        "updated_at": meta.get("updated_at"),
        "vision_task_type": meta.get("vision_task_type"),
    }


def update_dataset_identity_meta(dataset_root, **patch):
    """更新数据集稳定身份元数据。"""
    meta = ensure_dataset_task_identity(dataset_root)
    for key, value in patch.items():
        if value is not None:
            meta[key] = value
    save_dataset_task_meta(dataset_root, meta)
    return load_dataset_identity_meta(dataset_root)
