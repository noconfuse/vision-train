"""编排数据集增删改查、导入和整理等应用层用例。"""

import os
import random

from contexts.dataset.domain.capabilities import (
    DATASET_OPERATION_AUGMENT_DATASET,
    DATASET_OPERATION_AUTO_ANNOTATE,
    DATASET_OPERATION_CREATE_SUBSET,
    DATASET_OPERATION_DELETE_LABEL,
    DATASET_OPERATION_DEDUPLICATE_IMAGES,
    DATASET_OPERATION_MERGE_DATASETS,
    DATASET_OPERATION_REORDER_LABELS,
    DATASET_OPERATION_SPLIT_DATASET,
    DATASET_OPERATION_UPLOAD_IMAGES,
    require_dataset_operation,
)
from contexts.dataset.infrastructure.dataset_layout import (
    DATASET_SPLIT_TRAIN,
    STANDARD_DATASET_SPLITS,
    get_dataset_auto_labels_dir,
    get_dataset_split_content_dir,
)
from contexts.project.infrastructure.project_paths import (
    get_project_dataset_dir,
    get_project_training_dir,
)
from contexts.dataset.infrastructure.dataset_augmentation import build_augmented_subset
from contexts.dataset.infrastructure.dataset_import_runtime import (
    cleanup_import_jobs as cleanup_dataset_import_jobs,
    create_import_job as create_dataset_import_job,
    has_import_job,
)
from contexts.dataset.infrastructure.dataset_labels import (
    delete_dataset_label as delete_label,
    reorder_dataset_labels as reorder_labels,
    resolve_dataset_label_id as resolve_label_id,
)
from contexts.dataset.infrastructure.dataset_mutations import (
    merge_standard_datasets as merge_datasets,
    split_standard_dataset as split_dataset,
)
from contexts.dataset.infrastructure.dataset_repository import analyze_dataset as analyze_dataset_record
from contexts.dataset.infrastructure.dataset_repository import resolve_project_dataset_root
from contexts.dataset.infrastructure.dataset_repository import scan_project_datasets as scan_project_dataset_records
from contexts.dataset.infrastructure.dataset_task_strategy import resolve_dataset_task_strategy
from contexts.dataset.infrastructure.dataset_task_type import load_dataset_identity_meta, load_dataset_vision_task_type
from contexts.dataset.infrastructure.dataset_versioning import (
    create_dataset_version_snapshot,
    delete_dataset_version_store,
    get_current_dataset_version_record,
    list_dataset_version_records,
    restore_dataset_version_snapshot,
)
from contexts.training.infrastructure.workflow_repository import delete_dataset_training_state
from contexts.dataset.infrastructure.dataset_schema import (
    find_dataset_config,
    load_dataset_names,
    load_dataset_yaml,
    require_dataset_config_path,
    save_dataset_vision_task_type,
    save_standard_dataset_yaml,
    save_dataset_tags,
    validate_dataset_name as validate_name,
)
from constants.media import IMAGE_FILE_EXTENSIONS
from shared.utils.fs_utils import (
    compute_file_md5,
    remove_file_silent,
    remove_tree,
)
from shared.utils.path_utils import (
    build_file_item,
    build_file_items,
    is_within_path,
    resolve_allowed_dir_path,
    resolve_storage_path,
    sanitize_bundle_name,
    slice_items,
    storage_path_ref,
)
from shared.utils.value_utils import parse_bool, require_present
from shared.utils.zip_utils import split_archive_filename


def _present_dataset_version(record):
    """把内部版本记录转换成接口输出结构。"""
    if not record:
        return None
    return {
        **record,
        "snapshot_path": storage_path_ref(record["snapshot_path"]) if record.get("snapshot_path") else None,
        "source_dataset_path": storage_path_ref(record["source_dataset_path"]) if record.get("source_dataset_path") else None,
    }


def _publish_dataset_version(project_path, dataset_root, dataset_name, reason, *, source_version_id=None):
    """为当前工作数据集发布一个新版本。"""
    return _present_dataset_version(
        create_dataset_version_snapshot(
            project_path,
            dataset_root,
            dataset_name=dataset_name,
            reason=reason,
            source_version_id=source_version_id,
        )
    )


