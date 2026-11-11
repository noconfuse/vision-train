"""提供 GPU 服务器配置的增删改查与连通性预检接口。"""

from flask import Blueprint

from app.http import json_body_endpoint, json_endpoint, param
from contexts.compute.application.compute_service import (
    create_compute_target,
    delete_compute_target,
    list_compute_targets,
    preflight_compute_target,
    update_compute_target,
)
from shared.utils.value_utils import parse_bool

bp = Blueprint("compute", __name__)

bp.add_url_rule(
    "/api/compute_targets",
    view_func=json_endpoint(list_compute_targets),
    methods=["GET"],
)
bp.add_url_rule(
    "/api/compute_targets/create",
    view_func=json_body_endpoint(
        create_compute_target,
        name=param("name", required=True),
        ssh_host=param("ssh_host", required=True),
        remote_workspace=param("remote_workspace", default=""),
        device=param("device", default=""),
        keep_remote_copy=param("keep_remote_copy", default=False, transform=parse_bool),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/compute_targets/update",
    view_func=json_body_endpoint(
        update_compute_target,
        target_id=param("target_id", required=True),
        name=param("name"),
        ssh_host=param("ssh_host"),
        remote_workspace=param("remote_workspace"),
        device=param("device"),
        keep_remote_copy=param("keep_remote_copy", transform=parse_bool),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/compute_targets/delete",
    view_func=json_body_endpoint(
        delete_compute_target,
        target_id=param("target_id", required=True),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/compute_targets/preflight",
    view_func=json_body_endpoint(
        preflight_compute_target,
        target_id=param("target_id", required=True),
    ),
    methods=["POST"],
)
