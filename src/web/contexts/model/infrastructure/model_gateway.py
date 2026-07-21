"""管理预训练模型下载状态并汇总项目可用模型。"""

import logging
import os
import threading
import time
from urllib import request

from app.config import PRETRAINED_MODELS_DIR
from contexts.model.domain.capabilities import build_model_capabilities
from contexts.model.infrastructure.model_catalog import (
    describe_model_path,
    is_model_allowed_for_task,
    load_ultralytics_catalog,
    load_pretrained_model_config_items,
    local_path_for_name,
    resolve_model_vision_task_type,
)
from contexts.project.infrastructure.project_paths import get_project_models_dir
from contexts.task.domain.task_artifact_keys import ARTIFACT_BEST_WEIGHT_PATH, ARTIFACT_LAST_WEIGHT_PATH
from contexts.task.infrastructure.task_repository import get_task_history as load_task_history
from contexts.training.application.queries import list_training_workflow_records
from shared.utils.fs_utils import safe_size
from shared.utils.json_utils import encode_json
from shared.utils.path_utils import storage_path_ref
from ultralytics.utils import ASSETS_URL
from ultralytics.utils.downloads import GITHUB_ASSETS_NAMES, check_disk_space

logger = logging.getLogger(__name__)
_MODEL_USAGE_AUTO_ANNOTATE = "auto_annotate"

_download_status = {}
_download_lock = threading.Lock()
_DOWNLOAD_STATE_IDLE = "idle"
_DOWNLOAD_STATE_DOWNLOADING = "downloading"
_DOWNLOAD_STATE_READY = "ready"
_DOWNLOAD_STATE_FAILED = "failed"
_DOWNLOAD_TTL = 3600


def _serialize_download_event(event):
    """把模型下载事件编码成 SSE 数据块。"""
    return f"data: {encode_json(event, ensure_ascii=False)}\n\n"


def cleanup_pretrained_downloads():
    """清理长时间未更新的已结束下载状态。"""
    now = time.time()
    with _download_lock:
        expired = [
            name
            for name, status in _download_status.items()
            if status.get("state") != _DOWNLOAD_STATE_DOWNLOADING
            and now - status.get("updated_at", now) > _DOWNLOAD_TTL
        ]
        for name in expired:
            _download_status.pop(name, None)


def _ensure_status(name):
    """确保指定模型具备统一的下载状态结构。"""
    status = _download_status.setdefault(
        name,
        {
            "name": name,
            "state": _DOWNLOAD_STATE_IDLE,
            "progress": 0,
            "bytes_downloaded": 0,
            "total_bytes": 0,
            "error": None,
            "message": "",
            "events": [],
            "updated_at": time.time(),
        },
    )
    status.setdefault("events", [])
    status.setdefault("message", "")
    status.setdefault("error", None)
    status.setdefault("progress", 0)
    status.setdefault("bytes_downloaded", 0)
    status.setdefault("total_bytes", 0)
    status["updated_at"] = time.time()
    return status


def _build_status_snapshot(name, status):
    """把内部状态转换为对外稳定结构。"""
    local_path = local_path_for_name(name)
    is_downloaded = os.path.isfile(local_path)
    ready_size = safe_size(local_path) if is_downloaded else 0
    return {
        "name": name,
        "is_downloaded": is_downloaded,
        "local_path": local_path if is_downloaded else None,
        "state": status.get("state", _DOWNLOAD_STATE_IDLE) if not is_downloaded else _DOWNLOAD_STATE_READY,
        "progress": 100 if is_downloaded else int(status.get("progress", 0) or 0),
        "bytes_downloaded": ready_size if is_downloaded else int(status.get("bytes_downloaded", 0) or 0),
        "total_bytes": ready_size if is_downloaded else int(status.get("total_bytes", 0) or 0),
        "error": status.get("error"),
        "message": status.get("message") or "",
    }


def _append_download_event(name, **patch):
    """刷新下载状态并记录一条可供 SSE 推送的事件。"""
    with _download_lock:
        status = _ensure_status(name)
        status.update({key: value for key, value in patch.items() if key != "events"})
        status["updated_at"] = time.time()
        event = _build_status_snapshot(name, status)
        status["events"].append(event)
        return event


def _resolve_pretrained_download_url(name):
    """解析官方预训练模型的真实下载地址。"""
    if name in GITHUB_ASSETS_NAMES:
        return f"{ASSETS_URL}/{name}"
    raise ValueError(f"不支持的官方预训练模型: {name}")


