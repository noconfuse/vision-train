"""部署模板任务的创建、执行与删除入口。"""

import os

from db import session_scope
from db.models import Task

from contexts.task.domain.task_artifact_keys import (
    ARTIFACT_BEST_WEIGHT_PATH,
    ARTIFACT_DATASET_YAML,
    ARTIFACT_EXPORT_PATH,
    ARTIFACT_LAST_WEIGHT_PATH,
    ARTIFACT_LOG_PATH,
    ARTIFACT_STOP_SIGNAL_PATH,
    ARTIFACT_TASK_DIR,
    ARTIFACT_TEMPLATE_DIR,
    ARTIFACT_TEMPLATE_MANIFEST_PATH,
    ARTIFACT_TEMPLATE_SOURCE_FORMAT,
    ARTIFACT_TEMPLATE_SOURCE_MODEL_PATH,
    ARTIFACT_TEMPLATE_TYPE,
)
from contexts.task.domain.task_types import TASK_TYPE_EXPORT, TASK_TYPE_TEMPLATE
from contexts.task.infrastructure.task_repository import (
    create_task as start_task,
    update_task as update_task_status,
)
from contexts.task.infrastructure.task_runtime import (
    list_project_tasks,
    load_task,
)
from contexts.task.infrastructure.worker_task_ops import (
    build_worker_artifacts,
    finish_worker_task,
    is_stop_requested,
    mark_worker_exited,
    mark_worker_started,
    update_worker_task_progress,
)
from contexts.training.domain.training_constants import (
    TRAINING_TEMPLATE_DIRNAME,
    WORKFLOW_TYPE_TRAINING,
)
from contexts.training.infrastructure.execution_context import resolve_task_vision_task_type
from contexts.training.infrastructure.inference_template_gateway import (
    generate_inference_template_bundle,
    normalize_inference_template_type,
    normalize_template_source_format,
    resolve_template_source_path,
)
from contexts.training.infrastructure.training_artifacts import (
    build_training_task_run_dir,
    get_training_best_weight_path,
    get_training_last_weight_path,
)
from contexts.training.infrastructure.workflow_repository import (
    ensure_training_workflow_record,
    touch_training_workflow_record,
)
from shared.infra.worker_process import spawn_worker_process
from shared.utils.fs_utils import remove_path_silent
from shared.utils.path_utils import (
    is_within_path,
    project_name_from_path,
    resolve_storage_path,
)
from shared.utils.time_utils import now_iso
from protocols.task_status import (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_RUNNING,
    TASK_STATUS_STOPPED,
    is_active_task_status,
)


TEMPLATE_SOURCE_CHOICES = (
    {
        "key": "best",
        "label": "最优权重 best.pt",
        "format": "pt",
    },
    {
        "key": "last",
        "label": "最终权重 last.pt",
        "format": "pt",
    },
)


def list_template_source_choices():
    """列出可用的模板源模型选项（仅 PT 权重）。"""
    return [dict(item) for item in TEMPLATE_SOURCE_CHOICES]


def list_template_source_choices_for_task(project_path, training_id):
    """列出模板源选项：PT 权重 + 该训练任务的导出记录。"""
    if not project_path or not training_id:
        return [dict(item) for item in TEMPLATE_SOURCE_CHOICES]
    weight_choices = list_template_source_choices()
    export_choices = _list_export_template_choices(project_path, training_id)
    return weight_choices + export_choices


def _list_export_template_choices(project_path, training_id):
    """汇总导出产物作为模板源选项。"""
    items = list_project_tasks(
        project_path,
        type_=TASK_TYPE_EXPORT,
        limit=200,
        include_archived=True,
    )
    choices = []
    for task in items:
        if task.get("payload", {}).get("src_task_id") != training_id:
            continue
        if task.get("status") != TASK_STATUS_COMPLETED:
            continue
        artifacts = task.get("artifacts") or {}
        export_path = resolve_storage_path(artifacts.get(ARTIFACT_EXPORT_PATH))
        if not export_path:
            continue
        payload = task.get("payload") or {}
        source_format = normalize_template_source_format(payload.get("format") or "onnx")
        primary_model_path = resolve_template_source_path(export_path, source_format)
        if not primary_model_path:
            continue
        choices.append(
            {
                "key": f"export:{task['id']}",
                "label": f"导出：{_format_export_label(payload, task['id'])}",
                "format": source_format,
                "source_model_path": primary_model_path,
                "export_task_id": task["id"],
            }
        )
    return choices


def _format_export_label(payload, fallback_id):
    fmt = str(payload.get("format") or "").strip().lower()
    imgsz = payload.get("imgsz") or ""
    flags = []
    if payload.get("half"):
        flags.append("FP16")
    if payload.get("int8"):
        flags.append("INT8")
    suffix = " · ".join(flags)
    parts = [p for p in (fmt, imgsz) if p]
    if suffix:
        parts.append(suffix)
    if not parts:
        return fallback_id
    return " · ".join(str(item) for item in parts)


