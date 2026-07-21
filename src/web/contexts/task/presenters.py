"""将任务记录转换为对外稳定的接口 DTO。"""

from shared.utils.path_utils import storage_path_ref


def _build_task_capabilities_snapshot(task):
    """仅为带视觉任务类型的任务补充训练链能力快照。"""
    vision_task_type = (task or {}).get("vision_task_type")
    if not vision_task_type:
        return None
    from contexts.training.domain.capability_snapshot import build_training_capabilities_snapshot

    return build_training_capabilities_snapshot(vision_task_type)


def present_task(task):
    """把内部任务记录映射为对外返回结构。"""
    if not task:
        return task
    item = dict(task)
    if item.get("project_path"):
        item["project_path"] = storage_path_ref(item["project_path"])
    if item.get("dataset_path"):
        item["dataset_path"] = storage_path_ref(item["dataset_path"])
    snapshot = _build_task_capabilities_snapshot(item)
    if snapshot:
        item["capabilities_snapshot"] = snapshot
    return item


def present_tasks(tasks):
    """批量映射任务记录列表。"""
    return [present_task(task) for task in (tasks or [])]
