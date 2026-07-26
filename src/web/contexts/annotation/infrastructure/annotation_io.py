"""处理标注协议共用的文件编解码与图片上下文解析。"""

import os

from contexts.dataset.infrastructure.dataset_repository import resolve_project_dataset_root
from contexts.dataset.infrastructure.dataset_layout import (
    extract_classification_class_name,
    build_label_relpath,
    get_dataset_auto_labels_dir,
    get_dataset_labels_dir,
    get_dataset_split_dir,
    get_dataset_split_content_dir,
    get_dataset_unlabeled_dir,
)
from contexts.dataset.infrastructure.dataset_schema import (
    load_dataset_names,
    load_dataset_yaml,
)
from contexts.dataset.infrastructure.dataset_task_type import load_dataset_vision_task_type
from protocols.vision_task_type import VISION_TASK_TYPE_CLASSIFY
from shared.utils.path_utils import is_within_path, resolve_storage_path
from shared.utils.value_utils import require_present
from shared.utils.yolo_utils import parse_yolo_class_id


def get_dataset_root(project_path, dataset_name):
    """解析并校验标注所属的数据集根目录。"""
    ds_root = resolve_project_dataset_root(project_path, dataset_name=dataset_name)
    if not ds_root:
        raise ValueError("数据集不存在")
    return ds_root


def resolve_dataset_image_context(project_path, dataset_name, split, image_ref):
    """解析图片路径、标签路径以及分类目录上下文。"""
    image_path = resolve_storage_path(image_ref)
    require_present(image_path=image_path)

    ds_root = get_dataset_root(project_path, dataset_name)
    return build_dataset_image_context(ds_root, split, image_path)


def build_dataset_image_context(dataset_root, split, image_path):
    """基于已知数据集根目录和图片路径解析标注上下文。"""
    image_path = resolve_storage_path(image_path)
    require_present(image_path=image_path)
    vision_task_type = load_dataset_vision_task_type(dataset_root)
    if not os.path.isfile(image_path):
        raise ValueError("图片不存在")

    split_dir = get_dataset_split_dir(dataset_root, split)
    unlabeled_dir = get_dataset_unlabeled_dir(dataset_root, split)
    auto_dir = get_dataset_auto_labels_dir(dataset_root, split)
    manual_dir = get_dataset_labels_dir(dataset_root, split)
    img_dir = get_dataset_split_content_dir(dataset_root, split, vision_task_type)
    class_names = load_dataset_names(dataset_root)

    if vision_task_type == VISION_TASK_TYPE_CLASSIFY:
        is_unlabeled = is_within_path(image_path, unlabeled_dir)
        if is_unlabeled:
            rel = os.path.relpath(image_path, unlabeled_dir)
            rel_noext = os.path.splitext(rel)[0]
            class_name = ""
            sample_relative_path = rel
            auto_label_path = os.path.join(auto_dir, "unlabeled", build_label_relpath(rel_noext))
        else:
            if not is_within_path(image_path, split_dir):
                raise ValueError("image_path 非法")
            rel = os.path.relpath(image_path, split_dir)
            rel_noext = os.path.splitext(rel)[0]
            class_name = extract_classification_class_name(rel)
            sample_relative_path = rel.split(os.sep, 1)[1] if class_name and os.sep in rel else os.path.basename(image_path)
            auto_label_path = ""
        return {
            "dataset_root": dataset_root,
            "split": split,
            "vision_task_type": vision_task_type,
            "image_path": image_path,
            "image_dir": unlabeled_dir if is_unlabeled else split_dir,
            "relative_path": rel,
            "relative_noext": rel_noext,
            "sample_relative_path": sample_relative_path,
            "manual_dir": manual_dir,
            "auto_dir": auto_dir,
            "manual_label_path": "",
            "auto_label_path": auto_label_path,
            "class_names": class_names,
            "class_name": class_name,
            "is_unlabeled": is_unlabeled,
            "split_dir": split_dir,
            "unlabeled_dir": unlabeled_dir,
        }

    if not is_within_path(image_path, img_dir):
        raise ValueError("image_path 非法")
    if not os.path.isfile(image_path):
        raise ValueError("图片不存在")

    rel = os.path.relpath(image_path, img_dir)
    rel_noext = os.path.splitext(rel)[0]
    return {
        "dataset_root": dataset_root,
        "split": split,
        "vision_task_type": vision_task_type,
        "image_path": image_path,
        "image_dir": img_dir,
        "relative_path": rel,
        "relative_noext": rel_noext,
        "manual_dir": manual_dir,
        "auto_dir": auto_dir,
        "manual_label_path": os.path.join(manual_dir, build_label_relpath(rel_noext)),
        "auto_label_path": os.path.join(auto_dir, build_label_relpath(rel_noext)),
        "class_names": class_names,
        "class_name": extract_classification_class_name(rel),
        "is_unlabeled": False,
        "split_dir": split_dir,
        "unlabeled_dir": unlabeled_dir,
    }


