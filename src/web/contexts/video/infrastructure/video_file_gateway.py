"""处理视频文件上传命名、落盘与删除。"""

import os

from contexts.project.infrastructure.project_paths import (
    get_project_videos_dir,
)
from contexts.task.domain.task_types import TASK_TYPE_FRAME_EXTRACTION
from contexts.task.infrastructure.task_runtime import list_project_tasks
from protocols.task_status import is_active_task_status
from shared.utils.fs_utils import remove_file_silent
from constants.media import VIDEO_FILE_EXTENSION_SET
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


def _collect_frame_extraction_tasks_for_video(project_path, video_name):
    """收集该视频关联的所有 frame_extraction 任务（已结束 + 运行中）。"""
    tasks = list_project_tasks(project_path, type_=TASK_TYPE_FRAME_EXTRACTION, limit=500)
    matched = []
    for item in tasks or []:
        payload = item.get("payload") or {}
        if payload.get("video_name") == video_name:
            matched.append(item)
    return matched


def remove_video_file(project_path, video_name):
    """删除视频文件并清理对应缩略图、关联抽帧任务。

    关联抽帧任务策略：
    - 已结束的：直接删除任务目录 + 任务记录；
    - 运行中的：先写停止信号让 worker 安全退出，状态会被 worker 自己改回 stopped/failed，
      后续的删除会由下一次"删除任务"动作或 worker 退出后完成。
    """
    validated_name = validate_leaf_name(video_name, field_name="video_name")
    videos_dir = get_project_videos_dir(project_path)
    video_path = os.path.join(videos_dir, validated_name)
    if not os.path.isfile(video_path):
        raise ValueError(f"视频 {validated_name} 不存在")

    related_tasks = _collect_frame_extraction_tasks_for_video(project_path, validated_name)

    # 先发停止信号给运行中的 task；worker 退出后会把 status 标成 stopped/failed。
    stop_requested_ids = []
    for task in related_tasks:
        if is_active_task_status(task.get("status")):
            try:
                from contexts.task.infrastructure.task_runtime import request_task_stop
                request_task_stop(task["id"])
                stop_requested_ids.append(task["id"])
            except ValueError:
                # 任务已不在 running/stopping 等情况下跳过；不影响视频删除主流程。
                pass

    remove_file_silent(video_path)
    remove_file_silent(os.path.join(videos_dir, ".thumbnails", f"{validated_name}.jpg"))

    # 已结束的 task：直接复用 delete_extraction_task 清理目录 + 记录。
    deleted_task_ids = []
    still_active_after_stop = []
    from contexts.video.infrastructure.video_task_gateway import delete_extraction_task
    for task in related_tasks:
        if task["id"] in stop_requested_ids:
            # worker 还没回写状态前不强制删，记录下来由前端轮询兜底。
            still_active_after_stop.append(task["id"])
            continue
        try:
            delete_extraction_task(project_path, task["id"])
            deleted_task_ids.append(task["id"])
        except ValueError:
            # delete_extraction_task 自己会校验 active，这里跳过即可。
            continue

    return {
        "deleted": validated_name,
        "deleted_task_ids": deleted_task_ids,
        "stop_requested_task_ids": stop_requested_ids,
        "pending_cleanup_task_ids": still_active_after_stop,
    }
