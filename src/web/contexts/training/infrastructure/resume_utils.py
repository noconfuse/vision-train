"""提供训练恢复（续跑）所需的任务、权重与参数解析逻辑。"""

from contexts.task.application.task_service import load_task
from contexts.training.infrastructure.training_artifacts import resolve_training_resume_weight
from protocols.task_type import TASK_TYPE_TRAINING


def _resolve_training_starter(training_starter):
    """解析恢复训练使用的启动器，默认落到标准训练启动函数。"""
    if training_starter:
        return training_starter
    from contexts.training.infrastructure.execution_starters import start_training_task

    return start_training_task


def _resume_training_config(task):
    """取被续任务存下的训练参数，这是续训参数的唯一来源。"""
    training_config = (task.get("payload") or {}).get("training_config") or {}
    if not training_config:
        raise ValueError("原训练任务没有留存训练参数")
    return training_config


def resume_training(project_path, dataset_name, task_id, training_starter=None):
    """按任务标识续跑训练：权重与训练参数都取自该任务的历史记录。"""
    training_starter = _resolve_training_starter(training_starter)
    task = load_task(task_id)
    if not task:
        raise ValueError("任务不存在或产物不可用")
    if task.get("project_path") != project_path:
        raise ValueError("任务不属于当前项目")
    if task.get("type") != TASK_TYPE_TRAINING:
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
        _resume_training_config(task),
        dataset_path=task.get("dataset_path"),
        workflow_id=task.get("workflow_id") or task["id"],
        resume_from_task_id=task["id"],
        resume_weight=resume_weight_name,
        model_path=resume_weight_path,
    )
    result["resume_weight"] = resume_weight_name
    return result
