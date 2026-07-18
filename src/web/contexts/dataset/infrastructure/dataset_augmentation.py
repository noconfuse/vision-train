"""实现数据集增强子集的采样、复制和扩增细节。"""

import math
import os
import random
import shutil

from PIL import Image, ImageEnhance, ImageFilter, ImageOps

from contexts.dataset.infrastructure.dataset_layout import (
    DATASET_SPLIT_TEST,
    DATASET_SPLIT_TRAIN,
    DATASET_SPLIT_VAL,
    build_label_relpath,
    get_dataset_images_dir,
    get_dataset_labels_dir,
)
from contexts.dataset.infrastructure.dataset_schema import save_standard_dataset_yaml
from shared.utils.media_constants import DATASET_SPLITS, EVAL_SPLITS, IMAGE_FILE_EXTENSIONS
from shared.utils.yolo_utils import collect_yolo_class_counts


def normalize_target_class_configs(target_class_configs):
    """校验并标准化目标类配置。"""
    if not isinstance(target_class_configs, list) or not target_class_configs:
        raise ValueError("请至少添加一个目标类")

    normalized = []
    seen_ids = set()
    for item in target_class_configs:
        if not isinstance(item, dict):
            raise ValueError("目标类配置格式不正确")
        class_id_raw = item.get("class_id")
        multiplier_raw = item.get("target_multiplier")
        if class_id_raw is None:
            raise ValueError("目标类配置缺少 class_id")
        if multiplier_raw is None:
            raise ValueError("目标类配置缺少目标样本倍数")
        try:
            class_id = int(class_id_raw)
        except Exception as exc:
            raise ValueError("目标类配置中的 class_id 无效") from exc
        try:
            target_multiplier = float(multiplier_raw)
        except Exception as exc:
            raise ValueError("目标样本倍数无效") from exc
        if class_id in seen_ids:
            raise ValueError("目标类中存在重复项")
        seen_ids.add(class_id)
        normalized.append(
            {
                "class_id": class_id,
                "name": str(item.get("name") or class_id),
                "target_multiplier": min(30.0, max(1.0, target_multiplier)),
            }
        )

    return normalized


def augment_one_sample(src_img, src_lbl, dst_img, dst_lbl, rng, enable_hflip, enable_vflip, color_jitter):
    """生成一张增强图片并同步变换对应 YOLO 标签。"""
    with Image.open(src_img) as image:
        image = image.convert("RGB")

    do_hflip = bool(enable_hflip) and (rng.random() < 0.5)
    do_vflip = bool(enable_vflip) and (rng.random() < 0.3)
    jitter = max(0.0, float(color_jitter or 0.0))
    if jitter > 0:
        brightness = 1.0 + rng.uniform(-jitter, jitter)
        contrast = 1.0 + rng.uniform(-jitter, jitter)
        saturation = 1.0 + rng.uniform(-jitter, jitter)
        image = ImageEnhance.Brightness(image).enhance(max(0.1, brightness))
        image = ImageEnhance.Contrast(image).enhance(max(0.1, contrast))
        image = ImageEnhance.Color(image).enhance(max(0.1, saturation))
        sharpness = 1.0 + rng.uniform(-min(0.35, jitter), min(0.35, jitter))
        image = ImageEnhance.Sharpness(image).enhance(max(0.25, sharpness))
        if rng.random() < min(0.35, 0.1 + jitter * 0.5):
            blur_radius = rng.uniform(0.0, min(1.1, max(0.15, jitter * 1.4)))
            image = image.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        if rng.random() < min(0.25, jitter * 0.45):
            image = ImageOps.autocontrast(image, cutoff=rng.uniform(0.0, min(3.0, jitter * 4.0)))
    if do_hflip:
        image = image.transpose(Image.FLIP_LEFT_RIGHT)
    if do_vflip:
        image = image.transpose(Image.FLIP_TOP_BOTTOM)
    os.makedirs(os.path.dirname(dst_img), exist_ok=True)
    image.save(dst_img)

    lines = []
    if src_lbl and os.path.exists(src_lbl):
        with open(src_lbl, "r", encoding="utf-8") as f:
            lines = f.readlines()

    output_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split()
        if len(parts) < 5:
            output_lines.append(stripped + "\n")
            continue
        try:
            class_id = int(float(parts[0]))
            x = float(parts[1])
            y = float(parts[2])
            w = float(parts[3])
            h = float(parts[4])
        except Exception:
            output_lines.append(stripped + "\n")
            continue
        if do_hflip:
            x = 1.0 - x
        if do_vflip:
            y = 1.0 - y
        x = min(1.0, max(0.0, x))
        y = min(1.0, max(0.0, y))
        w = min(1.0, max(0.0, w))
        h = min(1.0, max(0.0, h))
        rest = parts[5:]
        output_parts = [str(class_id), f"{x:.6f}", f"{y:.6f}", f"{w:.6f}", f"{h:.6f}"] + rest
        output_lines.append(" ".join(output_parts) + "\n")

    os.makedirs(os.path.dirname(dst_lbl), exist_ok=True)
    with open(dst_lbl, "w", encoding="utf-8") as f:
        f.writelines(output_lines)


