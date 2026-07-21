"""提供视频上下文对外稳定入口。"""

import os

from contexts.project.infrastructure.project_paths import get_project_task_images_dir, get_project_videos_dir
from contexts.task.domain.task_types import TASK_TYPE_FRAME_EXTRACTION
from contexts.task.infrastructure.task_runtime import list_project_tasks
from contexts.video.infrastructure.video_access import append_video_urls, build_task_image_items
from contexts.video.infrastructure.video_file_gateway import remove_video_file, save_uploaded_video
from contexts.video.infrastructure.video_task_gateway import (
    delete_extraction_task as delete_video_extraction_task,
    delete_task_images,
    import_task_images,
    list_task_images,
    list_videos,
    start_extraction,
)
from shared.utils.fs_utils import resolve_safe_child_path
from shared.utils.path_utils import validate_leaf_name


def list_project_videos(project_path):
    """返回补齐预览地址后的视频列表。"""
    return append_video_urls(project_path, list_videos(project_path))


def resolve_video_thumbnail_path(project_path, video_name):
    """解析视频缩略图文件路径。"""
    video_name = validate_leaf_name(video_name, field_name="video_name")
    return resolve_safe_child_path(
        os.path.join(get_project_videos_dir(project_path), ".thumbnails"),
        f"{video_name}.jpg",
    )


def resolve_video_stream_path(project_path, video_name):
    """解析视频原文件路径。"""
    video_name = validate_leaf_name(video_name, field_name="video_name")
    return resolve_safe_child_path(get_project_videos_dir(project_path), video_name)


def start_video_extraction(project_path, video_name, strategy="interval", value=1.0):
    """启动视频抽帧任务并返回统一结果。"""
    return {"task_id": start_extraction(project_path, video_name, strategy, value)}


def list_video_extraction_tasks(project_path):
    """列出项目中的抽帧任务。"""
    return list_project_tasks(project_path, type_=TASK_TYPE_FRAME_EXTRACTION, limit=500)


def list_video_task_image_items(project_path, task_id):
    """返回抽帧任务的前端展示图片项。"""
    return build_task_image_items(project_path, task_id, list_task_images(project_path, task_id))


def resolve_video_task_image_path(project_path, task_id, image_name):
    """解析抽帧任务中的单张图片路径。"""
    valid_name = validate_leaf_name(image_name, field_name="image_name")
    return resolve_safe_child_path(get_project_task_images_dir(project_path, task_id), valid_name)
