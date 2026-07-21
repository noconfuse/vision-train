"""提供视频上传、预览、抽帧与结果导入相关接口。"""

import mimetypes
import os

from flask import Blueprint, send_file

from app.http import form_body_endpoint, json_body_endpoint, param, query_params, query_params_endpoint
from contexts.video.application.use_cases import (
    delete_task_images,
    delete_video_extraction_task,
    import_task_images,
    list_project_videos,
    list_video_extraction_tasks,
    list_video_task_image_items,
    remove_video_file,
    resolve_video_stream_path,
    resolve_video_task_image_path,
    resolve_video_thumbnail_path,
    save_uploaded_video,
    start_video_extraction,
)
from shared.utils.path_utils import resolve_and_validate_project, resolve_project_path

bp = Blueprint("video", __name__)


bp.add_url_rule(
    "/api/videos",
    view_func=query_params_endpoint(
        list_project_videos,
        project_path=param(
            "project_path",
            required=True,
            transform=lambda value: resolve_and_validate_project(value)[0],
        ),
    ),
    methods=["GET"],
)
bp.add_url_rule(
    "/api/video/upload",
    view_func=form_body_endpoint(
        save_uploaded_video,
        project_path=param(
            "project_path",
            location="form",
            required=True,
            transform=lambda value: resolve_and_validate_project(value)[0],
        ),
        file_storage=param("file", location="files", required=True, required_message="未选择文件"),
        target_name=param("target_name", location="form"),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/video/delete",
    view_func=json_body_endpoint(
        remove_video_file,
        project_path=param(
            "project_path",
            required=True,
            transform=lambda value: resolve_and_validate_project(value)[0],
        ),
        video_name=param("video_name", required=True),
    ),
    methods=["POST"],
)


@bp.route("/api/video/thumbnail")
def api_video_thumbnail():
    """返回视频缩略图文件。"""
    try:
        params = query_params(
            project_path=param(
                "project_path",
                required=True,
                transform=lambda value: resolve_and_validate_project(value)[0],
            ),
            video_name=param("video_name", required=True),
        )
        thumb_path = resolve_video_thumbnail_path(params["project_path"], params["video_name"])
    except ValueError as exc:
        return str(exc), 400
    if os.path.exists(thumb_path):
        return send_file(thumb_path, mimetype="image/jpeg", conditional=True)
    return "Thumbnail not found", 404


@bp.route("/api/video/stream")
def api_video_stream():
    """返回视频流文件。"""
    try:
        params = query_params(
            project_path=param(
                "project_path",
                required=True,
                transform=lambda value: resolve_and_validate_project(value)[0],
            ),
            video_name=param("video_name", required=True),
        )
        video_path = resolve_video_stream_path(params["project_path"], params["video_name"])
    except ValueError as exc:
        return str(exc), 400
    if not os.path.exists(video_path):
        return "Video not found", 404
    mimetype = mimetypes.guess_type(video_path)[0] or "application/octet-stream"
    return send_file(video_path, mimetype=mimetype, conditional=True)


bp.add_url_rule(
    "/api/video/extract",
    view_func=json_body_endpoint(
        start_video_extraction,
        project_path=param(
            "project_path",
            required=True,
            transform=lambda value: resolve_and_validate_project(value)[0],
        ),
        video_name=param("video_name", required=True),
        strategy=param("strategy", default="interval"),
        value=param("value", default=1.0),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/video/tasks",
    view_func=query_params_endpoint(
        list_video_extraction_tasks,
        project_path=param(
            "project_path",
            required=True,
            transform=lambda value: resolve_and_validate_project(value)[0],
        ),
    ),
    methods=["GET"],
)
bp.add_url_rule(
    "/api/video/task/images",
    view_func=query_params_endpoint(
        list_video_task_image_items,
        project_path=param(
            "project_path",
            required=True,
            transform=lambda value: resolve_and_validate_project(value)[0],
        ),
        task_id=param("task_id", required=True),
    ),
    methods=["GET"],
)


@bp.route("/api/video/task/image_file")
def api_video_task_image_file():
    """返回抽帧任务中的单张图片文件。"""
    try:
        params = query_params(
            project_path=param("project_path", required=True, transform=resolve_project_path),
            task_id=param("task_id", required=True),
            image_name=param("image_name", required=True),
        )
        image_path = resolve_video_task_image_path(params["project_path"], params["task_id"], params["image_name"])
    except ValueError as exc:
        return str(exc), 400
    if os.path.exists(image_path):
        return send_file(image_path, mimetype="image/jpeg")
    return "Image not found", 404


bp.add_url_rule(
    "/api/video/task/import",
    view_func=json_body_endpoint(
        lambda project_path, task_id, dataset_name, selected_images: {
            "imported_count": import_task_images(project_path, task_id, dataset_name, selected_images)
        },
        project_path=param(
            "project_path",
            required=True,
            transform=lambda value: resolve_and_validate_project(value)[0],
        ),
        task_id=param("task_id", required=True),
        dataset_name=param("dataset_name", required=True),
        selected_images=param("selected_images"),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/video/task/batch_delete",
    view_func=json_body_endpoint(
        delete_task_images,
        project_path=param(
            "project_path",
            required=True,
            transform=lambda value: resolve_and_validate_project(value)[0],
        ),
        task_id=param("task_id", required=True),
        selected_images=param("selected_images", default=list),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/api/video/task/delete",
    view_func=json_body_endpoint(
        delete_video_extraction_task,
        project_path=param(
            "project_path",
            required=True,
            transform=lambda value: resolve_and_validate_project(value)[0],
        ),
        task_id=param("task_id", required=True),
    ),
    methods=["POST"],
)
