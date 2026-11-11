"""清点 dataset_v6/test/labels 里同类完全重合的标签行：先量，再决定删什么。

「完全重合」不等同于「两行字一模一样」——同一个目标两次落盘的坐标差几个千分位，
人眼看着是同一个框，字节比对却抓不到。所以这里按几何分档报数，
套叠（大框套小框，IoU 低但小框整个落在大框里）单独一档，不动。
"""

import argparse
import collections
import glob
import os
import sys

BOX_SIDES = 4


def box_area(a):
    return max(0.0, a[2] - a[0]) * max(0.0, a[3] - a[1])


def iou(a, b):
    inter = max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    union = box_area(a) + box_area(b) - inter
    return inter / union if union > 0 else 0.0


def min_cover(a, b):
    inter = max(0.0, min(a[2], b[2]) - max(a[0], b[0])) * max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    smaller = min(box_area(a), box_area(b))
    return inter / smaller if smaller > 0 else 0.0


def size_ratio(a, b):
    x, y = box_area(a), box_area(b)
    return min(x, y) / max(x, y) if max(x, y) > 0 else 0.0


def parse(line):
    """返回 (类别号, 数值元组)；四值的检测行才有框，其余行只按原文比。"""
    parts = line.strip().split()
    if len(parts) < 2:
        return None, None
    try:
        class_id = int(float(parts[0]))
        values = tuple(round(float(v), 6) for v in parts[1:])
    except ValueError:
        return None, None
    return class_id, values


def box_of(values):
    if len(values) != BOX_SIDES:
        return None
    cx, cy, w, h = values
    return (cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0)


def grade(a, b):
    """两行说的是同一件事时，属于哪一档；不是同一件事返回 None。"""
    ba, bb = box_of(a[1]), box_of(b[1])
    if ba is None or bb is None:
        return "identical_text" if a == b else None
    overlap = iou(ba, bb)
    if overlap >= 0.99:
        return "iou_ge_0.99"
    if overlap >= 0.95:
        return "iou_0.95_0.99"
    if overlap >= 0.90:
        return "iou_0.90_0.95"
    if overlap >= 0.80:
        return "iou_0.80_0.90"
    if overlap >= 0.70:
        return "iou_0.70_0.80"
    if min_cover(ba, bb) >= 0.90:
        return "nested"
    return None


def collect(paths):
    """读一批标签文件，返回 {文件名: [(类别号, 数值元组, 原文), ...]}；认不出的行丢掉。"""
    parsed_files = {}
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            lines = [line for line in handle.read().splitlines() if line.strip()]
        rows = []
        for line in lines:
            class_id, values = parse(line)
            if class_id is None:
                continue
            rows.append((class_id, values, line.strip()))
        parsed_files[os.path.basename(path)] = rows
    return parsed_files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("labels_dir")
    parser.add_argument("--limit", type=int, default=12, help="每档最多印几对样例")
    parser.add_argument("--against", help="另一批标签目录，跟它按同名文件比（候选 vs 人工标签）")
    args = parser.parse_args()

    if args.against:
        left = collect(sorted(glob.glob(os.path.join(args.labels_dir, "*.txt"))))
        right = collect(sorted(glob.glob(os.path.join(args.against, "*.txt"))))
        buckets = collections.Counter()
        files_hit = collections.defaultdict(set)
        samples = collections.defaultdict(list)
        for name, rows in left.items():
            other = right.get(name) or []
            for class_id, values, raw in rows:
                for other_class, other_values, other_raw in other:
                    if other_class != class_id:
                        continue
                    kind = grade((class_id, values), (other_class, other_values))
                    if kind is None:
                        continue
                    buckets[kind] += 1
                    files_hit[kind].add(name)
                    if len(samples[kind]) < args.limit:
                        samples[kind].append((name, raw, other_raw))
        print(f"{args.labels_dir} 共 {sum(len(v) for v in left.values())} 行，"
              f"{args.against} 共 {sum(len(v) for v in right.values())} 行，同名文件 {len(set(left) & set(right))} 个")
        print(f"\n{'档':<16}{'对数':>8}{'命中文件':>10}")
        for kind in ["identical_text", "iou_ge_0.99", "iou_0.95_0.99", "iou_0.90_0.95",
                     "iou_0.80_0.90", "iou_0.70_0.80", "nested"]:
            print(f"{kind:<16}{buckets[kind]:>8}{len(files_hit[kind]):>10}")
        for kind in ["iou_ge_0.99", "iou_0.95_0.99", "iou_0.90_0.95", "nested"]:
            for name, first, second in samples[kind]:
                print(f"\n[{kind}] {name}\n  {first}\n  {second}")
        return 0

    files = sorted(glob.glob(os.path.join(args.labels_dir, "*.txt")))
    buckets = collections.Counter()
    files_hit = collections.defaultdict(set)
    samples = collections.defaultdict(list)
    line_shapes = collections.Counter()
    total_lines = 0

    for path in files:
        with open(path, encoding="utf-8") as handle:
            lines = [line for line in handle.read().splitlines() if line.strip()]
        total_lines += len(lines)
        parsed = []
        for index, line in enumerate(lines):
            class_id, values = parse(line)
            if class_id is None:
                line_shapes["unparsable"] += 1
                continue
            line_shapes[len(values)] += 1
            parsed.append((index, class_id, values, line))
        for i in range(len(parsed)):
            for j in range(i + 1, len(parsed)):
                if parsed[i][1] != parsed[j][1]:
                    continue
                kind = grade((parsed[i][1], parsed[i][2]), (parsed[j][1], parsed[j][2]))
                if kind is None:
                    continue
                buckets[kind] += 1
                files_hit[kind].add(path)
                if len(samples[kind]) < args.limit:
                    samples[kind].append(
                        (os.path.basename(path), parsed[i][3].strip(), parsed[j][3].strip())
                    )

    print(f"文件 {len(files)} 个、标签行 {total_lines} 条")
    print(f"每行数值个数分布：{dict(sorted(line_shapes.items(), key=lambda kv: str(kv[0])))}")
    print()
    print(f"{'档':<16}{'对数':>8}{'命中文件':>10}")
    for kind in ["identical_text", "iou_ge_0.99", "iou_0.95_0.99", "iou_0.90_0.95",
                 "iou_0.80_0.90", "iou_0.70_0.80", "nested"]:
        print(f"{kind:<16}{buckets[kind]:>8}{len(files_hit[kind]):>10}")

    for kind in ["identical_text", "iou_ge_0.99", "iou_0.95_0.99", "iou_0.90_0.95",
                 "iou_0.80_0.90", "iou_0.70_0.80", "nested"]:
        if not samples[kind]:
            continue
        print(f"\n--- {kind} 样例 ---")
        for name, first, second in samples[kind]:
            print(f"{name}\n  {first}\n  {second}")


if __name__ == "__main__":
    sys.exit(main())
