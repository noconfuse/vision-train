"""待确认自动标注的落盘与读取：YOLO 标签文件 + 逐条元信息文件成对读写。

标签文件只有类别和几何，回答不了审核时的两个问题：「模型有多确定」「这批框是哪次跑出来的」。
元信息单独落在 auto_labels/<split>/meta/ 下的同名 json，items 与标签文件行序一一对应，
所以接受/拒绝时两个文件必须一起改写，只留一个就会串位。
"""

import os

from contexts.dataset.application.dataset_service import get_dataset_auto_meta_path
from shared.utils.fs_utils import remove_empty_dirs_up_to, remove_file_silent
from shared.utils.json_utils import load_json_file, save_json_file
from shared.utils.time_utils import now_iso
from shared.utils.yolo_utils import read_yolo_lines, write_yolo_lines

AUTO_META_VERSION = 1


def _meta_path(context):
    path = context.get("auto_meta_path") or ""
    if path:
        return path
    return get_dataset_auto_meta_path(context.get("auto_label_path") or "", context.get("auto_dir") or "")


def describe_auto_items(annotation):
    """把自动标注载荷压成与标签行序对齐的元信息列表。

    检测/分割/姿态的载荷字段名不同（boxes / polygons / instances），分类只有一个候选类别，
    但每一项都能给出「模型有多确定」这一个数，其余信息留给标签文件本身。
    """
    payload = annotation or {}
    for key in ("boxes", "polygons", "instances"):
        items = payload.get(key)
        if isinstance(items, list):
            return [{"conf": _clean_conf(item.get("conf"))} for item in items]
    if payload.get("class_id") is not None:
        return [{"conf": _clean_conf(payload.get("conf"))}]
    return []


def _clean_conf(value):
    if value is None:
        return None
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def write_auto_annotation(context, lines, items, source=None, merge_existing=True):
    """写入待确认自动标注：标签文件与元信息文件同时落盘。

    审过的图才会清空，所以这里不覆盖：这张图上还没被审掉的候选原样留着，新候选跟在后面。
    覆盖写会让「换个模型或降一档置信度再跑一轮」把上一轮没人看过的框顶掉——查重时
    旧候选被当成依据读了一遍，写完就不存在了，等于依据还在、本体没了。
    分类任务的候选文件是一张图一个答案，追加会变成两个答案，由调用方关掉合并。
    """
    carried = load_auto_meta(context)
    carried_lines = read_yolo_lines(context["auto_label_path"]) if merge_existing else []
    carried_items = carried["items"] if merge_existing else []
    # 元信息按行下标对位：上一轮没带元信息的批次补不上置信度，占位空着也比错位强
    padded = [dict(carried_items[index]) if index < len(carried_items) else {} for index in range(len(carried_lines))]
    task_id = (source or {}).get("task_id")
    merged_lines = list(carried_lines) + list(lines or [])
    write_yolo_lines(context["auto_label_path"], merged_lines)
    meta_path = _meta_path(context)
    if not meta_path:
        return context["auto_label_path"]
    save_json_file(
        meta_path,
        {
            "version": AUTO_META_VERSION,
            # 合并写之后一份文件里可能躺着几轮的框：source 只说最近这一轮，逐行的出处看 items.task_id
            "source": dict(source or {}),
            "written_at": now_iso(),
            "items": padded + [{**(item or {}), "task_id": task_id} for item in (items or [])],
        },
    )
    return context["auto_label_path"]


def load_auto_meta(context):
    """读取待确认自动标注的元信息；没有文件时返回空结构，让调用方按「无记录」处理。"""
    meta_path = _meta_path(context)
    if not meta_path or not os.path.exists(meta_path):
        return {"source": {}, "items": []}
    data = load_json_file(meta_path, default=None)
    if not isinstance(data, dict):
        return {"source": {}, "items": []}
    items = data.get("items")
    return {
        "source": data.get("source") if isinstance(data.get("source"), dict) else {},
        "items": items if isinstance(items, list) else [],
    }


def attach_conf(boxes, meta):
    """把元信息里的逐条置信度贴回解码后的框，下标对不上就当没记录。

    老批次（补录前）没有元信息文件，此时 conf 为 None，前端要照实说「没有置信度记录」，
    而不是给个 0 让人以为模型很不确定。
    """
    items = (meta or {}).get("items") or []
    enriched = []
    for index, box in enumerate(boxes or []):
        item = items[index] if index < len(items) else {}
        enriched.append({**box, "conf": _clean_conf((item or {}).get("conf"))})
    return enriched


def drop_auto_annotation(context):
    """删除待确认自动标注（标签与元信息一起删），并清掉因此变空的目录。"""
    remove_file_silent(context.get("auto_label_path") or "")
    auto_dir = context.get("auto_dir") or ""
    if auto_dir:
        remove_empty_dirs_up_to(context.get("auto_label_path") or "", auto_dir)
    meta_path = _meta_path(context)
    if meta_path:
        remove_file_silent(meta_path)
        if auto_dir:
            remove_empty_dirs_up_to(meta_path, auto_dir)


def _line_class_id(line):
    """标签行第一个数就是类别号；认不出类别的行不算命中筛选（宁可留着）。"""
    parts = str(line or "").split()
    if not parts:
        return None
    try:
        return int(float(parts[0]))
    except ValueError:
        return None


def clear_auto_annotation(context, class_ids=None):
    """清掉这一张图上还没审的候选，标签文件和元信息成对处理，人工标签不在这里、也不被碰。

    没给类别就整份删（这一轮跑废了，全部推倒重来）；给了类别就删到行——低置信度跑出来的
    废框通常只属于探测的那几个类，一把删整份会把同一张图上别的类还没审的候选一起带走。
    作用在单张图上，是因为「清空这批」跟的是列表页当前筛出来的名单，不是整个 split 目录。
    """
    stats = {"cleared_images": 0, "dropped_items": 0, "kept_items": 0}
    label_path = context.get("auto_label_path") or ""
    if not label_path or not os.path.exists(label_path):
        return stats
    lines = read_yolo_lines(label_path)
    keep_flags = [(_line_class_id(line) not in class_ids) for line in lines] if class_ids else []
    if keep_flags and any(keep_flags):
        _keep_lines(label_path, lines, keep_flags, context.get("auto_dir") or "")
        stats["kept_items"] = sum(keep_flags)
        stats["dropped_items"] = len(keep_flags) - stats["kept_items"]
        return stats
    drop_auto_annotation(context)
    stats["cleared_images"] = 1
    stats["dropped_items"] = len(lines)
    return stats


def _keep_lines(label_path, lines, keep_flags, auto_dir):
    """只留下没被筛中的行，元信息按同一把旗子剪，行序对位不能错。"""
    write_yolo_lines(label_path, [line for line, flag in zip(lines, keep_flags) if flag])
    meta_path = get_dataset_auto_meta_path(label_path, auto_dir)
    data = load_json_file(meta_path, default=None) if os.path.exists(meta_path) else None
    if isinstance(data, dict):
        items = data.get("items")
        if isinstance(items, list) and len(items) == len(lines):
            data["items"] = [item for item, flag in zip(items, keep_flags) if flag]
        data["written_at"] = now_iso()
        save_json_file(meta_path, data)