def _load_names(source_root):
    """优先从配置读取类别名，缺失时退回分析结果。"""
    names = load_dataset_names(source_root)
    if not names:
        info = analyze_dataset_record(source_root) or {}
        raw = info.get("names") or []
        if isinstance(raw, list):
            names = [str(x) for x in raw]
    return names


def list_project_datasets(project_path):
    """返回项目内全部受协议管理的数据集摘要，作为 dataset 上下文公开查询入口。"""
    return scan_project_dataset_records(project_path)


def has_dataset_import_job(job_id):
    """判断导入任务是否仍有效，作为 dataset 上下文公开查询入口。"""
    return has_import_job(job_id)


def get_dataset_info(project_path, dataset_name):
    """读取单个数据集的详细统计信息。"""
    require_present(project_path=project_path, dataset_name=dataset_name)
    dataset_root = resolve_project_dataset_root(project_path, dataset_name=dataset_name)
    if not dataset_root:
        raise ValueError("数据集不存在")
    info = analyze_dataset_record(dataset_root)
    info["name"] = dataset_name
    info["path"] = dataset_root
    info.update(load_dataset_identity_meta(dataset_root))
    return info


def list_dataset_versions(project_path, dataset_name):
    """列出数据集的全部历史版本。"""
    require_present(project_path=project_path, dataset_name=dataset_name)
    dataset_root = resolve_project_dataset_root(project_path, dataset_name=dataset_name)
    if not dataset_root:
        raise ValueError("数据集不存在")
    identity = load_dataset_identity_meta(dataset_root)
    return {
        "dataset_name": dataset_name,
        "dataset_id": identity["dataset_id"],
        "current_version_id": identity.get("current_version_id"),
        "versions": [_present_dataset_version(item) for item in list_dataset_version_records(project_path, identity["dataset_id"])],
    }


def publish_dataset_version(project_path, dataset_name, reason="manual_publish"):
    """把当前工作数据集冻结成一个新的历史版本。"""
    require_present(project_path=project_path, dataset_name=dataset_name)
    dataset_root = resolve_project_dataset_root(project_path, dataset_name=dataset_name)
    if not dataset_root:
        raise ValueError("数据集不存在")
    return {
        "dataset_name": dataset_name,
        "version": _publish_dataset_version(project_path, dataset_root, dataset_name, reason),
    }


def restore_dataset_version(project_path, dataset_name, version_id):
    """将历史版本恢复为当前工作数据集，并生成新的当前版本。

    若当前版本本身就是上一次“恢复”出来的、且内容来源于待恢复到的目标版本，
    则拒绝重复恢复，避免版本列表里出现内容相同的恢复记录。
    """
    require_present(project_path=project_path, dataset_name=dataset_name, version_id=version_id)
    dataset_root = resolve_project_dataset_root(project_path, dataset_name=dataset_name)
    if not dataset_root:
        raise ValueError("数据集不存在")

    current_record = get_current_dataset_version_record(project_path, dataset_root)
    if (
        current_record
        and current_record.get("version_id") != version_id
        and current_record.get("reason") == "restore"
        and current_record.get("source_version_id") == version_id
    ):
        raise ValueError(
            "当前版本已是该版本的恢复结果，内容一致；如需重新恢复，请先做一次修改（例如发布当前版本）"
        )

    result = restore_dataset_version_snapshot(project_path, dataset_root, version_id, dataset_name=dataset_name)
    return {
        "dataset_name": dataset_name,
        **result,
    }


