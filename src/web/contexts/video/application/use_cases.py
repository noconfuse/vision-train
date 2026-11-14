"""提供视频上下文对外稳定入口。"""

import logging
import os

from contexts.project.application.project_service import get_project_task_images_dir, get_project_videos_dir
from protocols.task_type import TASK_TYPE_FRAME_EXTRACTION, TASK_TYPE_VIDEO_TRANSCODE
from protocols.task_status import is_active_task_status
from contexts.task.application.task_service import list_project_tasks
from contexts.video.infrastructure.video_access import append_video_urls, build_task_image_items
from contexts.video.infrastructure.video_file_gateway import remove_video_file, save_uploaded_video
from contexts.video.infrastructure.video_runtime import browser_can_play_video, probe_video_media
from contexts.video.infrastructure.video_task_gateway import (
    delete_extraction_task as delete_video_extraction_task,
    delete_task_images,
    import_task_images,
    list_task_images,
    list_videos,
    start_extraction,
    start_transcode,
)
from shared.utils.fs_utils import resolve_safe_child_path
from shared.utils.path_utils import validate_leaf_name

logger = logging.getLogger(__name__)


def list_project_videos(project_path):
    """返回补齐预览地址与预览转码状态后的视频列表。"""
    videos = append_video_urls(project_path, list_videos(project_path))
    preview_task_by_video = {}
    for task in list_project_tasks(project_path, type_=TASK_TYPE_VIDEO_TRANSCODE, limit=500) or []:
        payload = task.get("payload") or {}
        if payload.get("mode") != "preview":
            continue
        name = payload.get("video_name")
        if not name:
            continue
        current = preview_task_by_video.get(name)
        if (
            current is None
            or is_active_task_status(task.get("status"))
            or (
                not is_active_task_status(current.get("status"))
                and str(task.get("created_at") or "") > str(current.get("created_at") or "")
            )
        ):
            preview_task_by_video[name] = task
    for video in videos:
        if video.get("preview_ready"):
            video["preview_status"] = "ready"
            video["preview_progress"] = 100
            video["preview_task_id"] = None
            continue
        task = preview_task_by_video.get(video["name"])
        if task and is_active_task_status(task.get("status")):
            video["preview_status"] = "processing"
            video["preview_progress"] = int(task.get("progress") or 0)
            video["preview_task_id"] = task.get("id")
        elif task and task.get("status") == "failed":
            video["preview_status"] = "failed"
            video["preview_progress"] = int(task.get("progress") or 0)
            video["preview_task_id"] = task.get("id")
        else:
            video["preview_status"] = "none"
            video["preview_progress"] = 0
            video["preview_task_id"] = None
    return videos


def upload_video(project_path, file_storage, target_name=None):
    """落盘上传视频，并为浏览器无法直接解码的格式自动启动预览转码。"""
    result = save_uploaded_video(project_path, file_storage, target_name)
    video_name = result.get("video_name")
    try:
        video_path = os.path.join(get_project_videos_dir(project_path), video_name)
        media = probe_video_media(video_path)
        ext = os.path.splitext(video_name)[1].lower()
        if not browser_can_play_video(media["codec"], ext):
            start_transcode(project_path, video_name, "preview")
    except Exception as exc:
        # 预览只是增强：上传已成功落盘，转码启动失败不应让上传整体报错，用户可在播放器里重试。
        logger.warning("上传后启动预览转码失败 %s: %s", video_name, exc)
    return result


def start_video_transcode(project_path, video_name, mode, start=None, end=None, target_name=None):
    """启动预览转码或区间裁剪任务。"""
    return start_transcode(project_path, video_name, mode, start=start, end=end, target_name=target_name)


def resolve_video_thumbnail_path(project_path, video_name):
    """解析视频缩略图文件路径。"""
    video_name = validate_leaf_name(video_name, field_name="video_name")
    return resolve_safe_child_path(
        os.path.join(get_project_videos_dir(project_path), ".thumbnails"),
        f"{video_name}.jpg",
    )


def resolve_video_stream_path(project_path, video_name, preview=False):
    """解析视频原文件或 H.264 预览副本路径。"""
    video_name = validate_leaf_name(video_name, field_name="video_name")
    videos_dir = get_project_videos_dir(project_path)
    if preview:
        preview_name = f"{os.path.splitext(video_name)[0]}.mp4"
        return resolve_safe_child_path(os.path.join(videos_dir, ".previews"), preview_name)
    return resolve_safe_child_path(videos_dir, video_name)


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
