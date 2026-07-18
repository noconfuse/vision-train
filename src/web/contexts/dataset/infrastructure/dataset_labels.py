"""维护 dataset.yaml 类别定义并重写标签文件中的类 id。"""

import os

from contexts.dataset.infrastructure.dataset_layout import (
    get_dataset_auto_labels_dir,
    get_dataset_labels_dir,
    normalize_standard_dataset_splits,
)
from contexts.dataset.infrastructure.dataset_schema import load_dataset_yaml, resolve_dataset_names_list, save_dataset_names
from shared.utils.fs_utils import remove_file_silent
from shared.utils.yaml_utils import load_yaml_file


def resolve_dataset_label_id(yaml_path, class_id=None, class_name=None):
    """从 class_id 或 class_name 解析目标类别 id。"""
    if class_id is not None:
        try:
            return int(class_id)
        except Exception as exc:
            raise ValueError("class_id 参数无效") from exc

    names = resolve_dataset_names_list(load_dataset_yaml(os.path.dirname(yaml_path)))
    if not names:
        raise ValueError("dataset.yaml 缺少 names 字段")

    target = str(class_name or "").strip()
    try:
        return names.index(target)
    except ValueError as exc:
        raise ValueError("未找到该标签") from exc


def _load_names_and_shape(yaml_path):
    """读取类别名并保留 names 的原始结构形态。"""
    config = load_yaml_file(yaml_path, default={})
    raw_names = config.get("names")
    names = resolve_dataset_names_list(raw_names)
    if not names:
        raise ValueError("dataset.yaml 缺少 names 字段")
    return config, names, isinstance(raw_names, dict)


def _write_names_back(yaml_path, config, names, original_is_dict):
    """把更新后的类别名写回 dataset.yaml。"""
    save_dataset_names(yaml_path, config, names, original_is_dict=original_is_dict)


def _iter_dataset_label_files(ds_root, split_list):
    """遍历指定 split 下的手工与自动标签文件。"""
    for split in split_list:
        for base in (
            get_dataset_labels_dir(ds_root, split),
            get_dataset_auto_labels_dir(ds_root, split),
        ):
            if not os.path.isdir(base):
                continue
            for root, _, files in os.walk(base):
                for filename in files:
                    if filename.lower().endswith(".txt"):
                        yield os.path.join(root, filename)


def reorder_dataset_labels(ds_root, yaml_path, order, splits=None):
    """重排类别顺序并同步所有标签文件的 id。"""
    config, old_names, original_is_dict = _load_names_and_shape(yaml_path)

    try:
        order_ints = [int(value) for value in order]
    except Exception as exc:
        raise ValueError("order 参数无效") from exc

    count = len(old_names)
    if len(order_ints) != count:
        raise ValueError("order 长度必须等于类别数")
    if len(set(order_ints)) != count:
        raise ValueError("order 不能包含重复项")
    if any(index < 0 or index >= count for index in order_ints):
        raise ValueError("order 存在越界索引")

    new_names = [old_names[index] for index in order_ints]
    id_map = {old_idx: new_idx for new_idx, old_idx in enumerate(order_ints)}
    _write_names_back(yaml_path, config, new_names, original_is_dict)

    updated_files = 0
    updated_lines = 0
    skipped_files = 0

    for file_path in _iter_dataset_label_files(ds_root, normalize_standard_dataset_splits(splits)):
        changed = False
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            skipped_files += 1
            continue

        output = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                output.append(line)
                continue
            parts = stripped.split()
            if not parts:
                output.append(line)
                continue
            try:
                class_id = int(float(parts[0]))
            except Exception:
                output.append(line)
                continue

            if class_id in id_map:
                new_class_id = id_map[class_id]
                if new_class_id != class_id:
                    parts[0] = str(new_class_id)
                    changed = True
                    updated_lines += 1
                output.append(" ".join(parts) + "\n")
            else:
                output.append(line if line.endswith("\n") else (line + "\n"))

        if not changed:
            skipped_files += 1
            continue

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(output)
            updated_files += 1
        except Exception:
            skipped_files += 1

    return {
        "updated_files": updated_files,
        "updated_lines": updated_lines,
        "skipped_files": skipped_files,
        "order": order_ints,
    }


def delete_dataset_label(ds_root, yaml_path, delete_id, splits=None, delete_empty_files=True):
    """删除一个类别并下移后续类别 id。"""
    config, old_names, original_is_dict = _load_names_and_shape(yaml_path)

    if delete_id < 0 or delete_id >= len(old_names):
        raise ValueError("class_id 越界")
    deleted_name = old_names[delete_id]
    new_names = [name for idx, name in enumerate(old_names) if idx != delete_id]
    _write_names_back(yaml_path, config, new_names, original_is_dict)

    updated_files = 0
    deleted_files = 0
    shifted_lines = 0
    removed_lines = 0
    skipped_files = 0

    for file_path in _iter_dataset_label_files(ds_root, normalize_standard_dataset_splits(splits)):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception:
            skipped_files += 1
            continue

        output = []
        changed = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            parts = stripped.split()
            if not parts:
                continue
            try:
                class_id = int(float(parts[0]))
            except Exception:
                output.append(line if line.endswith("\n") else (line + "\n"))
                continue

            if class_id == delete_id:
                changed = True
                removed_lines += 1
                continue
            if class_id > delete_id:
                parts[0] = str(class_id - 1)
                changed = True
                shifted_lines += 1
            output.append(" ".join(parts) + "\n")

        if not changed:
            skipped_files += 1
            continue

        if delete_empty_files and not output:
            try:
                remove_file_silent(file_path)
                deleted_files += 1
                updated_files += 1
                continue
            except Exception:
                skipped_files += 1
                continue

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(output)
            updated_files += 1
        except Exception:
            skipped_files += 1

    return {
        "deleted_label_id": delete_id,
        "deleted_label_name": deleted_name,
        "nc": len(new_names),
        "updated_files": updated_files,
        "deleted_files": deleted_files,
        "shifted_lines": shifted_lines,
        "removed_lines": removed_lines,
        "skipped_files": skipped_files,
        "splits": normalize_standard_dataset_splits(splits),
    }
