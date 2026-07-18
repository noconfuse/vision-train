"""执行视频抽帧 worker 并回写任务状态。"""

import logging
import os

from contexts.project.infrastructure.project_paths import get_project_task_images_dir, get_project_videos_dir
from contexts.task.domain.task_types import TASK_TYPE_FRAME_EXTRACTION
from contexts.task.domain.task_artifact_keys import (
    ARTIFACT_IMAGES_DIR,
    ARTIFACT_STOP_SIGNAL_PATH,
)
from contexts.task.infrastructure.task_repository import (
    merge_task_artifacts as merge_artifacts,
    update_task as update_task_status,
)
from contexts.task.infrastructure.task_runtime import load_task
from contexts.task.infrastructure.worker_task_ops import finish_worker_task, is_stop_requested, mark_worker_exited, mark_worker_started
from contexts.video.infrastructure.video_runtime import (
    extract_frames_with_ffmpeg,
    get_video_frame_count_ffprobe,
    should_use_robust_mode,
)
from task_status import TASK_STATUS_COMPLETED, TASK_STATUS_FAILED, TASK_STATUS_RUNNING, TASK_STATUS_STOPPED

logger = logging.getLogger(__name__)
def execute_extraction_task(task_id):
    """执行一个视频抽帧任务直到完成、失败或停止。"""
    task = load_task(task_id)
    if not task or task.get("type") != TASK_TYPE_FRAME_EXTRACTION:
        raise ValueError(f"抽帧任务不存在: {task_id}")

    payload = task.get("payload") or {}
    project_path = task.get("project_path")
    video_name = payload.get("video_name")
    strategy = payload.get("strategy", "interval")
    value = payload.get("value", 1.0)

    if not project_path or not video_name:
        raise ValueError(f"抽帧任务参数不完整: {task_id}")

    video_path = os.path.join(get_project_videos_dir(project_path), str(video_name or ""))
    images_dir = get_project_task_images_dir(project_path, task_id)
    os.makedirs(images_dir, exist_ok=True)

    artifacts = dict(task.get("artifacts") or {})
    stop_signal_path = artifacts.get(ARTIFACT_STOP_SIGNAL_PATH)

    update_task_status(task_id, status=TASK_STATUS_RUNNING, message=f"开始抽帧 {video_name}...")
    mark_worker_started(task_id, os.getpid(), artifacts_patch={ARTIFACT_IMAGES_DIR: images_dir})

    try:
        if not os.path.isfile(video_path):
            raise FileNotFoundError(f"视频不存在: {video_name}")

        import cv2
        import numpy as np

        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()

        if total_frames <= 0:
            ffprobe_frames = get_video_frame_count_ffprobe(video_path)
            if ffprobe_frames > 0:
                total_frames = ffprobe_frames

        merge_artifacts(
            task_id,
            {
                ARTIFACT_IMAGES_DIR: images_dir,
                "total_frames": total_frames,
                "fps": fps,
            },
        )

        video_basename = os.path.splitext(video_name)[0]
        success, extracted_count = extract_frames_with_ffmpeg(
            video_path,
            images_dir,
            strategy,
            value,
            total_frames,
            fps,
            video_basename,
        )
        if success and extracted_count > 0:
            finish_worker_task(
                task_id,
                TASK_STATUS_COMPLETED,
                "抽帧完成",
                progress=100,
                artifacts_patch={
                    ARTIFACT_IMAGES_DIR: images_dir,
                    "total_frames": total_frames,
                    "extracted_count": extracted_count,
                },
                stop_signal_path=stop_signal_path,
            )
            return

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise RuntimeError("视频无法打开")

        extracted_count = 0
        use_robust = should_use_robust_mode(cap, fps, total_frames)

        def robust_extract(cap_obj):
            """按顺序读取视频帧并在异常流上尽量完成抽帧。"""
            nonlocal extracted_count
            interval_frames = 1
            if strategy == "interval":
                interval_frames = int(float(value) * fps)
            elif strategy == "count":
                count = int(value)
                if count > 0 and total_frames > 0:
                    interval_frames = int(total_frames / count)
                else:
                    interval_frames = int(fps)

            if interval_frames < 1:
                interval_frames = 1

            frame_idx = 0
            consecutive_failures = 0
            while True:
                try:
                    if is_stop_requested(stop_signal_path):
                        raise InterruptedError("用户终止抽帧")
                    if frame_idx % interval_frames != 0:
                        ok = cap_obj.grab()
                        if ok:
                            consecutive_failures = 0
                            frame_idx += 1
                            continue
                    ret, frame = cap_obj.read()
                    if ret and frame is not None:
                        frame_name = f"{video_basename}_f{frame_idx:06d}.jpg"
                        save_path = os.path.join(images_dir, frame_name)
                        cv2.imwrite(save_path, frame)
                        extracted_count += 1
                        consecutive_failures = 0
                        if total_frames > 0 and frame_idx % 100 == 0:
                            update_task_status(task_id, progress=min(99, int((frame_idx / total_frames) * 100)))
                    else:
                        consecutive_failures += 1
                        if consecutive_failures >= 300:
                            break
                    frame_idx += 1
                except InterruptedError:
                    raise
                except Exception:
                    consecutive_failures += 1
                    if consecutive_failures >= 300:
                        break

        if use_robust:
            robust_extract(cap)
        else:
            frame_indices = []
            if strategy == "interval":
                interval_frames = int(float(value) * fps)
                if interval_frames < 1:
                    interval_frames = 1
                frame_indices = range(0, total_frames, interval_frames)
            elif strategy == "count":
                count = int(value)
                if count > total_frames:
                    count = total_frames
                if count > 0:
                    frame_indices = np.linspace(0, total_frames - 1, count, dtype=int)
                    frame_indices = np.unique(frame_indices)

            total_to_extract = len(frame_indices)
            consecutive_failures = 0
            fallback_to_robust = False
            for idx, frame_idx in enumerate(frame_indices):
                if is_stop_requested(stop_signal_path):
                    raise InterruptedError("用户终止抽帧")
                if total_to_extract > 0:
                    update_task_status(task_id, progress=min(99, int((idx / total_to_extract) * 100)))
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(frame_idx))
                ret, frame = cap.read()
                if ret and frame is not None:
                    frame_name = f"{video_basename}_f{frame_idx:06d}.jpg"
                    save_path = os.path.join(images_dir, frame_name)
                    cv2.imwrite(save_path, frame)
                    extracted_count += 1
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    if idx < min(10, total_to_extract) and consecutive_failures >= 3:
                        fallback_to_robust = True
                        break

            if fallback_to_robust and extracted_count == 0:
                cap.release()
                cap = cv2.VideoCapture(video_path)
                if cap.isOpened():
                    robust_extract(cap)

        cap.release()
        finish_worker_task(
            task_id,
            TASK_STATUS_COMPLETED,
            "抽帧完成",
            progress=100,
            artifacts_patch={
                ARTIFACT_IMAGES_DIR: images_dir,
                "total_frames": total_frames,
                "extracted_count": extracted_count,
            },
            stop_signal_path=stop_signal_path,
        )
    except InterruptedError:
        finish_worker_task(task_id, TASK_STATUS_STOPPED, "抽帧已终止", stop_signal_path=stop_signal_path)
    except Exception as exc:
        logger.exception("抽帧 task %s 失败", task_id)
        finish_worker_task(
            task_id,
            TASK_STATUS_FAILED,
            f"抽帧失败: {exc}",
            error=str(exc),
            stop_signal_path=stop_signal_path,
        )
    finally:
        merge_artifacts(task_id, {ARTIFACT_IMAGES_DIR: images_dir})
        mark_worker_exited(task_id)
