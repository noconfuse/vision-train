"""提供模型列表、预训练选项与下载状态接口。"""

from flask import Blueprint, Response, stream_with_context

from app.http import json_error_response, param, query_params, query_params_endpoint
from contexts.model.application.use_cases import (
    list_pretrained_options,
    scan_models,
    stream_pretrained_download,
)
from shared.utils.path_utils import resolve_project_path
from shared.utils.value_utils import require_allowed_text
from protocols.vision_task_type import VISION_TASK_TYPE_SET

bp = Blueprint("model", __name__)
_MODEL_USAGE_SET = {"auto_annotate"}


bp.add_url_rule(
    "/api/models",
    view_func=query_params_endpoint(
        scan_models,
        project_path=param("project_path", transform=resolve_project_path),
        vision_task_type=param(
            "vision_task_type",
            transform=lambda value: require_allowed_text(
                value,
                allowed_values=VISION_TASK_TYPE_SET,
                field_name="vision_task_type",
            ),
        ),
        usage=param(
            "usage",
            transform=lambda value: require_allowed_text(
                value,
                allowed_values=_MODEL_USAGE_SET,
                field_name="usage",
            ),
        ),
    ),
    methods=["GET"],
)
@bp.route("/api/pretrained/prepare", methods=["GET"])
def api_prepare_pretrained():
    """以 SSE 方式推送模型准备实时进度。"""
    name = query_params(name=param("name", required=True, transform=lambda value: str(value).strip()))["name"]
    try:
        headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        }
        return Response(stream_with_context(stream_pretrained_download(name)), headers=headers)
    except ValueError as exc:
        return json_error_response(str(exc), status_code=400)


bp.add_url_rule(
    "/api/pretrained/options",
    view_func=query_params_endpoint(
        list_pretrained_options,
        vision_task_type=param(
            "vision_task_type",
            transform=lambda value: require_allowed_text(
                value,
                allowed_values=VISION_TASK_TYPE_SET,
                field_name="vision_task_type",
            ),
        ),
    ),
    methods=["GET"],
)
