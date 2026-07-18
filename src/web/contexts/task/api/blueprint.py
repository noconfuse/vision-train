"""提供任务查询、详情读取与停止接口。"""

from flask import Blueprint

from app.http import json_endpoint, param, query_params_endpoint
from contexts.task.infrastructure.task_runtime import list_task_items, load_task_item, request_task_stop as stop_task
from shared.utils.path_utils import resolve_project_path

bp = Blueprint("task", __name__)

bp.add_url_rule(
    "/api/tasks",
    view_func=query_params_endpoint(
        list_task_items,
        project_path=param("project_path", transform=resolve_project_path),
        project_name=param("project_name"),
        type_=param("type"),
        dataset_name=param("dataset_name"),
        status=param("status"),
        include_archived=param("include_archived", default=""),
        archived_only=param("archived_only", default=""),
        limit=param("limit", default="200"),
    ),
    methods=["GET"],
)


@bp.route("/api/tasks/<task_id>")
@json_endpoint
def api_task_detail(task_id):
    """返回单个任务详情。"""
    task = load_task_item(task_id)
    if not task:
        raise ValueError("任务不存在")
    return task

bp.add_url_rule("/api/tasks/<task_id>/stop", view_func=json_endpoint(stop_task), methods=["POST"])
