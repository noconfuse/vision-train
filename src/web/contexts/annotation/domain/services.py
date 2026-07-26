"""提供标注框/轮廓去重所需的领域计算逻辑。"""

import math

try:
    import cv2
    import numpy as np
except Exception:
    cv2 = None
    np = None

def box_iou_xyxy(a, b):
    """计算两个角点框的交并比。"""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)
    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    return inter / (area_a + area_b - inter + 1e-6)


def box_iou(a, b):
    """计算两个字典框的交并比。"""
    return box_iou_xyxy(
        (a["x1"], a["y1"], a["x2"], a["y2"]),
        (b["x1"], b["y1"], b["x2"], b["y2"]),
    )


def filter_duplicate_boxes(candidate_boxes, existing_manual, existing_auto, iou_thresh):
    """过滤与现有人工或自动框高度重叠的候选框。"""
    filtered = []
    for candidate in candidate_boxes:
        duplicate = False
        for existing in existing_manual:
            if existing["class"] == candidate["class"] and box_iou(existing, candidate) >= iou_thresh:
                duplicate = True
                break
        if not duplicate:
            for existing in existing_auto:
                if existing["class"] == candidate["class"] and box_iou(existing, candidate) >= iou_thresh:
                    duplicate = True
                    break
        if not duplicate:
            filtered.append(candidate)
    return filtered


def polygon_bbox(polygon):
    """返回多边形的外接框。"""
    points = (polygon or {}).get("points") or []
    if len(points) < 3:
        return None
    xs = [float(point.get("x", 0.0)) for point in points]
    ys = [float(point.get("y", 0.0)) for point in points]
    return {
        "x1": min(xs),
        "y1": min(ys),
        "x2": max(xs),
        "y2": max(ys),
    }


def polygon_area(polygon):
    """计算多边形面积。"""
    points = (polygon or {}).get("points") or []
    if len(points) < 3:
        return 0.0
    area = 0.0
    total = len(points)
    for index, point in enumerate(points):
        nxt = points[(index + 1) % total]
        area += float(point.get("x", 0.0)) * float(nxt.get("y", 0.0))
        area -= float(nxt.get("x", 0.0)) * float(point.get("y", 0.0))
    return abs(area) * 0.5


def _polygon_mask_iou(a_points, b_points, bbox):
    """在共享外接框 ROI 内用栅格化方式计算 polygon IoU。"""
    if cv2 is None or np is None:
        return None
    x1 = int(math.floor(bbox["x1"]))
    y1 = int(math.floor(bbox["y1"]))
    x2 = int(math.ceil(bbox["x2"]))
    y2 = int(math.ceil(bbox["y2"]))
    width = max(1, x2 - x1 + 3)
    height = max(1, y2 - y1 + 3)
    try:
        mask_a = np.zeros((height, width), dtype=np.uint8)
        mask_b = np.zeros((height, width), dtype=np.uint8)
        contour_a = np.array(
            [[[int(round(float(point.get("x", 0.0)) - x1 + 1)), int(round(float(point.get("y", 0.0)) - y1 + 1))]] for point in a_points],
            dtype=np.int32,
        )
        contour_b = np.array(
            [[[int(round(float(point.get("x", 0.0)) - x1 + 1)), int(round(float(point.get("y", 0.0)) - y1 + 1))]] for point in b_points],
            dtype=np.int32,
        )
        cv2.fillPoly(mask_a, [contour_a], 1)
        cv2.fillPoly(mask_b, [contour_b], 1)
        inter = int(np.logical_and(mask_a, mask_b).sum())
        union = int(np.logical_or(mask_a, mask_b).sum())
        if union <= 0:
            return 0.0
        return inter / float(union)
    except Exception:
        return None


def polygon_iou(a, b):
    """计算两个 polygon 的 IoU，优先使用 mask IoU，失败时退化到 bbox IoU。"""
    bbox_a = polygon_bbox(a)
    bbox_b = polygon_bbox(b)
    if not bbox_a or not bbox_b:
        return 0.0
    bbox_overlap = box_iou(bbox_a, bbox_b)
    if bbox_overlap <= 0:
        return 0.0
    points_a = (a or {}).get("points") or []
    points_b = (b or {}).get("points") or []
    if len(points_a) < 3 or len(points_b) < 3:
        return 0.0
    union_bbox = {
        "x1": min(bbox_a["x1"], bbox_b["x1"]),
        "y1": min(bbox_a["y1"], bbox_b["y1"]),
        "x2": max(bbox_a["x2"], bbox_b["x2"]),
        "y2": max(bbox_a["y2"], bbox_b["y2"]),
    }
    precise_iou = _polygon_mask_iou(points_a, points_b, union_bbox)
    if precise_iou is not None:
        return precise_iou
    return bbox_overlap


