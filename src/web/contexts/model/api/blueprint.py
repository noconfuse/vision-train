"""提供模型列表、预训练选项与下载状态接口。"""

from flask import Blueprint

from app.http import json_body_endpoint, json_endpoint, param, query_params_endpoint
from contexts.model.infrastructure.model_gateway import (
    download_pretrained,
    get_pretrained_status,
    list_pretrained_options,
    scan_models,
)
from shared.utils.path_utils import resolve_project_path

bp = Blueprint("model", __name__)


bp.add_url_rule(
    "/api/models",
    view_func=query_params_endpoint(
        scan_models,
        project_path=param("project_path", transform=resolve_project_path),
    ),
    methods=["GET"],
)
bp.add_url_rule(
    "/api/pretrained/download",
    view_func=json_body_endpoint(
        download_pretrained,
        name=param("name", required=True, transform=lambda value: str(value).strip()),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/pretrained/status",
    view_func=query_params_endpoint(
        get_pretrained_status,
        name=param("name", required=True, transform=lambda value: str(value).strip()),
    ),
    methods=["GET"],
)
bp.add_url_rule("/api/pretrained/options", view_func=json_endpoint(list_pretrained_options), methods=["GET"])
