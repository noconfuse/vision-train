"""负责任务记录与任务历史的数据库读写。"""

import logging
import uuid

from sqlalchemy import or_

from db import session_scope
from db.models import Task, TaskHistory
from shared.utils.time_utils import now_iso
from protocols.task_status import ACTIVE_TASK_STATUSES, TASK_STATUS_ACTIVE, TASK_STATUS_INTERRUPTED, TASK_STATUS_PENDING, TASK_STATUS_RUNNING, TASK_STATUS_STOPPING

logger = logging.getLogger(__name__)


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


def list_task_records(**filters):
    """按过滤条件查询任务记录列表。"""
    project_path = filters.get("project_path")
    type_ = filters.get("type_")
    dataset_id = filters.get("dataset_id")
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
    """把重启后遗留的活动任务标记为中断。"""
    now = now_iso()
    with session_scope() as session:
        orphans = session.query(Task).filter(
            or_(
                Task.status == TASK_STATUS_PENDING,
                Task.status == TASK_STATUS_RUNNING,
                Task.status == TASK_STATUS_STOPPING,
            )
        ).all()
        count = len(orphans)
        for task in orphans:
            task.status = TASK_STATUS_INTERRUPTED
            task.message = (task.message or "") + " [后端重启中断]"
            task.updated_at = now
            task.finished_at = now
        return count, count
