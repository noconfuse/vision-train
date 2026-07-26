"""暴露训练上下文的只读查询入口。"""

from db import session_scope
from db.models import Task

from contexts.task.domain.task_artifact_keys import (
    ARTIFACT_TEMPLATE_DIR,
    ARTIFACT_TEMPLATE_MANIFEST_PATH,
    ARTIFACT_TEMPLATE_TYPE,
)
from contexts.task.domain.task_types import TASK_TYPE_TEMPLATE
from contexts.task.infrastructure.task_repository import get_task_history as list_task_history
from contexts.task.infrastructure.task_runtime import load_task
from contexts.training.infrastructure.execution_support import get_batch_calibration as load_batch_calibration
from contexts.training.infrastructure.inference_template_gateway import list_inference_template_specs
from contexts.training.infrastructure.query_gateway import (
    get_training_artifacts,
    get_training_model_exports,
    get_training_run_artifacts,
)
from contexts.training.infrastructure.runtime_profile import build_runtime_profile
from contexts.training.infrastructure.test_dirs import list_training_test_dirs
from contexts.training.infrastructure.workflow_repository import (
    get_training_workflow as get_training_workflow_record,
    list_training_workflows as list_training_workflow_records,
)
from contexts.training.presenters import build_bundle_name
from protocols.task_status import is_active_task_status
from shared.utils.path_utils import resolve_allowed_dir_path


def get_training_model_export_bundle_info(project_path, export_dir_ref):
    """解析训练导出目录并返回打包所需信息。"""
    export_real = resolve_allowed_dir_path(export_dir_ref, allowed_roots=[project_path])
    return {
        "export_real": export_real,
        "bundle_name": build_bundle_name(export_real),
    }


def get_training_model_template_bundle_info(project_path, template_task_ref):
    """解析模板任务对应的部署目录并返回打包信息。"""
    template_real = resolve_allowed_dir_path(template_task_ref, allowed_roots=[project_path])
    return {
        "template_real": template_real,
        "bundle_name": build_bundle_name(template_real),
    }


def list_training_template_tasks(project_path, training_id):
    """汇总一个训练任务下所有部署模板任务。"""
    if not project_path or not training_id:
        return []
    with session_scope() as session:
        rows = (
            session.query(Task)
            .filter(
                Task.project_path == project_path,
                Task.type == TASK_TYPE_TEMPLATE,
                Task.payload.like(f'%\"src_task_id\": \"{training_id}\"%'),
            )
            .order_by(Task.created_at.desc())
            .all()
        )
        return [row.to_dict() for row in rows]


def has_active_template_task(project_path, training_id):
    """检查训练任务是否还有进行中的模板任务。"""
    for item in list_training_template_tasks(project_path, training_id):
        if is_active_task_status(item.get("status")):
            return True
    return False


def list_training_template_records_for_task(project_path, training_id):
    """把模板任务渲染为前端可直接消费的 DTO 列表。"""
    specs = {item["template_type"]: item for item in list_inference_template_specs()}
    records = []
    for item in list_training_template_tasks(project_path, training_id):
        artifacts = item.get("artifacts") or {}
        payload = item.get("payload") or {}
        template_type = str(payload.get("template_type") or artifacts.get(ARTIFACT_TEMPLATE_TYPE) or "").strip().lower()
        spec = specs.get(template_type) or {}
        template_dir = artifacts.get(ARTIFACT_TEMPLATE_DIR) or ""
        template_manifest = artifacts.get(ARTIFACT_TEMPLATE_MANIFEST_PATH) or ""
        records.append(
            {
                "task_id": item.get("id"),
                "status": item.get("status"),
                "message": item.get("message"),
                "error": item.get("error"),
                "progress": item.get("progress"),
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "finished_at": item.get("finished_at"),
                "source_format": payload.get("source_format") or artifacts.get("template_source_format") or "",
                "source": payload.get("source") or "best",
                "template_type": template_type,
                "template_label": spec.get("label") or template_type,
                "template_description": spec.get("description") or "",
                "runtime_mode": spec.get("runtime_mode") or "",
                "entrypoint": spec.get("entrypoint") or "",
                "template_dir": template_dir,
                "template_manifest_path": template_manifest,
                "template_bundle_url": (
                    f"/api/training/model_template_bundle?project_path={project_path}&template_task_id={item.get('id')}"
                    if template_dir
                    else None
                ),
            }
        )
    return records


__all__ = [
    "build_runtime_profile",
    "get_training_artifacts",
    "get_training_model_export_bundle_info",
    "get_training_model_template_bundle_info",
    "get_training_model_exports",
    "get_training_run_artifacts",
    "get_training_workflow_record",
    "has_active_template_task",
    "list_task_history",
    "list_template_source_choices",
    "list_training_template_source_choices",
    "list_training_template_records_for_task",
    "list_training_template_tasks",
    "list_training_test_dirs",
    "list_training_workflow_records",
    "load_batch_calibration",
]


TEMPLATE_SOURCE_CHOICES = (
    {"key": "best", "label": "最优权重 best.pt", "format": "pt"},
    {"key": "last", "label": "最终权重 last.pt", "format": "pt"},
)


def list_template_source_choices():
    """列出可用的模板源模型选项（前端可调用）。"""
    return [dict(item) for item in TEMPLATE_SOURCE_CHOICES]


def list_training_template_source_choices(project_path, training_id):
    """列出训练任务下可用的模板源选项（权重 + 导出）。"""
    from contexts.training.infrastructure.template_task_gateway import (
        list_template_source_choices_for_task,
    )

    return list_template_source_choices_for_task(project_path, training_id)