def create_subset(project_path, source_dataset, new_dataset_name, image_paths):
    """从现有图片集合复制出一个新的训练子集。"""
    require_present(
        project_path=project_path,
        source_dataset=source_dataset,
        new_dataset_name=new_dataset_name,
        image_paths=image_paths,
    )
    err = validate_name(new_dataset_name)
    if err:
        raise ValueError(err)

    target_root = get_project_dataset_dir(project_path, new_dataset_name)
    if os.path.exists(target_root):
        raise ValueError(f"数据集 {new_dataset_name} 已存在")

    source_root = resolve_project_dataset_root(project_path, dataset_name=source_dataset)
    if not source_root:
        raise ValueError("源数据集不存在")
    vision_task_type = load_dataset_vision_task_type(source_root)
    require_dataset_operation(vision_task_type, DATASET_OPERATION_CREATE_SUBSET)
    names = {}
    source_yaml = find_dataset_config(source_root)
    if source_yaml:
        names = load_dataset_yaml(source_root, default={}).get("names") or {}
    if not names:
        info = analyze_dataset_record(source_root) or {}
        if info.get("names"):
            names = {i: n for i, n in enumerate(info["names"])}

    strategy = resolve_dataset_task_strategy(vision_task_type)
    count = 0
    for image_path in image_paths:
        if strategy.copy_subset_sample(source_root, target_root, image_path):
            count += 1

    save_standard_dataset_yaml(
        target_root,
        names,
        vision_task_type=vision_task_type,
        include_test=False,
        val_fallback_split=DATASET_SPLIT_TRAIN,
    )
    save_dataset_vision_task_type(target_root, vision_task_type)
    return {
        "dataset_name": new_dataset_name,
        "image_count": count,
        "dataset_root": storage_path_ref(target_root),
        "version": _publish_dataset_version(project_path, target_root, new_dataset_name, "create_subset"),
    }


def augment_subset(project_path, source_dataset, new_dataset_name, payload):
    """按目标类配置生成增强子集。"""
    target_class_configs = payload.get("target_class_configs") or []
    require_present(project_path=project_path, source_dataset=source_dataset, target_class_configs=target_class_configs)
    dry_run = parse_bool(payload.get("dry_run", False), default=False)
    if not dry_run and not new_dataset_name:
        raise ValueError("缺少 new_dataset_name")

    source_root = resolve_project_dataset_root(project_path, dataset_name=source_dataset)
    if not source_root:
        raise ValueError("源数据集不存在")
    require_dataset_operation(load_dataset_vision_task_type(source_root), DATASET_OPERATION_AUGMENT_DATASET)
    target_root = ""
    if not dry_run:
        target_root = get_project_dataset_dir(project_path, new_dataset_name)
    if target_root and os.path.exists(target_root):
        raise ValueError(f"数据集 {new_dataset_name} 已存在")

    result = build_augmented_subset(
        source_root=source_root,
        target_root=target_root,
        names=_load_names(source_root),
        vision_task_type=load_dataset_vision_task_type(source_root),
        split=str(payload.get("split") or DATASET_SPLIT_TRAIN).strip() or DATASET_SPLIT_TRAIN,
        target_class_configs=target_class_configs,
        non_target_keep_ratio=min(1.0, max(0.0, float(payload.get("non_target_keep_ratio") if payload.get("non_target_keep_ratio") is not None else 0.35))),
        seed=int(payload.get("seed") or 42),
        copy_eval_splits=parse_bool(payload.get("copy_eval_splits", True), default=True),
        rebalance_eval_splits=parse_bool(payload.get("rebalance_eval_splits", False), default=False),
        enable_hflip=parse_bool(payload.get("enable_hflip", True), default=True),
        enable_vflip=parse_bool(payload.get("enable_vflip", False), default=False),
        dry_run=dry_run,
        eval_target_ratio=payload.get("eval_target_ratio"),
        color_jitter=min(0.8, max(0.0, float(payload.get("color_jitter") if payload.get("color_jitter") is not None else 0.2))),
    )
    if not result.get("dry_run"):
        result["new_dataset_name"] = new_dataset_name
        result["message"] = f"已创建增强子集 {new_dataset_name}：train样本 {result['output_total']} 张，目标类占比 {result['output_target_ratio']}%"
        result["version"] = _publish_dataset_version(project_path, target_root, new_dataset_name, "augment_subset")
    return result


def download_dataset_info(project_path, dataset_name):
    """校验下载路径并返回打包所需信息。"""
    require_present(project_path=project_path, dataset_name=dataset_name)
    dataset_root = resolve_project_dataset_root(project_path, dataset_name=dataset_name)
    if not dataset_root:
        raise FileNotFoundError("数据集不存在")
    dataset_real = resolve_allowed_dir_path(dataset_root, allowed_roots=[project_path])
    return {"dataset_root": dataset_real, "bundle_name": sanitize_bundle_name(dataset_name, default="dataset")}


