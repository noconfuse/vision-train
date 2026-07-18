"""提供标注框去重所需的领域计算逻辑。"""

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
