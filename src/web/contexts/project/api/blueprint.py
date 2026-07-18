"""提供项目列表、创建、更新、删除与名称校验接口。"""

from flask import Blueprint

from app.http import json_body_endpoint, json_endpoint, param
from contexts.project.application.use_cases import (
    create_project,
    delete_project,
    list_projects,
    update_project,
    validate_project_name_availability,
)
from shared.utils.value_utils import parse_bool

bp = Blueprint("project", __name__)


bp.add_url_rule(
    "/api/project/create",
    view_func=json_body_endpoint(
        create_project,
        name=param("name", required=True, transform=lambda value: str(value).strip()),
        description=param("description", default="", transform=lambda value: str(value).strip()),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/project/update",
    view_func=json_body_endpoint(
        update_project,
        name=param("name", required=True, transform=lambda value: str(value).strip()),
        description=param("description"),
        new_name=param(
            "new_name",
            transform=lambda value: (str(value).strip() or None) if value is not None else None,
        ),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/project/delete",
    view_func=json_body_endpoint(
        delete_project,
        name=param("name", required=True, transform=lambda value: str(value).strip()),
        confirm=param("confirm", default=False, transform=parse_bool),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/project/validate_name",
    view_func=json_body_endpoint(
        validate_project_name_availability,
        name=param("name", required=True, transform=lambda value: str(value).strip()),
    ),
    methods=["POST"],
)
bp.add_url_rule("/api/projects", view_func=json_endpoint(list_projects), methods=["GET"])
