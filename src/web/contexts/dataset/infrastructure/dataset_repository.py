"""负责项目内数据集根目录解析、统计分析与扫描。"""

import os

from contexts.dataset.infrastructure.dataset_scan_strategy import resolve_dataset_scan_strategy
from contexts.dataset.infrastructure.dataset_task_strategy import resolve_dataset_task_strategy
from contexts.dataset.infrastructure.dataset_task_type import load_dataset_identity_meta, load_dataset_vision_task_type
from contexts.dataset.infrastructure.dataset_versioning import get_current_dataset_version_record
from contexts.dataset.infrastructure.dataset_schema import (
    find_dataset_config,
    load_dataset_names,
    load_dataset_yaml,
    resolve_dataset_names_dict,
    resolve_dataset_tags,
)
from contexts.training.domain.capability_snapshot import build_training_capabilities_snapshot
from contexts.project.infrastructure.project_paths import (
    get_project_dataset_dir,
    get_project_training_dir,
)
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
    vision_task_type = load_dataset_vision_task_type(dataset_path)
    task_strategy = resolve_dataset_task_strategy(vision_task_type)
    data_config = load_dataset_yaml(dataset_path, default={})
    identity = load_dataset_identity_meta(dataset_path)
    capabilities = build_training_capabilities_snapshot(
        vision_task_type,
        dataset_metadata={
            **(data_config or {}),
            **(identity or {}),
        },
    )
    info = {
        "image_count": 0,
        "label_count": 0,
        "annotated_count": 0,
        "unannotated_count": 0,
        "total_objects": 0,
        "classes": [],
        "class_stats": [],
        "names": [],
        "has_train": False,
        "has_val": False,
        "has_test": False,
        "annotation_rate": 0.0,
        "tags": [],
        "vision_task_type": vision_task_type,
        "capabilities": capabilities,
        "task_metadata": {},
    }
    class_counts = {}
    class_names = resolve_dataset_names_dict(data_config.get("names"))
    class_name_to_id = {str(name): int(class_id) for class_id, name in class_names.items()}
    info["tags"] = resolve_dataset_tags(data_config)
    info["task_metadata"] = task_strategy.build_dataset_summary_metadata(dataset_path, data_config) or {}
    info["names"] = load_dataset_names(dataset_path)
    resolve_dataset_scan_strategy(vision_task_type).scan_dataset(
        dataset_path,
        info,
        class_name_to_id,
        class_counts,
    )

    if info["image_count"] > 0:
        info["annotation_rate"] = info["label_count"] / info["image_count"]
    info["annotated_count"] = int(info["label_count"] or 0)
    info["unannotated_count"] = max(0, int(info["image_count"] or 0) - int(info["annotated_count"] or 0))

    # 把「dataset.yaml.names 里已经有但本次扫描从没出现过的类别」也补回 class_stats，
    # 避免新建的类别或还没贴标签的类别在前端不可见（外层无法展示）。
    seen_ids = set(class_counts.keys())
    for cls_id in sorted(set(class_names.keys()) | seen_ids):
        count = class_counts.get(cls_id, 0)
        percentage = round((count / info["total_objects"] * 100), 1) if info["total_objects"] > 0 else 0
        stats = {
            "id": int(cls_id),
            "name": class_names.get(cls_id, f"class_{cls_id}"),
            "count": count,
            "percentage": percentage,
        }
        info["classes"].append(stats)
        info["class_stats"].append(stats)

    return info


def build_dataset_summary(dataset_root, analysis, *, name=None):
    """把分析结果组装为统一的数据集摘要结构。"""
    project_path = os.path.dirname(os.path.dirname(os.path.realpath(dataset_root)))
    identity = load_dataset_identity_meta(dataset_root)
    current_version = get_current_dataset_version_record(project_path, dataset_root)
    return {
        "name": name or project_name_from_path(dataset_root),
        "type": "training",
        "vision_task_type": analysis.get("vision_task_type"),
        "path": storage_path_ref(dataset_root),
        "dataset_id": identity.get("dataset_id"),
        "current_version_id": identity.get("current_version_id"),
        "versioning_status": identity.get("versioning_status"),
        "dataset_created_at": identity.get("created_at"),
        "dataset_updated_at": identity.get("updated_at"),
        "current_version_created_at": (current_version or {}).get("created_at"),
        "image_count": analysis["image_count"],
        "label_count": analysis["label_count"],
        "annotated_count": analysis["annotated_count"],
        "unannotated_count": analysis["unannotated_count"],
        "annotation_rate": analysis["annotation_rate"],
        "classes": analysis["classes"],
        "capabilities": analysis["capabilities"],
        "has_train": analysis["has_train"],
        "has_val": analysis["has_val"],
        "has_test": analysis["has_test"],
        "tags": analysis["tags"],
        **(analysis.get("task_metadata") or {}),
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
