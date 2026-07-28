"""数据集快照（DVC 入库 / 提交）后台任务执行入口。

由 task_worker 按 TASK_TYPE_DATASET_SNAPSHOT 分发到本模块的
``execute_dataset_snapshot_task``。执行过程中按文件总数推进 progress，
并把当前处理进度写回 task.artifacts.snapshot_progress，便于前端轮询。
"""

from __future__ import annotations

import logging
import os

from contexts.dataset.infrastructure import dvc_backend
from contexts.dataset.infrastructure.dataset_repository import resolve_project_dataset_root
from contexts.dataset.infrastructure.dataset_task_type import load_dataset_identity_meta
from contexts.dataset.infrastructure.dataset_versioning import (
    DATASET_VERSIONING_STATUS_FAILED,
    DATASET_VERSIONING_STATUS_READY,
    _build_version_record,
    _write_version_record,
    new_dataset_version_id,
    update_dataset_identity_meta,
)
from contexts.task.infrastructure.task_repository import (
    get_task_record,
    update_task as update_task_status,
)
from contexts.task.infrastructure.worker_task_ops import is_stop_requested
from shared.utils.time_utils import now_iso

logger = logging.getLogger(__name__)


def _set_progress(task_id: str, processed: int, total: int, message: str = "") -> None:
    """把处理进度和消息写回任务记录。"""
    patch = {
        "progress": int(round(100 * processed / total)) if total else 0,
        "message": message or f"快照进度 {processed}/{total}",
        "artifacts": {"snapshot_processed": processed, "snapshot_total": total},
    }
    update_task_status(task_id, **patch)


def _set_terminal(
    task_id: str,
    status: str,
    message: str = "",
    error: str = "",
    *,
    dataset_root: str | None = None,
    is_initial_snapshot: bool = False,
) -> None:
    """写入任务终态。"""
    patch = {
        "status": status,
        "message": message,
        "finished_at": now_iso(),
    }
    if error:
        patch["error"] = error
    update_task_status(task_id, **patch)
    if dataset_root and is_initial_snapshot and status in {"failed", "stopped", "interrupted"}:
        update_dataset_identity_meta(
            dataset_root,
            versioning_status=DATASET_VERSIONING_STATUS_FAILED,
        )


def _resolve_dataset_root(project_path: str, dataset_name: str, dataset_path: str | None) -> str:
    """从 task payload 中恢复数据集目录绝对路径。"""
    if dataset_path and os.path.isdir(dataset_path):
        return dataset_path
    if dataset_name:
        root = resolve_project_dataset_root(project_path, dataset_name=dataset_name)
        if root:
            return root
    raise ValueError("数据集不存在，无法执行快照任务")


def execute_dataset_snapshot_task(task_id: str) -> None:
    """执行单条数据集快照任务。

    payload 结构：
    - project_path, dataset_name, dataset_path
    - mode: add / commit
    - reason: import / manual_publish / split_dataset ...
    - source_version_id: 可选
    """
    task = get_task_record(task_id)
    if not task:
        raise ValueError(f"任务不存在: {task_id}")

    payload = task.get("payload") or {}
    artifacts = task.get("artifacts") or {}
    project_path = task.get("project_path") or payload.get("project_path") or ""
    dataset_name = payload.get("dataset_name") or task.get("dataset_name") or ""
    dataset_path = payload.get("dataset_path") or task.get("dataset_path") or ""
    mode = payload.get("mode") or "add"
    reason = payload.get("reason") or "manual_publish"
    source_version_id = payload.get("source_version_id") or ""
    is_initial_snapshot = bool(payload.get("is_initial_snapshot"))
    stop_signal_path = artifacts.get("stop_signal_path") or ""

    if not project_path:
        raise ValueError("缺少 project_path")

    dataset_root = _resolve_dataset_root(project_path, dataset_name, dataset_path)

    # 进度基准：先 walk 一次算文件数；中途允许停止信号打断。
    total = 0
    for _root, _dirs, files in os.walk(dataset_root):
        if is_stop_requested(stop_signal_path):
            _set_terminal(
                task_id,
                "stopped",
                message="快照任务已停止",
                dataset_root=dataset_root,
                is_initial_snapshot=is_initial_snapshot,
            )
            return
        for name in files:
            if name.endswith(".dvc"):
                continue
            total += 1
    _set_progress(task_id, 0, total, message="DVC 入库准备就绪")

    # 真正调 DVC；调用方通过 dvc_backend 自带进度阶段回调。
    def _on_progress(stage_processed: int) -> None:
        if is_stop_requested(stop_signal_path):
            return
        _set_progress(task_id, min(stage_processed, total), total)

    try:
        if mode == "add":
            dvc_rev = dvc_backend.dvc_add_dataset(project_path, dataset_root, on_progress=_on_progress)
        elif mode == "commit":
            dvc_rev = dvc_backend.dvc_commit_dataset(project_path, dataset_root)
        else:
            raise ValueError(f"不支持的 mode: {mode}")
    except dvc_backend.DVCUnavailableError as exc:
        _set_terminal(
            task_id,
            "failed",
            message="DVC 未安装",
            error=str(exc),
            dataset_root=dataset_root,
            is_initial_snapshot=is_initial_snapshot,
        )
        return
    except dvc_backend.DVCCommandError as exc:
        _set_terminal(
            task_id,
            "failed",
            message="DVC 命令执行失败",
            error=str(exc),
            dataset_root=dataset_root,
            is_initial_snapshot=is_initial_snapshot,
        )
        return

    if is_stop_requested(stop_signal_path):
        _set_terminal(
            task_id,
            "stopped",
            message="快照任务已停止",
            dataset_root=dataset_root,
            is_initial_snapshot=is_initial_snapshot,
        )
        return

    # 写项目侧的版本元数据 + 更新 current_version_id
    identity = load_dataset_identity_meta(dataset_root)
    dataset_id = identity["dataset_id"]
    version_id = new_dataset_version_id()
    record = _build_version_record(
        dataset_id=dataset_id,
        version_id=version_id,
        dataset_name=dataset_name or os.path.basename(os.path.realpath(dataset_root)),
        dataset_root=dataset_root,
        reason=reason,
        source_version_id=source_version_id,
        dvc_rev=dvc_rev,
    )
    _write_version_record(project_path, record)
    update_dataset_identity_meta(
        dataset_root,
        current_version_id=version_id,
        versioning_status=DATASET_VERSIONING_STATUS_READY,
    )

    _set_progress(task_id, total, total, message="快照入库完成")
    _set_terminal(task_id, "completed", message=f"已生成版本 {version_id}")
    logger.info("dataset snapshot task %s done, version=%s rev=%s", task_id, version_id, dvc_rev)
