"""负责项目内数据集根目录解析、统计分析与扫描。"""

import os

from contexts.dataset.infrastructure.dataset_layout import (
    get_dataset_images_dir,
    get_dataset_labels_dir,
    get_dataset_root_images_dir,
    get_dataset_root_labels_dir,
)
from contexts.dataset.infrastructure.dataset_schema import (
    find_dataset_config,
    load_dataset_names,
    load_dataset_yaml,
    resolve_dataset_names_dict,
    resolve_dataset_tags,
)
from contexts.project.infrastructure.project_paths import (
    get_project_dataset_dir,
    get_project_training_dir,
)
from shared.utils.media_constants import DATASET_SPLITS, IMAGE_FILE_EXTENSIONS
from shared.utils.path_utils import is_within_path, project_name_from_path, resolve_project_path, resolve_storage_path, storage_path_ref


def resolve_project_dataset_root(project_path, dataset_name=None, dataset_path=None):
    """在项目范围内解析合法的数据集根目录。"""
    project_path = resolve_project_path(project_path)
    if not project_path:
        return None

    resolved_by_path = None
    if dataset_path:
        candidate = resolve_storage_path(dataset_path)
        if candidate:
            real_candidate = os.path.realpath(candidate)
            if is_within_path(real_candidate, project_path) and os.path.isdir(real_candidate):
                resolved_by_path = real_candidate

    resolved_by_name = None
    if dataset_name:
        candidate = get_project_dataset_dir(project_path, dataset_name)
        real_candidate = os.path.realpath(candidate)
        if is_within_path(real_candidate, project_path) and os.path.isdir(real_candidate):
            resolved_by_name = real_candidate

    if dataset_name and dataset_path:
        if not resolved_by_name or not resolved_by_path:
            return None
        if resolved_by_name != resolved_by_path:
            raise ValueError("dataset_name 与 dataset_path 不一致")
        return resolved_by_name

    return resolved_by_path or resolved_by_name


def analyze_dataset(dataset_path):
    """统计数据集图片、标签和类别分布。"""
    info = {
        "image_count": 0,
        "label_count": 0,
        "total_objects": 0,
        "classes": [],
        "class_stats": [],
        "names": [],
        "has_train": False,
        "has_val": False,
        "has_test": False,
        "annotation_rate": 0.0,
        "tags": [],
    }
    class_counts = {}
    data_config = load_dataset_yaml(dataset_path, default={})
    class_names = resolve_dataset_names_dict(data_config.get("names"))
    info["tags"] = resolve_dataset_tags(data_config)
    info["names"] = load_dataset_names(dataset_path)

    def scan_split(img_dir, lbl_dir):
        """扫描单个 split 的图片与标签统计。"""
        if not os.path.exists(img_dir):
            return False
        images = []
        for root, dirs, files in os.walk(img_dir):
            dirs.sort()
            files.sort()
            for name in files:
                if not name.lower().endswith(IMAGE_FILE_EXTENSIONS):
                    continue
                images.append(os.path.join(root, name))
        if not images:
            return False
        info["image_count"] += len(images)
        if not os.path.exists(lbl_dir):
            return True
        for image_path in images:
            rel_path = os.path.relpath(image_path, img_dir)
            label_rel_path = os.path.splitext(rel_path)[0] + ".txt"
            label_path = os.path.join(lbl_dir, label_rel_path)
            if not os.path.exists(label_path):
                continue
            info["label_count"] += 1
            try:
                with open(label_path, "r", encoding="utf-8") as f:
                    for line in f:
                        parts = line.strip().split()
                        if not parts:
                            continue
                        cls_id = int(float(parts[0]))
                        class_counts[cls_id] = class_counts.get(cls_id, 0) + 1
                        info["total_objects"] += 1
            except Exception:
                pass
        return True

    has_split = False
    for split in DATASET_SPLITS:
        img_dir = get_dataset_images_dir(dataset_path, split)
        lbl_dir = get_dataset_labels_dir(dataset_path, split)
        if scan_split(img_dir, lbl_dir):
            info[f"has_{split}"] = True
            has_split = True

    if not has_split:
        scan_split(get_dataset_root_images_dir(dataset_path), get_dataset_root_labels_dir(dataset_path))

    if info["image_count"] > 0:
        info["annotation_rate"] = info["label_count"] / info["image_count"]

    for cls_id in sorted(class_counts.keys()):
        count = class_counts[cls_id]
        percentage = round((count / info["total_objects"] * 100), 1) if info["total_objects"] > 0 else 0
        stats = {
            "id": cls_id,
            "name": class_names.get(cls_id, f"class_{cls_id}"),
            "count": count,
            "percentage": percentage,
        }
        info["classes"].append(stats)
        info["class_stats"].append(stats)

    return info


def build_dataset_summary(dataset_root, analysis, *, name=None):
    """把分析结果组装为统一的数据集摘要结构。"""
    return {
        "name": name or project_name_from_path(dataset_root),
        "type": "training",
        "path": storage_path_ref(dataset_root),
        "image_count": analysis["image_count"],
        "label_count": analysis["label_count"],
        "annotation_rate": analysis["annotation_rate"],
        "classes": analysis["classes"],
        "has_train": analysis["has_train"],
        "has_val": analysis["has_val"],
        "has_test": analysis["has_test"],
        "tags": analysis["tags"],
    }


def scan_project_datasets(project_path):
    """遍历项目训练目录并收集受协议管理的数据集摘要。"""
    project_path = resolve_project_path(project_path)
    if not project_path:
        raise ValueError("缺少项目路径")
    datasets = []
    train_dir = get_project_training_dir(project_path)
    if not os.path.isdir(train_dir):
        return datasets

    for item in sorted(os.listdir(train_dir)):
        dataset_root = os.path.join(train_dir, item)
        if not os.path.isdir(dataset_root):
            continue
        if not find_dataset_config(dataset_root):
            continue
        analysis = analyze_dataset(dataset_root)
        datasets.append(build_dataset_summary(dataset_root, analysis, name=item))
    return datasets


def get_project_dataset_summary(project_path, dataset_name):
    """返回项目中单个数据集的摘要信息。"""
    dataset_root = resolve_project_dataset_root(project_path, dataset_name=dataset_name)
    if not dataset_root or not find_dataset_config(dataset_root):
        return None
    analysis = analyze_dataset(dataset_root)
    return build_dataset_summary(dataset_root, analysis)
