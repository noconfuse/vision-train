"""管理模型导出任务的创建、执行与删除。"""

import os

from contexts.task.domain.task_types import TASK_TYPE_EXPORT
from contexts.task.domain.task_artifact_keys import (
    ARTIFACT_BEST_WEIGHT_PATH,
    ARTIFACT_EXPORT_PATH,
    ARTIFACT_LOG_PATH,
    ARTIFACT_OUTPUT_DIR,
    ARTIFACT_STOP_SIGNAL_PATH,
    ARTIFACT_TASK_DIR,
)
from contexts.task.infrastructure.task_repository import (
    create_task as start_task,
    update_task as update_task_status,
)
from contexts.task.infrastructure.task_runtime import load_task
from contexts.task.infrastructure.worker_task_ops import (
    build_worker_artifacts,
    finish_worker_task,
    is_stop_requested,
    mark_worker_exited,
    mark_worker_started,
    update_worker_task_progress,
)
from contexts.training.domain.training_constants import WORKFLOW_TYPE_TRAINING
from contexts.training.infrastructure.artifact_scanner import scan_export_outputs, validate_export_request
from contexts.training.infrastructure.execution_context import resolve_task_vision_task_type
from contexts.training.infrastructure.export_runtime import attach_export_progress_callbacks
from contexts.training.infrastructure.runtime_profile import get_device
from contexts.training.infrastructure.training_artifacts import build_training_export_dir
from contexts.training.infrastructure.workflow_repository import ensure_training_workflow_record, touch_training_workflow_record
from shared.infra.worker_process import spawn_worker_process
from shared.utils.fs_utils import move_path, remove_path_silent
from shared.utils.path_utils import is_within_path, project_name_from_path, resolve_storage_path
from shared.utils.time_utils import now_iso
from shared.utils.value_utils import parse_bool
from protocols.task_status import TASK_STATUS_COMPLETED, TASK_STATUS_FAILED, TASK_STATUS_RUNNING, TASK_STATUS_STOPPED, is_active_task_status


def start_export_task(project_path, src_task_id, fmt="onnx", imgsz=640, half=False, int8=False):
    """创建导出任务并启动导出 worker。"""
    src_task = load_task(src_task_id)
    if not src_task or not src_task.get("artifacts", {}).get(ARTIFACT_OUTPUT_DIR):
        raise ValueError("任务或产物不可用")
    workflow_id = src_task.get("workflow_id") or src_task_id
    vision_task_type = resolve_task_vision_task_type(src_task)
    validate_export_request(fmt, half, int8, vision_task_type=vision_task_type)
    ensure_training_workflow_record(
        workflow_id=workflow_id,
        project_path=project_path,
        dataset_name=src_task.get("dataset_name"),
        dataset_path=src_task.get("dataset_path"),
        vision_task_type=vision_task_type,
    )
    source_artifacts = src_task.get("artifacts") or {}
    out_dir = source_artifacts[ARTIFACT_OUTPUT_DIR]
    weight_path = source_artifacts.get(ARTIFACT_BEST_WEIGHT_PATH)
    if not weight_path or not os.path.isfile(weight_path):
        raise ValueError("best.pt 不存在")
    export_task = start_task(
        project_path=project_path,
        project_name=project_name_from_path(project_path),
        type_=TASK_TYPE_EXPORT,
        dataset_name=src_task.get("dataset_name"),
        dataset_path=src_task.get("dataset_path"),
        vision_task_type=vision_task_type,
        payload={
            "src_task_id": src_task_id,
            "weight_path": weight_path,
            "format": fmt,
            "imgsz": imgsz,
            "half": half,
            "int8": int8,
        },
        message=f"导出 {fmt}...",
        artifacts={},
    )
    export_task = update_task_status(
        export_task["id"],
        workflow_id=workflow_id,
        workflow_type=WORKFLOW_TYPE_TRAINING,
    )
    export_dir = build_training_export_dir(out_dir, export_task["id"])
    artifacts = build_worker_artifacts(export_dir, "export-worker.log", "task_worker")
    artifacts[ARTIFACT_EXPORT_PATH] = ""
    update_task_status(export_task["id"], artifacts=artifacts)
    touch_training_workflow_record(workflow_id, dataset_path=src_task.get("dataset_path"), vision_task_type=vision_task_type)
    try:
        proc, _ = spawn_worker_process(export_task["id"], artifacts[ARTIFACT_LOG_PATH], "task_worker")
    except Exception as exc:
        update_task_status(
            export_task["id"],
            status="failed",
            error=str(exc),
            message="导出进程启动失败",
            finished_at=now_iso(),
        )
        raise ValueError(f"导出进程启动失败: {exc}")
    update_task_status(
        export_task["id"],
        started_at=now_iso(),
        status="running",
        progress=0,
        message=f"导出进程已启动，准备导出 {fmt}...",
    )
    mark_worker_started(export_task["id"], proc.pid, "task_worker")
    return {"task_id": export_task["id"], "workflow_id": workflow_id}


