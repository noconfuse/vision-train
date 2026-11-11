"""负责任务记录与任务历史的数据库读写。"""

import logging
import uuid
from datetime import datetime, timedelta

from sqlalchemy import or_

from db import session_scope
from db.models import Task, TaskHistory
from shared.utils.time_utils import now_iso
from protocols.task_status import ACTIVE_TASK_STATUSES, TASK_STATUS_ACTIVE, TASK_STATUS_INTERRUPTED, TASK_STATUS_PENDING, TASK_STATUS_RUNNING, TASK_STATUS_STOPPING

logger = logging.getLogger(__name__)

# 刚更新过的活动任务先不动：worker 还没来得及写 pid，或者另一个实例正在推它
ORPHAN_QUIET_SECONDS = 300


def new_workflow_id():
    """生成短格式 workflow 标识。"""
    return uuid.uuid4().hex[:12]


def create_task(
    project_path,
    project_name,
    type_,
    dataset_name=None,
    dataset_id=None,
    dataset_version_id=None,
    dataset_path=None,
    vision_task_type=None,
    payload=None,
    message=None,
    artifacts=None,
):
    """创建一条新的任务记录。"""
    now = now_iso()
    task = Task(
        type=type_,
        project_path=project_path,
        project_name=project_name,
        dataset_name=dataset_name,
        dataset_id=dataset_id,
        dataset_version_id=dataset_version_id,
        dataset_path=dataset_path,
        vision_task_type=vision_task_type,
        status=TASK_STATUS_PENDING,
        progress=0,
        message=message or f"已创建{type_}任务",
        payload=payload or {},
        artifacts=artifacts or {},
        log_text="",
        created_at=now,
        updated_at=now,
    )
    with session_scope() as session:
        session.add(task)
        session.flush()
        snapshot = task.to_dict()
    return snapshot


def update_task(task_id, **patch):
    """按补丁更新任务记录。"""
    with session_scope() as session:
        task = session.get(Task, task_id)
        if not task:
            logger.warning("update: task %s 不存在", task_id)
            return None
        for key, value in patch.items():
            if hasattr(task, key):
                setattr(task, key, value)
        task.updated_at = now_iso()
        session.flush()
        return task.to_dict()


def get_task_record(task_id):
    """读取单个任务记录。"""
    with session_scope() as session:
        task = session.get(Task, task_id)
        return task.to_dict() if task else None


_TASK_FILTERS = (
    "project_path",
    "project_name",
    "type_",
    "dataset_id",
    "dataset_name",
    "dataset_version_id",
    "status",
    "limit",
    "include_archived",
    "archived_only",
)


def list_task_records(**filters):
    """按过滤条件查询任务记录；认不出的条件直接报错，不能让它在静默失效后放大结果集。"""
    unknown = sorted(key for key in filters if key not in _TASK_FILTERS)
    if unknown:
        raise ValueError(f"list_task_records 不支持这些过滤条件：{unknown}")
    project_path = filters.get("project_path")
    type_ = filters.get("type_")
    dataset_id = filters.get("dataset_id")
    dataset_name = filters.get("dataset_name")
    dataset_version_id = filters.get("dataset_version_id")
    status = filters.get("status")
    project_name = filters.get("project_name")
    limit = filters.get("limit", 200)
    include_archived = filters.get("include_archived", False)
    archived_only = filters.get("archived_only", False)
    with session_scope() as session:
        query = session.query(Task)
        if project_path:
            query = query.filter(Task.project_path == project_path)
        if project_name:
            query = query.filter(Task.project_name == project_name)
        if type_:
            query = query.filter(Task.type == type_)
        if dataset_id:
            query = query.filter(Task.dataset_id == dataset_id)
        if dataset_name:
            query = query.filter(Task.dataset_name == dataset_name)
        if dataset_version_id:
            query = query.filter(Task.dataset_version_id == dataset_version_id)
        if status:
            if status == TASK_STATUS_ACTIVE:
                query = query.filter(Task.status.in_(ACTIVE_TASK_STATUSES))
            else:
                query = query.filter(Task.status == status)
        if archived_only:
            query = query.filter(Task.archived_at.is_not(None))
        elif not include_archived:
            query = query.filter(Task.archived_at.is_(None))
        query = query.order_by(Task.created_at.desc()).limit(limit)
        return [task.to_dict() for task in query.all()]


def merge_task_artifacts(task_id, patch):
    """合并并回写任务 artifacts 字段。"""
    task = get_task_record(task_id)
    if not task:
        return None
    artifacts = dict(task.get("artifacts") or {})
    artifacts.update(patch)
    return update_task(task_id, artifacts=artifacts)


def get_task_history(task_id):
    """读取任务训练历史曲线数据。"""
    with session_scope() as session:
        query = session.query(TaskHistory).filter(TaskHistory.task_id == task_id).order_by(TaskHistory.epoch)
        return [item.to_dict() for item in query.all()]


def append_task_history(task_id, epoch, box_loss=None, cls_loss=None, dfl_loss=None, map50=None, map50_95=None, extra=None):
    """追加一条任务历史指标记录。"""
    with session_scope() as session:
        history = TaskHistory(
            task_id=task_id,
            epoch=epoch,
            box_loss=box_loss,
            cls_loss=cls_loss,
            dfl_loss=dfl_loss,
            map50=map50,
            map50_95=map50_95,
            extra_json=extra,
        )
        session.add(history)


def delete_task(task_id):
    """删除单个任务记录。"""
    with session_scope() as session:
        task = session.get(Task, task_id)
        if not task:
            return None
        result = task.to_dict()
        session.delete(task)
        return result


def mark_orphan_tasks_interrupted():
    """启动时回收重启遗留的活动任务：有活 worker 认领的、刚刚还在动的都不碰。

    多个后端实例共用一个库时，别的实例正在跑的任务在本地看也只是一条活动任务，
    无条件判死会把别人跑得正欢的训练扫成 interrupted。worker 的 pid 加上命令行里的
    task_id 是唯一能证明「确实有人在跑」的证据；安静期留给刚创建、还没写出 pid 的任务，
    它们归创建它们的实例自己管，下一次启动再判。
    """
    from contexts.task.infrastructure.task_runtime import is_worker_alive

    now = now_iso()
    reclaimed = 0
    spared = 0
    with session_scope() as session:
        orphans = session.query(Task).filter(
            or_(
                Task.status == TASK_STATUS_PENDING,
                Task.status == TASK_STATUS_RUNNING,
                Task.status == TASK_STATUS_STOPPING,
            )
        ).all()
        for task in orphans:
            if is_worker_alive(task.to_dict()) is True or _recently_active(task.updated_at):
                spared += 1
                continue
            task.status = TASK_STATUS_INTERRUPTED
            task.message = (task.message or "") + " [后端重启中断]"
            task.updated_at = now
            task.finished_at = now
            reclaimed += 1
    if spared:
        logger.info("启动回收跳过 %s 个活动任务：活 worker 认领或还在安静期内", spared)
    return reclaimed, reclaimed


def _recently_active(updated_at):
    """距上次更新不足安静期的任务算「还有人在管」，时间解析不出来就算旧。"""
    try:
        updated = datetime.fromisoformat(str(updated_at))
    except (TypeError, ValueError):
        return False
    return updated > datetime.now() - timedelta(seconds=ORPHAN_QUIET_SECONDS)
