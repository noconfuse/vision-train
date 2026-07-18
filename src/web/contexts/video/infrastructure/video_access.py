"""构造视频资源展示项。"""

import os
from urllib.parse import urlencode

from contexts.project.infrastructure.project_paths import get_project_task_images_dir
from shared.utils.path_utils import build_file_items, project_path_ref


def append_video_urls(project_path, videos):
    """为视频列表补充缩略图和播放地址。"""
    project_ref = project_path_ref(project_path)
    for video in videos:
        query = urlencode({"project_path": project_ref, "video_name": video["name"]})
        video["thumbnail_url"] = f"/api/video/thumbnail?{query}"
        video["stream_url"] = f"/api/video/stream?{query}"
    return videos


def build_task_image_items(project_path, task_id, image_names):
    """将图片名列表转换为前端可展示项。"""
    project_ref = project_path_ref(project_path)
    task_images_dir = get_project_task_images_dir(project_path, task_id)
    return build_file_items(
        (os.path.join(task_images_dir, image_name) for image_name in image_names),
        url_builder=lambda file_path, _raw: (
            f"/api/video/task/image_file?project_path={project_ref}&task_id={task_id}&image_name={os.path.basename(file_path)}"
        ),
    )