def collect_split_items(dataset_root, split_name, target_class_ids=None, prefix_split=False):
    """收集一个 split 中的图片、标签和目标类命中信息。"""
    items = []
    target_id_set = {int(value) for value in (target_class_ids or [])}
    src_img_dir = get_dataset_images_dir(dataset_root, split_name)
    src_lbl_dir = get_dataset_labels_dir(dataset_root, split_name)
    if not os.path.isdir(src_img_dir):
        return items

    for root, _, files in os.walk(src_img_dir):
        for filename in files:
            if not filename.lower().endswith(IMAGE_FILE_EXTENSIONS):
                continue
            img_path = os.path.join(root, filename)
            rel = os.path.relpath(img_path, src_img_dir)
            out_rel = os.path.join(split_name, rel) if prefix_split else rel
            lbl_path = os.path.join(src_lbl_dir, build_label_relpath(rel))
            class_counts = collect_yolo_class_counts(lbl_path)
            classes = set(class_counts.keys())
            target_classes = tuple(sorted(cid for cid in classes if cid in target_id_set))
            items.append(
                {
                    "img": img_path,
                    "lbl": lbl_path if os.path.exists(lbl_path) else None,
                    "rel": out_rel,
                    "orig_rel": rel,
                    "orig_split": split_name,
                    "class_ids": tuple(sorted(classes)),
                    "class_counts": class_counts,
                    "target_classes": target_classes,
                    "has_target": bool(target_classes) if target_id_set else False,
                }
            )
    return items


def build_output_rel(item, target_split):
    """为复制样本生成稳定且尽量不冲突的输出文件名。"""
    rel = item.get("orig_rel") or item.get("rel") or os.path.basename(item["img"])
    rel = rel.replace("\\", "/")
    rel_dir = os.path.dirname(rel).replace("/", "__").strip("_")
    rel_name = os.path.basename(rel)
    if rel_dir:
        rel_name = f"{rel_dir}__{rel_name}"
    if item.get("orig_split") and item.get("orig_split") != target_split:
        rel_name = f"{item['orig_split']}__{rel_name}"
    return rel_name


def copy_dataset_item(item, dst_img_dir, dst_lbl_dir, target_split=None):
    """复制单个样本到目标 split，并补空标签文件。"""
    rel = build_output_rel(item, target_split) if target_split else item["rel"]
    dst_img = os.path.join(dst_img_dir, rel)
    dst_lbl = os.path.join(dst_lbl_dir, os.path.splitext(rel)[0] + ".txt")
    os.makedirs(os.path.dirname(dst_img), exist_ok=True)
    os.makedirs(os.path.dirname(dst_lbl), exist_ok=True)
    shutil.copy2(item["img"], dst_img)
    if item.get("lbl") and os.path.exists(item["lbl"]):
        shutil.copy2(item["lbl"], dst_lbl)
    else:
        with open(dst_lbl, "w", encoding="utf-8") as f:
            f.write("")


