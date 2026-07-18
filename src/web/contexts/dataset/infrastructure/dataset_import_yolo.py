"""归一化 YOLO 数据集目录结构并补齐标准配置。"""

import os

from app.config import DATASET_CONFIG_FILENAME
from contexts.dataset.infrastructure.dataset_layout import (
    DATASET_SPLIT_TEST,
    DATASET_SPLIT_TRAIN,
    DATASET_SPLIT_VAL,
    build_dataset_yaml_image_ref,
    get_dataset_images_dir,
    get_dataset_labels_dir,
)
from contexts.dataset.infrastructure.dataset_schema import find_dataset_config, load_dataset_yaml, resolve_dataset_names_dict, save_dataset_config
from shared.utils.fs_utils import move_dir_contents, remove_dir_if_empty, remove_file_silent
from shared.utils.media_constants import DATASET_SPLITS
from shared.utils.path_utils import is_within_path, normalize_path_ref
from shared.utils.yaml_utils import load_yaml_file


def _resolve_yolo_base_dir(dataset_root, config):
    """解析 YOLO 配置中的 path 基准目录。"""
    base_ref = normalize_path_ref((config or {}).get("path") or ".") or "."
    if os.path.isabs(base_ref):
        raise ValueError("dataset.yaml 的 path 必须为数据集根目录内的相对路径")
    candidate = os.path.normpath(os.path.join(dataset_root, base_ref))
    if not is_within_path(candidate, dataset_root):
        raise ValueError("dataset.yaml 的 path 超出数据集根目录")
    if not os.path.isdir(candidate):
        raise ValueError("dataset.yaml 的 path 指向不存在的目录")
    return candidate


def _resolve_yolo_split_pair(base_dir, raw_ref):
    """按单一配置规则推导 split 的图片与标签目录。"""
    raw_text = str(raw_ref or "")
    if os.path.isabs(raw_text):
        raise ValueError("dataset.yaml 的 split 路径必须为相对路径")
    ref = normalize_path_ref(raw_text)
    if not ref:
        raise ValueError("dataset.yaml 的 split 路径不能为空")
    parts = ref.split("/")
    if parts[0] == "images":
        split_rel = "/".join(parts[1:])
        if not split_rel:
            raise ValueError("dataset.yaml 的 split 路径必须指向具体分片目录")
        return (
            os.path.normpath(os.path.join(base_dir, "images", split_rel)),
            os.path.normpath(os.path.join(base_dir, "labels", split_rel)),
        )
    if parts[-1] == "images":
        split_rel = "/".join(parts[:-1])
        if not split_rel:
            raise ValueError("dataset.yaml 的 split 路径必须指向具体分片目录")
        return (
            os.path.normpath(os.path.join(base_dir, ref)),
            os.path.normpath(os.path.join(base_dir, split_rel, "labels")),
        )
    return (
        os.path.normpath(os.path.join(base_dir, ref, "images")),
        os.path.normpath(os.path.join(base_dir, ref, "labels")),
    )


def _collect_standard_split_pairs(dataset_root):
    """收集当前已存在的标准 split 对。"""
    split_pairs = []
    if os.path.isdir(get_dataset_images_dir(dataset_root, DATASET_SPLIT_TRAIN)):
        split_pairs.append((DATASET_SPLIT_TRAIN, DATASET_SPLIT_TRAIN))
    if os.path.isdir(get_dataset_images_dir(dataset_root, DATASET_SPLIT_VAL)):
        split_pairs.append((DATASET_SPLIT_VAL, DATASET_SPLIT_VAL))
    if os.path.isdir(get_dataset_images_dir(dataset_root, DATASET_SPLIT_TEST)):
        split_pairs.append((DATASET_SPLIT_TEST, DATASET_SPLIT_TEST))
    return split_pairs


def _resolve_yolo_split_dirs(dataset_root, config):
    """严格按 dataset.yaml 配置解析各 split 源路径。"""
    resolved = {}
    base_dir = _resolve_yolo_base_dir(dataset_root, config)
    for split in DATASET_SPLITS:
        raw_ref = (config or {}).get(split)
        if raw_ref in (None, "", []):
            continue
        image_dir, label_dir = _resolve_yolo_split_pair(base_dir, raw_ref)
        if not is_within_path(image_dir, dataset_root) or not is_within_path(label_dir, dataset_root):
            raise ValueError(f"dataset.yaml 的 {split} 路径超出数据集根目录")
        if not os.path.isdir(image_dir):
            raise ValueError(f"dataset.yaml 的 {split} 图片目录不存在")
        if not os.path.isdir(label_dir):
            raise ValueError(f"dataset.yaml 的 {split} 标签目录不存在")
        resolved[split] = (image_dir, label_dir)
    if not resolved:
        raise ValueError("dataset.yaml 缺少可解析的 split 路径")
    return resolved


def is_standard_yolo_dataset(dataset_root):
    """判断数据集是否已符合项目标准 YOLO 协议。"""
    if not os.path.isdir(dataset_root):
        return False
    if find_dataset_config(dataset_root) is None:
        return False
    config = load_dataset_yaml(dataset_root, default={})
    if not isinstance(config, dict):
        return False
    try:
        if os.path.normpath(_resolve_yolo_base_dir(dataset_root, config)) != os.path.normpath(dataset_root):
            return False
    except ValueError:
        return False
    split_pairs = _collect_standard_split_pairs(dataset_root)
    if not split_pairs:
        return False
    for split, _ in split_pairs:
        if normalize_path_ref(config.get(split)) != build_dataset_yaml_image_ref(split):
            return False
        if not os.path.isdir(get_dataset_labels_dir(dataset_root, split)):
            return False
    return True