def resolve_template_source_selection(selection):
    """根据用户选择解析具体源模型路径与格式。"""
    normalized = str(selection or "").strip().lower()
    if not normalized or normalized == "pt":
        return None
    for choice in TEMPLATE_SOURCE_CHOICES:
        if choice["key"] == normalized:
            return choice
    raise ValueError("不支持的源模型选项")


def start_template_task(
    project_path,
    src_task_id,
    template_type,
    source="best",
    source_format="pt",
    source_model_path=None,
):
    """创建模板生成任务并启动 worker。"""
    src_task = load_task(src_task_id)
    if not src_task or not src_task.get("artifacts", {}).get("output_dir"):
        raise ValueError("任务或产物不可用")
    workflow_id = src_task.get("workflow_id") or src_task_id
    vision_task_type = resolve_task_vision_task_type(src_task)
    ensure_training_workflow_record(
        workflow_id=workflow_id,
        project_path=project_path,
        dataset_name=src_task.get("dataset_name"),
        dataset_id=src_task.get("dataset_id"),
        dataset_version_id=src_task.get("dataset_version_id"),
        dataset_path=src_task.get("dataset_path"),
        vision_task_type=vision_task_type,
    )
    normalized_template_type = normalize_inference_template_type(template_type)
    artifacts = src_task.get("artifacts") or {}

    selected_source_model_path, normalized_format = _resolve_source_model(
        source=source,
        source_format=source_format,
        source_model_path=source_model_path,
        artifacts=artifacts,
    )
    output_dir = artifacts.get("output_dir")

    template_task = start_task(
        project_path=project_path,
        project_name=project_name_from_path(project_path),
        type_=TASK_TYPE_TEMPLATE,
        dataset_name=src_task.get("dataset_name"),
        dataset_id=src_task.get("dataset_id"),
        dataset_version_id=src_task.get("dataset_version_id"),
        dataset_path=src_task.get("dataset_path"),
        vision_task_type=vision_task_type,
        payload={
            "src_task_id": src_task_id,
            "template_type": normalized_template_type,
            "source": source,
            "source_format": normalized_format,
            "source_model_path": selected_source_model_path,
        },
        message=f"正在生成 {normalized_template_type} 部署模板...",
        artifacts={},
    )
    template_task = update_task_status(
        template_task["id"],
        workflow_id=workflow_id,
        workflow_type=WORKFLOW_TYPE_TRAINING,
    )
    task_dir = build_training_task_run_dir(output_dir, TRAINING_TEMPLATE_DIRNAME, template_task["id"])
    worker_artifacts = build_worker_artifacts(task_dir, "template-worker.log", "task_worker")
    worker_artifacts[ARTIFACT_TEMPLATE_DIR] = ""
    worker_artifacts[ARTIFACT_TEMPLATE_MANIFEST_PATH] = ""
    worker_artifacts[ARTIFACT_TEMPLATE_TYPE] = normalized_template_type
    worker_artifacts[ARTIFACT_TEMPLATE_SOURCE_FORMAT] = normalized_format
    worker_artifacts[ARTIFACT_TEMPLATE_SOURCE_MODEL_PATH] = selected_source_model_path
    update_task_status(template_task["id"], artifacts=worker_artifacts)
    touch_training_workflow_record(
        workflow_id,
        dataset_id=src_task.get("dataset_id"),
        dataset_version_id=src_task.get("dataset_version_id"),
        dataset_path=src_task.get("dataset_path"),
        vision_task_type=vision_task_type,
    )
    try:
        proc, _ = spawn_worker_process(template_task["id"], worker_artifacts[ARTIFACT_LOG_PATH], "task_worker")
    except Exception as exc:
        update_task_status(
            template_task["id"],
            status=TASK_STATUS_FAILED,
            error=str(exc),
            message="模板进程启动失败",
            finished_at=now_iso(),
        )
        raise ValueError(f"模板进程启动失败: {exc}")
    update_task_status(
        template_task["id"],
        started_at=now_iso(),
        status=TASK_STATUS_RUNNING,
        progress=0,
        message=f"模板生成已启动，准备生成 {normalized_template_type}...",
    )
    mark_worker_started(template_task["id"], proc.pid, "task_worker")
    return {"task_id": template_task["id"], "workflow_id": workflow_id}


