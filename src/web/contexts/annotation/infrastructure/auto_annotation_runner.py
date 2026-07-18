"""执行单张和批量自动标注任务并回写任务状态。"""

import os
import threading

from task_status import TASK_STATUS_COMPLETED, TASK_STATUS_FAILED, TASK_STATUS_RUNNING

from contexts.annotation.domain.services import filter_duplicate_boxes
from contexts.annotation.infrastructure.annotation_io import (
    decode_yolo_file,
    get_dataset_root,
    get_image_size_fallback as get_annotation_image_size,
)
from contexts.annotation.infrastructure.batch_helpers import (
    append_auto_label_boxes,
    build_auto_label_path,
    extract_prediction_boxes,
    list_batch_image_paths,
    load_existing_manual_boxes,
)
from contexts.annotation.infrastructure.model_gateway import get_auto_annotate_model
from contexts.annotation.infrastructure.openvino_gateway import predict_openvino_boxes
from contexts.model.infrastructure.model_catalog import pick_openvino_xml
from contexts.task.infrastructure.task_repository import (
    create_task as start_task,
    update_task as update_task_status,
)
from contexts.task.infrastructure.task_runtime import list_tasks as list_task_items, load_task
from shared.utils.path_utils import project_name_from_path, resolve_storage_path
from shared.utils.time_utils import now_iso
from shared.utils.value_utils import require_present


def auto_annotate_image(project_path, image_ref, model_path=None, conf=0.25, max_det=200):
    """对单张图片执行模型推理并返回检测框。"""
    image_path = resolve_storage_path(image_ref)
    require_present("缺少图片路径", image_path=image_path)
    if not os.path.isfile(image_path):
        raise ValueError("图片不存在")

    ov_xml = pick_openvino_xml(model_path) if model_path else None
    if ov_xml:
        result = predict_openvino_boxes(ov_xml, [image_path], conf=float(conf), max_det=int(max_det))
        return result[0] if result else []

    from ultralytics import YOLO

    if model_path:
        model = YOLO(model_path)
    else:
        model = get_auto_annotate_model(project_path, prefer_project_best=True)
    if model is None:
        raise ValueError("模型不可用")

    results = model.predict(image_path, conf=float(conf), max_det=int(max_det), verbose=False)
    boxes = []
    for prediction in results:
        for box in prediction.boxes:
            xyxy = box.xyxy[0].tolist()
            cls = int(box.cls.item()) if hasattr(box, "cls") else 0
            boxes.append({"class": cls, "x1": xyxy[0], "y1": xyxy[1], "x2": xyxy[2], "y2": xyxy[3]})
    return boxes


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
    require_present(project_path=project_path, dataset_name=dataset_name)

    project_name = project_name_from_path(project_path)
    dataset_root = get_dataset_root(project_path, dataset_name)
    task = start_task(
        project_path=project_path,
        project_name=project_name,
        type_="auto_annotation",
        dataset_name=dataset_name,
        dataset_path=dataset_root,
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
            ov_xml = pick_openvino_xml(model_path) if model_path else None
            use_openvino = bool(ov_xml)
            model = None
            if not use_openvino:
                from ultralytics import YOLO

                if model_path:
                    model = YOLO(model_path)
                else:
                    model = get_auto_annotate_model(project_path, prefer_project_best=True)
            if model is None and not use_openvino:
                raise ValueError("模型不可用")

            ds_root = dataset_root
            img_dir = os.path.join(ds_root, split, "images")
            lbl_dir = os.path.join(ds_root, "auto_labels", split)
            os.makedirs(lbl_dir, exist_ok=True)

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
                if use_openvino:
                    results = predict_openvino_boxes(ov_xml, batch, conf=conf, max_det=max_det)
                else:
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
                    auto_label_path = build_auto_label_path(img_dir, lbl_dir, image_path)
                    boxes = extract_prediction_boxes(result, use_openvino=use_openvino)
                    if not boxes:
                        continue
                    width, height = get_annotation_image_size(image_path)
                    rel_noext = os.path.splitext(os.path.relpath(image_path, img_dir))[0]
                    existing_manual = load_existing_manual_boxes(ds_root, split, rel_noext, width, height)
                    existing_auto = decode_yolo_file(auto_label_path, width, height)
                    filtered = filter_duplicate_boxes(boxes, existing_manual, existing_auto, float(iou_thresh))
                    if not filtered:
                        continue
                    try:
                        append_auto_label_boxes(auto_label_path, filtered, width, height)
                        added += len(filtered)
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
                message=f"完成（新增 {added} 个框 / {pending} 张图）",
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