def list_dataset_images(project_path, dataset_name, split=DATASET_SPLIT_TRAIN, offset=0, limit=50, classes_raw=None, mode="include", unannotated_raw=None, has_auto_label_raw=None):
    """按类别和标注状态筛选数据集图片。"""
    require_present(project_path=project_path, dataset_name=dataset_name)
    dataset_root = get_project_dataset_dir(project_path, dataset_name)
    vision_task_type = load_dataset_vision_task_type(dataset_root)
    names = load_dataset_names(dataset_root)
    strategy = resolve_dataset_task_strategy(vision_task_type)

    unannotated = parse_bool(unannotated_raw)
    has_auto_label = parse_bool(has_auto_label_raw)
    class_ids = []
    if classes_raw is not None and str(classes_raw).strip() != "":
        for part in str(classes_raw).split(","):
            s = part.strip()
            if not s:
                continue
            try:
                class_ids.append(int(float(s)))
            except Exception:
                continue
    class_id_set = set(class_ids)

    images = []
    for image_path in strategy.iter_list_image_paths(
        dataset_root,
        split,
        unannotated=unannotated,
        has_auto_label=has_auto_label,
    ):
        item = strategy.build_image_record(
            dataset_root,
            split,
            image_path,
            names,
            class_id_set,
            mode,
            unannotated,
            has_auto_label,
        )
        if item:
            images.append(item)
    images.sort(key=lambda item: item["path"] if isinstance(item, dict) else str(item))
    items = build_file_items(images)
    return slice_items(items, offset=offset, limit=limit)


def upload_dataset_images(project_path, dataset_name, split, files):
    """保存上传图片并避免文件名冲突。"""
    require_present(project_path=project_path, dataset_name=dataset_name, files=files)
    dataset_root = get_project_dataset_dir(project_path, dataset_name)
    vision_task_type = load_dataset_vision_task_type(dataset_root)
    require_dataset_operation(vision_task_type, DATASET_OPERATION_UPLOAD_IMAGES)
    strategy = resolve_dataset_task_strategy(vision_task_type)
    saved = strategy.upload_images(dataset_root, split, files)
    if not saved and files:
        supported = ", ".join(IMAGE_FILE_EXTENSIONS)
        raise ValueError(f"未保存任何图片，当前支持的图片格式为: {supported}")
    return {"saved": build_file_items(saved), "count": len(saved)}


def delete_dataset_image(project_path, dataset_name, split, image_rel=None, image_path=None):
    """删除图片及其手工和自动标签文件。"""
    require_present(project_path=project_path, dataset_name=dataset_name)
    dataset_root = get_project_dataset_dir(project_path, dataset_name)
    vision_task_type = load_dataset_vision_task_type(dataset_root)
    strategy = resolve_dataset_task_strategy(vision_task_type)
    if not image_rel and image_path:
        try:
            image_rel = strategy.resolve_image_relative_path(dataset_root, split, image_path)
        except Exception:
            image_rel = None
    if not image_rel:
        raise ValueError("缺少 image_rel 或 image_path")
    resolved_image_path = resolve_storage_path(image_path) if image_path else None
    return {"deleted": strategy.delete_image(dataset_root, split, image_rel, image_path=resolved_image_path)}


def batch_delete_dataset_images(project_path, dataset_name, split, image_paths):
    """批量执行图片删除并收集逐项结果。"""
    require_present(project_path=project_path, dataset_name=dataset_name, image_paths=image_paths)
    results = []
    deleted_count = 0
    for image_path in image_paths:
        try:
            resolved_path = resolve_storage_path(image_path) or image_path
            result = delete_dataset_image(project_path, dataset_name, split, image_path=image_path)
            image_deleted = bool((result.get("deleted") or {}).get("image"))
            deleted_count += 1 if image_deleted else 0
            results.append({"item": build_file_item(resolved_path), "success": True, **result})
        except Exception as exc:
            results.append({"item": {"path": image_path}, "success": False, "error": str(exc)})
    return {"deleted_count": deleted_count, "results": results}