def get_image_size(image_path):
    """读取图片的宽高尺寸。"""
    try:
        from PIL import Image

        with Image.open(image_path) as image:
            return image.size
    except Exception as exc:
        raise ValueError("无法读取图片尺寸") from exc


def get_image_size_fallback(image_path):
    """优先用 PIL、失败后退回 cv2 获取图片尺寸。"""
    try:
        return get_image_size(image_path)
    except Exception:
        try:
            import cv2

            image = cv2.imread(image_path)
            if image is not None and getattr(image, "shape", None) is not None:
                height, width = image.shape[:2]
                return width, height
        except Exception:
            pass
    return 1, 1


def encode_detect_lines(labels, width, height):
    """把矩形框列表编码为 YOLO 文本行。"""
    lines = []
    for item in labels or []:
        cls = int(item.get("class", 0))
        x1 = float(item["x1"])
        y1 = float(item["y1"])
        x2 = float(item["x2"])
        y2 = float(item["y2"])
        cx = ((x1 + x2) / 2.0) / width
        cy = ((y1 + y2) / 2.0) / height
        ww = (x2 - x1) / width
        hh = (y2 - y1) / height
        lines.append(f"{cls} {cx:.6f} {cy:.6f} {ww:.6f} {hh:.6f}")
    return lines


def decode_detect_file(label_path, width, height):
    """把 YOLO 标签文件解码为像素坐标框。"""
    boxes = []
    if not os.path.exists(label_path):
        return boxes
    try:
        with open(label_path, "r", encoding="utf-8") as handle:
            for line in handle:
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                cls = parse_yolo_class_id(parts[0])
                cx = float(parts[1]) * width
                cy = float(parts[2]) * height
                ww = float(parts[3]) * width
                hh = float(parts[4]) * height
                x1 = max(0.0, cx - ww / 2)
                y1 = max(0.0, cy - hh / 2)
                x2 = min(float(width), cx + ww / 2)
                y2 = min(float(height), cy + hh / 2)
                boxes.append({"class": cls, "x1": x1, "y1": y1, "x2": x2, "y2": y2})
    except Exception:
        return []
    return boxes


