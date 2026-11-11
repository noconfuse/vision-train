"""记录每个数据集在各 split 下「上次打开的图片」游标，供列表快速回到上次位置。

存储在项目级非 DVC 目录 .dataset-store/.browse_cursor.json 中，结构为
{ dataset_name: { split: { "path": ..., "name": ..., "updated_at": ... } } }。
"""

import os

from contexts.dataset.infrastructure.dataset_versioning import get_project_dataset_store_dir
from shared.utils.json_utils import load_json_file, save_json_file
from shared.utils.path_utils import resolve_storage_path
from shared.utils.time_utils import now_iso

DATASET_BROWSE_CURSOR_FILENAME = ".browse_cursor.json"


def get_dataset_cursor_path(project_path):
    """返回项目级浏览游标文件路径。"""
    return os.path.join(get_project_dataset_store_dir(project_path), DATASET_BROWSE_CURSOR_FILENAME)


def _load_cursor_map(project_path):
    data = load_json_file(get_dataset_cursor_path(project_path), default={}) or {}
    return data if isinstance(data, dict) else {}


def _cursor_target_exists(raw_path):
    """游标指向的图片是否还在：删图或移图后，旧游标不能把列表定位到不存在的文件上。"""
    try:
        return os.path.isfile(resolve_storage_path(raw_path))
    except (ValueError, OSError):
        return False


def get_dataset_browse_cursor(project_path, dataset_name, split):
    """读取指定数据集 / split 的上次打开图片，无记录或图片已不在时返回空 dict。"""
    by_split = _load_cursor_map(project_path).get(str(dataset_name)) or {}
    if not isinstance(by_split, dict):
        return {}
    entry = by_split.get(str(split)) or {}
    if not isinstance(entry, dict) or not entry.get("path"):
        return {}
    if not _cursor_target_exists(entry.get("path")):
        return {}
    return {"path": entry.get("path"), "name": entry.get("name")}


def set_dataset_browse_cursor(project_path, dataset_name, split, image_path, image_name=None):
    """写入指定数据集 / split 的上次打开图片，返回存储后的游标记录。"""
    if not str(image_path or "").strip():
        raise ValueError("缺少 image_path")
    cursor_map = _load_cursor_map(project_path)
    dataset_key = str(dataset_name)
    by_split = cursor_map.get(dataset_key)
    if not isinstance(by_split, dict):
        by_split = {}
        cursor_map[dataset_key] = by_split
    record = {
        "path": str(image_path),
        "name": str(image_name or os.path.basename(str(image_path).replace("\\", "/"))),
        "updated_at": now_iso(),
    }
    by_split[str(split)] = record
    save_json_file(get_dataset_cursor_path(project_path), cursor_map)
    return record
