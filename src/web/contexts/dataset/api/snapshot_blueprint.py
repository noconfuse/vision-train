"""数据集快照任务启动入口。

DVC 入库/提交复用现有任务中心（type=dataset_snapshot），所以只保留 start；
查询、停止、重试全部走 ``/api/task/...``，前端无需新增接口。
"""

from flask import Blueprint

from app.http import json_body_endpoint, param

from contexts.dataset.infrastructure.dataset_versioning import start_snapshot_job

bp = Blueprint("dataset_snapshot", __name__, url_prefix="/api/dataset/snapshot")


def _snapshot_start_body(
    project_path: str = "",
    dataset_root: str = "",
    dataset_name: str = "",
    mode: str = "add",
    reason: str = "manual_publish",
    source_version_id: str = "",
):
    """启动一条 dataset_snapshot 任务，返回 task_id。"""
    if not project_path or not dataset_root:
        raise ValueError("缺少 project_path / dataset_root")
    if mode not in ("add", "commit"):
        raise ValueError("mode 必须为 add 或 commit")
    task_id = start_snapshot_job(
        project_path=project_path,
        dataset_root=dataset_root,
        dataset_name=dataset_name,
        mode=mode,
        reason=reason,
        source_version_id=source_version_id or None,
    )
    return {"task_id": task_id}


snapshot_start = json_body_endpoint(
    _snapshot_start_body,
    project_path=param("project_path", required=True),
    dataset_root=param("dataset_root", required=True),
    dataset_name=param("dataset_name"),
    mode=param("mode"),
    reason=param("reason"),
    source_version_id=param("source_version_id"),
)
bp.add_url_rule("/start", view_func=snapshot_start, methods=["POST"])