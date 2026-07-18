"""管理预训练模型下载状态并汇总项目可用模型。"""

import logging
import os
import threading

from app.config import PRETRAINED_MODELS_DIR
from contexts.model.infrastructure.model_catalog import (
    describe_model_path,
    load_ultralytics_catalog,
    load_pretrained_model_config_items,
    local_path_for_name,
    resolve_ultralytics_download_path,
)
from contexts.project.infrastructure.project_paths import get_project_models_dir
from contexts.task.domain.task_artifact_keys import ARTIFACT_BEST_WEIGHT_PATH, ARTIFACT_LAST_WEIGHT_PATH
from contexts.task.infrastructure.task_repository import get_task_history as load_task_history
from contexts.training.infrastructure.workflow_repository import list_training_workflows
from shared.utils.fs_utils import safe_size
from shared.utils.path_utils import storage_path_ref

logger = logging.getLogger(__name__)

_download_status = {}
_download_lock = threading.Lock()


def _download_pretrained_async(name):
    """异步下载预训练模型并维护下载状态。"""
    local_path = local_path_for_name(name)
    if os.path.isfile(local_path):
        with _download_lock:
            _download_status[name] = {"state": "ready", "progress": 100, "error": None}
        return

    with _download_lock:
        current = _download_status.get(name, {})
        if current.get("state") == "downloading":
            return
        _download_status[name] = {"state": "downloading", "progress": 0, "error": None}

    def _worker():
        """执行实际下载并在完成后移动到本地缓存目录。"""
        try:
            from ultralytics import YOLO

            YOLO(name)
            downloaded_path = resolve_ultralytics_download_path(name)
            if not downloaded_path:
                raise RuntimeError(f"未能下载 {name}：ultralytics 自动下载失败")
            os.makedirs(PRETRAINED_MODELS_DIR, exist_ok=True)
            if os.path.abspath(downloaded_path) != os.path.abspath(local_path):
                os.replace(downloaded_path, local_path)
            with _download_lock:
                _download_status[name] = {"state": "ready", "progress": 100, "error": None}
        except Exception as exc:
            logger.exception("download_pretrained %s failed", name)
            with _download_lock:
                _download_status[name] = {"state": "failed", "progress": 0, "error": str(exc)}

    threading.Thread(target=_worker, daemon=True, name=f"dl-{name}").start()


def list_pretrained_options():
    """返回预训练模型目录及本地缓存状态。"""
    options = []
    for item in load_ultralytics_catalog():
        name = item["name"]
        local_path = local_path_for_name(name)
        is_downloaded = os.path.isfile(local_path)
        with _download_lock:
            status = _download_status.get(name, {})
        options.append(
            {
                **item,
                "is_downloaded": is_downloaded,
                "local_path": local_path if is_downloaded else None,
                "size_bytes": safe_size(local_path) if is_downloaded else 0,
                "download_state": status.get("state", "idle") if not is_downloaded else "ready",
                "download_progress": status.get("progress", 0) if not is_downloaded else 100,
                "download_error": status.get("error"),
            }
        )
    return options


def get_pretrained_status(name):
    """返回单个预训练模型的当前状态。"""
    if not name:
        raise ValueError("缺少模型名")
    local_path = local_path_for_name(name)
    is_downloaded = os.path.isfile(local_path)
    with _download_lock:
        status = _download_status.get(name, {})
    return {
        "name": name,
        "is_downloaded": is_downloaded,
        "local_path": local_path if is_downloaded else None,
        "state": status.get("state", "idle") if not is_downloaded else "ready",
        "progress": status.get("progress", 0) if not is_downloaded else 100,
        "error": status.get("error"),
    }


def download_pretrained(name):
    """校验模型名后启动异步下载。"""
    if not name:
        raise ValueError("缺少模型名")
    _download_pretrained_async(name)
    return get_pretrained_status(name)


def _build_model_item(name, model_type, path, size, **extra):
    """构造统一的模型展示项。"""
    return {
        "name": name,
        "type": model_type,
        "path": path,
        "size": size,
        **extra,
    }


def _list_global_pretrained_models():
    """扫描全局预训练目录中的可用模型。"""
    models = []
    existing_paths = set()

    try:
        for item in load_pretrained_model_config_items(os.path.dirname(PRETRAINED_MODELS_DIR)).values():
            path = item.get("path")
            if not path:
                continue
            artifact = describe_model_path(path, default_name=item.get("name"))
            add_path = artifact["path"] if artifact else None
            if not artifact or add_path in existing_paths:
                continue
            models.append(_build_model_item(artifact["name"], "pretrained", add_path, artifact["size"], is_global=True))
            existing_paths.add(add_path)
    except Exception as exc:
        logger.warning("加载 pretrained config 失败: %s", exc)

    if os.path.exists(PRETRAINED_MODELS_DIR):
        for entry in os.listdir(PRETRAINED_MODELS_DIR):
            artifact = describe_model_path(os.path.join(PRETRAINED_MODELS_DIR, entry))
            add_path = artifact["path"] if artifact else None
            if artifact and add_path not in existing_paths:
                models.append(_build_model_item(artifact["name"], "pretrained", add_path, artifact["size"], is_global=True))
                existing_paths.add(add_path)
    return models


def scan_models(project_path):
    """汇总全局模型、项目模型与训练产物模型。"""
    if not project_path:
        raise ValueError("缺少项目路径")
    models = []
    models.extend(_list_global_pretrained_models())

    models_dir = get_project_models_dir(project_path)
    if os.path.exists(models_dir):
        for item in os.listdir(models_dir):
            artifact = describe_model_path(os.path.join(models_dir, item), default_name=item)
            if artifact:
                models.append(_build_model_item(artifact["name"], "pretrained", artifact["path"], artifact["size"]))

    workflows = list_training_workflows(project_path)
    for workflow in workflows:
        training_task = workflow.get("latest_training_task") or {}
        run_id = training_task.get("id")
        dataset_name = training_task.get("dataset_name")
        if not run_id or not dataset_name:
            continue
        artifacts = training_task.get("artifacts") or {}
        history = load_task_history(run_id)
        metrics = {}
        if history:
            last = history[-1]
            metrics = {"map50": last.get("map50"), "map50_95": last.get("map50_95")}
        for weight_name, weight_path in (
            ("best.pt", artifacts.get(ARTIFACT_BEST_WEIGHT_PATH)),
            ("last.pt", artifacts.get(ARTIFACT_LAST_WEIGHT_PATH)),
        ):
            if not weight_path:
                continue
            if not os.path.exists(weight_path):
                continue
            models.append(
                _build_model_item(
                    f"{dataset_name}_{run_id}_{weight_name}",
                    "trained",
                    storage_path_ref(weight_path),
                    safe_size(weight_path),
                    source_run=run_id,
                    source_workflow=workflow.get("id"),
                    dataset=dataset_name,
                    created_at=training_task.get("created_at"),
                    metrics=metrics,
                )
            )
    return models
