"""暴露训练上下文的只读查询入口。"""

from contexts.task.infrastructure.task_repository import get_task_history as list_task_history
from contexts.training.infrastructure.execution_support import get_batch_calibration as load_batch_calibration
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
from shared.utils.path_utils import resolve_allowed_dir_path


def get_training_model_export_bundle_info(project_path, export_dir_ref):
    """解析训练导出目录并返回打包所需信息。"""
    export_real = resolve_allowed_dir_path(export_dir_ref, allowed_roots=[project_path])
    return {
        "export_real": export_real,
        "bundle_name": build_bundle_name(export_real),
    }


__all__ = [
    "build_runtime_profile",
    "get_training_artifacts",
    "get_training_model_export_bundle_info",
    "get_training_model_exports",
    "get_training_run_artifacts",
    "get_training_workflow_record",
    "list_task_history",
    "list_training_test_dirs",
    "list_training_workflow_records",
    "load_batch_calibration",
]
