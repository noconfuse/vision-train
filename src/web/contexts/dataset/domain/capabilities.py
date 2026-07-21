"""定义数据集能力表，作为前后端共享的行为真源。"""

from protocols.vision_task_type import (
    VISION_TASK_TYPE_CLASSIFY,
    VISION_TASK_TYPE_DETECT,
    VISION_TASK_TYPE_POSE,
    VISION_TASK_TYPE_SEGMENT,
)

DATASET_ANNOTATION_MODE_UNSUPPORTED = "unsupported"
DATASET_ANNOTATION_MODE_DETECT_BOXES = "detect_boxes"
DATASET_ANNOTATION_MODE_IMAGE_CLASS = "image_class"

DATASET_TRAINING_MODE_UNSUPPORTED = "unsupported"
DATASET_TRAINING_MODE_YOLO_DETECT = "yolo_detect"
DATASET_TRAINING_MODE_YOLO_CLASSIFY = "yolo_classify"

DATASET_AUTO_ANNOTATION_MODE_UNSUPPORTED = "unsupported"
DATASET_AUTO_ANNOTATION_MODE_DETECT_BOXES = "detect_boxes"
DATASET_AUTO_ANNOTATION_MODE_IMAGE_CLASS = "image_class"

DATASET_OPERATION_UPLOAD_IMAGES = "upload_images"
DATASET_OPERATION_CREATE_SUBSET = "create_subset"
DATASET_OPERATION_SPLIT_DATASET = "split_dataset"
DATASET_OPERATION_MANUAL_ANNOTATION = "manual_annotation"
DATASET_OPERATION_TRAIN = "train"
DATASET_OPERATION_AUTO_ANNOTATE = "auto_annotate"
DATASET_OPERATION_REORDER_LABELS = "reorder_labels"
DATASET_OPERATION_DELETE_LABEL = "delete_label"
DATASET_OPERATION_DEDUPLICATE_IMAGES = "deduplicate_images"
DATASET_OPERATION_MERGE_DATASETS = "merge_datasets"
DATASET_OPERATION_AUGMENT_DATASET = "augment_dataset"

DATASET_OPERATION_LABELS = {
    DATASET_OPERATION_UPLOAD_IMAGES: "上传图片",
    DATASET_OPERATION_CREATE_SUBSET: "生成子集",
    DATASET_OPERATION_SPLIT_DATASET: "重切分",
    DATASET_OPERATION_MANUAL_ANNOTATION: "标注",
    DATASET_OPERATION_TRAIN: "训练",
    DATASET_OPERATION_AUTO_ANNOTATE: "自动标注",
    DATASET_OPERATION_REORDER_LABELS: "调整标签顺序",
    DATASET_OPERATION_DELETE_LABEL: "删除标签",
    DATASET_OPERATION_DEDUPLICATE_IMAGES: "图片去重",
    DATASET_OPERATION_MERGE_DATASETS: "合并数据集",
    DATASET_OPERATION_AUGMENT_DATASET: "弱类补偿采样",
}

_BASE_OPERATIONS = {
    DATASET_OPERATION_UPLOAD_IMAGES: False,
    DATASET_OPERATION_CREATE_SUBSET: False,
    DATASET_OPERATION_SPLIT_DATASET: False,
    DATASET_OPERATION_MANUAL_ANNOTATION: False,
    DATASET_OPERATION_TRAIN: False,
    DATASET_OPERATION_AUTO_ANNOTATE: False,
    DATASET_OPERATION_REORDER_LABELS: False,
    DATASET_OPERATION_DELETE_LABEL: False,
    DATASET_OPERATION_DEDUPLICATE_IMAGES: False,
    DATASET_OPERATION_MERGE_DATASETS: False,
    DATASET_OPERATION_AUGMENT_DATASET: False,
}

