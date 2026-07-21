"""暴露标注与自动标注相关 HTTP 接口。"""

from flask import Blueprint

from app.http import json_body_endpoint, param, query_params_endpoint
from contexts.annotation.application.use_cases import (
    commit_auto_annotation,
    get_annotation_payload,
    list_missing_annotations,
    list_pending_auto_annotations,
    save_auto_annotation,
    save_manual_annotation,
    auto_annotate_image,
    get_batch_auto_annotation_status,
    start_batch_auto_annotation,
)
from shared.utils.path_utils import resolve_project_path

bp = Blueprint("annotation", __name__)


bp.add_url_rule(
    "/api/annotation/missing",
    view_func=query_params_endpoint(
        list_missing_annotations,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
        split=param("split", default="train"),
        offset=param("offset", default="0", transform=int),
        limit=param("limit", default="50", transform=int),
    ),
    methods=["GET"],
)
bp.add_url_rule(
    "/api/auto_annotate",
    view_func=json_body_endpoint(
        auto_annotate_image,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        image_ref=param("image_path", required=True),
        model_path=param("model_path", required=True, required_message="自动标注必须显式选择模型"),
        conf=param("conf", default=0.25),
        max_det=param("max_det", default=200),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/auto_annotate/batch",
    view_func=json_body_endpoint(
        start_batch_auto_annotation,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
        split=param("split", default="train"),
        model_path=param("model_path", required=True, required_message="自动标注必须显式选择模型"),
        image_paths=param("image_paths", default=list),
        conf=param("conf", default=0.25),
        max_det=param("max_det", default=200),
        batch_size=param("batch_size", default=1),
        iou_thresh=param("iou_thresh", default=0.5),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/annotation/pending",
    view_func=query_params_endpoint(
        list_pending_auto_annotations,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
        split=param("split", default="train"),
        offset=param("offset", default="0", transform=int),
        limit=param("limit", default="50", transform=int),
    ),
    methods=["GET"],
)
bp.add_url_rule(
    "/api/annotation/save",
    view_func=json_body_endpoint(
        save_manual_annotation,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
        split=param("split", default="train"),
        image_ref=param("image_path", required=True),
        annotation=param("annotation", default=dict),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/annotation/get",
    view_func=query_params_endpoint(
        get_annotation_payload,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
        split=param("split", default="train"),
        image_ref=param("image_path", required=True),
    ),
    methods=["GET"],
)
bp.add_url_rule(
    "/api/annotation/commit",
    view_func=json_body_endpoint(
        commit_auto_annotation,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
        split=param("split", default="train"),
        image_ref=param("image_path", required=True),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/annotation/save_auto",
    view_func=json_body_endpoint(
        save_auto_annotation,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
        split=param("split", default="train"),
        image_ref=param("image_path", required=True),
        annotation=param("annotation", default=dict),
    ),
    methods=["POST"],
)


bp.add_url_rule(
    "/api/auto_annotate/batch/status",
    view_func=query_params_endpoint(
        get_batch_auto_annotation_status,
        task_id=param("task_id", required=True),
    ),
    methods=["GET"],
)
