"""计算资源域门面：GPU 服务器配置、预检，以及给训练域用的远端执行原语。

界面上填的那条 `compute_targets` 记录就是唯一事实源：这里不读环境变量，也不给字段
兜默认值（只有远端工作目录留空时用表列自身的默认值）。
"""

from contexts.compute.domain.errors import RemoteExecutionError
from contexts.compute.domain.target_rules import normalize_target_fields
from contexts.compute.infrastructure import remote_shell
from contexts.compute.infrastructure.preflight import require_preflight_passed, run_preflight
from contexts.compute.infrastructure.target_repository import (
    create_target,
    delete_target,
    get_target,
    list_targets,
    require_target,
    update_target,
)
from protocols.task_status import TASK_STATUS_ACTIVE

__all__ = [
    "RemoteExecutionError",
    "build_detached_script",
    "copy_file_to_remote",
    "delete_compute_target",
    "get_compute_target",
    "list_compute_targets",
    "preflight_compute_target",
    "remote_check",
    "remote_kill",
    "remote_mkdir",
    "remote_pid_alive",
    "remote_remove",
    "remote_run",
    "remote_start_detached",
    "remote_tail",
    "remote_touch",
    "remote_write_text",
    "require_compute_target",
    "require_remote_ready",
    "sync_from_remote",
    "sync_to_remote",
    "update_compute_target",
]

build_detached_script = remote_shell.build_detached_script
copy_file_to_remote = remote_shell.copy_file_to_remote
remote_check = remote_shell.remote_check
remote_kill = remote_shell.remote_kill
remote_mkdir = remote_shell.remote_mkdir
remote_pid_alive = remote_shell.remote_pid_alive
remote_remove = remote_shell.remote_remove
remote_run = remote_shell.remote_run
remote_start_detached = remote_shell.remote_start_detached
remote_tail = remote_shell.remote_tail
remote_touch = remote_shell.remote_touch
remote_write_text = remote_shell.remote_write_text
sync_from_remote = remote_shell.sync_from_remote
sync_to_remote = remote_shell.sync_to_remote


def list_compute_targets():
    """返回全部已配置的 GPU 服务器。"""
    return list_targets()


def get_compute_target(target_id):
    """按 id 返回一台 GPU 服务器，不存在返回 None。"""
    return get_target(target_id)


def require_compute_target(target_id):
    """按 id 取一台必须存在的 GPU 服务器。"""
    return require_target(target_id)


def create_compute_target(name, ssh_host, remote_workspace=None, device=None, keep_remote_copy=False):
    """新增一台 GPU 服务器；工作目录和卡号留空就用表列的默认写法。"""
    fields = normalize_target_fields(
        name=name,
        ssh_host=ssh_host,
        remote_workspace=remote_workspace or "",
        device=device or "",
        keep_remote_copy=keep_remote_copy,
    )
    _require_unique_name(fields["name"])
    return create_target(**fields)


def update_compute_target(target_id, name=None, ssh_host=None, remote_workspace=None, device=None, keep_remote_copy=None):
    """修改一台 GPU 服务器；只改传上来的字段。"""
    require_target(target_id)
    patch = normalize_target_fields(
        name=name,
        ssh_host=ssh_host,
        remote_workspace=remote_workspace,
        device=device,
        keep_remote_copy=keep_remote_copy,
    )
    if "name" in patch:
        _require_unique_name(patch["name"], exclude_target_id=target_id)
    if not patch:
        raise ValueError("没有需要修改的内容")
    return update_target(target_id, patch)


def delete_compute_target(target_id):
    """删除一台 GPU 服务器；还有训练在它上面跑就不让删。"""
    target = require_target(target_id)
    running = _running_task_ids(target_id)
    if running:
        raise ValueError(
            f"{target['name']} 上还有 {len(running)} 个训练在跑（任务 {running[0]} 等），先停止后再删除"
        )
    delete_target(target_id)
    return {"deleted": True, "target_id": target_id}


def preflight_compute_target(target_id):
    """检查一台 GPU 服务器能否直接开始训练，返回逐项结果。"""
    return run_preflight(require_target(target_id))


def require_remote_ready(target_id):
    """训练启动前的硬门：预检不过就带着全部原因失败，通过则返回逐项结果。"""
    return require_preflight_passed(require_target(target_id))


def _require_unique_name(name, exclude_target_id=None):
    """服务器名称查重。"""
    for existing in list_targets():
        if existing["name"] != name:
            continue
        if exclude_target_id and existing["id"] == exclude_target_id:
            continue
        raise ValueError(f"已有一台叫「{name}」的 GPU 服务器，请换个名称")


def _running_task_ids(target_id):
    """列出还在这台服务器上跑的任务 id。"""
    from contexts.task.application.task_service import list_task_records

    return [
        task.get("id")
        for task in list_task_records(status=TASK_STATUS_ACTIVE, include_archived=True, limit=1000)
        if str((task.get("payload") or {}).get("compute_target_id") or "") == str(target_id)
    ]
