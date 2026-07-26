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
    get_dataset_root_images_dir,
    get_dataset_root_labels_dir,
)
from contexts.dataset.infrastructure.dataset_schema import (
    find_dataset_config,
    load_dataset_yaml,
    resolve_dataset_names_dict,
    save_dataset_config,
)
from shared.utils.fs_utils import move_dir_contents, remove_dir_if_empty, remove_file_silent
from constants.media import DATASET_SPLITS
from shared.utils.path_utils import is_within_path, normalize_path_ref
from shared.utils.yaml_utils import load_yaml_file


def _resolve_yolo_base_dir(dataset_root, config):
    """解析 YOLO 配置中的 path 基准目录。"""
    base_ref = normalize_path_ref((config or {}).get("path") or ".") or "."
    if os.path.isabs(base_ref):
        raise ValueError("dataset.yaml 的 path 必须为数据集根目录内的相对路径")
    candidate = os.path.normpath(os.path.join(dataset_root, base_ref))
    if is_within_path(candidate, dataset_root) and os.path.isdir(candidate):
        return candidate
    if os.path.basename(candidate) == os.path.basename(os.path.normpath(dataset_root)):
        return dataset_root
    if any(
        os.path.isdir(os.path.join(dataset_root, normalize_path_ref((config or {}).get(split) or "").split("/")[0]))
        for split in DATASET_SPLITS
        if (config or {}).get(split) not in (None, "", [])
    ):
        return dataset_root
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


def looks_like_standard_yolo_dataset(dataset_root):
    """判断目录是否已经符合标准 YOLO 图片/标签布局，即使暂时缺少 dataset.yaml。"""
    if not os.path.isdir(dataset_root):
        return False
    split_pairs = _collect_standard_split_pairs(dataset_root)
    if not split_pairs:
        return False
    for split, _ in split_pairs:
        if not os.path.isdir(get_dataset_labels_dir(dataset_root, split)):
            return False
    return True


def _collect_external_split_pairs(dataset_root):
    """收集外部 YOLO 常见布局 `images/{split}` + `labels/{split}` 的 split 对。"""
    split_pairs = []
    root_images_dir = get_dataset_root_images_dir(dataset_root)
    root_labels_dir = get_dataset_root_labels_dir(dataset_root)
    for split in DATASET_SPLITS:
        if os.path.isdir(os.path.join(root_images_dir, split)):
            split_pairs.append((split, split))
    if not split_pairs:
        return []
    for split, _ in split_pairs:
        if not os.path.isdir(os.path.join(root_labels_dir, split)):
            return []
    return split_pairs


def looks_like_external_yolo_source(dataset_root):
    """判断目录是否符合外部常见 YOLO 源布局。"""
    if not os.path.isdir(dataset_root):
        return False
    return bool(_collect_external_split_pairs(dataset_root))


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
    if not looks_like_standard_yolo_dataset(dataset_root):
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


def _build_default_pose_keypoint_names(keypoint_count):
    """生成默认关键点名称。"""
    return [f"kpt_{index}" for index in range(int(keypoint_count or 0))]


def _normalize_pose_skeleton(raw_skeleton, keypoint_count):
    """把 skeleton 规范为 zero-based 的 [[from, to], ...]。"""
    if not isinstance(raw_skeleton, list) or keypoint_count <= 0:
        return []
    normalized_pairs = []
    one_based_pairs = []
    for pair in raw_skeleton:
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            continue
        try:
            start = int(pair[0])
            end = int(pair[1])
        except (TypeError, ValueError):
            continue
        normalized_pairs.append([start, end])
        one_based_pairs.append([start - 1, end - 1])
    def _is_valid(pairs):
        return all(0 <= start < keypoint_count and 0 <= end < keypoint_count and start != end for start, end in pairs)
    if normalized_pairs and _is_valid(normalized_pairs):
        return normalized_pairs
    if one_based_pairs and _is_valid(one_based_pairs):
        return one_based_pairs
    return []