def polygon_overlap_metrics(existing, candidate):
    """返回 polygon 的 IoU 与候选被覆盖比例，用于待复核去重。"""
    bbox_existing = polygon_bbox(existing)
    bbox_candidate = polygon_bbox(candidate)
    if not bbox_existing or not bbox_candidate:
        return {"iou": 0.0, "candidate_covered_ratio": 0.0}
    bbox_overlap = box_iou(bbox_existing, bbox_candidate)
    if bbox_overlap <= 0:
        return {"iou": 0.0, "candidate_covered_ratio": 0.0}

    points_existing = (existing or {}).get("points") or []
    points_candidate = (candidate or {}).get("points") or []
    if len(points_existing) < 3 or len(points_candidate) < 3:
        return {"iou": 0.0, "candidate_covered_ratio": 0.0}

    union_bbox = {
        "x1": min(bbox_existing["x1"], bbox_candidate["x1"]),
        "y1": min(bbox_existing["y1"], bbox_candidate["y1"]),
        "x2": max(bbox_existing["x2"], bbox_candidate["x2"]),
        "y2": max(bbox_existing["y2"], bbox_candidate["y2"]),
    }

    if cv2 is not None and np is not None:
        try:
            x1 = int(math.floor(union_bbox["x1"]))
            y1 = int(math.floor(union_bbox["y1"]))
            x2 = int(math.ceil(union_bbox["x2"]))
            y2 = int(math.ceil(union_bbox["y2"]))
            width = max(1, x2 - x1 + 3)
            height = max(1, y2 - y1 + 3)
            existing_mask = np.zeros((height, width), dtype=np.uint8)
            candidate_mask = np.zeros((height, width), dtype=np.uint8)
            existing_contour = np.array(
                [[[int(round(float(point.get("x", 0.0)) - x1 + 1)), int(round(float(point.get("y", 0.0)) - y1 + 1))]] for point in points_existing],
                dtype=np.int32,
            )
            candidate_contour = np.array(
                [[[int(round(float(point.get("x", 0.0)) - x1 + 1)), int(round(float(point.get("y", 0.0)) - y1 + 1))]] for point in points_candidate],
                dtype=np.int32,
            )
            cv2.fillPoly(existing_mask, [existing_contour], 1)
            cv2.fillPoly(candidate_mask, [candidate_contour], 1)
            inter = int(np.logical_and(existing_mask, candidate_mask).sum())
            union = int(np.logical_or(existing_mask, candidate_mask).sum())
            candidate_area = int(candidate_mask.sum())
            return {
                "iou": inter / float(union) if union > 0 else 0.0,
                "candidate_covered_ratio": inter / float(candidate_area) if candidate_area > 0 else 0.0,
            }
        except Exception:
            pass

    bbox_intersection = max(0.0, min(bbox_existing["x2"], bbox_candidate["x2"]) - max(bbox_existing["x1"], bbox_candidate["x1"])) * max(
        0.0, min(bbox_existing["y2"], bbox_candidate["y2"]) - max(bbox_existing["y1"], bbox_candidate["y1"])
    )
    candidate_bbox_area = max(0.0, bbox_candidate["x2"] - bbox_candidate["x1"]) * max(0.0, bbox_candidate["y2"] - bbox_candidate["y1"])
    return {
        "iou": bbox_overlap,
        "candidate_covered_ratio": bbox_intersection / float(candidate_bbox_area + 1e-6),
    }


def filter_duplicate_polygons(candidate_polygons, existing_manual, existing_auto, iou_thresh):
    """过滤与现有人工或待复核轮廓高度重叠的候选 polygon。"""
    filtered = []
    for candidate in candidate_polygons:
        duplicate = False
        for existing in existing_manual:
            if existing.get("class") == candidate.get("class"):
                metrics = polygon_overlap_metrics(existing, candidate)
                if metrics["iou"] >= iou_thresh or metrics["candidate_covered_ratio"] >= 0.9:
                    duplicate = True
                    break
        if not duplicate:
            for existing in existing_auto:
                if existing.get("class") == candidate.get("class"):
                    metrics = polygon_overlap_metrics(existing, candidate)
                    if metrics["iou"] >= iou_thresh or metrics["candidate_covered_ratio"] >= 0.9:
                        duplicate = True
                        break
        if not duplicate:
            filtered.append(candidate)
    return filtered
