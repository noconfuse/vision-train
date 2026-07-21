"""封装 worker 工件、停止信号与完成态回写。"""

import os

from contexts.task.domain.task_artifact_keys import (
    ARTIFACT_LOG_PATH,
    ARTIFACT_STOP_SIGNAL_PATH,
    ARTIFACT_TASK_DIR,
    ARTIFACT_WORKER_EXITED_AT,
    ARTIFACT_WORKER_MODULE_NAME,
    ARTIFACT_WORKER_PID,
    ARTIFACT_WORKER_STARTED_AT,
    TASK_STORAGE_ARTIFACT_KEYS,
)
from contexts.task.infrastructure.task_repository import (
    get_task_record,
    merge_task_artifacts as merge_artifacts,
    update_task as update_task_status,
)
from shared.utils.fs_utils import remove_file_silent
from shared.utils.time_utils import now_iso
from protocols.task_status import TASK_STATUS_RUNNING


STOP_SIGNAL_FILENAME = ".stop-request"


def is_stop_requested(stop_signal_path):
    """判断 worker 是否已收到停止信号。"""
    return bool(stop_signal_path and os.path.exists(stop_signal_path))


def request_stop(stop_signal_path):
    """创建停止信号文件。"""
    if not stop_signal_path:
        raise ValueError("缺少 stop_signal_path")
    if os.path.exists(stop_signal_path):
        return False
    os.makedirs(os.path.dirname(stop_signal_path), exist_ok=True)
    with open(stop_signal_path, "w", encoding="utf-8") as handle:
        handle.write(now_iso())
    return True


def build_worker_artifacts(base_dir, log_filename, worker_module_name):
    """构建 worker 运行所需 artifacts 字段。"""
    os.makedirs(base_dir, exist_ok=True)
    stop_signal_path = os.path.join(base_dir, STOP_SIGNAL_FILENAME)
    log_path = os.path.join(base_dir, log_filename)
    remove_file_silent(stop_signal_path)
    return {
        ARTIFACT_TASK_DIR: base_dir,
        ARTIFACT_STOP_SIGNAL_PATH: stop_signal_path,
        ARTIFACT_LOG_PATH: log_path,
        ARTIFACT_WORKER_MODULE_NAME: worker_module_name,
        ARTIFACT_WORKER_PID: None,
        ARTIFACT_WORKER_STARTED_AT: None,
        ARTIFACT_WORKER_EXITED_AT: None,
    }


def mark_worker_started(task_id, pid, worker_module_name=None, artifacts_patch=None):
    """记录 worker 启动后的 PID 与工件信息。"""
    patch = {
        ARTIFACT_WORKER_PID: pid,
        ARTIFACT_WORKER_STARTED_AT: now_iso(),
        ARTIFACT_WORKER_EXITED_AT: None,
    }
    if worker_module_name:
        patch[ARTIFACT_WORKER_MODULE_NAME] = worker_module_name
    if artifacts_patch:
        patch.update(artifacts_patch)
    merge_artifacts(task_id, patch)


def mark_worker_exited(task_id):
    """记录 worker 已退出。"""
    merge_artifacts(
        task_id,
        {
            ARTIFACT_WORKER_PID: None,
            ARTIFACT_WORKER_EXITED_AT: now_iso(),
        },
    )


def list_task_storage_paths(task_dict):
    """收集任务 artifacts 中的持久化路径。"""
    if not task_dict:
        return []
    artifacts = task_dict.get("artifacts") or {}
    candidate_paths = []
    for key in TASK_STORAGE_ARTIFACT_KEYS:
        path = artifacts.get(key)
        if path and path not in candidate_paths:
            candidate_paths.append(path)
    return candidate_paths


def finish_worker_task(task_id, status, message, *, progress=None, error=None, artifacts_patch=None, stop_signal_path=None):
    """清理停止信号并回写任务结束状态。"""
    remove_file_silent(stop_signal_path)
    if artifacts_patch:
        merge_artifacts(task_id, artifacts_patch)
    patch = {"status": status, "message": message, "finished_at": now_iso()}
    if progress is not None:
        patch["progress"] = progress
    if error is not None:
        patch["error"] = error
    update_task_status(task_id, **patch)


def update_worker_task_progress(task_id, progress, message):
    """在运行中任务上单调更新进度与消息。"""
    task = get_task_record(task_id)
    if not task or task.get("status") != TASK_STATUS_RUNNING:
        return
    current_progress = int(task.get("progress") or 0)
    next_progress = max(current_progress, int(progress or 0))
    update_task_status(task_id, status=TASK_STATUS_RUNNING, progress=min(next_progress, 99), message=message)