_CAPABILITY_MAP = {
    VISION_TASK_TYPE_DETECT: {
        "annotation_mode": DATASET_ANNOTATION_MODE_DETECT_BOXES,
        "training_mode": DATASET_TRAINING_MODE_YOLO_DETECT,
        "auto_annotation_mode": DATASET_AUTO_ANNOTATION_MODE_DETECT_BOXES,
        "operations": {
            **_BASE_OPERATIONS,
            DATASET_OPERATION_UPLOAD_IMAGES: True,
            DATASET_OPERATION_CREATE_SUBSET: True,
            DATASET_OPERATION_SPLIT_DATASET: True,
            DATASET_OPERATION_MANUAL_ANNOTATION: True,
            DATASET_OPERATION_TRAIN: True,
            DATASET_OPERATION_AUTO_ANNOTATE: True,
            DATASET_OPERATION_REORDER_LABELS: True,
            DATASET_OPERATION_DELETE_LABEL: True,
            DATASET_OPERATION_DEDUPLICATE_IMAGES: True,
            DATASET_OPERATION_MERGE_DATASETS: True,
            DATASET_OPERATION_AUGMENT_DATASET: True,
        },
    },
    VISION_TASK_TYPE_CLASSIFY: {
        "annotation_mode": DATASET_ANNOTATION_MODE_IMAGE_CLASS,
        "training_mode": DATASET_TRAINING_MODE_YOLO_CLASSIFY,
        "auto_annotation_mode": DATASET_AUTO_ANNOTATION_MODE_IMAGE_CLASS,
        "operations": {
            **_BASE_OPERATIONS,
            DATASET_OPERATION_UPLOAD_IMAGES: True,
            DATASET_OPERATION_CREATE_SUBSET: True,
            DATASET_OPERATION_SPLIT_DATASET: True,
            DATASET_OPERATION_MANUAL_ANNOTATION: True,
            DATASET_OPERATION_TRAIN: True,
            DATASET_OPERATION_AUTO_ANNOTATE: True,
            DATASET_OPERATION_DEDUPLICATE_IMAGES: True,
            DATASET_OPERATION_MERGE_DATASETS: True,
        },
    },
    VISION_TASK_TYPE_SEGMENT: {
        "annotation_mode": DATASET_ANNOTATION_MODE_UNSUPPORTED,
        "training_mode": DATASET_TRAINING_MODE_UNSUPPORTED,
        "auto_annotation_mode": DATASET_AUTO_ANNOTATION_MODE_UNSUPPORTED,
        "operations": {**_BASE_OPERATIONS},
    },
    VISION_TASK_TYPE_POSE: {
        "annotation_mode": DATASET_ANNOTATION_MODE_UNSUPPORTED,
        "training_mode": DATASET_TRAINING_MODE_UNSUPPORTED,
        "auto_annotation_mode": DATASET_AUTO_ANNOTATION_MODE_UNSUPPORTED,
        "operations": {**_BASE_OPERATIONS},
    },
}


def build_dataset_capabilities(vision_task_type):
    """按任务类型构造统一能力表。"""
    capability = _CAPABILITY_MAP.get(vision_task_type)
    if capability:
        return {
            "annotation_mode": capability["annotation_mode"],
            "training_mode": capability["training_mode"],
            "auto_annotation_mode": capability["auto_annotation_mode"],
            "operations": dict(capability["operations"]),
        }
    return {
        "annotation_mode": DATASET_ANNOTATION_MODE_UNSUPPORTED,
        "training_mode": DATASET_TRAINING_MODE_UNSUPPORTED,
        "auto_annotation_mode": DATASET_AUTO_ANNOTATION_MODE_UNSUPPORTED,
        "operations": dict(_BASE_OPERATIONS),
    }


def is_dataset_operation_supported(vision_task_type, operation):
    """判断当前任务类型是否支持指定操作。"""
    return bool(build_dataset_capabilities(vision_task_type)["operations"].get(operation))


def require_dataset_operation(vision_task_type, operation):
    """要求当前任务类型必须支持指定操作。"""
    if is_dataset_operation_supported(vision_task_type, operation):
        return
    label = DATASET_OPERATION_LABELS.get(operation) or operation
    raise ValueError(f"当前任务类型暂不支持{label}")
