"""编排标注读写与标注列表查询的应用层用例。"""

from contexts.annotation.infrastructure.auto_annotation_runner import (
    auto_annotate_image as run_auto_annotate_image,
    get_batch_auto_annotation_status as read_batch_auto_annotation_status,
    start_batch_auto_annotation as run_batch_auto_annotation,
)
from contexts.annotation.infrastructure.annotation_task_strategy import resolve_annotation_task_strategy
from contexts.annotation.infrastructure.annotation_io import get_dataset_root, resolve_dataset_image_context
from contexts.dataset.infrastructure.dataset_task_type import load_dataset_vision_task_type
from contexts.annotation.infrastructure.segment_refine import (
    refine_polygon_with_grabcut,
    refine_polygon_boundary_patch,
    erase_polygon_with_stroke,
)
from protocols.vision_task_type import VISION_TASK_TYPE_SEGMENT


def _resolve_annotation_image_strategy(project_path, dataset_name, split, image_ref):
    """先解析图片上下文，再返回与该上下文匹配的标注策略。"""
    context = resolve_dataset_image_context(project_path, dataset_name, split, image_ref)
    strategy = resolve_annotation_task_strategy(context["vision_task_type"])
    return context, strategy


def _resolve_annotation_dataset_strategy(project_path, dataset_name):
    """解析数据集根目录，并返回与当前任务类型匹配的标注策略。"""
    dataset_root = get_dataset_root(project_path, dataset_name)
    strategy = resolve_annotation_task_strategy(load_dataset_vision_task_type(dataset_root))
    return dataset_root, strategy



def get_annotation_payload(project_path, dataset_name, split, image_ref):
    """组合单张图片的尺寸、人工框和自动框。"""
    context, strategy = _resolve_annotation_image_strategy(project_path, dataset_name, split, image_ref)
    return strategy.get_annotation_payload(context)


def save_manual_annotation(project_path, dataset_name, split, image_ref, annotation):
    """保存人工标注并清除对应自动标注。"""
    context, strategy = _resolve_annotation_image_strategy(project_path, dataset_name, split, image_ref)
    return strategy.save_manual_annotation(context, annotation)


def save_auto_annotation(project_path, dataset_name, split, image_ref, annotation):
    """保存自动标注结果到待确认目录。"""
    context, strategy = _resolve_annotation_image_strategy(project_path, dataset_name, split, image_ref)
    return strategy.save_auto_annotation(context, annotation)


def commit_auto_annotation(project_path, dataset_name, split, image_ref):
    """把自动标注框并入人工标注文件。"""
    context, strategy = _resolve_annotation_image_strategy(project_path, dataset_name, split, image_ref)
    return strategy.commit_auto_annotation(context)


def list_missing_annotations(project_path, dataset_name, split, offset=0, limit=50):
    """列出当前任务类型下缺少人工标注的样本。"""
    dataset_root, strategy = _resolve_annotation_dataset_strategy(project_path, dataset_name)
    return strategy.list_missing_annotations(dataset_root, split, offset=offset, limit=limit)


def list_pending_auto_annotations(project_path, dataset_name, split, offset=0, limit=50):
    """列出当前任务类型下待确认的自动标注样本。"""
    dataset_root, strategy = _resolve_annotation_dataset_strategy(project_path, dataset_name)
    return strategy.list_pending_auto_annotations(dataset_root, split, offset=offset, limit=limit)


def auto_annotate_image(project_path, image_ref, model_path=None, conf=0.25, max_det=200):
    """执行单张图片自动标注，作为 annotation 上下文公开入口。"""
    return run_auto_annotate_image(project_path, image_ref, model_path=model_path, conf=conf, max_det=max_det)


