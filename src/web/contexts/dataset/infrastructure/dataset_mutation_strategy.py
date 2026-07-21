"""按数据集任务类型封装合并与重切分策略。"""

import os
import shutil

from constants.media import IMAGE_FILE_EXTENSIONS
from contexts.dataset.infrastructure.dataset_layout import (
    STANDARD_DATASET_SPLITS,
    extract_classification_class_name,
    get_dataset_images_dir,
    get_dataset_labels_dir,
    get_dataset_split_content_dir,
    get_dataset_split_dir,
    get_dataset_unlabeled_dir,
)
from contexts.dataset.infrastructure.dataset_schema import load_dataset_names
from protocols.vision_task_type import VISION_TASK_TYPE_CLASSIFY, VISION_TASK_TYPE_DETECT


class BaseDatasetMutationStrategy:
    """定义数据集变异策略基类。"""

    vision_task_type = ""

    def ensure_standard_split_dirs(self, *_args, **_kwargs):
        raise NotImplementedError

    def iter_split_samples(self, *_args, **_kwargs):
        raise NotImplementedError

    def copy_dataset_item(self, *_args, **_kwargs):
        raise NotImplementedError

    def move_item_to_subset(self, *_args, **_kwargs):
        raise NotImplementedError


class DetectDatasetMutationStrategy(BaseDatasetMutationStrategy):
    """目标检测数据集变异策略。"""

    vision_task_type = VISION_TASK_TYPE_DETECT

    def ensure_standard_split_dirs(self, dataset_root):
        for split in STANDARD_DATASET_SPLITS:
            os.makedirs(get_dataset_images_dir(dataset_root, split), exist_ok=True)
            os.makedirs(get_dataset_labels_dir(dataset_root, split), exist_ok=True)

    def iter_split_samples(self, dataset_root, split, class_name_to_id=None):
        img_dir = get_dataset_split_content_dir(dataset_root, split, self.vision_task_type)
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
                    "class_name": "",
                    "class_ids": (),
                }

    def copy_dataset_item(self, target_root, split, item, source_tag, stats):
        """把单个检测样本复制到目标 split，并同步复制标签文件。"""
        dst_img_dir = get_dataset_images_dir(target_root, split)
        dst_lbl_dir = get_dataset_labels_dir(target_root, split)
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

    def move_item_to_subset(self, dataset_root, item, split, rng):
        split_img_dir = get_dataset_split_content_dir(dataset_root, split, self.vision_task_type)
        split_lbl_dir = get_dataset_labels_dir(dataset_root, split)
        rel_path = item["rel"]
        dst_img = os.path.join(split_img_dir, rel_path)
        if os.path.exists(dst_img):
            rel_dir = os.path.dirname(rel_path)
            base_name = os.path.basename(rel_path)
            base, ext = os.path.splitext(base_name)
            renamed = f"{base}_{rng.randint(1000, 9999)}{ext}"
            dst_img = os.path.join(split_img_dir, rel_dir, renamed) if rel_dir else os.path.join(split_img_dir, renamed)
        from shared.utils.fs_utils import move_path

        move_path(item["current_img"], dst_img, ensure_parent=True)
        if item["current_lbl"]:
            rel_dst_img = os.path.relpath(dst_img, split_img_dir)
            dst_lbl = os.path.join(split_lbl_dir, os.path.splitext(rel_dst_img)[0] + ".txt")
            move_path(item["current_lbl"], dst_lbl, ensure_parent=True)


