"""维护数据集导入任务的内存态状态与事件流。"""

import os
import tempfile
import threading
import time
import uuid

from shared.utils.fs_utils import remove_file_silent
from shared.utils.json_utils import encode_json

_IMPORT_JOB_TTL = 3600
_IMPORT_JOBS = {}


def cleanup_import_jobs():
    """清理过期导入任务及其暂存压缩包。"""
    now = time.time()
    expired = [job_id for job_id, job in _IMPORT_JOBS.items() if now - job.get("updated_at", now) > _IMPORT_JOB_TTL]
    for job_id in expired:
        staging = _IMPORT_JOBS[job_id].get("staging_path")
        if staging and os.path.exists(staging):
            remove_file_silent(staging)
        _IMPORT_JOBS.pop(job_id, None)


def create_import_job(project_path, dataset_name, uploaded_file):
    """创建导入任务并把上传文件落到暂存区。"""
    job_id = uuid.uuid4().hex
    staging_dir = os.path.join(tempfile.gettempdir(), "vt_import_staging")
    os.makedirs(staging_dir, exist_ok=True)
    staging_path = os.path.join(staging_dir, f"{job_id}.zip")
    uploaded_file.save(staging_path)

    _IMPORT_JOBS[job_id] = {
        "project": project_path,
        "ds_name": dataset_name,
        "staging_path": staging_path,
        "orig_filename": uploaded_file.filename,
        "updated_at": time.time(),
        "events": [],
        "phase": "uploaded",
        "progress": 0,
        "message": "已上传",
        "done": False,
        "result": None,
        "error": None,
    }
    return {
        "job_id": job_id,
        "staging_path": staging_path,
        "file_size": os.path.getsize(staging_path),
    }


def has_import_job(job_id):
    """判断指定导入任务是否仍在内存中。"""
    return bool(job_id) and job_id in _IMPORT_JOBS


def get_import_job(job_id):
    """读取单个导入任务的当前状态。"""
    return _IMPORT_JOBS.get(job_id)


def emit_import_event(job_id, phase=None, progress=None, message=None, **extra):
    """追加一条导入事件并刷新任务状态。"""
    job = _IMPORT_JOBS.get(job_id)
    if not job:
        return
    if phase is not None:
        job["phase"] = phase
    if progress is not None:
        job["progress"] = progress
    if message is not None:
        job["message"] = message
    job["updated_at"] = time.time()
    job["events"].append(
        {
            **extra,
            **{key: value for key, value in (("phase", phase), ("progress", progress), ("message", message)) if value is not None},
        }
    )
    if len(job["events"]) > 200:
        job["events"] = job["events"][-200:]


def serialize_import_event(event):
    """把事件对象编码成 SSE 数据块。"""
    return f"data: {encode_json(event, ensure_ascii=False)}\n\n"


def build_progress_callback(job, progress_lock, phase, start_pct, end_pct, fmt, message_formatter):
    """构造供格式转换器调用的进度更新回调。"""
    def cb(s_idx, n_splits, i_idx, n_imgs):
        """按 split 和图片进度回写任务状态。"""
        total = max(1, n_splits) * max(1, n_imgs)
        cur = s_idx * max(1, n_imgs) + i_idx
        ratio = min(1.0, cur / total)
        pct = int(start_pct + (end_pct - start_pct) * ratio)
        with progress_lock:
            if job["done"]:
                return
            job["phase"] = phase
            job["progress"] = pct
            job["message"] = message_formatter(phase, fmt, s_idx, n_splits, i_idx, n_imgs)
            job["updated_at"] = time.time()
            job["events"].append({"phase": phase, "progress": pct, "message": job["message"]})

    return cb


def stream_import_events(job_id, runner):
    """启动导入线程并持续输出新增事件。"""
    job = get_import_job(job_id)
    if not job:
        raise ValueError("job_id 无效或已过期")

    progress_lock = threading.Lock()
    last_event_index = 0
    deadline = time.time() + 600
    worker = threading.Thread(target=runner, args=(job_id, progress_lock), daemon=True)
    worker.start()

    while time.time() < deadline:
        with progress_lock:
            done = job["done"]
            events = list(job["events"])
        while last_event_index < len(events):
            yield serialize_import_event(events[last_event_index])
            last_event_index += 1
        if done:
            return
        time.sleep(0.1)

    with progress_lock:
        job["done"] = True
        if not job.get("error"):
            job["error"] = "处理超时"
    emit_import_event(job_id, phase="done", progress=100, message="处理超时", done=True, success=False, error="处理超时")
    with progress_lock:
        events = list(job["events"])
    while last_event_index < len(events):
        yield serialize_import_event(events[last_event_index])
