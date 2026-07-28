"""负责任务读取、worker 对账与停止流程。"""

import os

from contexts.task.domain.task_artifact_keys import (
    ARTIFACT_LOG_PATH,
    ARTIFACT_STOP_SIGNAL_PATH,
    ARTIFACT_WORKER_EXITED_AT,
    ARTIFACT_WORKER_MODULE_NAME,
    ARTIFACT_WORKER_PID,
)
from contexts.task.domain.task_types import TASK_TYPE_TRAINING
from contexts.task.presenters import present_task, present_tasks
from contexts.task.infrastructure.worker_task_ops import request_stop as write_stop_signal
from shared.infra.worker_process import get_process_command, is_process_alive
from shared.utils.fs_utils import remove_file_silent
from shared.utils.path_utils import resolve_project_path
from shared.utils.time_utils import now_iso
from shared.utils.value_utils import parse_bool
from protocols.task_status import TASK_STATUS_FAILED, TASK_STATUS_STOPPED, TASK_STATUS_STOPPING, is_active_task_status

from contexts.task.infrastructure.task_repository import get_task_record, update_task


def _read_log_tail(log_path, max_bytes=4000):
    """读取任务日志尾部用于错误诊断。"""
    if not log_path or not os.path.isfile(log_path):
        return ""
    try:
        with open(log_path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes), os.SEEK_SET)
            text = handle.read().decode("utf-8", errors="replace")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines[-20:])
    except Exception:
        return ""


def attach_training_resume_info(task_dict):
    """为训练任务补充可恢复训练信息。"""
    if not task_dict or task_dict.get("type") != TASK_TYPE_TRAINING:
        return task_dict
    task_dict = dict(task_dict)
    from contexts.training.infrastructure.training_artifacts import resolve_training_resume_weight

    weight_name, weight_path = resolve_training_resume_weight(task_dict.get("artifacts") or {})
    task_dict["resume_available"] = bool(weight_path)
    task_dict["resume_weight"] = weight_name or ""
    return task_dict


def is_worker_alive(task_dict):
    """根据 PID 和命令行判断 worker 是否仍存活。"""
    artifacts = task_dict.get("artifacts") or {}
    worker_pid = artifacts.get(ARTIFACT_WORKER_PID)
    if not worker_pid:
        return None
    try:
        worker_pid = int(worker_pid)
    except (TypeError, ValueError):
        return False
    if not is_process_alive(worker_pid):
        return False
    cmdline = get_process_command(worker_pid)
    if not cmdline:
        return True
    worker_module_name = artifacts.get(ARTIFACT_WORKER_MODULE_NAME)
    if worker_module_name and worker_module_name not in cmdline:
        return False
    if task_dict.get("id") not in cmdline:
        return False
    return True


def reconcile_worker_task(task_dict):
    """对账任务状态与实际 worker 存活状态。"""
    if not task_dict:
        return task_dict
    if not is_active_task_status(task_dict.get("status")):
        return attach_training_resume_info(task_dict)

    artifacts = dict(task_dict.get("artifacts") or {})
    if not artifacts.get(ARTIFACT_WORKER_PID):
        return attach_training_resume_info(task_dict)

    worker_state = is_worker_alive(task_dict)
    if worker_state in (True, None):
        return attach_training_resume_info(task_dict)

    stop_signal_path = artifacts.get(ARTIFACT_STOP_SIGNAL_PATH)
    log_path = artifacts.get(ARTIFACT_LOG_PATH)
    log_tail = _read_log_tail(log_path)
    now = now_iso()
    artifacts[ARTIFACT_WORKER_PID] = None
    artifacts[ARTIFACT_WORKER_EXITED_AT] = now

    if stop_signal_path and os.path.exists(stop_signal_path):
        remove_file_silent(stop_signal_path)
        patched = update_task(
            task_dict["id"],
            status=TASK_STATUS_STOPPED,
            message=f'{task_dict.get("type") or "任务"}进程已退出，停止请求已生效',
            finished_at=now,
            artifacts=artifacts,
        )
    else:
        error = f'{task_dict.get("type") or "任务"} worker 进程异常退出'
        if log_tail:
            error = f"{error}\n\n最近日志:\n{log_tail}"
        patched = update_task(
            task_dict["id"],
            status=TASK_STATUS_FAILED,
            error=error,
            message="任务进程异常退出",
            finished_at=now,
            artifacts=artifacts,
        )
    return attach_training_resume_info(patched or task_dict)


def load_task(task_id):
    """读取任务并同步修正其运行状态。"""
    return reconcile_worker_task(get_task_record(task_id))


def load_task_item(task_id):
    """读取单个任务的对外展示结构。"""
    return present_task(load_task(task_id))


def list_tasks(**filters):
    """返回完成对账后的任务列表。"""
    from contexts.task.infrastructure.task_repository import list_task_records
    from protocols.task_status import TASK_STATUS_ACTIVE

    items = [reconcile_worker_task(item) for item in list_task_records(**filters)]
    status = filters.get("status")
    if status == TASK_STATUS_ACTIVE:
        return [item for item in items if is_active_task_status(item.get("status"))]
    if status:
        return [item for item in items if item.get("status") == status]
    return items


def list_task_items(
    *,
    project_path=None,
    project_name=None,
    type_=None,
    dataset_id=None,
    dataset_name=None,
    status=None,
    include_archived=False,
    archived_only=False,
    limit=200,
):
    """按接口查询语义返回任务列表。"""
    project_path = resolve_project_path(project_path) if project_path else project_path
    normalized_status = str(status or "").strip()
    if normalized_status.lower() == "active":
        normalized_status = "active"
    try:
        limit_value = int(limit or 200)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit 参数无效") from exc
    return present_tasks(
        list_tasks(
        project_path=project_path,
        project_name=project_name,
        type_=type_,
        dataset_id=dataset_id,
        dataset_name=dataset_name,
        status=normalized_status,
        include_archived=parse_bool(include_archived),
        archived_only=parse_bool(archived_only),
        limit=limit_value,
        )
    )


def list_project_tasks(project_path, **filters):
    """按项目路径查询任务。"""
    # 注意：调用方可能传入“已经通过 resolve_and_validate_project 解析过的绝对路径”，
    # 不能再走 resolve_project_path，否则 os.path.abspath 会把尾部斜杠去掉，
    # 与 DB 里存的 project_path 字符串对不上。
    if project_path and not os.path.isabs(project_path):
        project_path = resolve_project_path(project_path)
    return list_tasks(project_path=project_path, **filters)
def request_task_stop(task_id):
    """为活动任务写入停止信号。"""
    task = load_task(task_id)
    if not task:
        raise ValueError(f"任务 {task_id} 不存在")
    if not is_active_task_status(task.get("status")):
        raise ValueError("任务未在运行中，无需停止")
    stop_signal_path = (task.get("artifacts") or {}).get(ARTIFACT_STOP_SIGNAL_PATH)
    if not stop_signal_path:
        raise ValueError(f"任务 {task_id} 缺少停止信号路径")
    if task.get("status") == TASK_STATUS_STOPPING:
        return {"task_id": task_id, "stop_requested": True}
    write_stop_signal(stop_signal_path)
    update_task(task_id, status=TASK_STATUS_STOPPING, message="已发送停止请求，等待任务安全退出...")
    return {"task_id": task_id, "stop_requested": True}
