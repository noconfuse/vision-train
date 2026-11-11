"""查清「候选和人工标签落在同一个位置」这批行是哪一轮、什么时候写下来的。

对每一对重合的（候选行 vs 人工标签行）报：两边的修改时间、候选行在 meta 里的
task_id 和 conf。谁新谁旧决定了是「标签写晚了没人回收候选」还是「候选生成时没看到标签」。
"""

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure_label_duplicates import box_of, grade, iou, parse  # noqa: E402

ROOT = "projects/project-1/training/dataset_v6"


def read_rows(path):
    with open(path, encoding="utf-8") as handle:
        return [parse(line) for line in handle.read().splitlines() if line.strip()]


def meta_for(candidate_path):
    meta_path = os.path.join(os.path.dirname(candidate_path), "meta",
                             os.path.splitext(os.path.basename(candidate_path))[0] + ".json")
    if not os.path.exists(meta_path):
        return {}
    with open(meta_path, encoding="utf-8") as handle:
        return json.load(handle)


def stamp(path):
    return __import__("datetime").datetime.fromtimestamp(os.path.getmtime(path)).strftime("%m-%d %H:%M:%S")


def main():
    candidates = sorted(glob.glob(os.path.join(ROOT, "auto_labels/test/*.txt")))
    hits = 0
    task_ids = {}
    for candidate_path in candidates:
        name = os.path.basename(candidate_path)
        manual_path = os.path.join(ROOT, "test/labels", name)
        if not os.path.exists(manual_path):
            continue
        manual_rows = read_rows(manual_path)
        candidate_rows = read_rows(candidate_path)
        meta = meta_for(candidate_path)
        items = meta.get("items") or []
        pairs = []
        for index, (class_id, values) in enumerate(candidate_rows):
            for other_class, other_values in manual_rows:
                if other_class != class_id:
                    continue
                kind = grade((class_id, values), (other_class, other_values))
                if kind in ("iou_ge_0.99", "iou_0.95_0.99", "iou_0.90_0.95", "identical_text"):
                    item = items[index] if index < len(items) else {}
                    task_id = item.get("task_id") or meta.get("task_id") or "?"
                    pairs.append((kind, task_id, item.get("conf")))
                    task_ids[task_id] = task_ids.get(task_id, 0) + 1
        if not pairs:
            continue
        hits += 1
        if hits <= 12:
            print(f"{name}  候选 {stamp(candidate_path)} / 标签 {stamp(manual_path)}  {len(pairs)} 对")
            for kind, task_id, conf in pairs[:4]:
                print(f"    {kind} task={task_id} conf={conf}")
    print(f"\n命中文件 {hits} 个")
    print(f"按轮次：{task_ids}")


if __name__ == "__main__":
    main()
