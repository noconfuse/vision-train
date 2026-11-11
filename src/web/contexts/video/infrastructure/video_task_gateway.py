"""管理视频扫描、抽帧任务创建与抽帧结果导入删除。"""

import logging
import os
import shutil
from datetime import datetime

from contexts.dataset.application.dataset_service import (
    get_dataset_images_dir,
    get_dataset_labels_dir,
    find_dataset_config,
    load_dataset_identity_meta,
    load_dataset_vision_task_type,
)
from contexts.dataset.application.use_cases import (
    create_empty_dataset,
    enqueue_initial_dataset_snapshot,
)
from contexts.project.application.project_service import (
    get_project_dataset_dir,
    get_project_task_dir,
    get_project_task_images_dir,
    get_project_videos_dir,
)
from protocols.task_artifact_keys import (
    ARTIFACT_IMAGES_DIR,
    ARTIFACT_LOG_PATH,
)
from protocols.task_type import TASK_TYPE_FRAME_EXTRACTION
from contexts.task.application.task_service import (
    create_task as start_task,
    delete_task as remove_task,
    update_task as update_task_status,
    load_task,
    build_worker_artifacts,
    mark_worker_started,
)
from contexts.video.infrastructure.video_runtime import generate_video_thumbnail
from shared.infra.worker_process import spawn_worker_process
from shared.utils.fs_utils import remove_file_silent, remove_tree
from constants.media import IMAGE_FILE_EXTENSIONS, VIDEO_FILE_EXTENSIONS
from shared.utils.path_utils import project_name_from_path, validate_leaf_name
from shared.utils.time_utils import now_iso
from shared.utils.value_utils import require_present
from protocols.task_status import is_active_task_status

logger = logging.getLogger(__name__)


def _prepare_import_target_dataset(project_path, dataset_root, dataset_name, vision_task_type=None):
    """确定抽帧导入的目标数据集：带任务类型则走统一注册流程新建，否则要求已注册。"""
    if str(vision_task_type or "").strip():
        create_empty_dataset(project_path, dataset_name, vision_task_type)
        return
    if not find_dataset_config(dataset_root):
        raise ValueError(f"数据集 {dataset_name} 不存在，请先创建数据集")
    try:
        load_dataset_vision_task_type(dataset_root)
    except ValueError:
        raise ValueError(f"数据集 {dataset_name} 未完成注册，缺少任务类型与稳定身份，无法导入")


