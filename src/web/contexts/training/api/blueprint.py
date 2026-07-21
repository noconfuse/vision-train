"""暴露训练上下文的 HTTP 路由并完成请求参数装配。"""

from flask import Blueprint

from app.http import json_body_endpoint, json_endpoint, json_error_response, param, query_params, query_params_endpoint
from contexts.training.application.commands import (
    archive_training_workflow_record,
    continue_training,
    create_training_workflow_record,
    delete_export_task_record,
    delete_training_workflow_record,
    restore_training_workflow_record,
    resume_training,
    start_batch_calibration_task,
    start_evaluate_task,
    start_export_task,
    start_inference_task,
    start_retry_training_task,
    start_training_task,
)
from contexts.training.application.queries import (
    build_runtime_profile,
    get_training_artifacts,
    get_training_model_export_bundle_info,
    get_training_model_exports,
    get_training_run_artifacts,
    get_training_workflow_record,
    list_task_history,
    list_training_test_dirs,
    list_training_workflow_records,
    load_batch_calibration,
)
from shared.infra.zip_download import send_temp_zip
from shared.utils.path_utils import resolve_project_path
from shared.utils.value_utils import parse_bool
from shared.utils.zip_utils import build_directory_zip

bp = Blueprint("training", __name__)


bp.add_url_rule(
    "/api/training/workflow/create",
    view_func=json_body_endpoint(
        create_training_workflow_record,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
        dataset_path=param("dataset_path"),
        vision_task_type=param("vision_task_type"),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/training/start",
    view_func=json_body_endpoint(
        start_training_task,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
        model_name=param("model_name", required=True),
        model_path=param("model_path"),
        training_config=param("training_config", default=dict),
        dataset_path=param("dataset_path"),
        workflow_id=param("workflow_id"),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/training/batch_calibration",
    view_func=query_params_endpoint(
        load_batch_calibration,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name"),
        model_name=param("model_name"),
        imgsz=param("imgsz", default=640),
    ),
    methods=["GET"],
)
bp.add_url_rule(
    "/api/training/batch_calibration/start",
    view_func=json_body_endpoint(
        start_batch_calibration_task,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
        model_name=param("model_name", required=True),
        model_path=param("model_path"),
        imgsz=param("imgsz", default=640),
        dataset_path=param("dataset_path"),
        force=param("force", default=False, transform=parse_bool),
        workflow_id=param("workflow_id"),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/training/workflows",
    view_func=query_params_endpoint(
        list_training_workflow_records,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name"),
        include_archived=param("include_archived", transform=parse_bool),
        archived_only=param("archived_only", transform=parse_bool),
    ),
    methods=["GET"],
)
bp.add_url_rule(
    "/api/training/workflow",
    view_func=query_params_endpoint(
        get_training_workflow_record,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        workflow_id=param("workflow_id", required=True),
        dataset_name=param("dataset_name"),
        include_archived=param("include_archived", transform=parse_bool),
    ),
    methods=["GET"],
)
bp.add_url_rule(
    "/api/training/workflow/archive",
    view_func=json_body_endpoint(
        archive_training_workflow_record,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        workflow_id=param("workflow_id", required=True),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/training/workflow/restore",
    view_func=json_body_endpoint(
        restore_training_workflow_record,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        workflow_id=param("workflow_id", required=True),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/training/workflow/delete",
    view_func=json_body_endpoint(
        delete_training_workflow_record,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        workflow_id=param("workflow_id", required=True),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/training/run/artifacts",
    view_func=query_params_endpoint(
        get_training_run_artifacts,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        task_id=param("task_id", required=True),
    ),
    methods=["GET"],
)


bp.add_url_rule(
    "/api/training/continue",
    view_func=json_body_endpoint(
        continue_training,
        project_path=param("project_path", required=True, transform=resolve_project_path, required_message="缺少项目路径"),
        dataset_name=param("dataset_name", default="training"),
        training_config=param("training_config", default=dict),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/training/resume",
    view_func=json_body_endpoint(
        resume_training,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", default="training"),
        task_id=param("task_id", required=True),
        training_config=param("training_config", default=dict),
    ),
    methods=["POST"],
)


bp.add_url_rule(
    "/api/training/retry",
    view_func=json_body_endpoint(
        start_retry_training_task,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", default="training"),
        task_id=param("task_id", required=True),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/training/artifacts",
    view_func=query_params_endpoint(
        get_training_artifacts,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        task_id=param("task_id"),
    ),
    methods=["GET"],
)
bp.add_url_rule(
    "/api/training/start_evaluate",
    view_func=json_body_endpoint(
        start_evaluate_task,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
        src_task_id=param("task_id", required=True),
        use_best=param("use_best", default=True, transform=lambda value: parse_bool(value, default=True)),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/training/export",
    view_func=json_body_endpoint(
        start_export_task,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        src_task_id=param("task_id", required=True),
        fmt=param("format", default="onnx"),
        imgsz=param("imgsz", default=640),
        half=param("half", default=False, transform=parse_bool),
        int8=param("int8", default=False, transform=parse_bool),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/training/model_exports",
    view_func=query_params_endpoint(
        get_training_model_exports,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        task_id=param("task_id"),
        training_id=param("training_id"),
    ),
    methods=["GET"],
)
bp.add_url_rule(
    "/api/training/model_export/delete",
    view_func=json_body_endpoint(
        delete_export_task_record,
        silent=True,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        export_task_id=param("export_task_id", required=True),
    ),
    methods=["POST"],
)


@bp.route("/api/training/model_export_bundle")
def api_training_model_export_bundle():
    """打包并下载指定导出目录。"""
    try:
        params = query_params(
            project_path=param("project_path", required=True, transform=resolve_project_path),
            export_dir_ref=param("export_dir", required=True),
        )
    except ValueError as exc:
        return json_error_response(str(exc), status_code=400)
    try:
        info = get_training_model_export_bundle_info(params["project_path"], params["export_dir_ref"])
    except FileNotFoundError:
        return json_error_response("导出目录不存在", status_code=404)
    except Exception:
        return json_error_response("非法路径", status_code=400)

    tmp_zip = build_directory_zip(info["export_real"], info["bundle_name"])
    return send_temp_zip(tmp_zip, f"{info['bundle_name']}.zip")


bp.add_url_rule(
    "/api/training/test_dirs",
    view_func=query_params_endpoint(
        list_training_test_dirs,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
    ),
    methods=["GET"],
)
bp.add_url_rule(
    "/api/training/test_inference/start",
    view_func=json_body_endpoint(
        start_inference_task,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
        src_task_id=param("task_id", required=True),
        test_subdir=param("test_subdir", default="val"),
        conf=param("conf", default=0.25, transform=float),
        max_det=param("max_det", default=200, transform=int),
    ),
    methods=["POST"],
)


bp.add_url_rule("/api/training/runtime_profile", view_func=json_endpoint(build_runtime_profile), methods=["GET"])
bp.add_url_rule(
    "/api/training/metrics_history",
    view_func=query_params_endpoint(list_task_history, task_id=param("task_id", required=True)),
    methods=["GET"],
)
