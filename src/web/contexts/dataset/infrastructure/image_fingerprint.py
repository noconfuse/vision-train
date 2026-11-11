"""走查列表折叠相似帧用的图片指纹缓存。

存在项目级非 DVC 目录 ``.dataset-store/.image_fingerprints.json``，结构为
``{ 数据集名: { split: { 图片引用: {"h": 指纹, "m": mtime, "s": 字节数} } } }``，
与浏览游标同一个家。mtime 或大小变了就重算，所以换过的图不会拿旧指纹。

这只是显示用的派生数据：删掉这个文件最多多算一次，不影响任何标签或版本。
"""

import os

from contexts.dataset.infrastructure.dataset_versioning import get_project_dataset_store_dir
from shared.utils.image_hash import image_dhash
from shared.utils.json_utils import load_json_file, save_json_file
from shared.utils.path_utils import resolve_storage_path

DATASET_FINGERPRINT_FILENAME = ".image_fingerprints.json"


def get_dataset_fingerprint_path(project_path):
    """返回项目级图片指纹文件路径。"""
    return os.path.join(get_project_dataset_store_dir(project_path), DATASET_FINGERPRINT_FILENAME)


def _read_map(project_path):
    data = load_json_file(get_dataset_fingerprint_path(project_path), default={}) or {}
    return data if isinstance(data, dict) else {}


def _stat_of(image_path):
    """取 (mtime, size) 当作指纹的有效期戳；图不在了返回 None。

    mtime 留小数：同一秒内被换掉的图不少，取整就会让新图认旧指纹。
    """
    try:
        info = os.stat(image_path)
    except OSError:
        return None
    return info.st_mtime, int(info.st_size)


def fingerprints_for_items(project_path, dataset_name, items):
    """按列表记录取 dHash 指纹，返回与 ``items`` 等长的列表，读不出的图为 None。

    只重算缺失或已变样的图，并把本次涉及 split 的内容整体重写一遍（顺带清掉已删图的键），
    其他 split 的记录原样留着。
    """
    stored = _read_map(project_path)
    by_split = stored.get(str(dataset_name))
    by_split = by_split if isinstance(by_split, dict) else {}

    rebuilt = {}
    values = []
    for item in items:
        if not isinstance(item, dict):
            values.append(None)
            continue
        split = str(item.get("split") or "")
        ref = str(item.get("path") or "")
        bucket = rebuilt.setdefault(split, {})
        stamp = None
        value = None
        if ref:
            try:
                image_path = resolve_storage_path(ref)
            except ValueError:
                image_path = ""
            stamp = _stat_of(image_path) if image_path else None
            cached = by_split.get(split, {}).get(ref) if stamp else None
            if isinstance(cached, dict) and cached.get("h") is not None \
                    and cached.get("m") == stamp[0] and cached.get("s") == stamp[1]:
                value = int(cached["h"])
            elif stamp:
                value = image_dhash(image_path)
        if stamp:
            bucket[ref] = {"h": value, "m": stamp[0], "s": stamp[1]}
        values.append(value)

    merged = dict(by_split)
    merged.update(rebuilt)
    if merged != by_split:
        stored[str(dataset_name)] = merged
        save_json_file(get_dataset_fingerprint_path(project_path), stored)
    return values