def copy_split_directory(src_img_dir, src_lbl_dir, dst_img_dir, dst_lbl_dir):
    """原样复制整个评估 split 的图片和标签。"""
    copied = {"images": 0, "labels": 0}
    if os.path.isdir(src_img_dir):
        for root, _, files in os.walk(src_img_dir):
            for filename in files:
                src_fp = os.path.join(root, filename)
                rel = os.path.relpath(src_fp, src_img_dir)
                dst_fp = os.path.join(dst_img_dir, rel)
                os.makedirs(os.path.dirname(dst_fp), exist_ok=True)
                shutil.copy2(src_fp, dst_fp)
                copied["images"] += 1
    if os.path.isdir(src_lbl_dir):
        for root, _, files in os.walk(src_lbl_dir):
            for filename in files:
                src_fp = os.path.join(root, filename)
                rel = os.path.relpath(src_fp, src_lbl_dir)
                dst_fp = os.path.join(dst_lbl_dir, rel)
                os.makedirs(os.path.dirname(dst_fp), exist_ok=True)
                shutil.copy2(src_fp, dst_fp)
                copied["labels"] += 1
    return copied


def build_target_class_occurrence_counts(items, target_class_ids):
    """统计目标类出现在多少张目标图片中。"""
    counts = {int(class_id): 0 for class_id in (target_class_ids or [])}
    for item in items:
        for class_id in item.get("target_classes") or ():
            counts[class_id] = counts.get(class_id, 0) + 1
    return counts


def build_class_balanced_augmentation_plan(target_items, target_class_configs, rng):
    """按每个目标类的目标样本倍数生成增强计划。"""
    class_ids = [int(item["class_id"]) for item in target_class_configs]
    source_counts = build_target_class_occurrence_counts(target_items, class_ids)
    target_multipliers = {
        int(item["class_id"]): float(item["target_multiplier"])
        for item in target_class_configs
    }
    desired_counts = {
        class_id: int(
            max(
                source_counts.get(class_id, 0),
                math.ceil(source_counts.get(class_id, 0) * target_multipliers.get(class_id, 1.0)),
            )
        )
        for class_id in class_ids
    }
    current_counts = dict(source_counts)
    planned_augmented_counts = {class_id: 0 for class_id in class_ids}
    items_by_class = {
        class_id: [item for item in target_items if class_id in (item.get("target_classes") or ())]
        for class_id in class_ids
    }

    if not target_items or not any(items_by_class.values()):
        return [], {
            "source_counts": source_counts,
            "target_multipliers": target_multipliers,
            "desired_counts": desired_counts,
            "planned_augmented_counts": planned_augmented_counts,
            "estimated_output_counts": current_counts,
        }

    max_iterations = sum(max(0, desired_counts[class_id] - source_counts.get(class_id, 0)) for class_id in class_ids)
    plan = []
    for _ in range(max_iterations):
        deficit_scores = {
            class_id: max(0, desired_counts.get(class_id, 0) - current_counts.get(class_id, 0))
            for class_id in class_ids
            if items_by_class.get(class_id) and desired_counts.get(class_id, 0) > current_counts.get(class_id, 0)
        }
        if not deficit_scores:
            break

        focus_class_id = max(
            deficit_scores,
            key=lambda class_id: (
                deficit_scores[class_id] / max(1, desired_counts.get(class_id, 1)),
                deficit_scores[class_id],
                -source_counts.get(class_id, 0),
            ),
        )
        candidate_items = items_by_class[focus_class_id]
        weighted_candidates = []
        for item in candidate_items:
            score = 0.0
            for class_id in item.get("target_classes") or ():
                deficit = max(0, desired_counts.get(class_id, 0) - current_counts.get(class_id, 0))
                if deficit <= 0:
                    continue
                score += deficit / max(1, desired_counts.get(class_id, 1))
                score += 1.0 / max(1, source_counts.get(class_id, 1))
            weighted_candidates.append((item, score if score > 0 else 1.0))

        total_score = sum(score for _, score in weighted_candidates)
        pick = rng.random() * total_score
        cursor = 0.0
        selected_item = candidate_items[-1]
        for item, score in weighted_candidates:
            cursor += score
            if pick <= cursor:
                selected_item = item
                break

        plan.append(selected_item)
        for class_id in selected_item.get("target_classes") or ():
            if class_id in current_counts:
                current_counts[class_id] = current_counts.get(class_id, 0) + 1
                planned_augmented_counts[class_id] = planned_augmented_counts.get(class_id, 0) + 1

    return plan, {
        "source_counts": source_counts,
        "target_multipliers": target_multipliers,
        "desired_counts": desired_counts,
        "planned_augmented_counts": planned_augmented_counts,
        "estimated_output_counts": current_counts,
    }