def execute_export_task(task_id):
    """执行模型导出并回写导出产物。"""
    task = load_task(task_id)
    if not task or task.get("type") != TASK_TYPE_EXPORT:
        raise ValueError(f"导出任务不存在: {task_id}")
    payload = task.get("payload") or {}
    artifacts = task.get("artifacts") or {}
    stop_signal_path = artifacts.get(ARTIFACT_STOP_SIGNAL_PATH)
    weight_path = resolve_storage_path(payload.get("weight_path")) if payload.get("weight_path") else payload.get("weight_path")
    export_dir = resolve_storage_path(artifacts.get(ARTIFACT_TASK_DIR)) if artifacts.get(ARTIFACT_TASK_DIR) else artifacts.get(ARTIFACT_TASK_DIR)
    if not weight_path or not os.path.isfile(weight_path):
        raise ValueError("导出权重不存在")
    if not export_dir:
        raise ValueError("导出目录不存在")
    mark_worker_started(task_id, os.getpid())
    try:
        from ultralytics import YOLO

        if is_stop_requested(stop_signal_path):
            raise InterruptedError("用户终止导出")
        export_format = payload.get("format", "onnx")
        export_int8 = parse_bool(payload.get("int8", False))
        export_half = parse_bool(payload.get("half", False))
        validate_export_request(
            export_format,
            export_half,
            export_int8,
            vision_task_type=resolve_task_vision_task_type(task),
        )
        update_task_status(task_id, status=TASK_STATUS_RUNNING, progress=max(task.get("progress") or 0, 5), message="正在加载导出模型...")
        model = YOLO(weight_path)
        attach_export_progress_callbacks(
            model,
            task_id=task_id,
            export_format=export_format,
            export_int8=export_int8,
            update_progress=update_worker_task_progress,
        )
        os.makedirs(export_dir, exist_ok=True)
        export_result = model.export(
            format=export_format,
            imgsz=payload.get("imgsz", 640),
            half=export_half,
            int8=export_int8,
            device=get_device(),
            project=os.path.dirname(export_dir),
            name=os.path.basename(export_dir),
        )
        export_path = resolve_storage_path(export_result) if export_result else export_result
        if not export_path:
            raise ValueError("导出产物路径缺失")
        export_path = _normalize_export_output_path(export_path, export_dir)
        files = scan_export_outputs(export_path)
        finish_worker_task(
            task_id,
            TASK_STATUS_COMPLETED,
            "导出完成",
            progress=100,
            artifacts_patch={"files": files, ARTIFACT_EXPORT_PATH: export_path},
            stop_signal_path=stop_signal_path,
        )
    except InterruptedError:
        finish_worker_task(task_id, TASK_STATUS_STOPPED, "导出已终止", stop_signal_path=stop_signal_path)
    except Exception as exc:
        finish_worker_task(task_id, TASK_STATUS_FAILED, "导出失败", error=str(exc), stop_signal_path=stop_signal_path)
    finally:
        mark_worker_exited(task_id)


def _normalize_export_output_path(export_path, export_dir):
    """将导出器生成的真实产物统一收口到当前导出任务目录。"""
    export_dir_real = os.path.realpath(export_dir)
    export_path_real = os.path.realpath(export_path)
    if is_within_path(export_path_real, export_dir_real):
        return export_path_real
    output_dir_real = os.path.realpath(os.path.dirname(os.path.dirname(export_dir_real)))
    if not is_within_path(export_path_real, output_dir_real):
        raise ValueError("导出产物路径不在当前训练输出目录中")
    normalized_path = os.path.join(export_dir_real, os.path.basename(export_path_real.rstrip("/\\")))
    if os.path.realpath(normalized_path) != export_path_real:
        move_path(export_path_real, normalized_path, ensure_parent=True)
    return normalized_path


def delete_export_task(project_path, export_task_id):
    """删除一个已结束的导出任务及其产物目录。"""
    from db import session_scope
    from db.models import Task

    task = load_task(export_task_id)
    if not task or task.get("type") != TASK_TYPE_EXPORT:
        return None
    if task.get("project_path") != project_path:
        raise ValueError("导出记录与当前项目不匹配")
    if is_active_task_status(task.get("status")):
        raise ValueError("导出正在进行中，无法删除")
    project_real = os.path.realpath(project_path)
    artifacts = task.get("artifacts") or {}
    task_dir = resolve_storage_path(artifacts.get(ARTIFACT_TASK_DIR))
    removed_paths = []
    if task_dir:
        real_path = os.path.realpath(task_dir)
        if is_within_path(real_path, project_real):
            if os.path.isdir(real_path) or os.path.isfile(real_path):
                remove_path_silent(real_path)
                removed_paths.append(real_path)
    with session_scope() as session:
        task_row = session.get(Task, export_task_id)
        if not task_row:
            return {"deleted": export_task_id, "removed_paths": removed_paths}
        session.delete(task_row)
    return {"deleted": export_task_id, "removed_paths": removed_paths}
