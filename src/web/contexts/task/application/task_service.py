"""任务上下文的跨域用例门面。

其他上下文只能通过本模块访问任务的创建、状态更新、worker 生命周期与展示结构，
不得直接引用 `contexts.task.domain` 或 `contexts.task.infrastructure`。
"""

from contexts.task.infrastructure.task_repository import (
    append_task_history,
    create_task,
    delete_task,
    get_task_history,
    get_task_record,
    list_task_records,
    mark_orphan_tasks_interrupted,
    merge_task_artifacts,
    new_workflow_id,
    update_task,
)
from contexts.task.infrastructure.task_runtime import (
    list_project_tasks,
    list_task_items,
    list_tasks,
    load_task,
    load_task_item,
    reconcile_worker_task,
    request_task_stop,
)
from contexts.task.infrastructure.worker_task_ops import (
    build_worker_artifacts,
    finish_worker_task,
    is_stop_requested,
    list_task_storage_paths,
    mark_worker_exited,
    mark_worker_started,
    request_stop,
    update_worker_task_progress,
)
from contexts.task.presenters import present_task, present_tasks

__all__ = [
    "append_task_history",
    "build_worker_artifacts",
    "create_task",
    "delete_task",
    "finish_worker_task",
    "get_task_history",
    "get_task_record",
    "is_stop_requested",
    "list_project_tasks",
    "list_task_items",
    "list_task_records",
    "list_task_storage_paths",
    "list_tasks",
    "load_task",
    "load_task_item",
    "mark_orphan_tasks_interrupted",
    "mark_worker_exited",
    "mark_worker_started",
    "merge_task_artifacts",
    "new_workflow_id",
    "present_task",
    "present_tasks",
    "reconcile_worker_task",
    "request_stop",
    "request_task_stop",
    "update_task",
    "update_worker_task_progress",
]