def _take_items(pool, count):
    """从可变列表头部取出指定数量的样本。"""
    count = max(0, min(int(count or 0), len(pool)))
    taken = pool[:count]
    del pool[:count]
    return taken


def _build_eval_items(split_name, total_count, min_target_count, eval_target_ratio, remaining_target_items, remaining_non_target_items, copied_eval, eval_preview, rng):
    """为一个评估 split 按目标占比组装样本集合。"""
    want_target = min(
        max(int(min_target_count), int(round(float(total_count) * float(eval_target_ratio)))),
        len(remaining_target_items),
    )
    picked = _take_items(remaining_target_items, want_target)
    missing = max(0, int(total_count) - len(picked))
    picked += _take_items(remaining_non_target_items, missing)
    missing = max(0, int(total_count) - len(picked))
    if missing > 0:
        picked += _take_items(remaining_target_items, missing)
    rng.shuffle(picked)
    copied_eval[split_name] = {
        "images": len(picked),
        "labels": len(picked),
        "target_images": len([item for item in picked if item["has_target"]]),
    }
    eval_preview[split_name] = {
        "total": len(picked),
        "target": len([item for item in picked if item["has_target"]]),
        "requested_total": int(total_count),
        "requested_min_target": int(min_target_count),
    }
    return picked


