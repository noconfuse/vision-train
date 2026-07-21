"""读写训练工作流记录并聚合关联任务视图。"""

from db import session_scope
from db.models import Task, WorkflowRecord
from contexts.task.domain.task_types import TRAINING_TASK_TYPES
from contexts.task.infrastructure.task_repository import new_workflow_id
from contexts.task.infrastructure.task_runtime import list_project_tasks
from contexts.training.domain.training_constants import WORKFLOW_TYPE_TRAINING
from contexts.task.infrastructure.worker_task_ops import list_task_storage_paths
from contexts.dataset.infrastructure.dataset_task_type import load_dataset_vision_task_type
from shared.utils.fs_utils import remove_tree
from shared.utils.path_utils import project_name_from_path
from shared.utils.time_utils import now_iso
from shared.utils.value_utils import require_present
from protocols.vision_task_type import VISION_TASK_TYPE_SET
from protocols.task_status import is_active_task_status
from contexts.training.infrastructure.workflow_state import build_training_workflow
from contexts.training.presenters import present_training_workflow, present_training_workflow_record


def require_workflow_vision_task_type(value):
    """校验训练工作流记录中的任务类型。"""
    if value not in VISION_TASK_TYPE_SET:
        raise ValueError("训练工作流缺少合法的 vision_task_type")
    return value

def get_training_workflow_record(workflow_id, include_archived=False):
    """读取单个训练工作流记录。"""
    if not workflow_id:
        return None
    with session_scope() as session:
        workflow = session.get(WorkflowRecord, workflow_id)
        if not workflow or workflow.type != WORKFLOW_TYPE_TRAINING:
            return None
        if workflow.archived_at and not include_archived:
            return None
        return workflow.to_dict()


def create_training_workflow_record(project_path, dataset_name, dataset_path=None, workflow_id=None, vision_task_type=None):
    """创建一条训练工作流记录。"""
    require_present(project_path=project_path, dataset_name=dataset_name)
    workflow_id = workflow_id or new_workflow_id()
    existing = get_training_workflow_record(workflow_id, include_archived=True)
    if existing:
        return present_training_workflow_record(existing)
    resolved_vision_task_type = require_workflow_vision_task_type(
        vision_task_type if vision_task_type is not None else load_dataset_vision_task_type(dataset_path) if dataset_path else None
    )
    now = now_iso()
    workflow = WorkflowRecord(
        id=workflow_id,
        type=WORKFLOW_TYPE_TRAINING,
        project_path=project_path,
        project_name=project_name_from_path(project_path),
        dataset_name=dataset_name,
        dataset_path=dataset_path,
        vision_task_type=resolved_vision_task_type,
        created_at=now,
        updated_at=now,
    )
    with session_scope() as session:
        session.add(workflow)
        session.flush()
        return present_training_workflow_record(workflow.to_dict())


def ensure_training_workflow_record(
    workflow_id,
    project_path,
    dataset_name,
    dataset_path=None,
    vision_task_type=None,
):
    """确保指定训练工作流记录存在。"""
    existing = get_training_workflow_record(workflow_id, include_archived=True)
    if existing:
        if existing.get("vision_task_type"):
            return present_training_workflow_record(existing)
        return touch_training_workflow_record(
            workflow_id,
            vision_task_type=require_workflow_vision_task_type(
                vision_task_type if vision_task_type is not None else load_dataset_vision_task_type(dataset_path) if dataset_path else None
            ),
        ) or present_training_workflow_record(existing)
    return create_training_workflow_record(
        project_path,
        dataset_name,
        dataset_path=dataset_path,
        workflow_id=workflow_id,
        vision_task_type=vision_task_type,
    )


def touch_training_workflow_record(workflow_id, **patch):
    """更新训练工作流记录的补丁字段和更新时间。"""
    if not workflow_id:
        return None
    with session_scope() as session:
        workflow = session.get(WorkflowRecord, workflow_id)
        if not workflow or workflow.type != WORKFLOW_TYPE_TRAINING:
            return None
        for key, value in patch.items():
            if hasattr(workflow, key) and value is not None:
                setattr(workflow, key, value)
        workflow.updated_at = now_iso()
        session.flush()
        return present_training_workflow_record(workflow.to_dict())


def list_training_workflow_tasks(project_path, dataset_name=None, workflow_id=None, include_archived=True):
    """列出训练工作流相关的任务记录。"""
    items = list_project_tasks(
        project_path,
        dataset_name=dataset_name,
        limit=1000,
        include_archived=include_archived,
    )
    items = [task for task in items if task.get("type") in TRAINING_TASK_TYPES]
    if workflow_id:
        items = [task for task in items if task.get("workflow_id") == workflow_id]
    return items


