"""定义训练导出能力表。"""

from protocols.vision_task_type import (
    VISION_TASK_TYPE_CLASSIFY,
    VISION_TASK_TYPE_DETECT,
    VISION_TASK_TYPE_POSE,
    VISION_TASK_TYPE_SEGMENT,
)

EXPORT_FORMAT_ONNX = "onnx"
EXPORT_FORMAT_OPENVINO = "openvino"
EXPORT_FORMAT_ENGINE = "engine"

_COMMON_FORMATS = (
    {
        "value": EXPORT_FORMAT_ONNX,
        "label": "ONNX",
        "supports_half": True,
        "supports_int8": False,
        "hardware_key": "",
    },
    {
        "value": EXPORT_FORMAT_OPENVINO,
        "label": "OpenVINO",
        "supports_half": True,
        "supports_int8": True,
        "hardware_key": "",
    },
    {
        "value": EXPORT_FORMAT_ENGINE,
        "label": "TensorRT",
        "supports_half": True,
        "supports_int8": True,
        "hardware_key": "engine",
    },
)

_PROFILE_MAP = {
    VISION_TASK_TYPE_DETECT: {
        "default_format": EXPORT_FORMAT_ONNX,
        "formats": _COMMON_FORMATS,
        "engine_hint_supported": "TensorRT 导出会先生成 ONNX 中间模型，并依赖 TensorRT 运行环境。",
        "engine_hint_unsupported": "当前主机环境不支持 TensorRT 导出。",
        "half_enabled_text": "减小模型体积，适合常规部署。",
        "half_disabled_text": "当前格式不支持。",
        "half_conflict_text": "INT8 已开启，FP16 不能同时开启。",
        "int8_enabled_text": "更小更快，但精度可能下降。",
        "int8_disabled_text": "当前格式不支持。",
        "int8_conflict_text": "FP16 已开启，INT8 不能同时开启。",
    },
    VISION_TASK_TYPE_CLASSIFY: {
        "default_format": EXPORT_FORMAT_ONNX,
        "formats": _COMMON_FORMATS,
        "engine_hint_supported": "TensorRT 导出会先生成 ONNX 中间模型，并依赖 TensorRT 运行环境。",
        "engine_hint_unsupported": "当前主机环境不支持 TensorRT 导出。",
        "half_enabled_text": "减小模型体积，适合常规部署。",
        "half_disabled_text": "当前格式不支持。",
        "half_conflict_text": "INT8 已开启，FP16 不能同时开启。",
        "int8_enabled_text": "更小更快，但精度可能下降。",
        "int8_disabled_text": "当前格式不支持。",
        "int8_conflict_text": "FP16 已开启，INT8 不能同时开启。",
    },
    VISION_TASK_TYPE_SEGMENT: {
        "default_format": EXPORT_FORMAT_ONNX,
        "formats": (),
        "engine_hint_supported": "",
        "engine_hint_unsupported": "",
        "half_enabled_text": "",
        "half_disabled_text": "当前任务类型暂未接入导出。",
        "half_conflict_text": "",
        "int8_enabled_text": "",
        "int8_disabled_text": "当前任务类型暂未接入导出。",
        "int8_conflict_text": "",
    },
    VISION_TASK_TYPE_POSE: {
        "default_format": EXPORT_FORMAT_ONNX,
        "formats": (),
        "engine_hint_supported": "",
        "engine_hint_unsupported": "",
        "half_enabled_text": "",
        "half_disabled_text": "当前任务类型暂未接入导出。",
        "half_conflict_text": "",
        "int8_enabled_text": "",
        "int8_disabled_text": "当前任务类型暂未接入导出。",
        "int8_conflict_text": "",
    },
}


def get_training_export_profile(vision_task_type):
    """返回任务类型对应的导出能力表。"""
    profile = _PROFILE_MAP.get(vision_task_type)
    if not profile:
        raise ValueError("当前任务类型暂未接入导出")
    return profile


def build_training_export_profile(vision_task_type):
    """构造可序列化的导出能力表。"""
    profile = get_training_export_profile(vision_task_type)
    return {
        "default_format": profile["default_format"],
        "formats": [dict(item) for item in profile["formats"]],
        "engine_hint_supported": profile["engine_hint_supported"],
        "engine_hint_unsupported": profile["engine_hint_unsupported"],
        "half_enabled_text": profile["half_enabled_text"],
        "half_disabled_text": profile["half_disabled_text"],
        "half_conflict_text": profile["half_conflict_text"],
        "int8_enabled_text": profile["int8_enabled_text"],
        "int8_disabled_text": profile["int8_disabled_text"],
        "int8_conflict_text": profile["int8_conflict_text"],
    }


def get_export_format_support(vision_task_type, export_format):
    """返回某个任务类型下指定导出格式的支持信息。"""
    profile = get_training_export_profile(vision_task_type)
    return next((item for item in profile["formats"] if item["value"] == export_format), None)
