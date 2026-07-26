"""将训练相关产物和导出结果转换为前端展示数据。"""

import os
from urllib.parse import quote

from contexts.task.domain.task_artifact_keys import ARTIFACT_EXPORT_PATH
from contexts.task.presenters import present_task, present_tasks
from contexts.training.domain.capability_snapshot import build_training_capabilities_snapshot
from contexts.training.infrastructure.artifact_scanner import scan_export_outputs, scan_training_run_artifacts
from shared.utils.path_utils import build_file_item, build_file_items, storage_path_ref


def present_run_artifacts(artifacts):
    """将训练运行产物转换为前端可访问链接。"""
    return {
        "images": build_file_items(artifacts.get("images", [])),
        "weights": build_file_items(artifacts.get("weights", [])),
        "config": build_file_item(artifacts["config"]) if artifacts.get("config") else None,
    }


def present_task_artifacts(output_dir):
    """将任务产物索引补齐为可访问的 URL 结构。"""
    artifacts = scan_training_run_artifacts(output_dir) if output_dir else {"images": [], "weights": [], "config": None}
    result = {}
    for key, value in artifacts.items():
        if value and isinstance(value, str) and os.path.exists(value):
            result[key] = build_file_item(value)
        elif value and isinstance(value, list) and value and os.path.exists(value[0]):
            result[key] = build_file_items(value)
        else:
            result[key] = value
    return result


def build_export_bundle_url(project_path, export_root):
    """生成导出目录打包下载地址。"""
    return (
        f"/api/training/model_export_bundle?project_path={quote(storage_path_ref(project_path), safe='')}"
        f"&export_dir={quote(storage_path_ref(export_root), safe='')}"
    )


def present_training_workflow_record(workflow_record):
    """把工作流记录映射为对外返回结构。"""
    if not workflow_record:
        return workflow_record
    item = dict(workflow_record)
    if item.get("project_path"):
        item["project_path"] = storage_path_ref(item["project_path"])
    if item.get("dataset_path"):
        item["dataset_path"] = storage_path_ref(item["dataset_path"])
    if item.get("vision_task_type"):
        item["capabilities_snapshot"] = build_training_capabilities_snapshot(item["vision_task_type"])
    return item


def present_training_workflow(workflow):
    """把聚合后的工作流视图映射为对外稳定 DTO。"""
    if not workflow:
        return workflow
    item = present_training_workflow_record(workflow)
    for key in (
        "active_task",
        "latest_task",
        "latest_training_task",
        "latest_calibration_task",
        "latest_evaluate_task",
        "latest_inference_task",
        "step_task",
    ):
        item[key] = present_task(item.get(key))
    task_groups = dict(item.get("tasks") or {})
    for key, value in task_groups.items():
        task_groups[key] = present_tasks(value)
    item["tasks"] = task_groups
    return item


def build_export_record(project_path, training_task_id, export_dir, export_task):
    """组装单个导出任务的展示记录。"""
    export_status = (export_task or {}).get("status")
    task_artifacts = (export_task or {}).get("artifacts") or {}
    task_payload = (export_task or {}).get("payload") or {}
    export_path = ""
    scan_root = export_dir
    raw_files = []
    relative_base = export_dir
    bundle_root = export_dir
    if export_status == "completed":
        export_path = task_artifacts.get(ARTIFACT_EXPORT_PATH) or ""
        scan_root = export_path or export_dir
        raw_files = scan_export_outputs(scan_root)
        relative_base = scan_root if os.path.isdir(scan_root) else os.path.dirname(scan_root)
        bundle_root = scan_root if os.path.isdir(scan_root) else export_dir

    files = build_file_items(raw_files, relative_to=relative_base)

    primary_model = next((item for item in files if item["name"].endswith((".onnx", ".xml", ".engine"))), None)
    return {
        "training_id": training_task_id,
        "export_task_id": (export_task or {}).get("id") or os.path.basename(export_dir),
        "status": export_status,
        "message": (export_task or {}).get("message"),
        "error": (export_task or {}).get("error"),
        "payload": task_payload,
        "created_at": (export_task or {}).get("created_at"),
        "updated_at": (export_task or {}).get("updated_at"),
        "export_dir": storage_path_ref(export_dir),
        "export_path": storage_path_ref(export_path) if export_path else "",
        "primary_model_path": (primary_model or {}).get("path", ""),
        "primary_model_url": (primary_model or {}).get("url"),
        "bundle_url": build_export_bundle_url(project_path, bundle_root) if export_status == "completed" and bundle_root else None,
        "files": files,
        "total_size_bytes": sum(item["size_bytes"] for item in files),
    }


def list_training_export_records(project_path, training_task_id, output_dir, export_tasks_by_id):
    """汇总训练输出目录下的导出记录。"""
    export_root = os.path.join(output_dir, "export")
    if not os.path.isdir(export_root):
        return []
    exports = []
    for name in os.listdir(export_root):
        export_dir = os.path.join(export_root, name)
        if not os.path.isdir(export_dir):
            continue
        exports.append(build_export_record(project_path, training_task_id, export_dir, export_tasks_by_id.get(name)))
    return exports


def build_bundle_name(export_dir):
    """生成导出压缩包文件名。"""
    export_name = os.path.basename(export_dir.rstrip("/\\")) or "export"
    parent_name = os.path.basename(os.path.dirname(export_dir.rstrip("/\\"))) or "model-export"
    return f"{parent_name}-{export_name}"