def reorder_dataset_labels_use_case(project_path, dataset_name, order, splits=None):
    """调用底层标签重排逻辑并补充路径信息。"""
    require_present(project_path=project_path, dataset_name=dataset_name, order=order)
    dataset_root = resolve_project_dataset_root(project_path, dataset_name=dataset_name)
    if not dataset_root:
        raise ValueError("数据集不存在")
    require_dataset_operation(load_dataset_vision_task_type(dataset_root), DATASET_OPERATION_REORDER_LABELS)
    yaml_path = require_dataset_config_path(dataset_root)
    result = reorder_labels(dataset_root, yaml_path, order, splits=splits)
    return {"dataset_root": storage_path_ref(dataset_root), "yaml_path": storage_path_ref(yaml_path), **result}


def delete_dataset_label_use_case(project_path, dataset_name, class_id=None, class_name=None, splits=None):
    """解析待删类别后调用标签删除逻辑。"""
    require_present(project_path=project_path, dataset_name=dataset_name)
    if class_id is None and (class_name is None or str(class_name).strip() == ""):
        raise ValueError("缺少 class_id 或 class_name")
    dataset_root = resolve_project_dataset_root(project_path, dataset_name=dataset_name)
    if not dataset_root:
        raise ValueError("数据集不存在")
    require_dataset_operation(load_dataset_vision_task_type(dataset_root), DATASET_OPERATION_DELETE_LABEL)
    yaml_path = require_dataset_config_path(dataset_root)
    delete_id = resolve_label_id(yaml_path, class_id=class_id, class_name=class_name)
    return delete_label(dataset_root, yaml_path, delete_id, splits=splits, delete_empty_files=True)


def update_dataset_tags(project_path, dataset_name, tags):
    """更新 dataset.yaml 中的 tags 字段。"""
    require_present(project_path=project_path, dataset_name=dataset_name)
    dataset_root = resolve_project_dataset_root(project_path, dataset_name=dataset_name)
    if not dataset_root:
        raise ValueError("数据集不存在")
    save_dataset_tags(dataset_root, tags)
    return {}


def clear_dataset_auto_labels(project_path, dataset_name):
    """清空数据集下所有 split 的自动标注文件。"""
    require_present(project_path=project_path, dataset_name=dataset_name)
    dataset_root = resolve_project_dataset_root(project_path, dataset_name=dataset_name)
    if not dataset_root:
        raise ValueError("数据集不存在")
    require_dataset_operation(load_dataset_vision_task_type(dataset_root), DATASET_OPERATION_AUTO_ANNOTATE)

    deleted_files = 0
    cleared_splits = []
    for split in STANDARD_DATASET_SPLITS:
        auto_dir = get_dataset_auto_labels_dir(dataset_root, split)
        if not os.path.isdir(auto_dir):
            continue
        split_deleted = 0
        for root, _, files in os.walk(auto_dir):
            for filename in files:
                file_path = os.path.join(root, filename)
                remove_file_silent(file_path)
                split_deleted += 1
        remove_tree(auto_dir)
        cleared_splits.append(split)
        deleted_files += split_deleted

    return {
        "dataset_name": dataset_name,
        "cleared_splits": cleared_splits,
        "deleted_auto_label_files": deleted_files,
    }


def delete_dataset_folder(project_path, dataset_name, dataset_path=None):
    """删除项目内指定的数据集目录。"""
    require_present(project_path=project_path, dataset_name=dataset_name)
    target_path = dataset_path or get_project_dataset_dir(project_path, dataset_name)
    deleted_path = resolve_allowed_dir_path(target_path, allowed_roots=[project_path])
    dataset_identity = load_dataset_identity_meta(deleted_path)
    training_cleanup = delete_dataset_training_state(
        project_path,
        dataset_identity["dataset_id"],
        dataset_name=dataset_name,
    )
    remove_tree(deleted_path)
    removed_version_store = delete_dataset_version_store(project_path, dataset_identity["dataset_id"])
    return {
        "deleted_path": storage_path_ref(deleted_path),
        "dataset_id": dataset_identity["dataset_id"],
        "removed_version_store": storage_path_ref(removed_version_store),
        **training_cleanup,
    }