def _download_pretrained_async(name):
    """异步下载预训练模型并维护下载状态。"""
    local_path = local_path_for_name(name)
    if os.path.isfile(local_path):
        _append_download_event(
            name,
            state=_DOWNLOAD_STATE_READY,
            progress=100,
            bytes_downloaded=safe_size(local_path),
            total_bytes=safe_size(local_path),
            error=None,
            message="模型已就绪",
        )
        return

    with _download_lock:
        current = _ensure_status(name)
        if current.get("state") == _DOWNLOAD_STATE_DOWNLOADING:
            return
        current["events"] = []

    _append_download_event(
        name,
        state=_DOWNLOAD_STATE_DOWNLOADING,
        progress=0,
        bytes_downloaded=0,
        total_bytes=0,
        error=None,
        message="开始准备模型...",
    )

    def _worker():
        """执行实际下载并在完成后移动到本地缓存目录。"""
        partial_path = f"{local_path}.part"
        try:
            url = _resolve_pretrained_download_url(name)
            os.makedirs(PRETRAINED_MODELS_DIR, exist_ok=True)
            if os.path.exists(partial_path):
                os.remove(partial_path)
            with request.urlopen(url) as response:
                total_bytes = int(response.getheader("Content-Length", 0) or 0)
                if total_bytes > 1048576:
                    check_disk_space(total_bytes, path=PRETRAINED_MODELS_DIR)
                chunk_size = max(8192, min(1048576, total_bytes // 1000)) if total_bytes else 8192
                downloaded_bytes = 0
                last_progress = -1
                _append_download_event(
                    name,
                    state=_DOWNLOAD_STATE_DOWNLOADING,
                    progress=0,
                    bytes_downloaded=0,
                    total_bytes=total_bytes,
                    error=None,
                    message="正在下载模型...",
                )
                with open(partial_path, "wb") as downloaded_file:
                    while True:
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        downloaded_file.write(chunk)
                        downloaded_bytes += len(chunk)
                        progress = int(downloaded_bytes * 100 / total_bytes) if total_bytes else 0
                        if progress != last_progress:
                            last_progress = progress
                            _append_download_event(
                                name,
                                state=_DOWNLOAD_STATE_DOWNLOADING,
                                progress=progress,
                                bytes_downloaded=downloaded_bytes,
                                total_bytes=total_bytes,
                                error=None,
                                message="正在下载模型...",
                            )
            if total_bytes and safe_size(partial_path) != total_bytes:
                raise RuntimeError(f"模型下载不完整: {safe_size(partial_path)}/{total_bytes}")
            os.replace(partial_path, local_path)
            with _download_lock:
                _ensure_status(name)["events"] = []
            _append_download_event(
                name,
                state=_DOWNLOAD_STATE_READY,
                progress=100,
                bytes_downloaded=safe_size(local_path),
                total_bytes=safe_size(local_path),
                error=None,
                message="模型已就绪",
            )
        except Exception as exc:
            logger.exception("download_pretrained %s failed", name)
            if os.path.exists(partial_path):
                try:
                    os.remove(partial_path)
                except OSError:
                    pass
            _append_download_event(
                name,
                state=_DOWNLOAD_STATE_FAILED,
                progress=0,
                error=str(exc),
                message="模型下载失败",
            )

    threading.Thread(target=_worker, daemon=True, name=f"dl-{name}").start()


def list_pretrained_options(vision_task_type=None):
    """返回预训练模型目录及本地缓存状态。"""
    cleanup_pretrained_downloads()
    options = []
    for item in load_ultralytics_catalog(vision_task_type=vision_task_type):
        name = item["name"]
        with _download_lock:
            status = _build_status_snapshot(name, _ensure_status(name))
        options.append(
            {
                **item,
                "capabilities": build_model_capabilities(item.get("vision_task_type")),
                "is_downloaded": status["is_downloaded"],
                "local_path": status["local_path"],
                "size_bytes": status["bytes_downloaded"] if status["is_downloaded"] else 0,
                "download_state": status["state"],
                "download_progress": status["progress"],
                "download_error": status["error"],
                "download_message": status["message"],
                "download_total_bytes": status["total_bytes"],
                "downloaded_bytes": status["bytes_downloaded"],
            }
        )
    return options


def get_pretrained_status(name):
    """返回单个预训练模型的当前状态。"""
    if not name:
        raise ValueError("缺少模型名")
    cleanup_pretrained_downloads()
    with _download_lock:
        return _build_status_snapshot(name, _ensure_status(name))


def stream_pretrained_download(name):
    """以 SSE 方式流式返回指定模型的真实下载进度。"""
    if not name:
        raise ValueError("缺少模型名")
    cleanup_pretrained_downloads()
    _download_pretrained_async(name)
    last_event_index = 0
    deadline = time.time() + 1800
    while time.time() < deadline:
        with _download_lock:
            status = _ensure_status(name)
            events = list(status.get("events", []))
            snapshot = _build_status_snapshot(name, status)
        while last_event_index < len(events):
            yield _serialize_download_event(events[last_event_index])
            last_event_index += 1
        if snapshot["state"] in {_DOWNLOAD_STATE_READY, _DOWNLOAD_STATE_FAILED}:
            if not events:
                yield _serialize_download_event(snapshot)
            return
        time.sleep(0.1)
    yield _serialize_download_event(
        _append_download_event(
            name,
            state=_DOWNLOAD_STATE_FAILED,
            progress=0,
            error="模型准备超时",
            message="模型准备超时",
        )
    )


def _build_model_item(name, model_type, path, size, **extra):
    """构造统一的模型展示项。"""
    vision_task_type = extra.get("vision_task_type")
    return {
        "name": name,
        "type": model_type,
        "path": path,
        "size": size,
        "capabilities": build_model_capabilities(vision_task_type),
        **extra,
    }


def _is_auto_annotate_candidate_path(path):
    """当前自动标注仅接收可直接由 YOLO 加载的 PyTorch 权重。"""
    return str(path or "").lower().endswith(".pt")


def _list_global_pretrained_models(vision_task_type=None, usage=None):
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
            if (
                not artifact
                or add_path in existing_paths
                or not is_model_allowed_for_task(artifact["name"], vision_task_type)
                or (usage == _MODEL_USAGE_AUTO_ANNOTATE and not _is_auto_annotate_candidate_path(add_path))
            ):
                continue
            models.append(
                _build_model_item(
                    artifact["name"],
                    "pretrained",
                    add_path,
                    artifact["size"],
                    is_global=True,
                    vision_task_type=resolve_model_vision_task_type(artifact["name"]),
                )
            )
            existing_paths.add(add_path)
    except Exception as exc:
        logger.warning("加载 pretrained config 失败: %s", exc)

    if os.path.exists(PRETRAINED_MODELS_DIR):
        for entry in os.listdir(PRETRAINED_MODELS_DIR):
            artifact = describe_model_path(os.path.join(PRETRAINED_MODELS_DIR, entry))
            add_path = artifact["path"] if artifact else None
            if (
                artifact
                and add_path not in existing_paths
                and is_model_allowed_for_task(artifact["name"], vision_task_type)
                and (usage != _MODEL_USAGE_AUTO_ANNOTATE or _is_auto_annotate_candidate_path(add_path))
            ):
                models.append(
                    _build_model_item(
                        artifact["name"],
                        "pretrained",
                        add_path,
                        artifact["size"],
                        is_global=True,
                        vision_task_type=resolve_model_vision_task_type(artifact["name"]),
                    )
                )
                existing_paths.add(add_path)
    return models


def scan_models(project_path, vision_task_type=None, usage=None):
    """汇总全局模型、项目模型与训练产物模型。"""
    if not project_path:
        raise ValueError("缺少项目路径")
    models = []
    models.extend(_list_global_pretrained_models(vision_task_type=vision_task_type, usage=usage))

    models_dir = get_project_models_dir(project_path)
    if os.path.exists(models_dir):
        for item in os.listdir(models_dir):
            artifact = describe_model_path(os.path.join(models_dir, item), default_name=item)
            if (
                artifact
                and is_model_allowed_for_task(artifact["name"], vision_task_type)
                and (usage != _MODEL_USAGE_AUTO_ANNOTATE or _is_auto_annotate_candidate_path(artifact["path"]))
            ):
                models.append(
                    _build_model_item(
                        artifact["name"],
                        "pretrained",
                        artifact["path"],
                        artifact["size"],
                        vision_task_type=resolve_model_vision_task_type(artifact["name"]),
                    )
                )

    workflows = list_training_workflow_records(project_path)
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
            metrics = {
                "map50": last.get("map50"),
                "map50_95": last.get("map50_95"),
                "top1": (last.get("extra") or {}).get("top1"),
                "top5": (last.get("extra") or {}).get("top5"),
            }
        task_vision_task_type = training_task.get("vision_task_type")
        if vision_task_type not in (None, "") and task_vision_task_type != vision_task_type:
            continue
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
                    vision_task_type=task_vision_task_type,
                )
            )
    return models
