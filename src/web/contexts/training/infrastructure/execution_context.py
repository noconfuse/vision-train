"""解析训练执行链统一上下文，收口能力判断与数据入口推导。"""

import os

from contexts.dataset.domain.capabilities import (
    DATASET_OPERATION_TRAIN,
    build_dataset_capabilities,
    require_dataset_operation,
)
from contexts.dataset.infrastructure.dataset_import_yolo import ensure_dataset_yaml
from contexts.dataset.infrastructure.dataset_repository import find_dataset_config, resolve_project_dataset_root
from contexts.dataset.infrastructure.dataset_schema import normalize_dataset_yaml_for_training
from contexts.dataset.infrastructure.dataset_task_type import load_dataset_vision_task_type
from contexts.model.domain.capabilities import (
    MODEL_TRAINING_MODE_UNSUPPORTED,
    build_model_capabilities,
    model_training_mode_for_task,
)
from contexts.model.infrastructure.model_catalog import resolve_model_vision_task_type
from contexts.model.infrastructure.model_gateway import get_pretrained_status
from contexts.training.domain.training_profile import get_training_profile
from protocols.vision_task_type import VISION_TASK_TYPE_CLASSIFY, VISION_TASK_TYPE_SET
from shared.utils.path_utils import project_name_from_path, resolve_storage_path


def resolve_task_vision_task_type(task):
    """从任务主字段读取并校验视觉任务类型。"""
    vision_task_type = (task or {}).get("vision_task_type")
    if vision_task_type not in VISION_TASK_TYPE_SET:
        raise ValueError("任务缺少合法的 vision_task_type")
    return vision_task_type


def require_existing_file_path(path_value, error_message):
    """解析并校验文件路径存在。"""
    resolved_path = resolve_storage_path(path_value) if path_value else path_value
    if not resolved_path or not os.path.isfile(resolved_path):
        raise ValueError(error_message.format(path=resolved_path))
    return resolved_path


def require_existing_dir_path(path_value, error_message):
    """解析并校验目录路径存在。"""
    resolved_path = resolve_storage_path(path_value) if path_value else path_value
    if not resolved_path or not os.path.isdir(resolved_path):
        raise ValueError(error_message.format(path=resolved_path))
    return resolved_path


def resolve_dataset_root(project_path, dataset_name, dataset_path):
    """解析并校验训练所用数据集根目录。"""
    candidate = resolve_project_dataset_root(project_path, dataset_name=dataset_name, dataset_path=dataset_path)
    if candidate:
        return candidate
    project_name = project_name_from_path(project_path)
    raise ValueError(f"训练数据集 {dataset_name} 不存在（项目：{project_name}，数据集：{dataset_name}）")


def normalize_dataset_yaml_in_place(data_yaml, dataset_root):
    """原地规范 dataset.yaml 的 path 和 split 路径写法。"""
    if not data_yaml:
        return data_yaml
    normalized_path = resolve_storage_path(data_yaml) if data_yaml else data_yaml
    normalize_dataset_yaml_for_training(normalized_path, dataset_root)
    return normalized_path


def resolve_training_data_ref(vision_task_type, dataset_path, data_yaml):
    """按任务类型解析 Ultralytics 训练/评估所需的数据入口。"""
    if vision_task_type == VISION_TASK_TYPE_CLASSIFY:
        return require_existing_dir_path(dataset_path, "分类数据集目录不存在: {path}")
    return require_existing_file_path(data_yaml, "训练数据配置不存在: {path}")


def resolve_training_capability_context(vision_task_type):
    """按任务类型构造训练执行所需的能力上下文。"""
    dataset_capabilities = build_dataset_capabilities(vision_task_type)
    require_dataset_operation(vision_task_type, DATASET_OPERATION_TRAIN)
    training_mode = dataset_capabilities["training_mode"]
    if training_mode == MODEL_TRAINING_MODE_UNSUPPORTED:
        raise ValueError("当前数据集任务类型暂未接入训练")
    return {
        "vision_task_type": vision_task_type,
        "dataset_capabilities": dataset_capabilities,
        "training_mode": training_mode,
        "training_profile": get_training_profile(training_mode),
    }