def validate_dataset(dataset_path):
    """给出数据集是否可训练的基础校验结果。"""
    dataset_path = resolve_storage_path(dataset_path)
    if not dataset_path or not os.path.exists(dataset_path):
        raise ValueError("数据集路径无效")
    dataset_info = analyze_dataset_record(dataset_path)
    if not dataset_info:
        raise ValueError("无法分析数据集")
    can_train = bool((dataset_info.get("capabilities") or {}).get("operations", {}).get("train"))
    annotated_count = int(dataset_info.get("annotated_count") or dataset_info.get("label_count") or 0)
    validation = {
        "can_train": can_train and bool(dataset_info.get("has_train")) and annotated_count > 0,
        "can_validate": dataset_info["has_val"],
        "can_test": dataset_info["has_test"],
        "annotation_rate": dataset_info["annotation_rate"],
        "image_count": dataset_info["image_count"],
        "label_count": dataset_info["label_count"],
        "annotated_count": annotated_count,
        "unannotated_count": int(dataset_info.get("unannotated_count") or 0),
    }
    return {"validation": validation, "dataset_info": dataset_info}


def merge_dataset_pair(project_path, dataset_a, dataset_b, new_dataset_name):
    """合并两个类别定义一致的数据集。"""
    require_present(
        project_path=project_path,
        dataset_a=dataset_a,
        dataset_b=dataset_b,
        new_dataset_name=new_dataset_name,
    )
    if dataset_a == dataset_b:
        raise ValueError("两个数据集不能相同")
    dataset_a_root = resolve_project_dataset_root(project_path, dataset_name=dataset_a)
    dataset_b_root = resolve_project_dataset_root(project_path, dataset_name=dataset_b)
    if not dataset_a_root or not dataset_b_root:
        raise ValueError("数据集不存在")
    target_root = os.path.realpath(get_project_dataset_dir(project_path, new_dataset_name))
    if not is_within_path(target_root, project_path):
        raise ValueError("非法路径")
    if os.path.exists(target_root):
        raise ValueError(f"数据集 {new_dataset_name} 已存在")
    names_a = _load_names(dataset_a_root)
    names_b = _load_names(dataset_b_root)
    vision_task_type_a = load_dataset_vision_task_type(dataset_a_root)
    vision_task_type_b = load_dataset_vision_task_type(dataset_b_root)
    if not names_a or not names_b:
        raise ValueError("无法读取数据集类别信息")
    if names_a != names_b:
        raise ValueError("两个数据集类别不一致，无法合并")
    if vision_task_type_a != vision_task_type_b:
        raise ValueError("两个数据集任务类型不一致，无法合并")
    require_dataset_operation(vision_task_type_a, DATASET_OPERATION_MERGE_DATASETS)
    stats = merge_datasets(dataset_a_root, dataset_b_root, target_root, names_a, vision_task_type=vision_task_type_a)
    return {
        "dataset_root": storage_path_ref(target_root),
        "dataset_a_root": storage_path_ref(dataset_a_root),
        "dataset_b_root": storage_path_ref(dataset_b_root),
        "names": names_a,
        "stats": stats,
        "version": _publish_dataset_version(project_path, target_root, new_dataset_name, "merge_dataset_pair"),
    }


def split_dataset_use_case(project_path, dataset_name, val_ratio=0.1, test_ratio=0):
    """按类别分层抽样重建标准数据集的 split 分布。"""
    require_present(project_path=project_path, dataset_name=dataset_name)
    dataset_root = resolve_project_dataset_root(project_path, dataset_name=dataset_name)
    if not dataset_root:
        raise ValueError("数据集不存在")
    require_dataset_operation(load_dataset_vision_task_type(dataset_root), DATASET_OPERATION_SPLIT_DATASET)
    if float(val_ratio) + float(test_ratio) >= 1.0:
        raise ValueError("验证集和测试集比例之和必须小于1")
    counts = split_dataset(dataset_root, float(val_ratio), float(test_ratio), rng=random.Random())
    return {
        "dataset_name": dataset_name,
        "counts": counts,
        "version": _publish_dataset_version(project_path, dataset_root, dataset_name, "split_dataset"),
    }


