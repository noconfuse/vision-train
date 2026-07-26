"""执行单张和批量自动标注任务并回写任务状态。"""

import os
import threading

from protocols.task_status import TASK_STATUS_COMPLETED, TASK_STATUS_FAILED, TASK_STATUS_RUNNING

from contexts.annotation.infrastructure.annotation_io import (
    build_dataset_image_context,
    get_dataset_root,
)
from contexts.dataset.infrastructure.dataset_schema import find_dataset_config
from contexts.dataset.infrastructure.dataset_task_type import load_dataset_vision_task_type
from contexts.annotation.infrastructure.batch_helpers import list_batch_image_paths
from contexts.annotation.infrastructure.annotation_task_strategy import resolve_annotation_task_strategy
from contexts.task.infrastructure.task_repository import (
    create_task as start_task,
    update_task as update_task_status,
)
from contexts.task.infrastructure.task_runtime import list_tasks as list_task_items, load_task
from shared.utils.path_utils import project_name_from_path, resolve_storage_path
from shared.utils.time_utils import now_iso


def _find_dataset_root_for_image(project_path, image_path):
    """在项目目录内自下而上定位图片所属的数据集根目录。"""
    current_dir = os.path.dirname(resolve_storage_path(image_path) or image_path)
    project_path = os.path.realpath(project_path)
    while current_dir and os.path.realpath(current_dir).startswith(project_path):
        if find_dataset_config(current_dir):
            return current_dir
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            break
        current_dir = parent_dir
    raise ValueError("无法根据图片路径定位所属数据集")


def auto_annotate_image(project_path, image_ref, model_path=None, conf=0.25, max_det=200):
    """对单张图片执行模型推理并返回当前任务类型对应的自动标注结果。"""
    image_path = resolve_storage_path(image_ref)
    if not os.path.isfile(image_path):
        raise ValueError("图片不存在")
    dataset_root = _find_dataset_root_for_image(project_path, image_path)
    vision_task_type = load_dataset_vision_task_type(dataset_root)
    strategy = resolve_annotation_task_strategy(vision_task_type)

    from ultralytics import YOLO

    model = YOLO(model_path)
    if model is None:
        raise ValueError("模型不可用")

    results = model.predict(image_path, conf=float(conf), max_det=int(max_det), verbose=False)
    prediction = results[0] if results else None
    return strategy.extract_auto_annotation(prediction) if prediction is not None else {}


def get_batch_auto_annotation_status(task_id=None):
    """返回批量自动标注任务的对外状态摘要。"""
    task = None
    if task_id:
        task = load_task(task_id)
        if not task or task.get("type") != "auto_annotation":
            raise ValueError("自动标注任务不存在")
    else:
        tasks = list_task_items(type_="auto_annotation", limit=20)
        task = next((item for item in tasks if item.get("type") == "auto_annotation"), None)
        if not task:
            return {"task_id": None, "is_running": False, "progress": 0, "message": "", "added": 0, "pending": 0}

    artifacts = task.get("artifacts") or {}
    status = task.get("status")
    return {
        "task_id": task.get("id"),
        "status": status,
        "is_running": status in (TASK_STATUS_RUNNING,),
        "progress": int(task.get("progress") or 0),
        "message": task.get("message") or "",
        "error": task.get("error"),
        "added": int(artifacts.get("added") or 0),
        "pending": int(artifacts.get("pending") or 0),
    }


def start_batch_auto_annotation(
    project_path,
    dataset_name,
    split="train",
    model_path=None,
    image_paths=None,
    conf=0.25,
    max_det=200,
    batch_size=1,
    iou_thresh=0.5,
):
    """创建批量自动标注任务并启动后台线程。"""
    project_name = project_name_from_path(project_path)
    dataset_root = get_dataset_root(project_path, dataset_name)
    vision_task_type = load_dataset_vision_task_type(dataset_root)
    strategy = resolve_annotation_task_strategy(vision_task_type)
    if not strategy.supports_auto_annotation:
        raise ValueError("当前任务类型暂不支持自动标注")
    task = start_task(
        project_path=project_path,
        project_name=project_name,
        type_="auto_annotation",
        dataset_name=dataset_name,
        dataset_path=dataset_root,
        vision_task_type=vision_task_type,
        payload={
            "split": split,
            "model_path": model_path,
            "conf": conf,
            "max_det": max_det,
            "batch_size": batch_size,
            "iou_thresh": iou_thresh,
            "image_count": len(image_paths) if isinstance(image_paths, list) else None,
        },
        message="启动批量自动标注...",
    )
    task_id = task["id"]
    update_task_status(task_id, status=TASK_STATUS_RUNNING, started_at=now_iso())

    def run_batch():
        """批量推理图片、去重结果并持续更新任务进度。"""
        added = 0
        pending = 0
        try:
            from ultralytics import YOLO

            model = YOLO(model_path)
            if model is None:
                raise ValueError("模型不可用")

            img_dir = strategy.get_auto_annotation_image_dir(dataset_root, split)
            resolved_image_paths = [resolve_storage_path(path) for path in (image_paths or [])]
            images = list_batch_image_paths(img_dir, image_paths=resolved_image_paths)
            total = len(images)
            update_task_status(
                task_id,
                progress=0,
                message=f"执行批量自动标注（{total} 张）",
                payload={**(task.get("payload", {}) or {}), "image_count": total},
            )

            for index in range(0, len(images), int(batch_size)):
                batch = images[index : index + int(batch_size)]
                try:
                    results = model.predict(batch, conf=float(conf), max_det=int(max_det), verbose=False)
                except Exception as exc:
                    update_task_status(
                        task_id,
                        status=TASK_STATUS_FAILED,
                        error=str(exc),
                        message=f"推理失败: {exc}",
                        finished_at=now_iso(),
                    )
                    return

                for batch_index, result in enumerate(results):
                    image_path = batch[batch_index]
                    context = build_dataset_image_context(dataset_root, split, image_path)
                    annotation = strategy.extract_auto_annotation(result)
                    refined_annotation = strategy.refine_auto_annotation(context, annotation, float(iou_thresh))
                    if not strategy.has_auto_annotation_content(refined_annotation):
                        continue
                    try:
                        strategy.save_auto_annotation(context, refined_annotation)
                        added += strategy.count_auto_annotation_items(refined_annotation)
                        pending += 1
                    except Exception:
                        pass

                update_task_status(
                    task_id,
                    progress=int((index + len(batch)) / total * 100) if total else 100,
                    message=f"已处理 {min(index + len(batch), total)}/{total}",
                    artifacts={"added": added, "pending": pending},
                )

            update_task_status(
                task_id,
                status=TASK_STATUS_COMPLETED,
                progress=100,
                message=f"完成（新增 {added} 条自动标注 / {pending} 张图）",
                finished_at=now_iso(),
                artifacts={"added": added, "pending": pending},
            )
        except Exception as exc:
            update_task_status(
                task_id,
                status=TASK_STATUS_FAILED,
                error=str(exc),
                message=f"出错: {exc}",
                finished_at=now_iso(),
            )

    thread = threading.Thread(target=run_batch, name="auto-annot", daemon=True)
    thread.start()
    return {"task_id": task_id}