def execute_template_task(task_id):
    """执行模板生成 worker。"""
    task = load_task(task_id)
    if not task or task.get("type") != TASK_TYPE_TEMPLATE:
        raise ValueError(f"模板任务不存在: {task_id}")
    payload = task.get("payload") or {}
    src_task = load_task(payload.get("src_task_id")) if payload.get("src_task_id") else None
    artifacts = task.get("artifacts") or {}
    stop_signal_path = artifacts.get(ARTIFACT_STOP_SIGNAL_PATH)
    task_dir = resolve_storage_path(artifacts.get(ARTIFACT_TASK_DIR)) if artifacts.get(ARTIFACT_TASK_DIR) else artifacts.get(ARTIFACT_TASK_DIR)
    if not task_dir:
        raise ValueError("模板任务目录不存在")
    mark_worker_started(task_id, os.getpid())
    try:
        if is_stop_requested(stop_signal_path):
            raise InterruptedError("用户终止模板生成")

        update_worker_task_progress(task_id, 10, "正在解析源模型...")
        selected_source_model_path, normalized_format = _resolve_source_model(
            source=payload.get("source") or "best",
            source_format=payload.get("source_format") or "pt",
            source_model_path=payload.get("source_model_path"),
            artifacts=(src_task or {}).get("artifacts") or {},
        )

        template_type = normalize_inference_template_type(payload.get("template_type") or "fastapi_service")
        vision_task_type = resolve_task_vision_task_type(src_task or task)
        target_dir = os.path.join(task_dir, template_type)
        dataset_yaml_path = ((src_task or {}).get("artifacts") or {}).get(ARTIFACT_DATASET_YAML)
        training_task_id = (src_task or {}).get("id") or ""

        update_worker_task_progress(task_id, 35, "正在生成模板目录...")
        template_artifact = generate_inference_template_bundle(
            template_type=template_type,
            source_model_path=selected_source_model_path,
            source_format=normalized_format,
            vision_task_type=vision_task_type,
            dataset_yaml_path=dataset_yaml_path,
            training_task_id=training_task_id,
            target_dir=target_dir,
        )
        update_worker_task_progress(task_id, 90, "正在落盘模板产物...")
        finish_worker_task(
            task_id,
            TASK_STATUS_COMPLETED,
            "模板生成完成",
            progress=100,
            artifacts_patch={
                ARTIFACT_TEMPLATE_DIR: template_artifact["template_dir"],
                ARTIFACT_TEMPLATE_MANIFEST_PATH: template_artifact["manifest_path"],
                ARTIFACT_TEMPLATE_TYPE: template_artifact["template_type"],
                ARTIFACT_TEMPLATE_SOURCE_FORMAT: template_artifact["source_format"],
                ARTIFACT_TEMPLATE_SOURCE_MODEL_PATH: template_artifact["source_model_path"],
            },
            stop_signal_path=stop_signal_path,
        )
    except InterruptedError:
        finish_worker_task(task_id, TASK_STATUS_STOPPED, "模板生成已终止", stop_signal_path=stop_signal_path)
    except Exception as exc:
        finish_worker_task(task_id, TASK_STATUS_FAILED, "模板生成失败", error=str(exc), stop_signal_path=stop_signal_path)
    finally:
        mark_worker_exited(task_id)


def delete_template_task(project_path, template_task_id):
    """删除模板任务及其产物目录。"""
    task = load_task(template_task_id)
    if not task or task.get("type") != TASK_TYPE_TEMPLATE:
        return None
    if task.get("project_path") != project_path:
        raise ValueError("模板任务与当前项目不匹配")
    if is_active_task_status(task.get("status")):
        raise ValueError("模板任务正在进行中，无法删除")
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
        task_row = session.get(Task, template_task_id)
        if not task_row:
            return {"deleted": template_task_id, "removed_paths": removed_paths}
        session.delete(task_row)
    return {"deleted": template_task_id, "removed_paths": removed_paths}


def _resolve_source_model(*, source, source_format, source_model_path, artifacts):
    """根据入参解析最终的源模型路径与标准化格式。"""
    normalized_format = normalize_template_source_format(source_format)
    resolved_path = resolve_storage_path(source_model_path) if source_model_path else ""
    if resolved_path and os.path.isfile(resolved_path):
        return resolved_path, normalized_format
    if isinstance(source, str) and source.startswith("export:"):
        export_task_id = source.split(":", 1)[1]
        task = load_task(export_task_id)
        if not task or task.get("status") != TASK_STATUS_COMPLETED:
            raise ValueError("选中的导出任务不可用")
        export_path = resolve_storage_path(
            (task.get("artifacts") or {}).get(ARTIFACT_EXPORT_PATH)
        )
        if not export_path:
            raise ValueError("导出产物路径无效")
        export_format = normalize_template_source_format(
            (task.get("payload") or {}).get("format") or normalized_format
        )
        primary_path = resolve_template_source_path(export_path, export_format)
        if not primary_path:
            raise ValueError("未找到可用的导出模型文件")
        return primary_path, export_format
    choice = resolve_template_source_selection(source) or TEMPLATE_SOURCE_CHOICES[0]
    if choice["key"] == "last":
        weight_path = get_training_last_weight_path(artifacts)
    else:
        weight_path = get_training_best_weight_path(artifacts)
    if not weight_path:
        raise ValueError("源权重不存在")
    return weight_path, choice["format"]