def create_import_upload_job(project_path_ref, target_name, uploaded_file, vision_task_type):
    """校验上传 zip 并登记数据集导入任务。"""
    cleanup_dataset_import_jobs()
    if not uploaded_file:
        raise ValueError('未上传文件，请用 form-data 字段 "file"')
    if not uploaded_file.filename:
        raise ValueError("文件名为空")
    inferred_name, _archive_ext = split_archive_filename(uploaded_file.filename)
    dataset_name = (target_name or "").strip() or inferred_name
    err = validate_name(dataset_name)
    if err:
        raise ValueError(f'无法从文件名 "{dataset_name}" 推断合法数据集名，请用 target_name 参数指定' if not target_name else err)
    training_dir = get_project_training_dir(project_path_ref)
    os.makedirs(training_dir, exist_ok=True)
    dest = os.path.join(training_dir, dataset_name)
    if os.path.exists(dest):
        raise ValueError(f"数据集 {dataset_name} 已存在")
    return create_dataset_import_job(
        storage_path_ref(project_path_ref),
        dataset_name,
        uploaded_file,
        vision_task_type,
    )


def deduplicate_dataset_images(project_path, dataset_name=None, dataset_path=None, keep_split=DATASET_SPLIT_TRAIN):
    """按文件内容去重并保留优先 split 的样本。"""
    require_present("缺少 project_path，且 dataset_name 与 dataset_path 至少提供一个", project_path=project_path)
    if not dataset_name and not dataset_path:
        raise ValueError("缺少 dataset_name 或 dataset_path")

    dataset_root = resolve_project_dataset_root(project_path, dataset_name=dataset_name, dataset_path=dataset_path)
    if not dataset_root:
        raise ValueError("数据集不存在")
    vision_task_type = load_dataset_vision_task_type(dataset_root)
    require_dataset_operation(vision_task_type, DATASET_OPERATION_DEDUPLICATE_IMAGES)

    splits = list(STANDARD_DATASET_SPLITS)
    keep_split = str(keep_split or DATASET_SPLIT_TRAIN).strip().lower()
    if keep_split not in splits:
        keep_split = DATASET_SPLIT_TRAIN
    ordered_splits = [keep_split] + [split for split in splits if split != keep_split]
    priority = {split: index for index, split in enumerate(ordered_splits)}

    scanned = 0
    kept = {}
    duplicates = []
    errors = []

    for split in ordered_splits:
        images_dir = get_dataset_split_content_dir(dataset_root, split, vision_task_type)
        if not os.path.isdir(images_dir):
            continue
        for root, dirs, files in os.walk(images_dir):
            dirs.sort()
            files.sort()
            for file_name in files:
                if not file_name.lower().endswith(IMAGE_FILE_EXTENSIONS):
                    continue
                image_path = os.path.join(root, file_name)
                try:
                    rel_noext = os.path.splitext(os.path.relpath(image_path, images_dir))[0]
                    digest = compute_file_md5(image_path)
                    scanned += 1
                    item = {
                        "split": split,
                        "img": image_path,
                        "rel_noext": rel_noext,
                        "priority": priority.get(split, 9999),
                    }
                    previous = kept.get(digest)
                    if previous is None:
                        kept[digest] = item
                    elif item["priority"] < previous["priority"]:
                        duplicates.append(previous)
                        kept[digest] = item
                    else:
                        duplicates.append(item)
                except Exception as exc:
                    errors.append({"path": image_path, "error": str(exc)})

    deleted_images = 0
    deleted_labels = 0
    strategy = resolve_dataset_task_strategy(vision_task_type)
    for item in duplicates:
        try:
            if os.path.exists(item["img"]):
                if strategy.delete_duplicate_image(dataset_root, item["split"], item["img"]):
                    deleted_images += 1
        except Exception as exc:
            errors.append({"path": item["img"], "error": str(exc)})

        rel_noext = item["rel_noext"]
        split = item["split"]
        label_paths = strategy.resolve_deduplicate_label_paths(dataset_root, split, rel_noext)
        for label_path in label_paths:
            try:
                if os.path.exists(label_path):
                    remove_file_silent(label_path)
                    deleted_labels += 1
            except Exception as exc:
                errors.append({"path": label_path, "error": str(exc)})

    result = {
        "dataset_root": storage_path_ref(dataset_root),
        "keep_split": keep_split,
        "scanned_images": scanned,
        "unique_images": len(kept),
        "duplicate_images": len(duplicates),
        "deleted_images": deleted_images,
        "deleted_label_files": deleted_labels,
        "errors": errors[:50],
    }
    if deleted_images or deleted_labels:
        result["version"] = _publish_dataset_version(project_path, dataset_root, dataset_name or os.path.basename(dataset_root), "deduplicate_dataset")
    return result