def list_videos(project_path):
    """扫描项目视频目录并返回视频元数据。"""
    video_dir = get_project_videos_dir(project_path)
    videos = []
    if not os.path.exists(video_dir):
        return videos
    thumb_dir = os.path.join(video_dir, ".thumbnails")
    os.makedirs(thumb_dir, exist_ok=True)
    for file_name in os.listdir(video_dir):
        if not file_name.lower().endswith(VIDEO_FILE_EXTENSIONS):
            continue
        path = os.path.join(video_dir, file_name)
        try:
            size = os.path.getsize(path)
            thumb_path = os.path.join(thumb_dir, f"{file_name}.jpg")
            if not os.path.exists(thumb_path):
                generate_video_thumbnail(path, thumb_path)
            videos.append(
                {
                    "name": file_name,
                    "size": size,
                    "size_mb": round(size / (1024 * 1024), 2),
                    "modified": datetime.fromtimestamp(os.path.getmtime(path)).strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
        except Exception as exc:
            logger.warning("扫描视频 %s 失败: %s", file_name, exc)
    return sorted(videos, key=lambda item: item["name"])


def start_extraction(project_path, video_name, strategy="interval", value=1.0):
    """创建并启动视频抽帧 worker 任务。"""
    require_present(project_path=project_path)
    video_name = validate_leaf_name(video_name, field_name="video_name")
    task = start_task(
        project_path=project_path,
        project_name=project_name_from_path(project_path),
        type_=TASK_TYPE_FRAME_EXTRACTION,
        payload={"video_name": video_name, "strategy": strategy, "value": value},
        message=f"抽帧 {video_name} 中...",
    )
    task_id = task["id"]
    task_dir = get_project_task_dir(project_path, task_id)
    images_dir = get_project_task_images_dir(project_path, task_id)
    artifacts = build_worker_artifacts(task_dir, "frame-extraction-worker.log", "task_worker")
    artifacts[ARTIFACT_IMAGES_DIR] = images_dir
    update_task_status(task_id, artifacts=artifacts)
    try:
        proc, _ = spawn_worker_process(task_id, artifacts[ARTIFACT_LOG_PATH], "task_worker")
    except Exception as exc:
        update_task_status(
            task_id,
            status="failed",
            error=str(exc),
            message="抽帧进程启动失败",
            finished_at=now_iso(),
        )
        raise ValueError(f"启动抽帧进程失败: {exc}")
    update_task_status(
        task_id,
        started_at=now_iso(),
        status="running",
        message=f"抽帧进程已启动，准备处理 {video_name}...",
    )
    mark_worker_started(task_id, proc.pid, "task_worker", {ARTIFACT_IMAGES_DIR: images_dir})
    return task_id
def list_task_images(project_path, task_id):
    """列出抽帧任务输出目录中的图片。"""
    require_present(project_path=project_path, task_id=task_id)
    images_dir = get_project_task_images_dir(project_path, task_id)
    if not os.path.exists(images_dir):
        return []
    return sorted(file_name for file_name in os.listdir(images_dir) if file_name.lower().endswith(IMAGE_FILE_EXTENSIONS))


def import_task_images(project_path, task_id, dataset_name, selected_images=None, vision_task_type=None):
    """把抽帧图片复制到数据集训练分片；新建数据集时补齐注册与首个版本快照。"""
    require_present(project_path=project_path, task_id=task_id, dataset_name=dataset_name)
    source_dir = get_project_task_images_dir(project_path, task_id)
    dataset_root = get_project_dataset_dir(project_path, dataset_name)
    creates_dataset = bool(str(vision_task_type or "").strip())
    _prepare_import_target_dataset(project_path, dataset_root, dataset_name, vision_task_type)
    target_dir = get_dataset_images_dir(dataset_root, "train")
    labels_dir = get_dataset_labels_dir(dataset_root, "train")
    os.makedirs(target_dir, exist_ok=True)
    os.makedirs(labels_dir, exist_ok=True)
    if not selected_images:
        selected_images = [file_name for file_name in os.listdir(source_dir) if file_name.lower().endswith(IMAGE_FILE_EXTENSIONS)]
    success_count = 0
    for image_name in selected_images:
        src = os.path.join(source_dir, image_name)
        dst = os.path.join(target_dir, image_name)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            success_count += 1
    task = load_task(task_id)
    if task:
        artifacts = dict((task or {}).get("artifacts") or {})
        artifacts["imported_count"] = success_count
        update_task_status(task_id, artifacts=artifacts)
    result = {"dataset_name": dataset_name, "imported_count": success_count}
    if creates_dataset:
        result.update(
            enqueue_initial_dataset_snapshot(project_path, dataset_root, dataset_name, "frame_import")
        )
    else:
        result["dataset_id"] = load_dataset_identity_meta(dataset_root)["dataset_id"]
    return result


def delete_task_images(project_path, task_id, selected_images):
    """删除抽帧任务中的选定图片并同步任务计数。"""
    require_present(project_path=project_path, task_id=task_id, selected_images=selected_images)
    images_dir = get_project_task_images_dir(project_path, task_id)
    deleted = []
    for image_name in selected_images:
        if not isinstance(image_name, str):
            continue
        try:
            safe_name = validate_leaf_name(image_name, field_name="image_name")
        except ValueError:
            continue
        image_path = os.path.join(images_dir, safe_name)
        if os.path.exists(image_path):
            remove_file_silent(image_path)
            deleted.append(safe_name)
    if os.path.isdir(images_dir):
        try:
            remaining = list_task_images(project_path, task_id)
            task = load_task(task_id)
            artifacts = dict((task or {}).get("artifacts") or {})
            artifacts["extracted_count"] = len(remaining)
            update_task_status(task_id, artifacts=artifacts)
        except Exception:
            pass
    return {"deleted_count": len(deleted), "deleted_images": deleted}


def delete_extraction_task(project_path, task_id):
    """删除一个已结束的视频抽帧任务及其目录。"""
    task = load_task(task_id)
    if not task:
        raise ValueError("任务不存在")
    if task.get("type") != TASK_TYPE_FRAME_EXTRACTION:
        raise ValueError("任务类型不匹配")
    if os.path.realpath(task.get("project_path") or "") != os.path.realpath(project_path):
        raise ValueError("任务不属于当前项目")
    if is_active_task_status(task.get("status")):
        raise ValueError("任务仍在运行中，请先停止任务")

    task_dir = get_project_task_dir(project_path, task_id)
    remove_tree(task_dir)
    remove_task(task_id)
    return {"task_id": task_id, "deleted": True}
