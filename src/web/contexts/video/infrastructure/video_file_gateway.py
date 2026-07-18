"""处理视频文件上传命名、落盘与删除。"""

import os

from contexts.project.infrastructure.project_paths import (
    get_project_videos_dir,
)
from shared.utils.fs_utils import remove_file_silent
from shared.utils.media_constants import VIDEO_FILE_EXTENSION_SET
from shared.utils.path_utils import project_name_from_path, storage_path_ref, validate_filename, validate_leaf_name
from shared.utils.value_utils import require_present

MAX_VIDEO_SIZE = 2 * 1024 * 1024 * 1024


def save_uploaded_video(project_path, file_storage, target_name=None):
    """将上传视频分块写入项目视频目录。"""
    if not file_storage or not getattr(file_storage, "filename", ""):
        raise ValueError("未选择文件")
    require_present(project_path=project_path)
    videos_dir = get_project_videos_dir(project_path)
    os.makedirs(videos_dir, exist_ok=True)
    project_name = project_name_from_path(project_path)
    try:
        final_name = validate_filename(
            file_storage.filename,
            target_name=target_name,
            allowed_extensions=VIDEO_FILE_EXTENSION_SET,
            max_stem_length=200,
            field_name="视频名",
        )
    except ValueError as exc:
        if "扩展名不支持" in str(exc):
            raise ValueError(f'仅支持以下视频格式：{", ".join(sorted(VIDEO_FILE_EXTENSION_SET))}') from exc
        raise
    final_path = os.path.join(videos_dir, final_name)
    if os.path.exists(final_path):
        raise ValueError(f"视频 {final_name} 已存在，请先删除或换个名字")
    written = 0
    chunk_size = 8 * 1024 * 1024
    with open(final_path, "wb") as target:
        while True:
            chunk = file_storage.stream.read(chunk_size)
            if not chunk:
                break
            target.write(chunk)
            written += len(chunk)
            if written > MAX_VIDEO_SIZE:
                target.close()
                remove_file_silent(final_path)
                raise ValueError(f"视频超过最大尺寸 {MAX_VIDEO_SIZE // (1024**3)} GB")
    return {
        "video_name": final_name,
        "size": written,
        "project": project_name,
        "path": storage_path_ref(final_path),
    }


def remove_video_file(project_path, video_name):
    """删除视频文件并清理对应缩略图。"""
    validated_name = validate_leaf_name(video_name, field_name="video_name")
    videos_dir = get_project_videos_dir(project_path)
    video_path = os.path.join(videos_dir, validated_name)
    if not os.path.isfile(video_path):
        raise ValueError(f"视频 {validated_name} 不存在")
    remove_file_silent(video_path)
    remove_file_silent(os.path.join(videos_dir, ".thumbnails", f"{validated_name}.jpg"))
    return {"deleted": validated_name}