def _iter_split_label_files(dataset_root, split_pairs):
    """遍历指定 split 下的所有标签文件。"""
    for _, source_split in split_pairs:
        label_dir = get_dataset_labels_dir(dataset_root, source_split)
        if not os.path.isdir(label_dir):
            continue
        for root, _, files in os.walk(label_dir):
            for filename in files:
                if filename.endswith(".txt"):
                    yield os.path.join(root, filename)


def _scan_dataset_class_ids(dataset_root, split_pairs):
    """扫描标签文件中实际出现过的类别 id。"""
    class_ids = set()
    for file_path in _iter_split_label_files(dataset_root, split_pairs):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        class_ids.add(int(float(line.split()[0])))
                    except (ValueError, IndexError):
                        continue
        except Exception:
            continue
    return class_ids


def _rewrite_label_file_class_ids(file_path, id_map):
    """按映射重写单个标签文件里的类别 id。"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return

    output = []
    changed = False
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
        new_class_id = id_map.get(class_id, class_id)
        if new_class_id != class_id:
            changed = True
        parts[0] = str(new_class_id)
        output.append(" ".join(parts) + "\n")

    if changed:
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(output)


def ensure_dataset_yaml(dataset_root, *, force=False):
    """补写或修复标准 dataset.yaml，并对齐类别定义。"""
    if not os.path.isdir(dataset_root):
        return
    config_path = find_dataset_config(dataset_root)
    if config_path is not None and not force:
        return

    other_yaml = None
    config = {}
    source_yaml_path = config_path
    if source_yaml_path is None:
        for filename in os.listdir(dataset_root):
            if filename.lower().endswith((".yaml", ".yml")) and filename != DATASET_CONFIG_FILENAME:
                candidate = os.path.join(dataset_root, filename)
                if os.path.isfile(candidate):
                    other_yaml = candidate
                    source_yaml_path = candidate
                    break

    split_pairs = _collect_standard_split_pairs(dataset_root)

    if source_yaml_path:
        try:
            config = load_yaml_file(source_yaml_path, default={})
        except Exception:
            config = {}

    names_dict = resolve_dataset_names_dict(config.get("names") if isinstance(config, dict) else None)
    class_ids = _scan_dataset_class_ids(dataset_root, split_pairs)
    if not names_dict:
        names_dict = {class_id: f"class_{class_id}" for class_id in sorted(class_ids)}

    try:
        sorted_name_ids = sorted(int(key) for key in names_dict.keys())
    except Exception:
        sorted_name_ids = list(range(len(names_dict)))
        names_dict = {idx: value for idx, value in enumerate(names_dict.values())}

    if class_ids:
        sorted_class_ids = sorted(class_ids)
        expected_ids = list(range(len(sorted_name_ids)))
        if sorted_name_ids != expected_ids:
            id_map = {old_id: new_id for new_id, old_id in enumerate(sorted_class_ids)}
            normalized_names = {
                id_map[old_id]: str(names_dict.get(old_id, f"class_{old_id}"))
                for old_id in sorted_class_ids
            }
            for file_path in _iter_split_label_files(dataset_root, split_pairs):
                _rewrite_label_file_class_ids(file_path, id_map)
        else:
            normalized_names = {int(class_id): str(names_dict[class_id]) for class_id in sorted_name_ids}
    else:
        normalized_names = {int(class_id): str(class_name) for class_id, class_name in names_dict.items()}

    yaml_data = {"path": "."}
    for target, source in split_pairs:
        yaml_data[target] = build_dataset_yaml_image_ref(source)
    yaml_data["names"] = (
        dict(sorted(normalized_names.items(), key=lambda item: int(item[0])))
        if normalized_names
        else {0: "object"}
    )
    save_dataset_config(dataset_root, yaml_data)

    if other_yaml:
        remove_file_silent(other_yaml)


def normalize_yolo_layout(dataset_root):
    """把非标准 YOLO 目录内容搬运到标准布局。"""
    config = load_dataset_yaml(dataset_root, default={})
    split_dirs = _resolve_yolo_split_dirs(dataset_root, config if isinstance(config, dict) else {})
    for split, (src_img_dir, src_lbl_dir) in split_dirs.items():
        dst_img_dir = get_dataset_images_dir(dataset_root, split)
        dst_lbl_dir = get_dataset_labels_dir(dataset_root, split)
        if os.path.normpath(src_img_dir) != os.path.normpath(dst_img_dir):
            move_dir_contents(src_img_dir, dst_img_dir)
            remove_dir_if_empty(src_img_dir)
            remove_dir_if_empty(os.path.dirname(src_img_dir))
        if os.path.normpath(src_lbl_dir) != os.path.normpath(dst_lbl_dir):
            move_dir_contents(src_lbl_dir, dst_lbl_dir)
            remove_dir_if_empty(src_lbl_dir)
            remove_dir_if_empty(os.path.dirname(src_lbl_dir))
