"""统一生成训练任务目录并解析可复用权重路径。"""

import os

from contexts.task.domain.task_artifact_keys import (
    ARTIFACT_BEST_WEIGHT_PATH,
    ARTIFACT_LAST_WEIGHT_PATH,
)
from contexts.training.domain.training_constants import (
    TRAINING_CALIBRATIONS_DIRNAME,
    TRAINING_EXPORT_DIRNAME,
    TRAINING_INFERENCE_DIRNAME,
    TRAINING_OUTPUTS_DIRNAME,
    TRAINING_TASK_RUNS_DIRNAME,
    TRAINING_WEIGHTS_DIRNAME,
    TRAINING_WEIGHT_BEST_FILENAME,
    TRAINING_WEIGHT_LAST_FILENAME,
)
from shared.utils.path_utils import resolve_storage_path


def build_training_output_dir(project_path, dataset_name, run_id):
    """生成一次训练运行的输出目录。"""
    return os.path.join(project_path, TRAINING_OUTPUTS_DIRNAME, dataset_name, run_id)


def build_training_calibration_dir(project_path, dataset_name, calibration_id):
    """生成一次批次校准的输出目录。"""
    return os.path.join(project_path, TRAINING_CALIBRATIONS_DIRNAME, dataset_name, calibration_id)


def build_training_task_run_dir(output_dir, task_type, task_id):
    """生成训练派生任务的运行目录。"""
    return os.path.join(output_dir, TRAINING_TASK_RUNS_DIRNAME, task_type, task_id)


def build_training_export_dir(output_dir, task_id):
    """生成训练输出下的导出目录。"""
    return os.path.join(output_dir, TRAINING_EXPORT_DIRNAME, task_id)


def build_training_inference_dir(output_dir, task_id):
    """生成训练输出下的推理目录。"""
    return os.path.join(output_dir, TRAINING_INFERENCE_DIRNAME, task_id)


def build_training_weight_path(output_dir, weight_name):
    """生成指定权重文件的标准路径。"""
    return os.path.join(output_dir, TRAINING_WEIGHTS_DIRNAME, weight_name)


def build_training_weight_artifacts(output_dir):
    """生成任务产物中的 best/last 权重路径映射。"""
    output_dir = resolve_storage_path(output_dir) if output_dir else output_dir
    if not output_dir:
        return {
            ARTIFACT_BEST_WEIGHT_PATH: "",
            ARTIFACT_LAST_WEIGHT_PATH: "",
        }
    return {
        ARTIFACT_BEST_WEIGHT_PATH: build_training_weight_path(output_dir, TRAINING_WEIGHT_BEST_FILENAME),
        ARTIFACT_LAST_WEIGHT_PATH: build_training_weight_path(output_dir, TRAINING_WEIGHT_LAST_FILENAME),
    }


def get_training_best_weight_path(artifacts):
    """返回存在的 best 权重路径。"""
    weight_path = resolve_storage_path((artifacts or {}).get(ARTIFACT_BEST_WEIGHT_PATH)) if (artifacts or {}).get(ARTIFACT_BEST_WEIGHT_PATH) else ""
    return weight_path if weight_path and os.path.isfile(weight_path) else ""


def get_training_last_weight_path(artifacts):
    """返回存在的 last 权重路径。"""
    weight_path = resolve_storage_path((artifacts or {}).get(ARTIFACT_LAST_WEIGHT_PATH)) if (artifacts or {}).get(ARTIFACT_LAST_WEIGHT_PATH) else ""
    return weight_path if weight_path and os.path.isfile(weight_path) else ""


def resolve_training_resume_weight(artifacts):
    """选择续训优先使用的权重文件。"""
    last_weight_path = get_training_last_weight_path(artifacts)
    if last_weight_path:
        return TRAINING_WEIGHT_LAST_FILENAME, last_weight_path
    best_weight_path = get_training_best_weight_path(artifacts)
    if best_weight_path:
        return TRAINING_WEIGHT_BEST_FILENAME, best_weight_path
    return None, None
