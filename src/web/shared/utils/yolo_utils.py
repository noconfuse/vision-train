"""处理 YOLO 标签文件的读写与类别提取。"""

import os


def parse_yolo_class_id(raw_value):
    """把 YOLO 标签中的类别编号解析为整数。"""
    return int(float(raw_value))


def read_yolo_lines(label_path):
    """读取并过滤标签文件中的非空行。"""
    if not os.path.exists(label_path):
        return []
    try:
        with open(label_path, "r", encoding="utf-8") as handle:
            return [line.strip() for line in handle if line.strip()]
    except Exception:
        return []


def write_yolo_lines(label_path, lines):
    """写入 YOLO 标签行并确保父目录存在。"""
    os.makedirs(os.path.dirname(label_path), exist_ok=True)
    with open(label_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines or []))


def collect_yolo_class_ids(label_path):
    """收集标签文件里出现过的类别编号。"""
    class_ids = set()
    for line in read_yolo_lines(label_path):
        parts = line.split()
        if not parts:
            continue
        try:
            class_ids.add(parse_yolo_class_id(parts[0]))
        except Exception:
            continue
    return class_ids


def collect_yolo_class_counts(label_path):
    """统计标签文件里各类别出现次数。"""
    class_counts = {}
    for line in read_yolo_lines(label_path):
        parts = line.split()
        if not parts:
            continue
        try:
            class_id = parse_yolo_class_id(parts[0])
        except Exception:
            continue
        class_counts[class_id] = class_counts.get(class_id, 0) + 1
    return class_counts
