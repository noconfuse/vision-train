"""提供视频上传、预览、抽帧与结果导入相关接口。"""

import mimetypes
import os

from flask import Blueprint, send_file

from app.http import form_body_endpoint, json_body_endpoint, param, query_params, query_params_endpoint
from contexts.task.domain.task_types import TASK_TYPE_FRAME_EXTRACTION
from contexts.task.infrastructure.task_runtime import list_project_tasks
from contexts.video.infrastructure.video_access import append_video_urls, build_task_image_items
from contexts.video.infrastructure.video_file_gateway import remove_video_file, save_uploaded_video
from contexts.video.infrastructure.video_task_gateway import (
    delete_task_images,
    delete_extraction_task as gateway_delete_extraction_task,
    import_task_images,
    list_task_images,
    list_videos as gateway_list_videos,
    start_extraction,
)
from contexts.project.infrastructure.project_paths import (
    get_project_task_images_dir,
    get_project_videos_dir,
)
from shared.utils.path_utils import resolve_and_validate_project, resolve_project_path, resolve_safe_child_path, validate_leaf_name

bp = Blueprint("video", __name__)


bp.add_url_rule(
    "/api/videos",
    view_func=query_params_endpoint(
        lambda project_path: append_video_urls(project_path, gateway_list_videos(project_path)),
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
        video_name = validate_leaf_name(params["video_name"], field_name="video_name")
        thumb_path = resolve_safe_child_path(
            os.path.join(get_project_videos_dir(params["project_path"]), ".thumbnails"),
            f"{video_name}.jpg",
        )
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
        video_name = validate_leaf_name(params["video_name"], field_name="video_name")
        video_path = resolve_safe_child_path(get_project_videos_dir(params["project_path"]), video_name)
    except ValueError as exc:
        return str(exc), 400
    if not os.path.exists(video_path):
        return "Video not found", 404
    mimetype = mimetypes.guess_type(video_path)[0] or "application/octet-stream"
    return send_file(video_path, mimetype=mimetype, conditional=True)


bp.add_url_rule(
    "/api/video/extract",
    view_func=json_body_endpoint(
        lambda project_path, video_name, strategy, value: {
            "task_id": start_extraction(project_path, video_name, strategy, value)
        },
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
        lambda project_path: list_project_tasks(project_path, type_=TASK_TYPE_FRAME_EXTRACTION, limit=500),
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
        lambda project_path, task_id: build_task_image_items(project_path, task_id, list_task_images(project_path, task_id)),
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
        valid_name = validate_leaf_name(params["image_name"], field_name="image_name")
        image_path = resolve_safe_child_path(get_project_task_images_dir(params["project_path"], params["task_id"]), valid_name)
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
        gateway_delete_extraction_task,
        project_path=param(
            "project_path",
            required=True,
            transform=lambda value: resolve_and_validate_project(value)[0],
        ),
        task_id=param("task_id", required=True),
    ),
    methods=["POST"],
)