class ClassifyDatasetMutationStrategy(BaseDatasetMutationStrategy):
    """图像分类数据集变异策略。"""

    vision_task_type = VISION_TASK_TYPE_CLASSIFY

    def _iter_classification_root_samples(self, root_dir, class_name_to_id=None, is_unlabeled=False):
        """遍历分类目录或未标注目录下的图片样本。"""
        if not os.path.isdir(root_dir):
            return
        for root, dirs, files in os.walk(root_dir):
            dirs.sort()
            files.sort()
            for filename in files:
                if not filename.lower().endswith(IMAGE_FILE_EXTENSIONS):
                    continue
                img_path = os.path.join(root, filename)
                rel = os.path.relpath(img_path, root_dir)
                class_name = "" if is_unlabeled else extract_classification_class_name(rel)
                class_key = class_name_to_id.get(class_name) if class_name_to_id and class_name else None
                yield {
                    "img": img_path,
                    "lbl": None,
                    "rel": rel,
                    "base": os.path.basename(rel),
                    "name_no_ext": os.path.splitext(os.path.basename(rel))[0],
                    "class_name": class_name,
                    "class_ids": (class_key,) if class_key is not None else ((f"class:{class_name}",) if class_name else ()),
                    "is_unlabeled": is_unlabeled,
                }

    def ensure_standard_split_dirs(self, dataset_root):
        for split in STANDARD_DATASET_SPLITS:
            os.makedirs(get_dataset_split_dir(dataset_root, split), exist_ok=True)

    def iter_split_samples(self, dataset_root, split, class_name_to_id=None):
        """遍历分类 split 样本，并按当前数据集 names 生成稳定类别签名。"""
        class_name_to_id = self._load_class_name_to_id(dataset_root)
        yield from self._iter_classification_root_samples(
            get_dataset_split_content_dir(dataset_root, split, self.vision_task_type),
            class_name_to_id=class_name_to_id,
            is_unlabeled=False,
        )
        yield from self._iter_classification_root_samples(
            get_dataset_unlabeled_dir(dataset_root, split),
            class_name_to_id=class_name_to_id,
            is_unlabeled=True,
        )

    def _load_class_name_to_id(self, dataset_root):
        """按数据集 names 顺序解析类别名到 class id 的映射。"""
        return {str(name): index for index, name in enumerate(load_dataset_names(dataset_root))}

    def copy_dataset_item(self, target_root, split, item, source_tag, stats):
        """把单个分类样本复制到目标 split 的类别目录。"""
        dst_img_dir = get_dataset_unlabeled_dir(target_root, split) if item.get("is_unlabeled") else get_dataset_split_content_dir(target_root, split, self.vision_task_type)
        rel_dir = os.path.dirname(item["rel"])
        base, ext = os.path.splitext(os.path.basename(item["rel"]))
        dst_dir = os.path.join(dst_img_dir, rel_dir) if rel_dir else dst_img_dir
        os.makedirs(dst_dir, exist_ok=True)

        dst_img = os.path.join(dst_dir, base + ext)
        if os.path.exists(dst_img):
            idx = 1
            while True:
                candidate_base = f"{base}_{source_tag}{idx}"
                candidate_img = os.path.join(dst_dir, candidate_base + ext)
                if not os.path.exists(candidate_img):
                    dst_img = candidate_img
                    stats["renamed_images"] += 1
                    break
                idx += 1

        shutil.copy2(item["img"], dst_img)
        stats["copied_images"] += 1

    def move_item_to_subset(self, dataset_root, item, split, rng):
        split_img_dir = get_dataset_unlabeled_dir(dataset_root, split) if item.get("is_unlabeled") else get_dataset_split_content_dir(dataset_root, split, self.vision_task_type)
        rel_path = item["rel"]
        dst_img = os.path.join(split_img_dir, rel_path)
        if os.path.exists(dst_img):
            rel_dir = os.path.dirname(rel_path)
            base_name = os.path.basename(rel_path)
            base, ext = os.path.splitext(base_name)
            renamed = f"{base}_{rng.randint(1000, 9999)}{ext}"
            dst_img = os.path.join(split_img_dir, rel_dir, renamed) if rel_dir else os.path.join(split_img_dir, renamed)
        from shared.utils.fs_utils import move_path

        move_path(item["current_img"], dst_img, ensure_parent=True)


_DATASET_MUTATION_STRATEGIES = {
    VISION_TASK_TYPE_DETECT: DetectDatasetMutationStrategy(),
    VISION_TASK_TYPE_CLASSIFY: ClassifyDatasetMutationStrategy(),
}


def resolve_dataset_mutation_strategy(vision_task_type):
    """按任务类型解析数据集变异策略。"""
    strategy = _DATASET_MUTATION_STRATEGIES.get(vision_task_type)
    if not strategy:
        raise ValueError(f"当前任务类型暂未接入变异策略: {vision_task_type}")
    return strategy
