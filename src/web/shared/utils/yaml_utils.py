"""封装 YAML 读写与 names 字段归一化。"""

import os

import yaml


def load_yaml_file(file_path, default=None):
    """读取 YAML 文件，缺失时返回默认值。"""
    if not file_path or not os.path.isfile(file_path):
        return {} if default is None else default
    with open(file_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or ({} if default is None else default)


def save_yaml_file(file_path, data):
    """把数据写回 YAML 文件并保留键顺序。"""
    with open(file_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)


def resolve_names_dict(raw_names):
    """把 names 字段归一化为按索引排序的字典。"""
    if isinstance(raw_names, list):
        return {idx: str(name) for idx, name in enumerate(raw_names)}
    if isinstance(raw_names, dict):
        pairs = []
        for key, value in raw_names.items():
            try:
                idx = int(key)
            except Exception:
                continue
            pairs.append((idx, str(value)))
        pairs.sort(key=lambda item: item[0])
        return {idx: value for idx, value in pairs}
    return {}


def resolve_names_list(raw_names):
    """把 names 字段归一化为连续列表。"""
    names_dict = resolve_names_dict(raw_names)
    if not names_dict:
        return []
    max_idx = max(names_dict.keys())
    return [names_dict.get(idx, f"class_{idx}") for idx in range(max_idx + 1)]