def build_augmented_subset(
    source_root,
    target_root,
    names,
    split,
    target_class_configs,
    non_target_keep_ratio,
    seed,
    copy_eval_splits,
    rebalance_eval_splits,
    enable_hflip,
    enable_vflip,
    dry_run,
    eval_target_ratio,
    color_jitter,
):
    """生成或预估增强子集的数据与统计结果。"""
    rng = random.Random(seed)
    target_class_configs = normalize_target_class_configs(target_class_configs)
    target_class_ids = [item["class_id"] for item in target_class_configs]
    copied_eval = {}
    eval_preview = {}
    source_eval_stats = {}
    keep_base_items = []
    target_items = []
    kept_non_target_items = []
    keep_non_target_count = 0
    target_class_plan = {
        "source_counts": {},
        "planned_augmented_counts": {},
        "estimated_output_counts": {},
    }

    if rebalance_eval_splits:
        all_items = []
        for split_name in DATASET_SPLITS:
            all_items.extend(collect_split_items(source_root, split_name, target_class_ids=target_class_ids, prefix_split=False))
        if not all_items:
            raise ValueError("源数据集图片为空")

        original_total_count = len(all_items)
        original_target_count = len([item for item in all_items if item["has_target"]])
        if original_target_count == 0:
            raise ValueError("未找到包含该标签的样本")

        source_eval_stats = {
            "train_total": len([item for item in all_items if item["orig_split"] == DATASET_SPLIT_TRAIN]),
            "train_target": len([item for item in all_items if item["orig_split"] == DATASET_SPLIT_TRAIN and item["has_target"]]),
            "val_total": len([item for item in all_items if item["orig_split"] == DATASET_SPLIT_VAL]),
            "val_target": len([item for item in all_items if item["orig_split"] == DATASET_SPLIT_VAL and item["has_target"]]),
            "test_total": len([item for item in all_items if item["orig_split"] == DATASET_SPLIT_TEST]),
            "test_target": len([item for item in all_items if item["orig_split"] == DATASET_SPLIT_TEST and item["has_target"]]),
        }
        overall_target_ratio = (float(original_target_count) / float(original_total_count)) if original_total_count > 0 else 0.0
        if eval_target_ratio is None or str(eval_target_ratio).strip() == "":
            eval_target_ratio = overall_target_ratio
        else:
            eval_target_ratio = float(eval_target_ratio)
            if eval_target_ratio > 1.0 and eval_target_ratio <= 100.0:
                eval_target_ratio = eval_target_ratio / 100.0
        eval_target_ratio = min(0.9, max(0.0, float(eval_target_ratio)))

        remaining_target_items = [item for item in all_items if item["has_target"]]
        remaining_non_target_items = [item for item in all_items if not item["has_target"]]
        rng.shuffle(remaining_target_items)
        rng.shuffle(remaining_non_target_items)

        val_items = _build_eval_items(
            DATASET_SPLIT_VAL,
            source_eval_stats["val_total"],
            source_eval_stats["val_target"],
            eval_target_ratio,
            remaining_target_items,
            remaining_non_target_items,
            copied_eval,
            eval_preview,
            rng,
        )
        test_items = _build_eval_items(
            DATASET_SPLIT_TEST,
            source_eval_stats["test_total"],
            source_eval_stats["test_target"],
            eval_target_ratio,
            remaining_target_items,
            remaining_non_target_items,
            copied_eval,
            eval_preview,
            rng,
        )

        remaining_train_items = remaining_target_items + remaining_non_target_items
        rng.shuffle(remaining_train_items)
        target_items = [item for item in remaining_train_items if item["has_target"]]
        non_target_items = [item for item in remaining_train_items if not item["has_target"]]
        keep_non_target_count = int(round(len(non_target_items) * non_target_keep_ratio))
        kept_non_target_items = non_target_items[:keep_non_target_count]
        keep_base_items = target_items + kept_non_target_items
    else:
        items = collect_split_items(source_root, split, target_class_ids=target_class_ids, prefix_split=False)
        if not items:
            raise ValueError(f"{split}/images 不存在或图片为空")

        target_items = [item for item in items if item["has_target"]]
        non_target_items = [item for item in items if not item["has_target"]]
        if len(target_items) == 0:
            raise ValueError("未找到包含该标签的样本")

        rng.shuffle(non_target_items)
        keep_non_target_count = int(round(len(non_target_items) * non_target_keep_ratio))
        kept_non_target_items = non_target_items[:keep_non_target_count]
        keep_base_items = target_items + kept_non_target_items
        original_target_count = len(target_items)
        original_total_count = len(items)

    augmentation_plan, target_class_plan = build_class_balanced_augmentation_plan(
        target_items=target_items,
        target_class_configs=target_class_configs,
        rng=rng,
    )
    output_total_count = len(target_items) + len(augmentation_plan) + keep_non_target_count
    output_target_count = len(target_items) + len(augmentation_plan)
    output_target_ratio = (float(output_target_count) / float(output_total_count)) if output_total_count > 0 else 0.0

    if dry_run:
        payload = {
            "success": True,
            "dry_run": True,
            "source_split": ("all" if rebalance_eval_splits else split),
            "target_class_ids": target_class_ids,
            "original_total": original_total_count,
            "original_target": original_target_count,
            "non_target_total": max(0, original_total_count - original_target_count),
            "configured_non_target_keep_ratio": round(float(non_target_keep_ratio), 4),
            "estimated_kept_non_target": int(keep_non_target_count),
            "estimated_output_total": int(output_total_count),
            "estimated_output_target": int(output_target_count),
            "estimated_output_target_ratio": round(output_target_ratio * 100, 2),
            "target_class_plan": target_class_plan,
            "rebalance_eval_splits": rebalance_eval_splits,
            "message": f"预估完成：目标类占比约 {round(output_target_ratio * 100, 2)}%",
        }
        if rebalance_eval_splits:
            payload["source_eval_stats"] = source_eval_stats
            payload["eval_target_ratio"] = round(float(eval_target_ratio) * 100, 2)
            payload["estimated_eval"] = eval_preview
        return payload

    out_train_img = get_dataset_images_dir(target_root, DATASET_SPLIT_TRAIN)
    out_train_lbl = get_dataset_labels_dir(target_root, DATASET_SPLIT_TRAIN)
    os.makedirs(out_train_img, exist_ok=True)
    os.makedirs(out_train_lbl, exist_ok=True)

    copied_base_count = 0
    for item in keep_base_items:
        copy_dataset_item(item, out_train_img, out_train_lbl, target_split=DATASET_SPLIT_TRAIN)
        copied_base_count += 1

    augmented_count = 0
    if augmentation_plan:
        for index, source in enumerate(augmentation_plan):
            rel_for_train = build_output_rel(source, DATASET_SPLIT_TRAIN)
            rel_noext, ext = os.path.splitext(rel_for_train)
            if not ext:
                ext = ".jpg"
            aug_rel = f"{rel_noext}__aug_{index + 1:05d}{ext}"
            dst_img = os.path.join(out_train_img, aug_rel)
            dst_lbl = os.path.join(out_train_lbl, f"{rel_noext}__aug_{index + 1:05d}.txt")
            augment_one_sample(
                src_img=source["img"],
                src_lbl=source["lbl"],
                dst_img=dst_img,
                dst_lbl=dst_lbl,
                rng=rng,
                enable_hflip=enable_hflip,
                enable_vflip=enable_vflip,
                color_jitter=color_jitter,
            )
            augmented_count += 1

    if rebalance_eval_splits:
        for eval_split, items in ((DATASET_SPLIT_VAL, val_items), (DATASET_SPLIT_TEST, test_items)):
            if not items:
                continue
            dst_eval_img = get_dataset_images_dir(target_root, eval_split)
            dst_eval_lbl = get_dataset_labels_dir(target_root, eval_split)
            for item in items:
                copy_dataset_item(item, dst_eval_img, dst_eval_lbl, target_split=eval_split)
    elif copy_eval_splits:
        for eval_split in EVAL_SPLITS:
            copied_eval[eval_split] = copy_split_directory(
                get_dataset_images_dir(source_root, eval_split),
                get_dataset_labels_dir(source_root, eval_split),
                get_dataset_images_dir(target_root, eval_split),
                get_dataset_labels_dir(target_root, eval_split),
            )

    yaml_names = {idx: name for idx, name in enumerate(names)}
    save_standard_dataset_yaml(
        target_root,
        yaml_names,
        include_val=True,
        include_test=os.path.isdir(get_dataset_images_dir(target_root, DATASET_SPLIT_TEST)),
        val_fallback_split=DATASET_SPLIT_VAL if os.path.isdir(get_dataset_images_dir(target_root, DATASET_SPLIT_VAL)) else DATASET_SPLIT_TRAIN,
    )

    output_total_count = copied_base_count + augmented_count
    output_target_count = len(target_items) + augmented_count
    output_target_ratio = (float(output_target_count) / float(output_total_count)) if output_total_count > 0 else 0.0

    return {
        "dry_run": False,
        "source_split": ("all" if rebalance_eval_splits else split),
        "target_class_ids": target_class_ids,
        "original_total": original_total_count,
        "original_target": original_target_count,
        "copied_non_target": len(kept_non_target_items),
        "configured_non_target_keep_ratio": round(float(non_target_keep_ratio), 4),
        "copied_base": copied_base_count,
        "augmented": augmented_count,
        "output_total": output_total_count,
        "output_target": output_target_count,
        "output_target_ratio": round(output_target_ratio * 100, 2),
        "target_class_plan": target_class_plan,
        "copied_eval": copied_eval,
        "rebalance_eval_splits": rebalance_eval_splits,
        "eval_target_ratio": round(float(eval_target_ratio) * 100, 2) if rebalance_eval_splits else None,
        "estimated_eval": eval_preview if rebalance_eval_splits else None,
        "message": f"已创建增强子集：train样本 {output_total_count} 张，目标类占比 {round(output_target_ratio * 100, 2)}%",
    }