def decode_classification_file(label_path):
    """把分类标签文件解码为单个类别 id。"""
    if not os.path.exists(label_path):
        return None
    try:
        with open(label_path, "r", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                return parse_yolo_class_id(text.split()[0])
    except Exception:
        return None
    return None


def encode_classification_lines(annotation):
    """把图像级分类标注编码为单行类别 id。"""
    class_id = annotation.get("class_id") if isinstance(annotation, dict) else None
    if class_id is None or class_id == "":
        return []
    return [str(int(class_id))]


def resolve_classification_class_id(context):
    """从分类样本当前目录推导类别 id。"""
    class_name = context.get("class_name") or ""
    class_names = context.get("class_names") or []
    try:
        return next(index for index, name in enumerate(class_names) if str(name) == class_name)
    except StopIteration:
        return None


def encode_segment_lines(labels, width, height):
    """把分割多边形列表编码为 YOLO segment 文本行。"""
    lines = []
    for item in labels or []:
        cls = int(item.get("class", 0))
        points = item.get("points") or []
        if len(points) < 3:
            continue
        coords = []
        last = None
        for pt in points:
            x = float(pt.get("x"))
            y = float(pt.get("y"))
            x = max(0.0, min(float(width), x))
            y = max(0.0, min(float(height), y))
            pair = (x, y)
            if last is not None and pair == last:
                continue
            last = pair
            coords.append(x / float(width))
            coords.append(y / float(height))
        if len(coords) < 6:
            continue
        lines.append(f"{cls} " + " ".join(f"{v:.6f}" for v in coords))
    return lines


def decode_segment_file(label_path, width, height):
    """把 YOLO segment 标签文件解码为像素坐标多边形。"""
    polygons = []
    if not os.path.exists(label_path):
        return polygons
    try:
        with open(label_path, "r", encoding="utf-8") as handle:
            for line in handle:
                parts = line.strip().split()
                if len(parts) < 7:
                    continue
                cls = parse_yolo_class_id(parts[0])
                coords = parts[1:]
                if len(coords) < 6:
                    continue
                if len(coords) % 2 == 1:
                    coords = coords[:-1]
                points = []
                for idx in range(0, len(coords), 2):
                    try:
                        x = float(coords[idx]) * float(width)
                        y = float(coords[idx + 1]) * float(height)
                    except Exception:
                        continue
                    x = max(0.0, min(float(width), x))
                    y = max(0.0, min(float(height), y))
                    points.append({"x": x, "y": y})
                if len(points) < 3:
                    continue
                if points and points[0] == points[-1]:
                    points = points[:-1]
                polygons.append({"class": cls, "points": points})
    except Exception:
        return []
    return polygons


def _normalize_pose_kpt_shape(raw_kpt_shape):
    """把配置中的 kpt_shape 规范为 [count, dims]。"""
    if not isinstance(raw_kpt_shape, (list, tuple)) or len(raw_kpt_shape) != 2:
        return None
    try:
        keypoint_count = int(raw_kpt_shape[0])
        dims = int(raw_kpt_shape[1])
    except (TypeError, ValueError):
        return None
    if keypoint_count <= 0 or dims not in (2, 3):
        return None
    return [keypoint_count, dims]


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
    if not normalized_pairs:
        return []

    def _is_valid(pairs):
        return all(0 <= start < keypoint_count and 0 <= end < keypoint_count and start != end for start, end in pairs)

    if _is_valid(normalized_pairs):
        return normalized_pairs
    if _is_valid(one_based_pairs):
        return one_based_pairs
    return []


def load_pose_annotation_meta(dataset_root, class_names=None):
    """读取 pose 标注所需的关键点元数据。"""
    config = load_dataset_yaml(dataset_root, default={})
    kpt_shape = _normalize_pose_kpt_shape((config or {}).get("kpt_shape")) or [0, 3]
    keypoint_count = int(kpt_shape[0])
    dims = int(kpt_shape[1])
    flip_idx = (config or {}).get("flip_idx")
    if not isinstance(flip_idx, list) or len(flip_idx) != keypoint_count:
        flip_idx = list(range(keypoint_count))
    else:
        flip_idx = [int(value) for value in flip_idx]
    raw_kpt_names = (config or {}).get("kpt_names")
    normalized_kpt_names = {}
    if isinstance(raw_kpt_names, dict):
        for raw_class_id, names in raw_kpt_names.items():
            try:
                class_id = int(raw_class_id)
            except (TypeError, ValueError):
                continue
            if isinstance(names, list) and len(names) == keypoint_count:
                normalized_kpt_names[class_id] = [str(name) for name in names]
    default_names = [f"kpt_{index}" for index in range(keypoint_count)]
    class_count = len(class_names or [])
    for class_id in range(class_count):
        normalized_kpt_names.setdefault(class_id, list(default_names))
    if not normalized_kpt_names:
        normalized_kpt_names[0] = list(default_names)
    skeleton = _normalize_pose_skeleton((config or {}).get("skeleton"), keypoint_count)
    return {
        "kpt_shape": [keypoint_count, dims],
        "keypoint_count": keypoint_count,
        "dims": dims,
        "flip_idx": flip_idx,
        "kpt_names": normalized_kpt_names,
        "skeleton": skeleton,
    }


def _infer_pose_line_dims(payload_length, kpt_shape):
    """按配置或标签长度推断单行 pose 标签的关键点维度。"""
    normalized_shape = _normalize_pose_kpt_shape(kpt_shape)
    if normalized_shape:
        keypoint_count, dims = normalized_shape
        expected_length = keypoint_count * dims
        if payload_length >= expected_length:
            return dims, keypoint_count
    if payload_length > 0 and payload_length % 3 == 0:
        return 3, payload_length // 3
    if payload_length > 0 and payload_length % 2 == 0:
        return 2, payload_length // 2
    return None, 0


def decode_pose_file(label_path, width, height, *, kpt_shape=None):
    """把 YOLO pose 标签解码为像素坐标关键点实例。"""
    instances = []
    if not os.path.exists(label_path):
        return instances
    try:
        with open(label_path, "r", encoding="utf-8") as handle:
            for line in handle:
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                cls = parse_yolo_class_id(parts[0])
                cx = float(parts[1]) * float(width)
                cy = float(parts[2]) * float(height)
                ww = float(parts[3]) * float(width)
                hh = float(parts[4]) * float(height)
                x1 = max(0.0, cx - ww / 2.0)
                y1 = max(0.0, cy - hh / 2.0)
                x2 = min(float(width), cx + ww / 2.0)
                y2 = min(float(height), cy + hh / 2.0)
                payload = parts[5:]
                dims, keypoint_count = _infer_pose_line_dims(len(payload), kpt_shape)
                if not dims or keypoint_count <= 0:
                    continue
                points = []
                for index in range(keypoint_count):
                    base = index * dims
                    try:
                        px = float(payload[base]) * float(width)
                        py = float(payload[base + 1]) * float(height)
                    except (TypeError, ValueError, IndexError):
                        px = 0.0
                        py = 0.0
                    visible = 0
                    if dims == 3:
                        try:
                            visible = int(float(payload[base + 2]))
                        except (TypeError, ValueError, IndexError):
                            visible = 0
                    elif px > 0 or py > 0:
                        visible = 2
                    px = max(0.0, min(float(width), px))
                    py = max(0.0, min(float(height), py))
                    visible = max(0, min(2, visible))
                    points.append({"x": px, "y": py, "visible": visible})
                instances.append(
                    {
                        "class": cls,
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2,
                        "keypoints": points,
                    }
                )
    except Exception:
        return []
    return instances


def _build_pose_bbox(instance, width, height, keypoints):
    """优先使用实例自带 bbox，缺失时从可见关键点回推。"""
    try:
        x1 = float(instance.get("x1"))
        y1 = float(instance.get("y1"))
        x2 = float(instance.get("x2"))
        y2 = float(instance.get("y2"))
    except (TypeError, ValueError):
        x1 = y1 = x2 = y2 = None
    if None not in (x1, y1, x2, y2) and x2 > x1 and y2 > y1:
        return (
            max(0.0, min(float(width), x1)),
            max(0.0, min(float(height), y1)),
            max(0.0, min(float(width), x2)),
            max(0.0, min(float(height), y2)),
        )
    visible_points = [
        (
            max(0.0, min(float(width), float(point.get("x", 0.0)))),
            max(0.0, min(float(height), float(point.get("y", 0.0)))),
        )
        for point in (keypoints or [])
        if int(point.get("visible", 0) or 0) > 0
    ]
    if not visible_points:
        return 0.0, 0.0, 0.0, 0.0
    xs = [point[0] for point in visible_points]
    ys = [point[1] for point in visible_points]
    min_x = min(xs)
    max_x = max(xs)
    min_y = min(ys)
    max_y = max(ys)
    if max_x <= min_x:
        max_x = min(float(width), min_x + 1.0)
    if max_y <= min_y:
        max_y = min(float(height), min_y + 1.0)
    return min_x, min_y, max_x, max_y


def encode_pose_lines(labels, width, height, *, kpt_shape=None):
    """把关键点实例编码为 YOLO pose 文本行。"""
    lines = []
    normalized_shape = _normalize_pose_kpt_shape(kpt_shape)
    keypoint_count = int(normalized_shape[0]) if normalized_shape else 0
    dims = int(normalized_shape[1]) if normalized_shape else 3
    for item in labels or []:
        cls = int(item.get("class", 0))
        keypoints = list((item or {}).get("keypoints") or [])
        current_count = keypoint_count or len(keypoints)
        if current_count <= 0:
            continue
        x1, y1, x2, y2 = _build_pose_bbox(item, width, height, keypoints)
        if x2 <= x1 or y2 <= y1:
            continue
        cx = ((x1 + x2) / 2.0) / float(width)
        cy = ((y1 + y2) / 2.0) / float(height)
        ww = max(0.0, x2 - x1) / float(width)
        hh = max(0.0, y2 - y1) / float(height)
        coords = []
        for index in range(current_count):
            point = keypoints[index] if index < len(keypoints) and isinstance(keypoints[index], dict) else {}
            visible = int(point.get("visible", 0) or 0)
            visible = max(0, min(2, visible))
            if visible > 0:
                px = max(0.0, min(float(width), float(point.get("x", 0.0))))
                py = max(0.0, min(float(height), float(point.get("y", 0.0))))
            else:
                px = 0.0
                py = 0.0
            coords.append(f"{px / float(width):.6f}")
            coords.append(f"{py / float(height):.6f}")
            if dims == 3:
                coords.append(str(max(0, min(2, visible))))
        lines.append(f"{cls} {cx:.6f} {cy:.6f} {ww:.6f} {hh:.6f} " + " ".join(coords))
    return lines