def start_batch_auto_annotation(project_path, dataset_name, split="train", model_path=None, image_paths=None, conf=0.25, max_det=200, batch_size=1, iou_thresh=0.5):
    """启动批量自动标注任务，作为 annotation 上下文公开入口。"""
    return run_batch_auto_annotation(
        project_path,
        dataset_name,
        split=split,
        model_path=model_path,
        image_paths=image_paths,
        conf=conf,
        max_det=max_det,
        batch_size=batch_size,
        iou_thresh=iou_thresh,
    )


def get_batch_auto_annotation_status(task_id=None):
    """查询批量自动标注任务状态，作为 annotation 上下文公开入口。"""
    return read_batch_auto_annotation_status(task_id=task_id)


def refine_segment_annotation(project_path, dataset_name, split, image_ref, stroke, class_id=0, spacing_px=10):
    context, strategy = _resolve_annotation_image_strategy(project_path, dataset_name, split, image_ref)
    if context["vision_task_type"] != VISION_TASK_TYPE_SEGMENT:
        raise ValueError("当前任务类型不支持分割拟合")
    _ = strategy
    stroke_points = (stroke or {}).get("points") or []
    if not isinstance(stroke_points, list) or len(stroke_points) < 3:
        raise ValueError("缺少有效包围轨迹")
    result = refine_polygon_with_grabcut(
        context["image_path"],
        stroke_points,
        spacing_px=float(spacing_px or 10),
        iterations=3,
        snap_radius_px=6,
    )
    return {
        "vision_task_type": context["vision_task_type"],
        "width": result.get("width"),
        "height": result.get("height"),
        "polygons": [
            {
                "class": int(class_id or 0),
                "points": result.get("points") or [],
            }
        ],
    }


def refine_segment_boundary_patch_annotation(project_path, dataset_name, split, image_ref, polygon, point_idx, target_point, class_id=0, spacing_px=10):
    context, strategy = _resolve_annotation_image_strategy(project_path, dataset_name, split, image_ref)
    if context["vision_task_type"] != VISION_TASK_TYPE_SEGMENT:
        raise ValueError("当前任务类型不支持边界精修")
    _ = strategy
    polygon_points = (polygon or {}).get("points") or []
    if len(polygon_points) < 3:
        raise ValueError("缺少当前轮廓")
    result = refine_polygon_boundary_patch(
        context["image_path"],
        polygon_points,
        point_idx=int(point_idx),
        target_point=target_point or {},
        spacing_px=float(spacing_px or 10),
        patch_arc_px=56,
        snap_radius_px=8,
    )
    return {
        "vision_task_type": context["vision_task_type"],
        "width": result.get("width"),
        "height": result.get("height"),
        "polygons": [
            {
                "class": int(class_id or 0),
                "points": result.get("points") or [],
            }
        ],
    }


def erase_segment_annotation(project_path, dataset_name, split, image_ref, polygon, stroke, class_id=0, spacing_px=10, stroke_width_px=18):
    context, strategy = _resolve_annotation_image_strategy(project_path, dataset_name, split, image_ref)
    if context["vision_task_type"] != VISION_TASK_TYPE_SEGMENT:
        raise ValueError("当前任务类型不支持橡皮擦微调")
    _ = strategy
    polygon_points = (polygon or {}).get("points") or []
    stroke_points = (stroke or {}).get("points") or []
    if len(polygon_points) < 3:
        raise ValueError("缺少当前轮廓")
    if len(stroke_points) < 2:
        raise ValueError("缺少橡皮擦轨迹")
    result = erase_polygon_with_stroke(
        context["image_path"],
        polygon_points,
        stroke_points,
        spacing_px=float(spacing_px or 10),
        stroke_width_px=float(stroke_width_px or 18),
    )
    out_polys = []
    for p in result.get("polygons") or []:
        out_polys.append({"class": int(class_id or 0), "points": p.get("points") or []})
    return {
        "vision_task_type": context["vision_task_type"],
        "width": result.get("width"),
        "height": result.get("height"),
        "polygons": out_polys,
    }
