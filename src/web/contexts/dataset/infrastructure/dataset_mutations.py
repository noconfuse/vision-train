"""编排标准数据集的合并与重切分流程。"""

import os
import random
import tempfile
from collections import defaultdict

from contexts.dataset.infrastructure.dataset_layout import STANDARD_DATASET_SPLITS
from contexts.dataset.infrastructure.dataset_mutation_strategy import resolve_dataset_mutation_strategy
from contexts.dataset.infrastructure.dataset_schema import save_standard_dataset_yaml
from contexts.dataset.infrastructure.dataset_task_type import (
    load_dataset_vision_task_type,
    require_dataset_vision_task_type,
    save_dataset_vision_task_type,
)
from shared.utils.fs_utils import move_path


def _copy_dataset_into(source_root, target_root, source_tag, vision_task_type):
    """把一个源数据集并入目标目录，同时累计复制统计。"""
    stats = {"copied_images": 0, "copied_labels": 0, "renamed_images": 0, "missing_labels": 0}
    strategy = resolve_dataset_mutation_strategy(vision_task_type)
    for split in STANDARD_DATASET_SPLITS:
        for item in strategy.iter_split_samples(source_root, split):
            strategy.copy_dataset_item(target_root, split, item, source_tag, stats)
    return stats


def merge_standard_datasets(dataset_a_root, dataset_b_root, target_root, names, vision_task_type):
    """把两个标准数据集合并到新的目标目录。"""
    vision_task_type = require_dataset_vision_task_type(vision_task_type)
    os.makedirs(target_root, exist_ok=False)
    resolve_dataset_mutation_strategy(vision_task_type).ensure_standard_split_dirs(target_root)
    save_standard_dataset_yaml(
        target_root,
        list(names),
        vision_task_type=vision_task_type,
        include_val=True,
        include_test=True,
    )
    save_dataset_vision_task_type(target_root, vision_task_type)
    return {
        "a": _copy_dataset_into(dataset_a_root, target_root, "a", vision_task_type),
        "b": _copy_dataset_into(dataset_b_root, target_root, "b", vision_task_type),
    }


def _collect_dataset_pairs(dataset_root, vision_task_type):
    """收集全部 split 样本，为分层抽样准备统一样本池。"""
    pairs = []
    strategy = resolve_dataset_mutation_strategy(vision_task_type)
    for split in STANDARD_DATASET_SPLITS:
        pairs.extend(list(strategy.iter_split_samples(dataset_root, split) or []))
    return pairs


def _read_item_class_ids(item):
    """读取单张样本标签中的类别集合，用于分层抽样。"""
    class_ids = (item or {}).get("class_ids")
    if class_ids:
        return tuple(class_ids)
    label_path = (item or {}).get("lbl")
    if not label_path or not os.path.isfile(label_path):
        return ()
    class_ids = set()
    try:
        with open(label_path, "r", encoding="utf-8") as handle:
            for line in handle:
                parts = line.strip().split()
                if not parts:
                    continue
                try:
                    class_ids.add(int(float(parts[0])))
                except (TypeError, ValueError):
                    continue
    except OSError:
        return ()
    return tuple(sorted(class_ids))


def _build_item_stratum_key(item):
    """按样本类别签名构造分层抽样 key。"""
    class_ids = _read_item_class_ids(item)
    if class_ids:
        return class_ids
    return ("__unlabeled__",)


def _build_stratified_split_sets(pairs, val_ratio, test_ratio, rng):
    """按类别分层抽样构造 train/val/test 三个样本集合。"""
    groups = defaultdict(list)
    for item in pairs:
        groups[_build_item_stratum_key(item)].append(item)

    train_set = []
    val_set = []
    test_set = []
    for items in groups.values():
        bucket = list(items)
        rng.shuffle(bucket)
        total = len(bucket)
        n_val = int(total * val_ratio)
        n_test = int(total * test_ratio)
        n_train = total - n_val - n_test
        train_set.extend(bucket[:n_train])
        val_set.extend(bucket[n_train:n_train + n_val])
        test_set.extend(bucket[n_train + n_val:])

    rng.shuffle(train_set)
    rng.shuffle(val_set)
    rng.shuffle(test_set)
    return train_set, val_set, test_set


def _move_pairs_to_temp(pairs, temp_dir):
    """把现有样本临时搬走，避免重切分时发生路径冲突。"""
    for index, item in enumerate(pairs):
        img_ext = os.path.splitext(item["base"])[1]
        dst_img = os.path.join(temp_dir, f"img_{index:08d}{img_ext}")
        move_path(item["img"], dst_img, ensure_parent=True)
        item["current_img"] = dst_img
        if item["lbl"]:
            dst_lbl = os.path.join(temp_dir, f"lbl_{index:08d}.txt")
            move_path(item["lbl"], dst_lbl, ensure_parent=True)
            item["current_lbl"] = dst_lbl
        else:
            item["current_lbl"] = None


def split_standard_dataset(dataset_root, val_ratio, test_ratio, rng=None):
    """按类别分层抽样重写标准数据集的 split 分布。"""
    vision_task_type = require_dataset_vision_task_type(load_dataset_vision_task_type(dataset_root))
    strategy = resolve_dataset_mutation_strategy(vision_task_type)
    pairs = _collect_dataset_pairs(dataset_root, vision_task_type)
    if not pairs:
        raise ValueError("未找到图片文件")

    rng = rng or random.Random()
    train_set, val_set, test_set = _build_stratified_split_sets(pairs, val_ratio, test_ratio, rng)

    with tempfile.TemporaryDirectory(dir=dataset_root) as temp_dir:
        _move_pairs_to_temp(pairs, temp_dir)
        strategy.ensure_standard_split_dirs(dataset_root)
        for item in train_set:
            strategy.move_item_to_subset(dataset_root, item, "train", rng)
        for item in val_set:
            strategy.move_item_to_subset(dataset_root, item, "val", rng)
        for item in test_set:
            strategy.move_item_to_subset(dataset_root, item, "test", rng)

    return {
        "train": len(train_set),
        "val": len(val_set),
        "test": len(test_set),
    }
