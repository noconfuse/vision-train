"""暴露数据集相关 HTTP 接口，并把请求参数转交应用层用例。"""

from flask import Blueprint, Response, stream_with_context

from app.http import form_body_endpoint, json_body_endpoint, json_error_response, param, query_params, query_params_endpoint
from contexts.dataset.application.use_cases import (
    augment_subset,
    batch_delete_dataset_images,
    clear_dataset_auto_labels,
    create_import_upload_job,
    create_subset,
    deduplicate_dataset_images,
    delete_dataset_folder,
    delete_dataset_image,
    delete_dataset_label_use_case,
    download_dataset_info,
    get_dataset_info,
    list_dataset_images,
    merge_dataset_pair,
    reorder_dataset_labels_use_case,
    split_dataset_use_case,
    update_dataset_tags,
    upload_dataset_images,
    validate_dataset,
)
from contexts.dataset.infrastructure.dataset_import import run_import_job
from contexts.dataset.infrastructure.dataset_import_runtime import has_import_job as has_dataset_import_job
from contexts.dataset.infrastructure.dataset_import_runtime import stream_import_events as stream_dataset_import_events
from contexts.dataset.infrastructure.dataset_repository import scan_project_datasets
from shared.infra.zip_download import send_temp_zip
from shared.utils.path_utils import resolve_and_validate_project, resolve_project_path, resolve_storage_path
from shared.utils.zip_utils import build_directory_zip

bp = Blueprint("dataset", __name__)


bp.add_url_rule(
    "/api/datasets",
    view_func=query_params_endpoint(
        scan_project_datasets,
        project_path=param("project_path", required=True, transform=resolve_project_path),
    ),
    methods=["GET"],
)
bp.add_url_rule(
    "/api/dataset/create_subset",
    view_func=json_body_endpoint(
        create_subset,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        source_dataset=param("source_dataset", required=True),
        new_dataset_name=param("new_dataset_name", required=True),
        image_paths=param("image_paths", default=list),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/dataset/augment_subset",
    view_func=json_body_endpoint(
        augment_subset,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        source_dataset=param("source_dataset", required=True),
        new_dataset_name=param("new_dataset_name"),
        payload=param(location="whole", empty_as_missing=False),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/dataset/info",
    view_func=query_params_endpoint(
        get_dataset_info,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
    ),
    methods=["GET"],
)


@bp.route("/api/dataset/download")
def api_dataset_download():
    """打包并下载指定数据集目录。"""
    try:
        info = download_dataset_info(
            **query_params(
                project_path=param("project_path", required=True, transform=resolve_project_path),
                dataset_name=param("dataset_name", required=True),
            )
        )
        tmp_zip = build_directory_zip(info["dataset_root"], info["bundle_name"])
        return send_temp_zip(tmp_zip, f"{info['bundle_name']}.zip")
    except FileNotFoundError as exc:
        return json_error_response(str(exc), status_code=404)
    except Exception as exc:
        return json_error_response(str(exc), status_code=400)


bp.add_url_rule(
    "/api/dataset/images",
    view_func=query_params_endpoint(
        list_dataset_images,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
        split=param("split", default="train"),
        offset=param("offset", default="0", transform=int),
        limit=param("limit", default="50", transform=int),
        classes_raw=param(("classes", "class")),
        mode=param("mode", default="include", transform=lambda value: str(value).strip().lower()),
        unannotated_raw=param("unannotated"),
        has_auto_label_raw=param("has_auto_label"),
    ),
    methods=["GET"],
)
bp.add_url_rule(
    "/api/dataset/upload",
    view_func=form_body_endpoint(
        upload_dataset_images,
        project_path=param("project_path", location="form", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", location="form", required=True),
        split=param("split", location="form", default="train"),
        files=param("files", location="files_list", default=list),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/dataset/delete",
    view_func=json_body_endpoint(
        delete_dataset_image,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
        split=param("split", default="train"),
        image_rel=param("image_rel"),
        image_path=param("image_path"),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/dataset/batch_delete",
    view_func=json_body_endpoint(
        batch_delete_dataset_images,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
        split=param("split", default="train"),
        image_paths=param("image_paths", default=list),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/dataset/reorder_labels",
    view_func=json_body_endpoint(
        reorder_dataset_labels_use_case,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
        order=param("order", required=True),
        splits=param("splits"),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/dataset/delete_label",
    view_func=json_body_endpoint(
        delete_dataset_label_use_case,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
        class_id=param("class_id"),
        class_name=param("class_name"),
        splits=param("splits"),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/dataset/update_tags",
    view_func=json_body_endpoint(
        update_dataset_tags,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
        tags=param("tags", default=list),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/dataset/clear_auto_labels",
    view_func=json_body_endpoint(
        clear_dataset_auto_labels,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/dataset/delete_folder",
    view_func=json_body_endpoint(
        delete_dataset_folder,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
        dataset_path=param("dataset_path", transform=resolve_storage_path),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/dataset/validate",
    view_func=json_body_endpoint(
        validate_dataset,
        dataset_path=param("dataset_path", required=True),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/dataset/merge",
    view_func=json_body_endpoint(
        merge_dataset_pair,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_a=param("dataset_a", required=True),
        dataset_b=param("dataset_b", required=True),
        new_dataset_name=param("new_dataset_name", required=True),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/dataset/split",
    view_func=json_body_endpoint(
        split_dataset_use_case,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name", required=True),
        val_ratio=param("val_ratio", default=0.1, transform=float),
        test_ratio=param("test_ratio", default=0, transform=float),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/dataset/deduplicate_images",
    view_func=json_body_endpoint(
        deduplicate_dataset_images,
        project_path=param("project_path", required=True, transform=resolve_project_path),
        dataset_name=param("dataset_name"),
        dataset_path=param("dataset_path", transform=resolve_storage_path),
        keep_split=param("keep_split", default="train"),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/dataset/import/upload",
    view_func=form_body_endpoint(
        create_import_upload_job,
        project_path_ref=param(
            "project_path",
            location="form",
            required=True,
            transform=lambda value: resolve_and_validate_project(value)[0],
        ),
        target_name=param("target_name", location="form"),
        uploaded_file=param("file", location="files", required=True, required_message="未上传文件"),
    ),
    methods=["POST"],
)


@bp.route("/api/dataset/import/process", methods=["GET"])
def api_import_dataset_process():
    """以 SSE 方式推送导入任务进度。"""
    job_id = query_params(job_id=param("job_id", required=True, transform=lambda value: str(value).strip()))["job_id"]
    try:
        if not has_dataset_import_job(job_id):
            raise ValueError("job_id 无效或已过期")
    except ValueError as exc:
        return json_error_response(str(exc), status_code=404)
    headers = {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    return Response(stream_with_context(stream_dataset_import_events(job_id, run_import_job)), headers=headers)
