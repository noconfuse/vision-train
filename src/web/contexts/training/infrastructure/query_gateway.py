"""集中封装训练产物、导出记录与最近任务查询。"""

from contexts.task.domain.task_artifact_keys import ARTIFACT_OUTPUT_DIR
from contexts.task.domain.task_types import TASK_TYPE_EXPORT, TASK_TYPE_TRAINING
from contexts.task.infrastructure.task_runtime import list_project_tasks, load_task
from contexts.training.infrastructure.artifact_scanner import scan_training_run_artifacts
from contexts.training.presenters import list_training_export_records, present_run_artifacts, present_task_artifacts
from shared.utils.value_utils import require_present


def _load_project_task(project_path, task_id):
    """读取任务并校验其归属于当前项目。"""
    task = load_task(task_id)
    if not task:
        return None
    if task.get("project_path") != project_path:
        raise ValueError("任务不属于当前项目")
    return task


def get_training_run_artifacts(project_path, task_id):
    """返回指定训练运行的图片、权重与配置产物。"""
    require_present(project_path=project_path, task_id=task_id)
    task = _load_project_task(project_path, task_id)
    if not task:
        return present_run_artifacts({"images": [], "weights": [], "config": None})
    out_dir = (task.get("artifacts") or {}).get(ARTIFACT_OUTPUT_DIR, "")
    return present_run_artifacts(scan_training_run_artifacts(out_dir))


def get_training_artifacts(project_path, task_id=None):
    """返回指定任务或最近训练任务的通用产物索引。"""
    require_present("缺少项目路径", project_path=project_path)
    out_dir = ""
    if task_id:
        task = _load_project_task(project_path, task_id)
        if not task:
            return {}
        out_dir = (task.get("artifacts") or {}).get(ARTIFACT_OUTPUT_DIR, "")
    else:
        items = list_project_tasks(project_path, type_=TASK_TYPE_TRAINING, limit=1)
        task = items[0] if items else None
        out_dir = ((task or {}).get("artifacts") or {}).get(ARTIFACT_OUTPUT_DIR, "")
    return present_task_artifacts(out_dir)


def get_training_model_exports(project_path, task_id=None, training_id=None):
    """返回指定训练任务的导出记录列表。"""
    task_id = task_id or training_id
    if not project_path or not task_id:
        return []
    training_task = _load_project_task(project_path, task_id)
    output_dir = ((training_task or {}).get("artifacts") or {}).get(ARTIFACT_OUTPUT_DIR)
    if not output_dir:
        return []
    export_tasks = list_project_tasks(project_path, type_=TASK_TYPE_EXPORT, limit=1000, include_archived=True)
    export_tasks_by_id = {
        item.get("id"): item for item in export_tasks if item.get("payload", {}).get("src_task_id") == task_id
    }
    return list_training_export_records(project_path, task_id, output_dir, export_tasks_by_id)
