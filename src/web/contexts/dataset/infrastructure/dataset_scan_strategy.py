"""按数据集任务类型封装扫描与统计策略。"""

import os

from constants.media import DATASET_SPLITS, IMAGE_FILE_EXTENSIONS
from contexts.dataset.infrastructure.dataset_layout import (
    extract_classification_class_name,
    get_dataset_images_dir,
    get_dataset_labels_dir,
    get_dataset_root_images_dir,
    get_dataset_root_labels_dir,
    get_dataset_split_content_dir,
    get_dataset_unlabeled_dir,
)
from protocols.vision_task_type import (
    VISION_TASK_TYPE_CLASSIFY,
    VISION_TASK_TYPE_DETECT,
    VISION_TASK_TYPE_POSE,
    VISION_TASK_TYPE_SEGMENT,
)


class BaseDatasetScanStrategy:
    """定义数据集扫描策略基类。"""

    vision_task_type = ""

    def scan_dataset(self, *_args, **_kwargs):
        raise NotImplementedError


class DetectDatasetScanStrategy(BaseDatasetScanStrategy):
    """目标检测数据集扫描策略。"""

    vision_task_type = VISION_TASK_TYPE_DETECT

    def _scan_split(self, img_dir, lbl_dir, info, class_counts):
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
                with open(label_path, "r", encoding="utf-8") as handle:
                    for line in handle:
                        parts = line.strip().split()
                        if not parts:
                            continue
                        cls_id = int(float(parts[0]))
                        class_counts[cls_id] = class_counts.get(cls_id, 0) + 1
                        info["total_objects"] += 1
            except Exception:
                pass
        return True

    def scan_dataset(self, dataset_path, info, class_name_to_id, class_counts):
        has_split = False
        for split in DATASET_SPLITS:
            if self._scan_split(
                get_dataset_images_dir(dataset_path, split),
                get_dataset_labels_dir(dataset_path, split),
                info,
                class_counts,
            ):
                info[f"has_{split}"] = True
                has_split = True
        if not has_split:
            self._scan_split(
                get_dataset_root_images_dir(dataset_path),
                get_dataset_root_labels_dir(dataset_path),
                info,
                class_counts,
            )


class ClassifyDatasetScanStrategy(BaseDatasetScanStrategy):
    """图像分类数据集扫描策略。"""

    vision_task_type = VISION_TASK_TYPE_CLASSIFY

    def _scan_split(self, split_dir, info, class_name_to_id, class_counts):
        if not os.path.isdir(split_dir):
            return False
        found_images = False
        for root, dirs, files in os.walk(split_dir):
            dirs.sort()
            files.sort()
            for name in files:
                if not name.lower().endswith(IMAGE_FILE_EXTENSIONS):
                    continue
                rel_path = os.path.relpath(os.path.join(root, name), split_dir)
                class_name = extract_classification_class_name(rel_path)
                if not class_name:
                    continue
                found_images = True
                info["image_count"] += 1
                info["label_count"] += 1
                info["total_objects"] += 1
                class_id = class_name_to_id.get(class_name)
                if class_id is None:
                    continue
                class_counts[class_id] = class_counts.get(class_id, 0) + 1
        return found_images

    def _scan_unlabeled_split(self, unlabeled_dir, info):
        """统计分类任务未标注图片区中的图片数量。"""
        if not os.path.isdir(unlabeled_dir):
            return
        for _root, dirs, files in os.walk(unlabeled_dir):
            dirs.sort()
            files.sort()
            for name in files:
                if not name.lower().endswith(IMAGE_FILE_EXTENSIONS):
                    continue
                info["image_count"] += 1

    def scan_dataset(self, dataset_path, info, class_name_to_id, class_counts):
        for split in DATASET_SPLITS:
            if self._scan_split(
                get_dataset_split_content_dir(dataset_path, split, self.vision_task_type),
                info,
                class_name_to_id,
                class_counts,
            ):
                info[f"has_{split}"] = True
            self._scan_unlabeled_split(get_dataset_unlabeled_dir(dataset_path, split), info)


class SegmentDatasetScanStrategy(DetectDatasetScanStrategy):
    """实例分割数据集扫描策略。"""

    vision_task_type = VISION_TASK_TYPE_SEGMENT


class PoseDatasetScanStrategy(DetectDatasetScanStrategy):
    """姿态估计数据集扫描策略。"""

    vision_task_type = VISION_TASK_TYPE_POSE


_DATASET_SCAN_STRATEGIES = {
    VISION_TASK_TYPE_DETECT: DetectDatasetScanStrategy(),
    VISION_TASK_TYPE_CLASSIFY: ClassifyDatasetScanStrategy(),
    VISION_TASK_TYPE_SEGMENT: SegmentDatasetScanStrategy(),
    VISION_TASK_TYPE_POSE: PoseDatasetScanStrategy(),
}


def resolve_dataset_scan_strategy(vision_task_type):
    """按任务类型解析数据集扫描策略。"""
    strategy = _DATASET_SCAN_STRATEGIES.get(vision_task_type)
    if not strategy:
        raise ValueError(f"当前任务类型暂未接入扫描策略: {vision_task_type}")
    return strategy
