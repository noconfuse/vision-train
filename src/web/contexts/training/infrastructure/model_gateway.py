"""确保训练上下文使用的预训练模型已下载到本地。"""

import logging
import os
import threading
import time

from contexts.model.infrastructure.model_catalog import local_path_for_name, resolve_ultralytics_download_path

logger = logging.getLogger(__name__)

_download_status = {}
_download_lock = threading.Lock()

def _download_pretrained_async(model_name):
    """异步触发指定预训练模型的下载任务。"""
    local_path = local_path_for_name(model_name)
    if os.path.isfile(local_path):
        with _download_lock:
            _download_status[model_name] = {"state": "ready", "error": None}
        return

    with _download_lock:
        current = _download_status.get(model_name, {})
        if current.get("state") == "downloading":
            return
        _download_status[model_name] = {"state": "downloading", "error": None}

    def _worker():
        """执行实际下载并同步更新下载状态。"""
        try:
            from ultralytics import YOLO

            YOLO(model_name)
            downloaded_path = resolve_ultralytics_download_path(model_name)
            if not downloaded_path:
                raise RuntimeError(f"未能下载 {model_name}：ultralytics 自动下载失败")

            if os.path.abspath(downloaded_path) != os.path.abspath(local_path):
                os.replace(downloaded_path, local_path)

            with _download_lock:
                _download_status[model_name] = {"state": "ready", "error": None}
        except Exception as exc:
            logger.exception("下载预训练模型 %s 失败", model_name)
            with _download_lock:
                _download_status[model_name] = {"state": "failed", "error": str(exc)}

    threading.Thread(target=_worker, daemon=True, name=f"pretrained-{model_name}").start()


def ensure_pretrained_model(model_name, timeout=600):
    """等待指定预训练模型可用并返回本地路径。"""
    local_path = local_path_for_name(model_name)
    if os.path.isfile(local_path):
        return local_path

    _download_pretrained_async(model_name)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.isfile(local_path):
            return local_path
        with _download_lock:
            status = _download_status.get(model_name, {})
        if status.get("state") == "failed":
            raise RuntimeError(status.get("error") or f"下载 {model_name} 失败")
        time.sleep(0.5)

    raise TimeoutError(f"下载 {model_name} 超时")
