"""实现标准数据集的合并与重分片操作。"""

import os
import random
import shutil
import tempfile

from contexts.dataset.infrastructure.dataset_layout import (
    STANDARD_DATASET_SPLITS,
    get_dataset_images_dir,
    get_dataset_labels_dir,
)
from contexts.dataset.infrastructure.dataset_schema import save_standard_dataset_yaml
from shared.utils.media_constants import IMAGE_FILE_EXTENSIONS
from shared.utils.fs_utils import move_path


def _ensure_standard_split_dirs(dataset_root):
    """确保标准 split 目录在写入前已创建。"""
    for split in STANDARD_DATASET_SPLITS:
        os.makedirs(get_dataset_images_dir(dataset_root, split), exist_ok=True)
        os.makedirs(get_dataset_labels_dir(dataset_root, split), exist_ok=True)
def _iter_split_samples(dataset_root, split):
    """遍历一个 split 下的图片与标签配对样本。"""
    img_dir = get_dataset_images_dir(dataset_root, split)
    lbl_dir = get_dataset_labels_dir(dataset_root, split)
    if not os.path.isdir(img_dir):
        return

    for root, dirs, files in os.walk(img_dir):
        dirs.sort()
        files.sort()
        for filename in files:
            if not filename.lower().endswith(IMAGE_FILE_EXTENSIONS):
                continue
            img_path = os.path.join(root, filename)
            rel = os.path.relpath(img_path, img_dir)
            stem = os.path.splitext(rel)[0]
            lbl_path = os.path.join(lbl_dir, stem + ".txt")
            yield {
                "img": img_path,
                "lbl": lbl_path if os.path.exists(lbl_path) else None,
                "rel": rel,
                "base": os.path.basename(rel),
                "name_no_ext": os.path.splitext(os.path.basename(rel))[0],
            }


def _copy_dataset_into(source_root, target_root, source_tag):
    """把一个源数据集复制进合并目标并处理重名。"""
    stats = {"copied_images": 0, "copied_labels": 0, "renamed_images": 0, "missing_labels": 0}
    for split in STANDARD_DATASET_SPLITS:
        dst_img_dir = get_dataset_images_dir(target_root, split)
        dst_lbl_dir = get_dataset_labels_dir(target_root, split)

        for item in _iter_split_samples(source_root, split):
            rel_dir = os.path.dirname(item["rel"])
            base, ext = os.path.splitext(os.path.basename(item["rel"]))
            dst_dir = os.path.join(dst_img_dir, rel_dir) if rel_dir else dst_img_dir
            os.makedirs(dst_dir, exist_ok=True)

            dst_img = os.path.join(dst_dir, base + ext)
            dst_base = base
            if os.path.exists(dst_img):
                idx = 1
                while True:
                    candidate_base = f"{base}_{source_tag}{idx}"
                    candidate_img = os.path.join(dst_dir, candidate_base + ext)
                    if not os.path.exists(candidate_img):
                        dst_img = candidate_img
                        dst_base = candidate_base
                        stats["renamed_images"] += 1
                        break
                    idx += 1

            shutil.copy2(item["img"], dst_img)
            stats["copied_images"] += 1

            dst_lbl_dir2 = os.path.join(dst_lbl_dir, rel_dir) if rel_dir else dst_lbl_dir
            os.makedirs(dst_lbl_dir2, exist_ok=True)
            dst_lbl = os.path.join(dst_lbl_dir2, dst_base + ".txt")
            if item["lbl"]:
                shutil.copy2(item["lbl"], dst_lbl)
                stats["copied_labels"] += 1
            else:
                stats["missing_labels"] += 1
    return stats


def merge_standard_datasets(dataset_a_root, dataset_b_root, target_root, names):
    """把两个标准数据集合并到新的目标目录。"""
    os.makedirs(target_root, exist_ok=False)
    _ensure_standard_split_dirs(target_root)
    save_standard_dataset_yaml(target_root, list(names), include_val=True, include_test=True)
    return {
        "a": _copy_dataset_into(dataset_a_root, target_root, "a"),
        "b": _copy_dataset_into(dataset_b_root, target_root, "b"),
    }


def _collect_dataset_pairs(dataset_root):
    """收集全部 split 样本以便统一重分片。"""
    pairs = []
    for split in STANDARD_DATASET_SPLITS:
        pairs.extend(list(_iter_split_samples(dataset_root, split) or []))
    return pairs


def _move_pairs_to_temp(pairs, temp_dir):
    """先把现有样本搬到临时目录等待重新分配。"""
    for item in pairs:
        dst_img = os.path.join(temp_dir, f"img_{item['base']}")
        move_path(item["img"], dst_img, ensure_parent=True)
        item["current_img"] = dst_img
        if item["lbl"]:
            dst_lbl = os.path.join(temp_dir, f"lbl_{item['name_no_ext']}.txt")
            move_path(item["lbl"], dst_lbl, ensure_parent=True)
            item["current_lbl"] = dst_lbl
        else:
            item["current_lbl"] = None


def _move_pairs_to_subset(dataset_root, items, split, rng):
    """把临时样本恢复到指定 split 并避开重名。"""
    split_img_dir = get_dataset_images_dir(dataset_root, split)
    split_lbl_dir = get_dataset_labels_dir(dataset_root, split)
    for item in items:
        dst_img = os.path.join(split_img_dir, item["base"])
        if os.path.exists(dst_img):
            base, ext = os.path.splitext(item["base"])
            dst_img = os.path.join(split_img_dir, f"{base}_{rng.randint(1000, 9999)}{ext}")
        move_path(item["current_img"], dst_img, ensure_parent=True)
        if item["current_lbl"]:
            dst_lbl = os.path.join(split_lbl_dir, item["name_no_ext"] + ".txt")
            move_path(item["current_lbl"], dst_lbl, ensure_parent=True)


def split_standard_dataset(dataset_root, val_ratio, test_ratio, rng=None):
    """按比例重写标准数据集的 split 分布。"""
    pairs = _collect_dataset_pairs(dataset_root)
    if not pairs:
        raise ValueError("未找到图片文件")

    rng = rng or random.Random()
    rng.shuffle(pairs)

    total = len(pairs)
    n_val = int(total * val_ratio)
    n_test = int(total * test_ratio)
    n_train = total - n_val - n_test

    train_set = pairs[:n_train]
    val_set = pairs[n_train:n_train + n_val]
    test_set = pairs[n_train + n_val:]

    with tempfile.TemporaryDirectory(dir=dataset_root) as temp_dir:
        _move_pairs_to_temp(pairs, temp_dir)
        _ensure_standard_split_dirs(dataset_root)
        _move_pairs_to_subset(dataset_root, train_set, "train", rng)
        _move_pairs_to_subset(dataset_root, val_set, "val", rng)
        _move_pairs_to_subset(dataset_root, test_set, "test", rng)

    return {
        "train": len(train_set),
        "val": len(val_set),
        "test": len(test_set),
    }
