#!/usr/bin/env python3
"""给 project-1 的 PPE 数据集批量补 no_* 候选框，产物写进数据集的 auto_labels 待确认目录。

规则知识属于这个数据集，不属于产品：类别名、肩→髋/头部比例、证据阈值都写在本文件里。
默认只报告不改动，加 --apply 才写文件；写之前请确认统计口径没问题。

候选只进 `<dataset>/auto_labels/<split>/<stem>.txt`，不碰人工标签；
在标注页的待确认通道里核对，保存/提交后才成为正式标签。
已有待确认候选的图片会被跳过，所以本脚本可以重复执行。

用法：
    .venv/bin/python scripts/fill_unjudged_states.py                       # 演练，只出统计
    .venv/bin/python scripts/fill_unjudged_states.py --only no_vest        # 只看背心状态
    .venv/bin/python scripts/fill_unjudged_states.py --apply               # 真写文件
    .venv/bin/python scripts/fill_unjudged_states.py --rollback            # 按清单删掉写入的待确认文件
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

import yaml

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
SPLITS = ("train", "val", "test")

PERSON_CLASS = "person"
EDGE_TOUCH_RATIO = 0.015  # 框边贴画面边缘 = 该部位被裁出画
MIN_PERSON_SHORT_SIDE_PX = 40
NEIGHBOR_COVER_RATIO = 0.5  # 判定区域被旁人压过半 → 判不准
JUDGED_IOU = 0.15  # 区域里已有 worn/no_* 框 → 这个状态判过了
EVIDENCE_COVER_RATIO = 0.3
COMPLETE_JUDGMENT_RATIO = 0.8  # 这张图该配对已判完 ≥80% 的人，才允许推断「没有」

# 区域比例取自本数据集 3,540 张单人图的实测中位数（head y 0.00–0.19 / torso 肩→髋 0.20–0.65）
RULES = (
    {"absent": "no_helmet", "worn": "helmet", "region": "head", "edge": "top"},
    {"absent": "no_harness", "worn": "harness", "region": "torso", "edge": "bottom"},
    {"absent": "no_vest", "worn": "vest", "region": "torso", "edge": "bottom", "also_evidence": "harness"},
)
REGION_SHAPES = {
    "head": (0.30, 0.00, 0.70, 0.19),
    "torso": (0.18, 0.20, 0.82, 0.65),
}


def load_class_names(dataset: Path) -> dict[str, int]:
    config = yaml.safe_load((dataset / "dataset.yaml").read_text(encoding="utf-8")) or {}
    names = config.get("names") or {}
    if isinstance(names, dict):
        return {str(value): int(key) for key, value in names.items()}
    return {str(value): index for index, value in enumerate(names)}


def read_label(path: Path, width: int, height: int) -> list[tuple[int, tuple[float, float, float, float]]]:
    boxes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        class_id = int(float(parts[0]))
        cx, cy, w, h = (float(v) for v in parts[1:5])
        x1, y1 = (cx - w / 2) * width, (cy - h / 2) * height
        x2, y2 = (cx + w / 2) * width, (cy + h / 2) * height
        if x2 > x1 and y2 > y1:
            boxes.append((class_id, (x1, y1, x2, y2)))
    return boxes


def image_size(path: Path) -> tuple[int, int]:
    from PIL import Image

    with Image.open(path) as image:
        return image.size


def iou(a, b) -> float:
    iw = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    ih = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = iw * ih
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def covered_ratio(region, other) -> float:
    iw = max(0.0, min(region[2], other[2]) - max(region[0], other[0]))
    ih = max(0.0, min(region[3], other[3]) - max(region[1], other[1]))
    area = (region[2] - region[0]) * (region[3] - region[1])
    return (iw * ih) / area if area > 0 else 0.0


def region_box(person, rule, width, height):
    """按人在画面里的位置算判定区域；部位被裁出画时返回 None。"""
    px1, py1, px2, py2 = person
    edge = rule["edge"]
    if edge == "top" and py1 <= EDGE_TOUCH_RATIO * height:
        return None
    if edge == "bottom" and py2 >= (1.0 - EDGE_TOUCH_RATIO) * height:
        return None
    sx1, sy1, sx2, sy2 = REGION_SHAPES[rule["region"]]
    pw, ph = px2 - px1, py2 - py1
    box = (
        min(max(px1 + sx1 * pw, 0.0), float(width)),
        min(max(py1 + sy1 * ph, 0.0), float(height)),
        min(max(px1 + sx2 * pw, 0.0), float(width)),
        min(max(py1 + sy2 * ph, 0.0), float(height)),
    )
    return box if box[2] > box[0] and box[3] > box[1] else None


def judgment_ratio(persons, rule, state_boxes, width, height) -> float:
    judgeable = judged = 0
    for person in persons:
        region = region_box(person, rule, width, height)
        if region is None:
            continue
        judgeable += 1
        if any(iou(region, existing) > JUDGED_IOU for existing in state_boxes):
            judged += 1
    return judged / judgeable if judgeable else 0.0


def has_evidence(rule, region, ratio) -> bool:
    if ratio >= COMPLETE_JUDGMENT_RATIO:
        return True
    return any(covered_ratio(region, other) >= EVIDENCE_COVER_RATIO for other in rule["evidence_boxes"])


def build_candidates(boxes, names: dict[str, int], width, height, only: set[str] | None):
    person_id = names.get(PERSON_CLASS)
    if person_id is None:
        raise SystemExit(f"数据集缺少 {PERSON_CLASS} 类，规则不适用")

    persons = []
    by_class: dict[int, list] = {}
    for class_id, box in boxes:
        by_class.setdefault(class_id, []).append(box)
        if class_id == person_id:
            persons.append(box)

    rules = []
    for rule in RULES:
        if only and rule["absent"] not in only:
            continue
        absent_id = names.get(rule["absent"])
        worn_id = names.get(rule["worn"])
        if absent_id is None or worn_id is None:
            continue
        rules.append(
            {
                **rule,
                "absent_id": absent_id,
                "state_boxes": by_class.get(worn_id, []) + by_class.get(absent_id, []),
                "evidence_boxes": by_class.get(names.get(rule.get("also_evidence") or ""), []),
            }
        )

    ratios = [judgment_ratio(persons, rule, rule["state_boxes"], width, height) for rule in rules]
    candidates = []
    skipped = Counter()
    for person in persons:
        if min(person[2] - person[0], person[3] - person[1]) < MIN_PERSON_SHORT_SIDE_PX:
            skipped["person_too_small"] += 1
            continue
        for rule, ratio in zip(rules, ratios):
            region = region_box(person, rule, width, height)
            if region is None:
                skipped["hips_out_of_frame" if rule["edge"] == "bottom" else "head_out_of_frame"] += 1
                continue
            if any(covered_ratio(region, other) > NEIGHBOR_COVER_RATIO for other in persons if other != person):
                skipped["covered_by_neighbor"] += 1
                continue
            if any(iou(region, existing) > JUDGED_IOU for existing in rule["state_boxes"]):
                skipped["already_judged"] += 1
                continue
            if not has_evidence(rule, region, ratio):
                skipped["pair_not_judged_in_image"] += 1
                continue
            candidates.append((rule["absent"], rule["absent_id"], region))
    return persons, candidates, skipped


def encode(box, width, height) -> str:
    class_id, (x1, y1, x2, y2) = box
    cx, cy = (x1 + x2) / 2 / width, (y1 + y2) / 2 / height
    w, h = (x2 - x1) / width, (y2 - y1) / height
    return f"{class_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"


def rollback(manifest: Path) -> int:
    """按清单删掉本脚本写过的 auto_labels 文件；清单之外的改动一律不碰。"""
    if not manifest.is_file():
        raise SystemExit(f"找不到清单 {manifest}，无法回滚")
    with manifest.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    wanted: dict[Path, set[str]] = {}
    for row in rows:
        wanted.setdefault(Path(row["auto_label"]), set()).add(row["class_id"])
    removed = kept = missing = 0
    for path, class_ids in wanted.items():
        if not path.is_file():
            missing += 1
            continue
        # 文件里出现过清单以外的类别，说明有人工改动，保留不动
        extra = [line.split()[0] for line in path.read_text(encoding="utf-8").splitlines() if line.split()]
        if set(extra) - class_ids:
            kept += 1
            continue
        path.unlink()
        removed += 1
    print(f"回滚：清单 {len(wanted)} 个文件 → 删除 {removed} 个，已不在磁盘 {missing} 个")
    if kept:
        print(f"另有 {kept} 个文件内容超出清单（可能被编辑过），未删除")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", default="projects/project-1/training/dataset", type=Path)
    parser.add_argument("--split", default="all", choices=("all", *SPLITS))
    parser.add_argument("--only", default="", help="逗号分隔，只生成这些类，例如 no_vest")
    parser.add_argument("--limit", type=int, default=0, help="每个 split 最多处理多少张，0 = 不限")
    parser.add_argument("--manifest", default="projects/project-1/training/curation/rule_fill_created.csv", type=Path)
    parser.add_argument("--apply", action="store_true", help="真正写 auto_labels 文件")
    parser.add_argument("--rollback", action="store_true", help="按 --manifest 删掉本脚本写入的待确认文件")
    args = parser.parse_args()

    if args.rollback:
        return rollback(args.manifest.resolve())

    dataset = args.dataset.resolve()
    names = load_class_names(dataset)
    only = {value.strip() for value in args.only.split(",") if value.strip()} or None
    splits = SPLITS if args.split == "all" else (args.split,)
    auto_root = dataset / "auto_labels"

    scanned = 0
    touched = 0
    written_files = 0
    created_total = Counter()
    skipped_total = Counter()
    existing_pending = 0
    manifest_rows = []

    for split in splits:
        images_dir = dataset / split / "images"
        labels_dir = dataset / split / "labels"
        if not labels_dir.is_dir():
            continue
        label_paths = sorted(labels_dir.glob("*.txt"))
        if args.limit:
            label_paths = label_paths[: args.limit]
        for label_path in label_paths:
            image_path = next(
                (images_dir / f"{label_path.stem}{ext}" for ext in IMAGE_EXTS if (images_dir / f"{label_path.stem}{ext}").is_file()),
                None,
            )
            if image_path is None:
                skipped_total["image_missing"] += 1
                continue
            scanned += 1
            auto_path = auto_root / split / f"{label_path.stem}.txt"
            if auto_path.exists():
                existing_pending += 1
                continue
            width, height = image_size(image_path)
            boxes = read_label(label_path, width, height)
            persons, candidates, skipped = build_candidates(boxes, names, width, height, only)
            skipped_total.update(skipped)
            if not candidates:
                continue
            touched += 1
            for class_name, class_id, region in candidates:
                created_total[class_name] += 1
                manifest_rows.append(
                    {
                        "split": split,
                        "image": str(image_path),
                        "auto_label": str(auto_path),
                        "class_name": class_name,
                        "class_id": class_id,
                        "x1": round(region[0] / width, 6),
                        "y1": round(region[1] / height, 6),
                        "x2": round(region[2] / width, 6),
                        "y2": round(region[3] / height, 6),
                    }
                )
            if args.apply:
                auto_path.parent.mkdir(parents=True, exist_ok=True)
                auto_path.write_text(
                    "\n".join(encode((class_id, region), width, height) for _, class_id, region in candidates) + "\n",
                    encoding="utf-8",
                )
                written_files += 1

    print(f"扫描 {scanned} 张 → 有候选 {touched} 张，已有待确认候选而跳过 {existing_pending} 张")
    print(f"候选框合计 {sum(created_total.values())} 个：{dict(created_total)}")
    print(f"跳过明细：{dict(skipped_total)}")
    if not args.apply:
        print("演练模式，未写任何文件。加 --apply 才会写入 auto_labels。")
        return 0

    print(f"已写入 {written_files} 个 auto_labels 文件")
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    with args.manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=tuple(manifest_rows[0].keys()) if manifest_rows else ())
        if manifest_rows:
            writer.writeheader()
            writer.writerows(manifest_rows)
    print(f"清单：{args.manifest}")
    print(f"回滚：.venv/bin/python scripts/fill_unjudged_states.py --rollback --manifest {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
