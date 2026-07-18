"""加载并缓存自动标注模型，优先选择项目最近训练权重。"""

import os

from contexts.task.domain.task_types import TASK_TYPE_TRAINING
from contexts.task.infrastructure.task_runtime import list_project_tasks
from contexts.training.infrastructure.training_artifacts import get_training_best_weight_path

_light_models = {}


def _load_yolo(model_ref, cache_key):
    """按缓存键加载并复用一个 YOLO 模型实例。"""
    from ultralytics import YOLO

    model = _light_models.get(cache_key)
    if model is None:
        model = YOLO(model_ref)
        _light_models[cache_key] = model
    return model


def _find_latest_project_weight(project_path):
    """查找项目最近训练任务产出的最佳权重。"""
    if not project_path:
        return ""
    runs = list_project_tasks(project_path, type_=TASK_TYPE_TRAINING, limit=50)
    for task in runs:
        artifacts = task.get("artifacts") or {}
        best_weight_path = get_training_best_weight_path(artifacts)
        if best_weight_path:
            return best_weight_path
    return ""


def get_auto_annotate_model(project_path=None, prefer_project_best=True):
    """返回自动标注默认应使用的模型对象。"""
    if prefer_project_best and project_path:
        weight_path = _find_latest_project_weight(project_path)
        if weight_path and os.path.exists(weight_path):
            try:
                return _load_yolo(weight_path, f"best:{weight_path}")
            except Exception:
                pass
    try:
        return _load_yolo("yolo11n.pt", "yolo11n")
    except Exception:
        return None