def _infer_pose_kpt_shape(dataset_root, split_pairs):
    """从姿态标签中推断 kpt_shape。"""
    for file_path in _iter_split_label_files(dataset_root, split_pairs):
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                for raw_line in handle:
                    parts = str(raw_line or "").strip().split()
                    if len(parts) <= 5:
                        continue
                    payload = parts[5:]
                    if not payload:
                        continue
                    if len(payload) % 3 == 0:
                        try:
                            visibility_values = [float(payload[index]) for index in range(2, len(payload), 3)]
                        except (TypeError, ValueError):
                            visibility_values = []
                        if visibility_values and all(value in (0.0, 1.0, 2.0) for value in visibility_values):
                            return [len(payload) // 3, 3]
                    if len(payload) % 3 == 0 and len(payload) % 2 != 0:
                        return [len(payload) // 3, 3]
                    if len(payload) % 2 == 0:
                        return [len(payload) // 2, 2]
        except Exception:
            continue
    return None


def build_pose_dataset_yaml_fields(config, dataset_root, split_pairs, normalized_names):
    """解析或推断姿态数据集所需的补充 YAML 字段。"""
    pose_yaml = {}
    raw_kpt_shape = (config or {}).get("kpt_shape")
    kpt_shape = None
    if isinstance(raw_kpt_shape, (list, tuple)) and len(raw_kpt_shape) == 2:
        try:
            keypoint_count = int(raw_kpt_shape[0])
            dims = int(raw_kpt_shape[1])
            if keypoint_count > 0 and dims in (2, 3):
                kpt_shape = [keypoint_count, dims]
        except (TypeError, ValueError):
            kpt_shape = None
    if kpt_shape is None:
        kpt_shape = _infer_pose_kpt_shape(dataset_root, split_pairs)
    if kpt_shape is None:
        raise ValueError("姿态数据集缺少 kpt_shape，且无法从标签推断关键点结构")

    pose_yaml["kpt_shape"] = kpt_shape
    keypoint_count = int(kpt_shape[0])

    flip_idx = (config or {}).get("flip_idx")
    if isinstance(flip_idx, list) and len(flip_idx) == keypoint_count:
        pose_yaml["flip_idx"] = [int(value) for value in flip_idx]
    else:
        pose_yaml["flip_idx"] = list(range(keypoint_count))

    raw_kpt_names = (config or {}).get("kpt_names")
    if isinstance(raw_kpt_names, dict) and raw_kpt_names:
        pose_yaml["kpt_names"] = raw_kpt_names
    else:
        default_names = _build_default_pose_keypoint_names(keypoint_count)
        pose_yaml["kpt_names"] = {
            int(class_id): list(default_names)
            for class_id in (normalized_names.keys() if normalized_names else [0])
        }
    skeleton = _normalize_pose_skeleton((config or {}).get("skeleton"), keypoint_count)
    if skeleton:
        pose_yaml["skeleton"] = skeleton
    return pose_yaml


def ensure_dataset_yaml(dataset_root, *, force=False, extra_yaml_builder=None):
    """补写或修复标准 dataset.yaml，并对齐类别定义。"""
    if not os.path.isdir(dataset_root):
        return
    config_path = find_dataset_config(dataset_root)
    config_filename = os.path.basename(config_path) if config_path else ""
    if config_path is not None and not force:
        return

    other_yaml = None
    config = {}
    source_yaml_path = config_path
    if source_yaml_path and config_filename != DATASET_CONFIG_FILENAME:
        other_yaml = source_yaml_path
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
    tags = (config or {}).get("tags")
    if isinstance(tags, list):
        yaml_data["tags"] = [str(tag).strip() for tag in tags if str(tag).strip()]
    if callable(extra_yaml_builder):
        yaml_data.update(extra_yaml_builder(config, dataset_root, split_pairs, yaml_data["names"]) or {})
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


def normalize_external_yolo_source_layout(dataset_root):
    """把外部常见 YOLO 源布局归一化为项目内部标准布局。"""
    split_pairs = _collect_external_split_pairs(dataset_root)
    if not split_pairs:
        raise ValueError("未识别到外部 YOLO 目录布局")
    root_images_dir = get_dataset_root_images_dir(dataset_root)
    root_labels_dir = get_dataset_root_labels_dir(dataset_root)
    for split, _ in split_pairs:
        src_img_dir = os.path.join(root_images_dir, split)
        src_lbl_dir = os.path.join(root_labels_dir, split)
        dst_img_dir = get_dataset_images_dir(dataset_root, split)
        dst_lbl_dir = get_dataset_labels_dir(dataset_root, split)
        move_dir_contents(src_img_dir, dst_img_dir)
        move_dir_contents(src_lbl_dir, dst_lbl_dir)
        remove_dir_if_empty(src_img_dir)
        remove_dir_if_empty(src_lbl_dir)
    for root, _, files in os.walk(root_labels_dir):
        for filename in files:
            if filename.endswith(".cache"):
                remove_file_silent(os.path.join(root, filename))
    remove_dir_if_empty(root_images_dir)
    remove_dir_if_empty(root_labels_dir)
