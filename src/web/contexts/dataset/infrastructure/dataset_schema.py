"""封装数据集配置结构解析与名称校验。"""

import os

from app.config import DATASET_CONFIG_FILENAME
from shared.utils.media_constants import DATASET_SPLITS
from shared.utils.name_utils import TOKEN_NAME_PATTERN, validate_token_name
from shared.utils.yaml_utils import (
    load_yaml_file,
    resolve_names_dict as resolve_dataset_names_dict,
    resolve_names_list as resolve_dataset_names_list,
    save_yaml_file,
)

__all__ = [
    "build_standard_dataset_config",
    "find_dataset_config",
    "load_dataset_yaml",
    "load_dataset_yaml_ref",
    "load_dataset_names",
    "normalize_dataset_yaml_for_training",
    "require_dataset_config_path",
    "resolve_dataset_names_dict",
    "resolve_dataset_names_list",
    "resolve_dataset_tags",
    "save_dataset_config",
    "save_dataset_config_file",
    "save_dataset_names",
    "save_standard_dataset_yaml",
    "save_dataset_tags",
    "validate_dataset_name",
]

DATASET_NAME_RE = TOKEN_NAME_PATTERN


def _normalize_dataset_split_value(value, old_base, new_base):
    """将 dataset.yaml 中的 split 引用归一化到目标数据集根目录下。"""
    if not value:
        return value
    value = str(value)
    if not os.path.isabs(value):
        return value.replace("\\", "/")
    abs_value = os.path.abspath(value)
    for base in filter(None, [old_base, new_base]):
        try:
            rel = os.path.relpath(abs_value, base)
        except ValueError:
            continue
        if rel == ".":
            return "."
        if not rel.startswith(".."):
            return rel.replace(os.sep, "/")
    return abs_value


def build_standard_dataset_config(names, *, include_val=True, include_test=True, val_fallback_split=None, tags=None):
    """构造符合项目协议的标准 dataset.yaml 内容。"""
    from contexts.dataset.infrastructure.dataset_layout import (
        DATASET_SPLIT_TEST,
        DATASET_SPLIT_TRAIN,
        DATASET_SPLIT_VAL,
        build_dataset_yaml_image_ref,
    )

    config = {
        "path": ".",
        "train": build_dataset_yaml_image_ref(DATASET_SPLIT_TRAIN),
        "val": build_dataset_yaml_image_ref(val_fallback_split or DATASET_SPLIT_VAL)
        if include_val
        else build_dataset_yaml_image_ref(DATASET_SPLIT_TRAIN),
        "names": names,
    }
    if include_test:
        config["test"] = build_dataset_yaml_image_ref(DATASET_SPLIT_TEST)
    cleaned_tags = resolve_dataset_tags({"tags": tags or []})
    if cleaned_tags:
        config["tags"] = cleaned_tags
    return config


def find_dataset_config(dataset_root):
    """返回标准 dataset.yaml 的路径。"""
    candidate = os.path.join(dataset_root, DATASET_CONFIG_FILENAME)
    return candidate if os.path.isfile(candidate) else None


def require_dataset_config_path(dataset_root):
    """返回已存在的 dataset.yaml 路径。"""
    config_path = find_dataset_config(dataset_root)
    if not config_path:
        raise ValueError("未找到 dataset.yaml")
    return config_path


def load_dataset_yaml(dataset_root, default=None):
    """读取 dataset.yaml 并在缺失时回退默认值。"""
    cfg = find_dataset_config(dataset_root)
    return load_yaml_file(cfg, default=default)


def load_dataset_yaml_ref(path_or_root, default=None):
    """从数据集根目录或直接 yaml 路径读取配置。"""
    if not path_or_root:
        return {} if default is None else default
    if os.path.isdir(path_or_root):
        return load_dataset_yaml(path_or_root, default=default)
    if not os.path.isfile(path_or_root):
        return {} if default is None else default
    return load_yaml_file(path_or_root, default=default)


def load_dataset_names(dataset_root):
    """把 dataset.yaml 的 names 字段规范为列表。"""
    return resolve_dataset_names_list(load_dataset_yaml(dataset_root).get("names"))


def normalize_dataset_yaml_for_training(yaml_path, dataset_root):
    """按训练链路协议归一化 dataset.yaml 的 path 与 split 引用。"""
    yaml_content = load_yaml_file(yaml_path, default={})
    if not isinstance(yaml_content, dict):
        raise ValueError(f"数据集配置格式错误: {yaml_path}")
    original_base = yaml_content.get("path")
    original_base = os.path.abspath(original_base) if original_base else None
    normalized = dict(yaml_content)
    changed = "path" in normalized
    normalized.pop("path", None)
    for key in DATASET_SPLITS:
        old_value = yaml_content.get(key)
        new_value = _normalize_dataset_split_value(old_value, original_base, dataset_root)
        if new_value != old_value:
            normalized[key] = new_value
            changed = True
    if not changed:
        return yaml_path
    return save_dataset_config_file(yaml_path, normalized)


def resolve_dataset_tags(config):
    """从配置对象中提取清洗后的 tags。"""
    tags = config.get("tags")
    if isinstance(tags, list):
        return [str(tag).strip() for tag in tags if str(tag).strip()]
    return []


def save_dataset_config_file(yaml_path, data):
    """按统一结构策略写回 dataset.yaml 文件。"""
    config = dict(data or {})
    raw_names = config.get("names")
    names_dict = resolve_dataset_names_dict(raw_names)
    if names_dict:
        config["names"] = names_dict if isinstance(raw_names, dict) else resolve_dataset_names_list(raw_names)
        config["nc"] = len(names_dict)
    cleaned_tags = resolve_dataset_tags(config)
    if cleaned_tags:
        config["tags"] = cleaned_tags
    elif "tags" in config:
        config["tags"] = []
    save_yaml_file(yaml_path, config)
    return yaml_path


def save_dataset_config(dataset_root, data):
    """按统一结构策略写回数据集根目录的 dataset.yaml。"""
    return save_dataset_config_file(os.path.join(dataset_root, DATASET_CONFIG_FILENAME), data)


def save_standard_dataset_yaml(dataset_root, names, *, include_val=True, include_test=True, val_fallback_split=None, tags=None):
    """按标准数据集协议生成并写回 dataset.yaml。"""
    return save_dataset_config(
        dataset_root,
        build_standard_dataset_config(
            names,
            include_val=include_val,
            include_test=include_test,
            val_fallback_split=val_fallback_split,
            tags=tags,
        ),
    )


def save_dataset_names(yaml_path, config, names, *, original_is_dict):
    """把更新后的类别名写回 dataset.yaml。"""
    patched = dict(config or {})
    patched["names"] = {idx: name for idx, name in enumerate(names)} if original_is_dict else list(names)
    return save_dataset_config_file(yaml_path, patched)


def save_dataset_tags(dataset_root, tags):
    """更新并写回数据集配置中的 tags 字段。"""
    yaml_path = find_dataset_config(dataset_root) or os.path.join(dataset_root, DATASET_CONFIG_FILENAME)
    data = load_dataset_yaml(dataset_root, default={}) if os.path.exists(yaml_path) else {}
    data["tags"] = resolve_dataset_tags({"tags": tags or []})
    return save_dataset_config_file(yaml_path, data)


def validate_dataset_name(name):
    """按项目命名规则校验数据集名称。"""
    return validate_token_name(
        name,
        empty_message="数据集名不能为空",
        invalid_message="数据集名只能包含字母/数字/下划线/短横线，长度不能超过 64 字符",
    )
