"""将任务记录转换为对外稳定的接口 DTO。"""

from shared.utils.path_utils import storage_path_ref


def present_task(task):
    """把内部任务记录映射为对外返回结构。"""
    if not task:
        return task
    item = dict(task)
    if item.get("project_path"):
        item["project_path"] = storage_path_ref(item["project_path"])
    if item.get("dataset_path"):
        item["dataset_path"] = storage_path_ref(item["dataset_path"])
    return item


def present_tasks(tasks):
    """批量映射任务记录列表。"""
    return [present_task(task) for task in (tasks or [])]
