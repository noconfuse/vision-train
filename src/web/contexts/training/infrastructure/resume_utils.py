"""提供训练续跑和恢复训练所需的任务与权重解析逻辑。"""

from contexts.task.domain.task_types import TASK_TYPE_TRAINING
from contexts.task.infrastructure.task_runtime import list_project_tasks, load_task
from contexts.training.infrastructure.training_artifacts import resolve_training_resume_weight


def start_resume_training(project_path, dataset_name, task, training_config, training_starter):
    """复用历史任务的权重和参数启动恢复训练。"""
    if not task or task.get("type") != TASK_TYPE_TRAINING:
        raise ValueError("训练任务不存在或类型不匹配")
    model_name = ((task.get("payload") or {}).get("model_name") or "").strip()
    if not model_name:
        raise ValueError("原始训练任务缺少模型名")
    resume_weight_name, resume_weight_path = resolve_training_resume_weight(task.get("artifacts") or {})
    if not resume_weight_path:
        raise ValueError("可恢复权重不存在")
    result = training_starter(
        project_path,
        dataset_name,
        model_name,
        training_config,
        dataset_path=task.get("dataset_path"),
        workflow_id=task.get("workflow_id") or task["id"],
        resume_from_task_id=task["id"],
        resume_weight=resume_weight_name,
        model_path=resume_weight_path,
    )
    result["resume_weight"] = resume_weight_name
    return result


def _resolve_training_starter(training_starter):
    """解析恢复训练使用的启动器，默认落到标准训练启动函数。"""
    if training_starter:
        return training_starter
    from contexts.training.infrastructure.execution_starters import start_training_task

    return start_training_task


def continue_training(project_path, dataset_name, training_config, training_starter=None):
    """查找最近可恢复的训练任务并启动续训。"""
    training_starter = _resolve_training_starter(training_starter)
    task = None
    for item in list_project_tasks(project_path, type_=TASK_TYPE_TRAINING, dataset_name=dataset_name, limit=20):
        _resume_weight_name, resume_weight_path = resolve_training_resume_weight(item.get("artifacts") or {})
        if resume_weight_path:
            task = item
            break
    if not task:
        raise ValueError("找不到可继续的运行（缺少可恢复权重）")
    return start_resume_training(project_path, dataset_name, task, training_config, training_starter)


def resume_training(project_path, dataset_name, task_id, training_config, training_starter=None):
    """按任务标识恢复指定训练任务。"""
    training_starter = _resolve_training_starter(training_starter)
    task = load_task(task_id)
    if not task:
        raise ValueError("任务不存在或产物不可用")
    if task.get("project_path") != project_path:
        raise ValueError("任务不属于当前项目")
    return start_resume_training(project_path, dataset_name, task, training_config, training_starter)
