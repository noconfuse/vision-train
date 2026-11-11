"""同类重复框的判据与只读统计。

判据不另造一个：沿用自动标注落盘去重用的那一条（见 `_same_object_rule`）
——两个同类框重叠七成以上，或者一个九成以上落在另一个里。

几何只回答「这两个框重合到什么程度」，回答不了「该删哪个」：一个人被标了两遍，
和两个人前后站得很近，在这里长得很像。所以这个模块只把重合度算出来给列表页当筛选项，
删哪个由人进标注页一张一张定，不做批量删除。
"""

import os

from shared.utils.yolo_utils import parse_yolo_class_id


def _same_object_rule():
    """取判据：跟自动标注落盘去重共用同一个函数、同一组阈值。

    在函数里取而不是模块顶部：annotation 的 infrastructure 会反向 import dataset 的
    application 层，两边都在模块顶部互引会成环。
    """
    from contexts.annotation.application.annotation_service import (
        SAME_OBJECT_COVER_THRESH,
        SAME_OBJECT_IOU_THRESH,
        box_min_cover_ratio,
        is_same_object_box,
    )

    return SAME_OBJECT_IOU_THRESH, SAME_OBJECT_COVER_THRESH, is_same_object_box, box_min_cover_ratio


def to_xyxy_box(box):
    """把 [cx, cy, w, h] 换成判据认得的 x1y1x2y2 字典。"""
    cx, cy, w, h = box
    return {
        "x1": cx - w / 2.0,
        "y1": cy - h / 2.0,
        "x2": cx + w / 2.0,
        "y2": cy + h / 2.0,
    }


def _box_area(box):
    return max(0.0, box["x2"] - box["x1"]) * max(0.0, box["y2"] - box["y1"])


def parse_label_line(raw_line):
    """把一行检测标签解析成 {class_id, box}；解析不了返回 None。"""
    parts = str(raw_line or "").strip().split()
    if len(parts) < 5:
        return None
    if len(parts) > 5:
        # 轮廓 / 姿态的行在第 5 个之后还有点位，不是检测框，不在这个判据范围内
        return None
    try:
        class_id = parse_yolo_class_id(parts[0])
        box = [float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])]
    except (TypeError, ValueError):
        return None
    return {"class_id": class_id, "box": box}


def find_redundant_lines(lines, exclude_classes=None):
    """在一份标签文件的行里找出「跟同类另一个框说的是同一个东西」的行。

    同类内按面积从大到小收敛：大框先留下，之后被判成同一个东西的算冗余，
    所以一张图里三个套叠的框只留最外面那个。返回 (冗余行记录, 统计)。
    统计里的 unparsed_lines / degenerate_boxes 是「这次判不了」的行，如实报出来，
    不当成没问题。
    """
    _, _, is_same, min_cover = _same_object_rule()
    excluded = {int(class_id) for class_id in (exclude_classes or ())}
    parsed = []
    unparsed = 0
    degenerate = 0
    for index, raw in enumerate(lines):
        if not str(raw).strip():
            continue
        item = parse_label_line(raw)
        if item is None:
            unparsed += 1
            continue
        box = to_xyxy_box(item["box"])
        if _box_area(box) <= 0:
            degenerate += 1
            continue
        parsed.append({"line_no": index + 1, "class_id": item["class_id"], "box": item["box"], "xy": box})

    by_class = {}
    for entry in parsed:
        by_class.setdefault(entry["class_id"], []).append(entry)

    records = []
    for class_id, entries in by_class.items():
        if class_id in excluded:
            continue
        kept = []
        for entry in sorted(entries, key=lambda item: -_box_area(item["xy"])):
            keeper = next((candidate for candidate in kept if is_same(candidate["xy"], entry["xy"])), None)
            if keeper is None:
                kept.append(entry)
            else:
                records.append({
                    "line_no": entry["line_no"],
                    "class_id": class_id,
                    "box": [round(value, 6) for value in entry["box"]],
                    "min_cover_ratio": round(min_cover(keeper["xy"], entry["xy"]), 4),
                    "kept_line_no": keeper["line_no"],
                    "kept_box": [round(value, 6) for value in keeper["box"]],
                })
    stats = {
        "boxes": len(parsed),
        "unparsed_lines": unparsed,
        "degenerate_boxes": degenerate,
    }
    return records, stats


def read_label_lines(label_path):
    with open(label_path, "r", encoding="utf-8") as handle:
        return handle.read().splitlines(keepends=True)


def count_redundant_boxes(label_path, exclude_classes=None):
    """数一份标签文件里有几个同类重复框；文件不存在算 0，读不出来如实抛。"""
    if not label_path or not os.path.isfile(label_path):
        return 0
    records, _ = find_redundant_lines(read_label_lines(label_path), exclude_classes=exclude_classes)
    return len(records)
