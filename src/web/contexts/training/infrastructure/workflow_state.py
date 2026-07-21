"""聚合训练工作流状态并提炼前端所需的视图字段。"""

from contexts.task.domain.task_types import (
    TASK_TYPE_BATCH_CALIBRATION,
    TASK_TYPE_EVALUATE,
    TASK_TYPE_EXPORT,
    TASK_TYPE_INFERENCE,
    TASK_TYPE_TRAINING,
)
from contexts.training.infrastructure.training_artifacts import resolve_training_resume_weight
from protocols.vision_task_type import VISION_TASK_TYPE_SET
from protocols.task_status import is_active_task_status


def workflow_sort_key(task):
    """Build one comparable timestamp key for workflow task ordering."""
    return (
        task.get('updated_at')
        or task.get('finished_at')
        or task.get('started_at')
        or task.get('created_at')
        or ''
    )


def pick_latest_task(tasks, type_=None):
    """Pick the latest task overall or under one specific type."""
    items = [task for task in (tasks or []) if not type_ or task.get('type') == type_]
    if not items:
        return None
    return sorted(items, key=workflow_sort_key)[-1]


def get_task_resume_info(task):
    """Build the frontend-facing resume availability summary for one training task."""
    if not task or task.get('type') != TASK_TYPE_TRAINING:
        return {'available': False, 'weight': ''}
    weight_name, weight_path = resolve_training_resume_weight(task.get("artifacts") or {})
    return {
        'available': bool(weight_path),
        'weight': weight_name or '',
    }


def build_training_workflow(workflow_record, tasks):
    """Aggregate one workflow record and its related tasks into one workflow view model."""
    workflow_meta = workflow_record or {}
    workflow_id = workflow_meta.get('id')
    ordered_tasks = sorted(tasks, key=lambda item: item.get('created_at') or '')
    latest_task = pick_latest_task(ordered_tasks)
    latest_training_task = pick_latest_task(ordered_tasks, TASK_TYPE_TRAINING)
    latest_calibration_task = pick_latest_task(ordered_tasks, TASK_TYPE_BATCH_CALIBRATION)
    latest_evaluate_task = pick_latest_task(ordered_tasks, TASK_TYPE_EVALUATE)
    latest_inference_task = pick_latest_task(ordered_tasks, TASK_TYPE_INFERENCE)
    export_count = sum(1 for task in ordered_tasks if task.get('type') == TASK_TYPE_EXPORT)
    resume_info = get_task_resume_info(latest_training_task)
    active_tasks = [task for task in ordered_tasks if is_active_task_status(task.get('status'))]
    active_task = sorted(active_tasks, key=workflow_sort_key)[-1] if active_tasks else None
    current_step = 'config'
    step_task = latest_training_task

    if active_task:
        if active_task.get('type') == TASK_TYPE_TRAINING:
            current_step = 'detail'
            step_task = latest_training_task or active_task
        elif active_task.get('type') == TASK_TYPE_BATCH_CALIBRATION:
            current_step = 'detail' if latest_training_task else 'config'
            step_task = latest_training_task
        elif active_task.get('type') == TASK_TYPE_EVALUATE:
            current_step = 'evaluate'
            step_task = latest_training_task
        elif active_task.get('type') == TASK_TYPE_EXPORT:
            current_step = 'export_config'
            step_task = latest_training_task
    elif export_count > 0:
        current_step = 'export_config'
    elif latest_evaluate_task:
        current_step = 'evaluate'
    elif latest_training_task:
        current_step = 'detail'

    workflow_status = (active_task or latest_task or {}).get('status') or 'pending'
    vision_task_type = workflow_meta.get("vision_task_type")
    if vision_task_type not in VISION_TASK_TYPE_SET:
        raise ValueError("训练工作流缺少合法的 vision_task_type")
    return {
        'id': workflow_id,
        'type': TASK_TYPE_TRAINING,
        'project_path': workflow_meta.get('project_path') or (latest_task or {}).get('project_path'),
        'project_name': workflow_meta.get('project_name') or (latest_task or {}).get('project_name'),
        'dataset_name': workflow_meta.get('dataset_name') or (latest_task or {}).get('dataset_name'),
        'dataset_path': workflow_meta.get('dataset_path') or (latest_task or {}).get('dataset_path'),
        'vision_task_type': vision_task_type,
        'status': workflow_status,
        'current_step': current_step,
        'created_at': workflow_meta.get('created_at') or (ordered_tasks[0] if ordered_tasks else {}).get('created_at'),
        'updated_at': workflow_sort_key(latest_task) if latest_task else workflow_meta.get('updated_at'),
        'archived_at': workflow_meta.get('archived_at'),
        'is_archived': bool(workflow_meta.get('archived_at')),
        'active_task': active_task,
        'latest_task': latest_task,
        'latest_training_task': latest_training_task,
        'latest_training_task_resume_available': resume_info['available'],
        'latest_training_task_resume_weight': resume_info['weight'],
        'latest_calibration_task': latest_calibration_task,
        'latest_evaluate_task': latest_evaluate_task,
        'latest_inference_task': latest_inference_task,
        'step_task': step_task,
        'summary': {
            'training_count': sum(1 for task in ordered_tasks if task.get('type') == TASK_TYPE_TRAINING),
            'calibration_count': sum(1 for task in ordered_tasks if task.get('type') == TASK_TYPE_BATCH_CALIBRATION),
            'evaluate_count': sum(1 for task in ordered_tasks if task.get('type') == TASK_TYPE_EVALUATE),
            'export_count': export_count,
            'inference_count': sum(1 for task in ordered_tasks if task.get('type') == TASK_TYPE_INFERENCE),
        },
        'tasks': {
            'training': [task for task in ordered_tasks if task.get('type') == TASK_TYPE_TRAINING],
            'batch_calibration': [task for task in ordered_tasks if task.get('type') == TASK_TYPE_BATCH_CALIBRATION],
            'evaluate': [task for task in ordered_tasks if task.get('type') == TASK_TYPE_EVALUATE],
            'export': [task for task in ordered_tasks if task.get('type') == TASK_TYPE_EXPORT],
            'inference': [task for task in ordered_tasks if task.get('type') == TASK_TYPE_INFERENCE],
        },
    }
