"""驱动压缩包数据集导入流程并产出进度事件。"""
from contexts.dataset.infrastructure.dataset_repository import get_project_dataset_summary
from contexts.dataset.infrastructure.dataset_import_formats import (
    resolve_import_archive_root,
)
from contexts.dataset.infrastructure.dataset_import_strategy import resolve_dataset_import_strategy
from contexts.dataset.infrastructure.dataset_import_runtime import (
    emit_import_event,
    get_import_job,
)
from contexts.dataset.infrastructure.dataset_task_type import save_dataset_vision_task_type
from contexts.project.infrastructure.project_paths import (
    get_project_dataset_dir,
)
from shared.utils.fs_utils import remove_path_silent
from shared.utils.path_utils import resolve_project_path
from shared.utils.zip_utils import safe_extract_archive
import os
import tempfile


def run_import_job(job_id, progress_lock):
    """执行一次数据集导入并持续上报阶段进度。"""
    job = get_import_job(job_id)
    if not job:
        raise ValueError("job_id 无效或已过期")

    try:
        staging_path = job["staging_path"]
        project_path = job["project"]
        dataset_name = job["ds_name"]
        vision_task_type = job["vision_task_type"]
        import_strategy = resolve_dataset_import_strategy(vision_task_type)

        abs_project = os.path.join(resolve_project_path(project_path), "")
        dest = get_project_dataset_dir(abs_project, dataset_name)

        temp_dir = tempfile.mkdtemp(prefix=f"vt_proc_{job_id[:8]}_")
        try:
            emit_import_event(job_id, phase="parsing", progress=5, message="解压压缩包...")
            safe_extract_archive(staging_path, temp_dir, original_name=job.get("orig_filename"))
            emit_import_event(job_id, phase="parsing", progress=20, message="检测数据集格式...")

            dataset_root = resolve_import_archive_root(temp_dir)
            source_format = import_strategy.detect_source_format(dataset_root)
            if source_format == "unknown":
                raise ValueError(
                    "无法识别数据集格式：压缩包根目录只允许是数据集根目录本身，或仅包一层目录；检测任务支持 YOLO（dataset.yaml）、Roboflow（data.yaml）、COCO（annotations/instances_*.json）和 Pascal VOC（Annotations/*.xml + JPEGImages/）；分类任务仅支持两类常见目录：class/* 或 train|val|test/class/*"
                )
            emit_import_event(job_id, phase="parsing", progress=30, message=f"检测到 {source_format.upper()} 格式")
            import_strategy.import_detected_format(source_format, dataset_root, dest, job, progress_lock)

            save_dataset_vision_task_type(dest, vision_task_type)
            emit_import_event(job_id, phase="saving", progress=95, message="完成落盘")

            new_dataset = get_project_dataset_summary(project_path, dataset_name)

            result = {
                "success": True,
                "project": project_path,
                "dataset_name": dataset_name,
                "source_format": source_format,
                "dataset": new_dataset,
            }
            emit_import_event(job_id, phase="done", progress=100, message="导入完成", done=True, success=True, result=result)
            with progress_lock:
                job["done"] = True
                job["result"] = result
        finally:
            remove_path_silent(temp_dir)
            remove_path_silent(staging_path)
    except ValueError as exc:
        with progress_lock:
            job["done"] = True
            job["error"] = str(exc)
        emit_import_event(job_id, phase="done", progress=100, message="失败", done=True, success=False, error=str(exc))
    except Exception as exc:
        with progress_lock:
            job["done"] = True
            job["error"] = f"导入失败: {exc}"
        emit_import_event(job_id, phase="done", progress=100, message="失败", done=True, success=False, error=f"导入失败: {exc}")