def resolve_training_model_context(model_name, vision_task_type, model_path=None):
    """解析训练所需模型上下文并校验与任务类型兼容。"""
    model_vision_task_type = resolve_model_vision_task_type(model_name)
    model_capabilities = build_model_capabilities(model_vision_task_type)
    required_training_mode = model_training_mode_for_task(vision_task_type)
    if required_training_mode == MODEL_TRAINING_MODE_UNSUPPORTED:
        raise ValueError("当前数据集任务类型暂未接入训练")
    if model_capabilities["training_mode"] != required_training_mode:
        raise ValueError("所选模型与当前数据集任务类型不匹配")
    if model_path:
        resolved_model_path = require_existing_file_path(model_path, "模型文件不存在: {path}")
    else:
        status = get_pretrained_status(model_name)
        if not status.get("is_downloaded"):
            download_state = status.get("state")
            if download_state == "failed":
                raise ValueError(f"预训练模型准备失败: {status.get('error') or model_name}")
            if download_state == "downloading":
                raise ValueError("预训练模型下载中，请等待模型准备完成后再启动")
            raise ValueError("预训练模型尚未下载，请先准备模型")
        resolved_model_path = require_existing_file_path(status.get("local_path"), "模型文件不存在: {path}")
    return {
        "model_name": model_name,
        "model_path": resolved_model_path,
        "model_vision_task_type": model_vision_task_type,
        "model_capabilities": model_capabilities,
    }


def resolve_training_sources_context(project_path, dataset_name, model_name, dataset_path, model_path=None):
    """一次性解析训练/校准启动所需的完整上下文。"""
    dataset_root = resolve_dataset_root(project_path, dataset_name, dataset_path)
    vision_task_type = load_dataset_vision_task_type(dataset_root)
    capability_context = resolve_training_capability_context(vision_task_type)
    model_context = resolve_training_model_context(model_name, vision_task_type, model_path=model_path)
    data_yaml = find_dataset_config(dataset_root)
    if not data_yaml:
        ensure_dataset_yaml(dataset_root)
        data_yaml = find_dataset_config(dataset_root)
    if not data_yaml:
        raise ValueError("未找到 dataset.yaml")
    data_yaml = resolve_storage_path(data_yaml) if data_yaml else data_yaml
    try:
        data_yaml = normalize_dataset_yaml_in_place(data_yaml=data_yaml, dataset_root=dataset_root)
    except Exception:
        pass
    return {
        **capability_context,
        **model_context,
        "dataset_path": dataset_root,
        "data_yaml": data_yaml,
        "data_ref": resolve_training_data_ref(vision_task_type, dataset_root, data_yaml),
    }


def resolve_task_training_runtime_context(task):
    """从训练任务记录中恢复训练执行上下文。"""
    vision_task_type = resolve_task_vision_task_type(task)
    capability_context = resolve_training_capability_context(vision_task_type)
    artifacts = (task or {}).get("artifacts") or {}
    dataset_path = resolve_storage_path((task or {}).get("dataset_path")) if (task or {}).get("dataset_path") else (task or {}).get("dataset_path")
    data_yaml = resolve_storage_path(artifacts.get("dataset_yaml")) if artifacts.get("dataset_yaml") else artifacts.get("dataset_yaml")
    model_path = require_existing_file_path(artifacts.get("model_path"), "模型文件不存在: {path}")
    return {
        **capability_context,
        "dataset_path": dataset_path,
        "data_yaml": data_yaml,
        "data_ref": resolve_training_data_ref(vision_task_type, dataset_path, data_yaml),
        "model_path": model_path,
    }


def resolve_task_evaluate_runtime_context(task):
    """从评估任务记录中恢复评估执行上下文。"""
    vision_task_type = resolve_task_vision_task_type(task)
    payload = (task or {}).get("payload") or {}
    dataset_path = resolve_storage_path((task or {}).get("dataset_path")) if (task or {}).get("dataset_path") else (task or {}).get("dataset_path")
    data_yaml = require_existing_file_path(payload.get("data_yaml"), "dataset.yaml 不可用: {path}")
    weight_path = require_existing_file_path(payload.get("weight_path"), "评估权重不存在: {path}")
    return {
        **resolve_training_capability_context(vision_task_type),
        "dataset_path": dataset_path,
        "data_yaml": data_yaml,
        "data_ref": resolve_training_data_ref(vision_task_type, dataset_path, data_yaml),
        "weight_path": weight_path,
        "split": str(payload.get("split") or "").strip(),
    }


__all__ = [
    "normalize_dataset_yaml_in_place",
    "require_existing_dir_path",
    "require_existing_file_path",
    "resolve_dataset_root",
    "resolve_task_evaluate_runtime_context",
    "resolve_task_training_runtime_context",
    "resolve_task_vision_task_type",
    "resolve_training_capability_context",
    "resolve_training_data_ref",
    "resolve_training_model_context",
    "resolve_training_sources_context",
]
