"""dataset_snapshot 任务的对外启动入口。

按 video_task_gateway.start_extraction 的模式：start_task + build_worker_artifacts
+ spawn_worker_process。
"""

from __future__ import annotations

import logging
import os

from contexts.dataset.infrastructure.dataset_task_type import ensure_dataset_task_identity
from contexts.project.infrastructure.project_paths import get_project_task_dir
from contexts.task.domain.task_types import TASK_TYPE_DATASET_SNAPSHOT
from contexts.task.infrastructure.task_repository import (
    create_task as start_task,
    get_task_record,
    update_task as update_task_status,
)
from contexts.task.infrastructure.worker_task_ops import build_worker_artifacts, mark_worker_started
from shared.infra.worker_process import spawn_worker_process
from shared.utils.path_utils import project_name_from_path, resolve_project_path, resolve_storage_path
from shared.utils.time_utils import now_iso

logger = logging.getLogger(__name__)


def start_dataset_snapshot_task(
    *,
    project_path: str,
    dataset_root: str,
    dataset_name: str,
    mode: str,
    reason: str = "manual_publish",
    source_version_id: str | None = None,
) -> str:
    """创建一条 dataset_snapshot 任务并启动 worker；返回 task_id。"""
    project_path = resolve_project_path(project_path)
    dataset_root = resolve_storage_path(dataset_root)
    if mode not in ("add", "commit"):
        raise ValueError(f"不支持的 mode: {mode}")
    if not dataset_root or not os.path.isdir(dataset_root):
        raise ValueError("数据集目录不存在，无法执行快照任务")

    # 确保 identity 已建，并把 dataset_id 写入 task / payload，
    # 避免前端按 dataset_id 轮询时拿到空列表。
    identity = ensure_dataset_task_identity(dataset_root)
    dataset_id = identity["dataset_id"]
    is_initial_snapshot = not bool(identity.get("current_version_id"))

    payload = {
        "project_path": project_path,
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "dataset_path": dataset_root,
        "mode": mode,
        "reason": reason,
        "source_version_id": source_version_id or "",
        "is_initial_snapshot": is_initial_snapshot,
    }
    task = start_task(
        project_path=project_path,
        project_name=project_name_from_path(project_path),
        type_=TASK_TYPE_DATASET_SNAPSHOT,
        dataset_name=dataset_name,
        dataset_id=dataset_id,
        dataset_path=dataset_root,
        payload=payload,
        message=f"准备快照：{reason}",
    )
    task_id = task["id"]
    task_dir = get_project_task_dir(project_path, task_id)
    artifacts = build_worker_artifacts(task_dir, "dataset-snapshot-worker.log", "task_worker")
    update_task_status(task_id, artifacts=artifacts)

    try:
        proc, _ = spawn_worker_process(task_id, artifacts["log_path"], "task_worker")
    except Exception as exc:
        update_task_status(
            task_id,
            status="failed",
            error=str(exc),
            message="快照进程启动失败",
            finished_at=now_iso(),
        )
        raise ValueError(f"启动快照进程失败: {exc}")

    update_task_status(
        task_id,
        started_at=now_iso(),
        status="running",
        message=f"DVC {mode} 进行中",
    )
    mark_worker_started(task_id, proc.pid, "task_worker")
    return task_id


def get_dataset_snapshot_task(task_id: str):
    """读取快照任务快照（任务中心的标准视图）。"""
    return get_task_record(task_id)
