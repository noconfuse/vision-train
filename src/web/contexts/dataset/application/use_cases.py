"""编排数据集增删改查、导入和整理等应用层用例。"""

import os
import random
import shutil

from contexts.dataset.infrastructure.dataset_layout import (
    DATASET_SPLIT_TRAIN,
    STANDARD_DATASET_SPLITS,
    build_label_relpath,
    get_dataset_auto_labels_dir,
    get_dataset_images_dir,
    get_dataset_legacy_labels_dir,
    get_dataset_labels_dir,
    resolve_existing_label_path_for_image,
)
from contexts.project.infrastructure.project_paths import (
    get_project_dataset_dir,
    get_project_training_dir,
)
from contexts.dataset.infrastructure.dataset_augmentation import build_augmented_subset
from contexts.dataset.infrastructure.dataset_import_runtime import (
    cleanup_import_jobs as cleanup_dataset_import_jobs,
    create_import_job as create_dataset_import_job,
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
from contexts.dataset.infrastructure.dataset_schema import (
    find_dataset_config,
    load_dataset_names,
    load_dataset_yaml,
    require_dataset_config_path,
    save_standard_dataset_yaml,
    save_dataset_tags,
    validate_dataset_name as validate_name,
)
from shared.utils.media_constants import IMAGE_FILE_EXTENSIONS
from shared.utils.fs_utils import allocate_nonconflicting_path, compute_file_md5, remove_file_silent, remove_tree
from shared.utils.path_utils import (
    build_file_item,
    build_file_items,
    derive_file_stem,
    is_within_path,
    resolve_allowed_dir_path,
    resolve_relative_child_path,
    resolve_safe_child_path,
    resolve_storage_path,
    sanitize_bundle_name,
    slice_items,
    storage_path_ref,
    validate_filename,
)
from shared.utils.value_utils import parse_bool, require_present


def _load_names(source_root):
    """优先从配置读取类别名，缺失时退回分析结果。"""
    names = load_dataset_names(source_root)
    if not names:
        info = analyze_dataset_record(source_root) or {}
        raw = info.get("names") or []
        if isinstance(raw, list):
            names = [str(x) for x in raw]
    return names


def get_dataset_info(project_path, dataset_name):
    """读取单个数据集的详细统计信息。"""
    require_present(project_path=project_path, dataset_name=dataset_name)
    dataset_root = resolve_project_dataset_root(project_path, dataset_name=dataset_name)
    if not dataset_root:
        raise ValueError("数据集不存在")
    info = analyze_dataset_record(dataset_root)
    info["name"] = dataset_name
    info["path"] = dataset_root
    return info


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
    target_images_dir = get_dataset_images_dir(target_root, DATASET_SPLIT_TRAIN)
    target_labels_dir = get_dataset_labels_dir(target_root, DATASET_SPLIT_TRAIN)
    os.makedirs(target_images_dir, exist_ok=True)
    os.makedirs(target_labels_dir, exist_ok=True)

    count = 0
    for image_path in image_paths:
        image_path = resolve_storage_path(image_path)
        if not image_path or not os.path.exists(image_path):
            continue
        image_name = os.path.basename(image_path)
        shutil.copy2(image_path, os.path.join(target_images_dir, image_name))

        label_path = resolve_existing_label_path_for_image(image_path)
        if label_path:
            shutil.copy2(label_path, os.path.join(target_labels_dir, os.path.basename(label_path)))
        count += 1

    source_root = resolve_project_dataset_root(project_path, dataset_name=source_dataset)
    names = {}
    if source_root:
        source_yaml = find_dataset_config(source_root)
        if source_yaml:
            names = load_dataset_yaml(source_root, default={}).get("names") or {}
        if not names:
            info = analyze_dataset_record(source_root) or {}
            if info.get("names"):
                names = {i: n for i, n in enumerate(info["names"])}

    save_standard_dataset_yaml(target_root, names, include_test=False, val_fallback_split=DATASET_SPLIT_TRAIN)
    return {"dataset_name": new_dataset_name, "image_count": count, "dataset_root": storage_path_ref(target_root)}


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
    target_root = ""
    if not dry_run:
        target_root = get_project_dataset_dir(project_path, new_dataset_name)
    if target_root and os.path.exists(target_root):
        raise ValueError(f"数据集 {new_dataset_name} 已存在")

    result = build_augmented_subset(
        source_root=source_root,
        target_root=target_root,
        names=_load_names(source_root),
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
    img_dir = get_dataset_images_dir(dataset_root, split)
    lbl_dir = get_dataset_labels_dir(dataset_root, split)
    auto_dir = get_dataset_auto_labels_dir(dataset_root, split)
    if not os.path.exists(img_dir):
        return {"items": [], "total": 0}

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
    for root, _, files in os.walk(img_dir):
        for filename in files:
            if not filename.lower().endswith(IMAGE_FILE_EXTENSIONS):
                continue
            image_path = os.path.join(root, filename)
            rel = os.path.relpath(image_path, img_dir)
            label_path = os.path.join(lbl_dir, build_label_relpath(rel))
            auto_label_path = os.path.join(auto_dir, build_label_relpath(rel))
            label_exists = os.path.exists(label_path)
            label_has_content = label_exists and os.path.getsize(label_path) > 0
            auto_label_exists = os.path.exists(auto_label_path)
            auto_label_has_content = auto_label_exists and os.path.getsize(auto_label_path) > 0
            if has_auto_label:
                if not auto_label_exists:
                    continue
            if unannotated:
                if label_exists:
                    continue
                images.append(
                    {
                        "path": image_path,
                        "pending": auto_label_has_content,
                        "has_auto_label": auto_label_has_content,
                        "annotated": label_has_content,
                    }
                )
                continue
            if class_id_set:
                present = set()
                if label_has_content:
                    try:
                        with open(label_path, "r", encoding="utf-8") as handle:
                            for line in handle:
                                parts = line.strip().split()
                                if not parts:
                                    continue
                                try:
                                    present.add(int(float(parts[0])))
                                except Exception:
                                    continue
                    except Exception:
                        present = set()
                has_any = bool(present & class_id_set)
                if mode == "exclude":
                    if has_any:
                        continue
                elif not has_any:
                    continue
            images.append(
                {
                    "path": image_path,
                    "pending": auto_label_has_content,
                    "has_auto_label": auto_label_has_content,
                    "annotated": label_has_content,
                }
            )
    images.sort(key=lambda item: item["path"] if isinstance(item, dict) else str(item))
    items = build_file_items(images)
    return slice_items(items, offset=offset, limit=limit)


def upload_dataset_images(project_path, dataset_name, split, files):
    """保存上传图片并避免文件名冲突。"""
    require_present(project_path=project_path, dataset_name=dataset_name, files=files)
    target_dir = get_dataset_images_dir(get_project_dataset_dir(project_path, dataset_name), split)
    os.makedirs(target_dir, exist_ok=True)
    saved = []
    for file in files:
        try:
            filename = validate_filename(
                file.filename,
                allowed_extensions=IMAGE_FILE_EXTENSIONS,
                field_name="图片名",
            )
        except ValueError:
            continue
        dst = allocate_nonconflicting_path(os.path.join(target_dir, filename))
        file.save(dst)
        saved.append(dst)
    return {"saved": build_file_items(saved), "count": len(saved)}


def delete_dataset_image(project_path, dataset_name, split, image_rel=None, image_path=None):
    """删除图片及其手工和自动标签文件。"""
    require_present(project_path=project_path, dataset_name=dataset_name)
    dataset_root = get_project_dataset_dir(project_path, dataset_name)
    img_dir = get_dataset_images_dir(dataset_root, split)
    lbl_dir = get_dataset_labels_dir(dataset_root, split)
    auto_dir = get_dataset_auto_labels_dir(dataset_root, split)
    if not image_rel and image_path:
        try:
            image_rel = resolve_relative_child_path(image_path, root=img_dir)
        except Exception:
            image_rel = None
    if not image_rel:
        raise ValueError("缺少 image_rel 或 image_path")

    image_target_real = resolve_safe_child_path(img_dir, image_rel)
    rel_noext = os.path.splitext(image_rel)[0]
    label_path = resolve_safe_child_path(lbl_dir, build_label_relpath(rel_noext))
    auto_path = resolve_safe_child_path(auto_dir, build_label_relpath(rel_noext))
    deleted = {"image": False, "label": False, "auto_label": False}
    if os.path.exists(image_target_real):
        remove_file_silent(image_target_real)
        deleted["image"] = True
    if os.path.exists(label_path):
        remove_file_silent(label_path)
        deleted["label"] = True
    if os.path.exists(auto_path):
        remove_file_silent(auto_path)
        deleted["auto_label"] = True
    return {"deleted": deleted}


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
    remove_tree(deleted_path)
    return {"deleted_path": storage_path_ref(deleted_path)}


def validate_dataset(dataset_path):
    """给出数据集是否可训练的基础校验结果。"""
    dataset_path = resolve_storage_path(dataset_path)
    if not dataset_path or not os.path.exists(dataset_path):
        raise ValueError("数据集路径无效")
    dataset_info = analyze_dataset_record(dataset_path)
    if not dataset_info:
        raise ValueError("无法分析数据集")
    validation = {
        "can_train": dataset_info["annotation_rate"] > 0.8,
        "can_validate": dataset_info["has_val"],
        "can_test": dataset_info["has_test"],
        "annotation_rate": dataset_info["annotation_rate"],
        "image_count": dataset_info["image_count"],
        "label_count": dataset_info["label_count"],
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
    if not names_a or not names_b:
        raise ValueError("无法读取数据集类别信息")
    if names_a != names_b:
        raise ValueError("两个数据集类别不一致，无法合并")
    stats = merge_datasets(dataset_a_root, dataset_b_root, target_root, names_a)
    return {
        "dataset_root": storage_path_ref(target_root),
        "dataset_a_root": storage_path_ref(dataset_a_root),
        "dataset_b_root": storage_path_ref(dataset_b_root),
        "names": names_a,
        "stats": stats,
    }


def split_dataset_use_case(project_path, dataset_name, val_ratio=0.1, test_ratio=0):
    """按比例重写标准数据集的 split 分布。"""
    require_present(project_path=project_path, dataset_name=dataset_name)
    dataset_root = resolve_project_dataset_root(project_path, dataset_name=dataset_name)
    if not dataset_root:
        raise ValueError("数据集不存在")
    if float(val_ratio) + float(test_ratio) >= 1.0:
        raise ValueError("验证集和测试集比例之和必须小于1")
    counts = split_dataset(dataset_root, float(val_ratio), float(test_ratio), rng=random.Random())
    return {"dataset_name": dataset_name, "counts": counts}


def create_import_upload_job(project_path_ref, target_name, uploaded_file):
    """校验上传 zip 并登记数据集导入任务。"""
    cleanup_dataset_import_jobs()
    if not uploaded_file:
        raise ValueError('未上传文件，请用 form-data 字段 "file"')
    if not uploaded_file.filename:
        raise ValueError("文件名为空")
    try:
        inferred_name = derive_file_stem(uploaded_file.filename, allowed_extensions={".zip"}, field_name="压缩包")
    except ValueError as exc:
        if "扩展名不支持" in str(exc):
            raise ValueError("仅支持 .zip 格式") from exc
        raise
    dataset_name = (target_name or "").strip() or inferred_name
    err = validate_name(dataset_name)
    if err:
        raise ValueError(f'无法从文件名 "{dataset_name}" 推断合法数据集名，请用 target_name 参数指定' if not target_name else err)
    training_dir = get_project_training_dir(project_path_ref)
    os.makedirs(training_dir, exist_ok=True)
    dest = os.path.join(training_dir, dataset_name)
    if os.path.exists(dest):
        raise ValueError(f"数据集 {dataset_name} 已存在")
    return create_dataset_import_job(storage_path_ref(project_path_ref), dataset_name, uploaded_file)


def deduplicate_dataset_images(project_path, dataset_name=None, dataset_path=None, keep_split=DATASET_SPLIT_TRAIN):
    """按文件内容去重并保留优先 split 的样本。"""
    require_present("缺少 project_path，且 dataset_name 与 dataset_path 至少提供一个", project_path=project_path)
    if not dataset_name and not dataset_path:
        raise ValueError("缺少 dataset_name 或 dataset_path")

    dataset_root = resolve_project_dataset_root(project_path, dataset_name=dataset_name, dataset_path=dataset_path)
    if not dataset_root:
        raise ValueError("数据集不存在")

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
        images_dir = get_dataset_images_dir(dataset_root, split)
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
    for item in duplicates:
        try:
            if os.path.exists(item["img"]):
                remove_file_silent(item["img"])
                deleted_images += 1
        except Exception as exc:
            errors.append({"path": item["img"], "error": str(exc)})

        rel_noext = item["rel_noext"]
        split = item["split"]
        for label_path in (
            os.path.join(get_dataset_labels_dir(dataset_root, split), build_label_relpath(rel_noext)),
            os.path.join(get_dataset_legacy_labels_dir(dataset_root, split), build_label_relpath(rel_noext)),
            os.path.join(get_dataset_auto_labels_dir(dataset_root, split), build_label_relpath(rel_noext)),
        ):
            try:
                if os.path.exists(label_path):
                    remove_file_silent(label_path)
                    deleted_labels += 1
            except Exception as exc:
                errors.append({"path": label_path, "error": str(exc)})

    return {
        "dataset_root": storage_path_ref(dataset_root),
        "keep_split": keep_split,
        "scanned_images": scanned,
        "unique_images": len(kept),
        "duplicate_images": len(duplicates),
        "deleted_images": deleted_images,
        "deleted_label_files": deleted_labels,
        "errors": errors[:50],
    }
