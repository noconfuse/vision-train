"""定义模型能力表，作为模型列表、预训练选项和训练入口的真源。"""

from protocols.vision_task_type import (
    VISION_TASK_TYPE_CLASSIFY,
    VISION_TASK_TYPE_DETECT,
    VISION_TASK_TYPE_POSE,
    VISION_TASK_TYPE_SEGMENT,
)

MODEL_TRAINING_MODE_UNSUPPORTED = "unsupported"
MODEL_TRAINING_MODE_YOLO_DETECT = "yolo_detect"
MODEL_TRAINING_MODE_YOLO_CLASSIFY = "yolo_classify"

MODEL_OPERATION_TRAIN = "train"
MODEL_OPERATION_EVALUATE = "evaluate"
MODEL_OPERATION_INFERENCE = "inference"
MODEL_OPERATION_EXPORT = "export"

_BASE_OPERATIONS = {
    MODEL_OPERATION_TRAIN: False,
    MODEL_OPERATION_EVALUATE: True,
    MODEL_OPERATION_INFERENCE: True,
    MODEL_OPERATION_EXPORT: True,
}

_MODEL_CAPABILITY_MAP = {
    VISION_TASK_TYPE_DETECT: {
        "training_mode": MODEL_TRAINING_MODE_YOLO_DETECT,
        "operations": {
            **_BASE_OPERATIONS,
            MODEL_OPERATION_TRAIN: True,
        },
    },
    VISION_TASK_TYPE_CLASSIFY: {
        "training_mode": MODEL_TRAINING_MODE_YOLO_CLASSIFY,
        "operations": {
            **_BASE_OPERATIONS,
            MODEL_OPERATION_TRAIN: True,
        },
    },
    VISION_TASK_TYPE_SEGMENT: {
        "training_mode": MODEL_TRAINING_MODE_UNSUPPORTED,
        "operations": {**_BASE_OPERATIONS},
    },
    VISION_TASK_TYPE_POSE: {
        "training_mode": MODEL_TRAINING_MODE_UNSUPPORTED,
        "operations": {**_BASE_OPERATIONS},
    },
}


def build_model_capabilities(vision_task_type):
    """按任务类型构造模型能力表。"""
    capability = _MODEL_CAPABILITY_MAP.get(vision_task_type)
    if capability:
        return {
            "training_mode": capability["training_mode"],
            "operations": dict(capability["operations"]),
        }
    return {
        "training_mode": MODEL_TRAINING_MODE_UNSUPPORTED,
        "operations": dict(_BASE_OPERATIONS),
    }


def model_training_mode_for_task(vision_task_type):
    """返回指定任务类型要求的模型训练方式。"""
    return build_model_capabilities(vision_task_type)["training_mode"]
