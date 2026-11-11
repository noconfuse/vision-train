"""清掉 test 里跟已写标签完全重合的同类框，各留一个；套叠（大框套小框）不动。

「完全重合」按几何判：同类、两边都是检测框、IoU ≥ 0.95（套叠不算，它 IoU 天生就低）。
实测这种框绝大多数不在标签文件里，而是在待复核候选里——候选行和人工标签行说的是同一个目标，
走查时两套记号叠在同一处，看起来就是同一个框画了两遍。所以删的是候选那一行，
人工标签原样留着（它才是人判过的）；标签文件内部真长出重合两行时留前面那行。

--execute 才落盘；先整目录备份到 /tmp，写逐行清单，删完按哈希自证只动了清单里的文件。
"""

import argparse
import collections
import datetime
import glob
import hashlib
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from measure_label_duplicates import box_of, grade, iou, parse  # noqa: E402

COINCIDENT = {"identical_text", "iou_ge_0.99", "iou_0.95_0.99"}
ROOT = os.path.join("projects", "project-1", "training", "dataset_v6")
LABELS_DIR = os.path.join(ROOT, "test", "labels")
CANDIDATES_DIR = os.path.join(ROOT, "auto_labels", "test")


def file_hash(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def snapshot(paths):
    return {path: file_hash(path) for path in paths if os.path.exists(path)}


def read_rows(path):
    """按文件顺序读成 [(原文, 类别号, 数值元组), ...]；解析不出来的行原样带着，不参与判定。"""
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as handle:
        lines = [line.strip() for line in handle.read().splitlines() if line.strip()]
    rows = []
    for line in lines:
        class_id, values = parse(line)
        rows.append((line, class_id, values))
    return rows


def meta_path_for(candidate_path):
    stem = os.path.splitext(os.path.basename(candidate_path))[0]
    return os.path.join(os.path.dirname(candidate_path), "meta", stem + ".json")


def load_meta_items(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as handle:
        return (json.load(handle) or {}).get("items")


def coincident_kind(a, b):
    """两行说的是同一个目标、而且完全重合时返回档位名，否则 None。"""
    if a[1] is None or b[1] is None or a[1] != b[1]:
        return None
    if len(a[2]) != 4 or len(b[2]) != 4:
        return "identical_text" if a[0] == b[0] else None
    kind = grade((a[1], a[2]), (b[1], b[2]))
    if kind not in COINCIDENT:
        return None
    return kind if iou(box_of(a[2]), box_of(b[2])) >= 0.95 else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true", help="真正落盘，默认只报数")
    parser.add_argument(
        "--backup-dir",
        default="/tmp/vt-dedup-coincident-%s" % datetime.date.today().strftime("%Y%m%d"),
    )
    args = parser.parse_args()

    label_paths = sorted(glob.glob(os.path.join(LABELS_DIR, "*.txt")))
    candidate_paths = sorted(glob.glob(os.path.join(CANDIDATES_DIR, "*.txt")))
    meta_paths = sorted(glob.glob(os.path.join(CANDIDATES_DIR, "meta", "*.json")))
    watched = label_paths + candidate_paths + meta_paths
    before = snapshot(watched)

    manifest = []
    # 每个文件记要删的行下标，落盘时按下标剪，重复原文也不会剪错
    candidate_drop = {}
    label_drop = {}

    for candidate_path in candidate_paths:
        name = os.path.basename(candidate_path)
        rows = read_rows(candidate_path)
        manual_rows = read_rows(os.path.join(LABELS_DIR, name))
        items = load_meta_items(meta_path_for(candidate_path))
        drop = []
        for index, row in enumerate(rows):
            match = next(((other, coincident_kind(row, other)) for other in manual_rows
                          if coincident_kind(row, other)), None)
            if match is None:
                continue
            other, kind = match
            drop.append(index)
            item = (items[index] if items and index < len(items) else {}) or {}
            manifest.append({"file": name, "side": "candidate", "grade": kind,
                             "removed_line": row[0], "matched_label_line": other[0],
                             "task_id": item.get("task_id"), "conf": item.get("conf")})
        if drop:
            candidate_drop[candidate_path] = drop

    for label_path in label_paths:
        rows = read_rows(label_path)
        kept = []
        drop = []
        for index, row in enumerate(rows):
            hit = next(((other_index, coincident_kind(row, rows[other_index]))
                        for other_index in kept if coincident_kind(row, rows[other_index])), None)
            if hit is None:
                kept.append(index)
                continue
            other_index, kind = hit
            drop.append(index)
            manifest.append({"file": os.path.basename(label_path), "side": "label", "grade": kind,
                             "removed_line": row[0], "matched_label_line": rows[other_index][0],
                             "task_id": None, "conf": None})
        if drop:
            label_drop[label_path] = drop

    by_side = collections.Counter(entry["side"] for entry in manifest)
    print(f"待复核候选里删 {by_side['candidate']} 行（{len(candidate_drop)} 个文件）")
    print(f"人工标签里删 {by_side['label']} 行（{len(label_drop)} 个文件）")
    print(f"档位分布：{dict(collections.Counter(entry['grade'] for entry in manifest))}")
    print(f"候选侧带出处（task_id 非空）的行数："
          f"{sum(1 for entry in manifest if entry['side'] == 'candidate' and entry.get('task_id'))}")

    if not args.execute:
        print("\n干跑：没有写任何文件。加 --execute 才落盘。")
        return 0
    if not manifest:
        print("没有要删的行，什么都不动。")
        return 0

    shutil.copytree(LABELS_DIR, os.path.join(args.backup_dir, "test_labels"), dirs_exist_ok=True)
    shutil.copytree(CANDIDATES_DIR, os.path.join(args.backup_dir, "auto_labels_test"), dirs_exist_ok=True)
    with open(os.path.join(args.backup_dir, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)

    for path, drop in candidate_drop.items():
        rows = read_rows(path)
        keep = [index for index in range(len(rows)) if index not in set(drop)]
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("".join(rows[index][0] + "\n" for index in keep))
        meta_file = meta_path_for(path)
        items = load_meta_items(meta_file)
        if not keep:
            os.remove(path)
            if os.path.exists(meta_file):
                os.remove(meta_file)
        elif items and len(items) == len(rows):
            with open(meta_file, "w", encoding="utf-8") as handle:
                json.dump({"version": 1, "items": [items[index] for index in keep]},
                          handle, ensure_ascii=False, indent=2)

    for path, drop in label_drop.items():
        rows = read_rows(path)
        keep = [index for index in range(len(rows)) if index not in set(drop)]
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("".join(rows[index][0] + "\n" for index in keep))

    after = snapshot(watched)
    changed = {path for path in set(before) | set(after) if before.get(path) != after.get(path)}
    expected = set(candidate_drop) | set(label_drop)
    expected |= {meta_path_for(path) for path in candidate_drop}
    unexpected = changed - expected
    print(f"\n落盘后内容变了的文件 {len(changed)} 个，其中清单外的 {len(unexpected)} 个")
    for path in sorted(unexpected):
        print(f"  意外变动：{path}")
    print(f"备份与逐行清单：{os.path.abspath(args.backup_dir)}")
    print("恢复：把备份目录里的 test_labels/、auto_labels_test/ 覆盖回原处即可（整目录备份，原文件没删）。")
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