def list_training_workflows(project_path, dataset_name=None, include_archived=False, archived_only=False):
    """查询项目下的训练工作流列表并聚合任务摘要。"""
    require_present("缺少项目路径", project_path=project_path)
    with session_scope() as session:
        query = session.query(WorkflowRecord).filter(
            WorkflowRecord.project_path == project_path,
            WorkflowRecord.type == WORKFLOW_TYPE_TRAINING,
        )
        if dataset_name:
            query = query.filter(WorkflowRecord.dataset_name == dataset_name)
        if archived_only:
            query = query.filter(WorkflowRecord.archived_at.is_not(None))
        elif not include_archived:
            query = query.filter(WorkflowRecord.archived_at.is_(None))
        records = [item.to_dict() for item in query.order_by(WorkflowRecord.updated_at.desc()).all()]
    if not records:
        return []
    items = list_training_workflow_tasks(project_path=project_path, dataset_name=dataset_name, include_archived=True)
    grouped = {}
    for task in items:
        workflow_id = task.get("workflow_id")
        if workflow_id:
            grouped.setdefault(workflow_id, []).append(task)
    workflows = [present_training_workflow(build_training_workflow(record, grouped.get(record["id"], []))) for record in records]
    workflows.sort(key=lambda item: item.get("updated_at") or "", reverse=True)
    return workflows


def get_training_workflow(project_path, workflow_id, dataset_name=None, include_archived=False):
    """获取单个训练工作流的聚合详情。"""
    require_present(project_path=project_path, workflow_id=workflow_id)
    workflow_record = get_training_workflow_record(workflow_id, include_archived=include_archived)
    if not workflow_record or workflow_record.get("project_path") != project_path:
        raise ValueError("工作流不存在")
    if dataset_name and workflow_record.get("dataset_name") != dataset_name:
        raise ValueError("工作流不存在")
    items = list_training_workflow_tasks(
        project_path=project_path,
        dataset_name=dataset_name,
        workflow_id=workflow_id,
        include_archived=True,
    )
    return present_training_workflow(build_training_workflow(workflow_record, items))


def archive_training_workflow(project_path, workflow_id):
    """归档一个没有活动任务的训练工作流。"""
    require_present(project_path=project_path, workflow_id=workflow_id)
    workflow = get_training_workflow_record(workflow_id, include_archived=True)
    if not workflow or workflow.get("project_path") != project_path:
        raise ValueError("工作流不存在")
    tasks = list_training_workflow_tasks(project_path=project_path, workflow_id=workflow_id)
    if any(is_active_task_status(task.get("status")) for task in tasks):
        raise ValueError("工作流存在进行中的任务，请先停止后再归档")
    if workflow.get("archived_at"):
        return workflow
    return touch_training_workflow_record(workflow_id, archived_at=now_iso())


def restore_training_workflow(project_path, workflow_id):
    """恢复一个已归档的训练工作流。"""
    require_present(project_path=project_path, workflow_id=workflow_id)
    workflow = get_training_workflow_record(workflow_id, include_archived=True)
    if not workflow or workflow.get("project_path") != project_path:
        raise ValueError("工作流不存在")
    if not workflow.get("archived_at"):
        return workflow
    with session_scope() as session:
        workflow_row = session.get(WorkflowRecord, workflow_id)
        if not workflow_row or workflow_row.type != WORKFLOW_TYPE_TRAINING:
            raise ValueError("工作流不存在")
        workflow_row.archived_at = None
        workflow_row.updated_at = now_iso()
        session.flush()
        return present_training_workflow_record(workflow_row.to_dict())


def delete_training_task_artifacts(task_dict):
    """删除工作流内任务关联的目录产物。"""
    removed = []
    for path in list_task_storage_paths(task_dict):
        if path:
            remove_tree(path)
            removed.append(path)
    return removed


def delete_training_workflow(project_path, workflow_id):
    """永久删除一个已归档训练工作流及其任务产物。"""
    require_present(project_path=project_path, workflow_id=workflow_id)
    workflow = get_training_workflow_record(workflow_id, include_archived=True)
    if not workflow or workflow.get("project_path") != project_path:
        raise ValueError("工作流不存在")
    if not workflow.get("archived_at"):
        raise ValueError("请先归档工作流，再执行永久删除")
    task_items = list_training_workflow_tasks(
        project_path=project_path,
        dataset_name=workflow.get("dataset_name"),
        workflow_id=workflow_id,
        include_archived=True,
    )
    if any(is_active_task_status(task.get("status")) for task in task_items):
        raise ValueError("工作流存在进行中的任务，请先停止后再删除")
    removed_paths = []
    removed_set = set()
    with session_scope() as session:
        db_tasks = session.query(Task).filter(Task.workflow_id == workflow_id).all()
        for task in db_tasks:
            for path in delete_training_task_artifacts(task.to_dict()):
                if path not in removed_set:
                    removed_set.add(path)
                    removed_paths.append(path)
            session.delete(task)
        workflow_row = session.get(WorkflowRecord, workflow_id)
        if workflow_row:
            session.delete(workflow_row)
    return {
        "deleted": workflow_id,
        "removed_task_ids": [task.get("id") for task in task_items],
        "removed_paths": removed_paths,
    }
