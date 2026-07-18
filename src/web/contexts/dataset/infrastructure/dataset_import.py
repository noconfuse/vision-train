"""驱动压缩包数据集导入流程并产出进度事件。"""
from contexts.dataset.infrastructure.dataset_repository import get_project_dataset_summary
from contexts.dataset.infrastructure.dataset_import_formats import (
    convert_coco_to_yolo,
    convert_roboflow_to_yolo,
    convert_voc_to_yolo,
    detect_dataset_format,
    format_import_progress_message,
    resolve_import_archive_root,
)
from contexts.dataset.infrastructure.dataset_import_yolo import ensure_dataset_yaml, is_standard_yolo_dataset, normalize_yolo_layout
from contexts.dataset.infrastructure.dataset_import_runtime import (
    build_progress_callback,
    emit_import_event,
    get_import_job,
)
from contexts.project.infrastructure.project_paths import (
    get_project_dataset_dir,
)
from shared.utils.fs_utils import move_path, remove_path_silent
from shared.utils.path_utils import resolve_project_path
from shared.utils.zip_utils import safe_extract_zip
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

        abs_project = os.path.join(resolve_project_path(project_path), "")
        dest = get_project_dataset_dir(abs_project, dataset_name)

        temp_dir = tempfile.mkdtemp(prefix=f"vt_proc_{job_id[:8]}_")
        try:
            emit_import_event(job_id, phase="parsing", progress=5, message="解压 zip 包...")
            safe_extract_zip(staging_path, temp_dir)
            emit_import_event(job_id, phase="parsing", progress=20, message="检测数据集格式...")

            dataset_root = resolve_import_archive_root(temp_dir)
            source_format = detect_dataset_format(dataset_root)
            if source_format == "unknown":
                raise ValueError(
                    "无法识别数据集格式：zip 根目录只允许是数据集根目录本身，或仅包一层目录；支持 YOLO（dataset.yaml）、Roboflow（data.yaml）、COCO（annotations/instances_*.json）或 Pascal VOC（Annotations/*.xml + JPEGImages/）"
                )
            emit_import_event(job_id, phase="parsing", progress=30, message=f"检测到 {source_format.upper()} 格式")

            if source_format == "yolo":
                move_path(dataset_root, dest)
                if not is_standard_yolo_dataset(dest):
                    emit_import_event(job_id, phase="converting", progress=60, message="规范化 YOLO 目录布局...")
                    normalize_yolo_layout(dest)
                    emit_import_event(job_id, phase="converting", progress=75, message="写入标准 dataset.yaml...")
                    ensure_dataset_yaml(dest, force=True)
                    if not is_standard_yolo_dataset(dest):
                        raise ValueError("YOLO 数据集未能归一化为项目标准目录协议")
            elif source_format == "roboflow":
                convert_roboflow_to_yolo(
                    dataset_root,
                    dest,
                    progress_cb=build_progress_callback(job, progress_lock, "converting", 30, 95, "ROBOFLOW", format_import_progress_message),
                )
            elif source_format == "coco":
                convert_coco_to_yolo(
                    dataset_root,
                    dest,
                    progress_cb=build_progress_callback(job, progress_lock, "converting", 30, 95, "COCO", format_import_progress_message),
                )
            elif source_format == "voc":
                convert_voc_to_yolo(
                    dataset_root,
                    dest,
                    progress_cb=build_progress_callback(job, progress_lock, "converting", 30, 95, "VOC", format_import_progress_message),
                )
            else:
                raise ValueError(f"未支持的格式: {source_format}")

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
