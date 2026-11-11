#!/usr/bin/env python3
"""整理 PPE 数据集：审计、隔离、近似去重、按组划分。

只读取原始数据集，所有输出写入 --out（默认 projects/<project>/training/curation）。
不移动、不删除原始图片和标签。

示例：
    .venv/bin/python scripts/curate_ppe_dataset.py
    .venv/bin/python scripts/curate_ppe_dataset.py --skip-dhash
    .venv/bin/python scripts/curate_ppe_dataset.py --manual-exclude curation/manual_quarantine.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

SPLITS = ("train", "val", "test")
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# 当前数据集的 9 个 ID 保持不变，只把名字对齐到目标规范。
CLASS_NAMES = {
    0: "person",
    1: "harness",
    2: "no_harness",
    3: "helmet",
    4: "no_helmet",
    5: "vest",
    6: "no_vest",
    7: "lanyard",
    8: "hook",
}
PERSON_ID = 0
PPE_IDS = {1, 2, 3, 4, 5, 6, 7, 8}
RARE_IDS = (5, 6, 7, 8)

SOURCE_RE = re.compile(r"^(F\d+)_")


@dataclass
class Record:
    path: Path
    rel: str
    split: str
    source: str
    label_path: Path
    boxes: list[tuple[int, float, float, float, float]]
    width: int
    height: int
    person_area_max: float = 0.0
    white_ratio: float = 0.0
    issues: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    group_id: int = -1
    new_split: str = ""
    dhash: int | None = None

    @property
    def counts(self) -> Counter:
        return Counter(box[0] for box in self.boxes)

    @property
    def person_boxes(self) -> list[tuple[int, float, float, float, float]]:
        return [box for box in self.boxes if box[0] == PERSON_ID]

    @property
    def excluded(self) -> bool:
        return bool(self.issues) or "manual" in self.flags


def parse_source(filename: str) -> str:
    match = SOURCE_RE.match(filename)
    return match.group(1) if match else "UNKNOWN"


def label_for_image(image: Path) -> Path:
    parts = list(image.parts)
    for index in range(len(parts) - 1, -1, -1):
        if parts[index] == "images":
            parts[index] = "labels"
            return Path(*parts).with_suffix(".txt")
    return image.with_suffix(".txt")


def image_pixels(image: Image.Image) -> list:
    if hasattr(image, "get_flattened_data"):
        return list(image.get_flattened_data())
    return list(image.getdata())


def scan_dataset(dataset: Path) -> list[Record]:
    records: list[Record] = []
    for split in SPLITS:
        image_dir = dataset / split / "images"
        label_dir = dataset / split / "labels"
        if not image_dir.is_dir():
            raise SystemExit(f"缺少目录: {image_dir}")
        for image_path in sorted(image_dir.iterdir()):
            if not image_path.is_file() or image_path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            label_path = label_dir / f"{image_path.stem}.txt"
            issues: list[str] = []
            boxes: list[tuple[int, float, float, float, float]] = []
            if not label_path.exists():
                issues.append("missing_label")
            else:
                for raw in label_path.read_text(encoding="utf-8", errors="replace").splitlines():
                    line = raw.strip()
                    if not line:
                        continue
                    parts = line.split()
                    if len(parts) != 5:
                        issues.append("invalid_label")
                        continue
                    try:
                        class_id = int(parts[0])
                        cx, cy, width, height = (float(value) for value in parts[1:])
                    except ValueError:
                        issues.append("invalid_label")
                        continue
                    if (
                        class_id not in CLASS_NAMES
                        or width <= 0
                        or height <= 0
                        or not all(0.0 <= value <= 1.0 for value in (cx, cy, width, height))
                    ):
                        issues.append("invalid_label")
                        continue
                    boxes.append((class_id, cx, cy, width, height))
                if not boxes and "invalid_label" not in issues:
                    issues.append("empty_label")

            width = height = 0
            white_ratio = 0.0
            try:
                with Image.open(image_path) as image:
                    width, height = image.size
                    thumbnail = image.convert("RGB")
                    thumbnail.thumbnail((64, 64))
                    pixels = image_pixels(thumbnail)
                    white_ratio = sum(
                        1 for red, green, blue in pixels if min(red, green, blue) >= 235
                    ) / max(1, len(pixels))
            except Exception:
                issues.append("unreadable_image")

            record = Record(
                path=image_path,
                rel=f"{split}/images/{image_path.name}",
                split=split,
                source=parse_source(image_path.name),
                label_path=label_path,
                boxes=boxes,
                width=width,
                height=height,
                white_ratio=white_ratio,
                issues=sorted(set(issues)),
            )
            add_flags(record)
            records.append(record)
    return records


def add_flags(record: Record) -> None:
    if record.issues:
        return
    counts = record.counts
    persons = record.person_boxes
    if record.boxes and not persons:
        record.flags.append("no_person")
    if persons and not any(class_id in counts for class_id in PPE_IDS):
        record.flags.append("person_only")
    if persons and record.width > 0 and record.height > 0:
        record.person_area_max = max(box[3] * box[4] for box in persons)
        if record.person_area_max >= 0.40:
            record.flags.append("closeup")
        if record.person_area_max >= 0.60:
            record.flags.append("extreme_closeup")
    if not persons and record.white_ratio >= 0.50:
        record.flags.append("product_like")
    if len(record.boxes) > 30:
        record.flags.append("dense")


def dhash(path: Path, size: int = 8) -> int | None:
    try:
        with Image.open(path) as image:
            gray = image.convert("L").resize((size + 1, size), Image.Resampling.BILINEAR)
            pixels = image_pixels(gray)
    except Exception:
        return None
    bits = 0
    for row in range(size):
        offset = row * (size + 1)
        for col in range(size):
            bits = (bits << 1) | (1 if pixels[offset + col] > pixels[offset + col + 1] else 0)
    return bits


def load_manual_exclusions(path: Path, dataset: Path) -> set[str]:
    if not path.exists():
        return set()
    excluded: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            raw = (row.get("rel") or row.get("abs") or row.get("path") or "").strip()
            if not raw:
                continue
            candidate = Path(raw)
            if candidate.is_absolute():
                try:
                    raw = str(candidate.relative_to(dataset.resolve()))
                except ValueError:
                    raw = str(candidate)
            raw = raw.replace("\\", "/").lstrip("./")
            excluded.add(raw)
    return excluded


def build_duplicate_groups(records: list[Record], threshold: int, progress_every: int = 2000) -> list[list[Record]]:
    hashed = [record for record in records if record.dhash is not None]
    total = len(hashed)
    print(f"dHash 已计算 {total} 张，开始分组（Hamming <= {threshold}）…")
    band_count = 8
    band_bits = 8
    bands = [defaultdict(list) for _ in range(band_count)]
    for index, record in enumerate(hashed):
        value = record.dhash or 0
        for band in range(band_count):
            bands[band][(value >> (band * band_bits)) & 0xFF].append(index)

    parent = list(range(total))
    rank = [0] * total

    def find(node: int) -> int:
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def union(left: int, right: int) -> None:
        left_root, right_root = find(left), find(right)
        if left_root == right_root:
            return
        if rank[left_root] < rank[right_root]:
            left_root, right_root = right_root, left_root
        parent[right_root] = left_root
        if rank[left_root] == rank[right_root]:
            rank[left_root] += 1

    checked: set[tuple[int, int]] = set()
    for index, record in enumerate(hashed):
        if index % progress_every == 0 and index:
            print(f"  分组进度 {index}/{total}")
        value = record.dhash or 0
        candidates: set[int] = set()
        for band in range(band_count):
            candidates.update(bands[band][(value >> (band * band_bits)) & 0xFF])
        for other in candidates:
            if other <= index:
                continue
            key = (index, other)
            if key in checked:
                continue
            checked.add(key)
            other_value = hashed[other].dhash or 0
            if (value ^ other_value).bit_count() <= threshold:
                union(index, other)

    components: dict[int, list[Record]] = defaultdict(list)
    for index, record in enumerate(hashed):
        components[find(index)].append(record)

    groups = sorted(components.values(), key=lambda members: min(member.rel for member in members))
    next_group_id = 0
    for members in groups:
        for record in members:
            record.group_id = next_group_id
        next_group_id += 1
    for record in records:
        if record.group_id < 0:
            record.group_id = next_group_id
            next_group_id += 1
    return groups + [[record] for record in records if record.dhash is None]


def assign_splits(
    records: list[Record],
    val_ratio: float,
    test_ratio: float,
    seed: int,
) -> tuple[dict[int, str], dict[str, dict[str, int]], dict[str, dict[str, int]]]:
    groups: dict[int, list[Record]] = defaultdict(list)
    for record in records:
        groups[record.group_id].append(record)

    group_source: dict[int, str] = {}
    for group_id, members in groups.items():
        group_source[group_id] = Counter(member.source for member in members).most_common(1)[0][0]

    totals = Counter(record.source for record in records)
    targets: dict[str, dict[str, int]] = {}
    for source, total in totals.items():
        test_count = int(round(total * test_ratio))
        val_count = int(round(total * val_ratio))
        targets[source] = {
            "train": max(0, total - test_count - val_count),
            "val": val_count,
            "test": test_count,
        }

    remaining = {source: dict(values) for source, values in targets.items()}
    rng = random.Random(seed)
    group_ids = list(groups)
    rng.shuffle(group_ids)
    shuffle_order = {group_id: index for index, group_id in enumerate(group_ids)}
    group_ids.sort(key=lambda group_id: (-len(groups[group_id]), shuffle_order[group_id]))

    assignments: dict[int, str] = {}
    for group_id in group_ids:
        source = group_source[group_id]
        size = len(groups[group_id])
        candidates = [split for split in ("test", "val", "train") if remaining[source][split] >= size]
        if not candidates:
            candidates = ["train"]

        def score(split: str) -> tuple[float, int]:
            target = targets[source][split]
            if target <= 0:
                return (-1.0, 0)
            return (remaining[source][split] / target, -SPLITS.index(split))

        chosen = max(candidates, key=score)
        assignments[group_id] = chosen
        remaining[source][chosen] -= size

    for record in records:
        record.new_split = assignments[record.group_id]

    # 稀有类覆盖：某个稀有类在 val/test 为 0 时，从 train 挪一个最小的组过去。
    for class_id in RARE_IDS:
        for split in ("val", "test"):
            covered = sum(
                1 for record in records if record.new_split == split and class_id in record.counts
            )
            if covered:
                continue
            movable = [
                group_id
                for group_id, members in groups.items()
                if assignments[group_id] == "train"
                and any(class_id in member.counts for member in members)
            ]
            if not movable:
                continue
            group_id = min(movable, key=lambda candidate: len(groups[candidate]))
            assignments[group_id] = split
            for member in groups[group_id]:
                member.new_split = split

    actual: dict[str, dict[str, int]] = {split: Counter() for split in SPLITS}
    for record in records:
        actual[record.new_split][record.source] += 1
    return assignments, targets, {split: dict(counter) for split, counter in actual.items()}


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_dataset_yaml(path: Path, dataset: Path, out: Path) -> None:
    lines = [
        "# 由 scripts/curate_ppe_dataset.py 生成；原始数据集未被修改。",
        f"path: {json.dumps(str(dataset.resolve()))}",
        f"train: {json.dumps(str((out / 'splits' / 'train.txt').resolve()))}",
        f"val: {json.dumps(str((out / 'splits' / 'val.txt').resolve()))}",
        f"test: {json.dumps(str((out / 'splits' / 'test.txt').resolve()))}",
        "names:",
    ]
    for class_id in sorted(CLASS_NAMES):
        lines.append(f"  {class_id}: {CLASS_NAMES[class_id]}")
    lines.append(f"nc: {len(CLASS_NAMES)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def validate_outputs(out: Path, records: list[Record]) -> None:
    listed: dict[str, set[Path]] = {}
    for split in SPLITS:
        list_path = out / "splits" / f"{split}.txt"
        paths = [Path(line.strip()) for line in list_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not paths:
            raise SystemExit(f"{list_path} 为空")
        for image_path in paths:
            if not image_path.exists():
                raise SystemExit(f"图片不存在: {image_path}")
            if not label_for_image(image_path).exists():
                raise SystemExit(f"标签不存在: {label_for_image(image_path)}")
        listed[split] = set(paths)

    overlaps = (listed["train"] & listed["val"]) | (listed["train"] & listed["test"]) | (listed["val"] & listed["test"])
    if overlaps:
        raise SystemExit(f"存在跨 split 重复图片: {list(overlaps)[:3]}")

    expected = {record.path.resolve() for record in records}
    actual = {path.resolve() for paths in listed.values() for path in paths}
    if expected != actual:
        missing = expected - actual
        extra = actual - expected
        raise SystemExit(f"split 列表与记录不一致，缺少 {len(missing)}，多出 {len(extra)}")

    group_splits: dict[int, set[str]] = defaultdict(set)
    for record in records:
        group_splits[record.group_id].add(record.new_split)
    leaked = {group_id: splits for group_id, splits in group_splits.items() if len(splits) > 1}
    if leaked:
        raise SystemExit(f"近似重复组跨 split: {list(leaked.items())[:3]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("projects/project-1/training/dataset"))
    parser.add_argument("--out", type=Path, default=Path("projects/project-1/training/curation"))
    parser.add_argument("--val-ratio", type=float, default=0.10)
    parser.add_argument("--test-ratio", type=float, default=0.10)
    parser.add_argument("--dup-threshold", type=int, default=6)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-dhash", action="store_true", help="跳过去重，只按单图划分（不推荐）")
    parser.add_argument("--manual-exclude", type=Path, default=None)
    args = parser.parse_args()

    dataset = args.dataset.resolve()
    out = args.out.resolve()
    if not dataset.is_dir():
        raise SystemExit(f"数据集不存在: {dataset}")
    out.mkdir(parents=True, exist_ok=True)

    print(f"扫描数据集: {dataset}")
    records = scan_dataset(dataset)
    print(f"共 {len(records)} 张图片，{sum(len(record.boxes) for record in records)} 个实例")

    manual_path = args.manual_exclude or (out / "manual_quarantine.csv")
    manual_rel = load_manual_exclusions(manual_path, dataset)
    if manual_rel:
        print(f"人工隔离清单: {len(manual_rel)} 条")
    for record in records:
        if record.rel in manual_rel:
            record.flags.append("manual")

    included = [record for record in records if not record.excluded]
    excluded = [record for record in records if record.excluded]
    print(f"自动隔离 {len(excluded) - sum(1 for record in excluded if 'manual' in record.flags)} 张，"
          f"人工隔离 {sum(1 for record in excluded if 'manual' in record.flags)} 张，"
          f"进入划分 {len(included)} 张")

    if not args.skip_dhash:
        for index, record in enumerate(included, start=1):
            record.dhash = dhash(record.path)
            if index % 2000 == 0:
                print(f"  dHash {index}/{len(included)}")
        build_duplicate_groups(included, args.dup_threshold)
    else:
        for index, record in enumerate(included):
            record.group_id = index

    _, targets, actual = assign_splits(
        included, val_ratio=args.val_ratio, test_ratio=args.test_ratio, seed=args.seed
    )

    groups: dict[int, list[Record]] = defaultdict(list)
    for record in included:
        groups[record.group_id].append(record)
    multi_groups = {group_id: members for group_id, members in groups.items() if len(members) > 1}
    cross_split_before = {
        group_id: members
        for group_id, members in multi_groups.items()
        if len({member.split for member in members}) > 1
    }

    # split 列表
    for split in SPLITS:
        split_records = sorted(
            (record for record in included if record.new_split == split), key=lambda record: record.rel
        )
        (out / "splits").mkdir(parents=True, exist_ok=True)
        (out / "splits" / f"{split}.txt").write_text(
            "\n".join(str(record.path.resolve()) for record in split_records) + "\n",
            encoding="utf-8",
        )

    write_dataset_yaml(out / "dataset_curated.yaml", dataset, out)

    # 报告
    class_stats = []
    for class_id, name in CLASS_NAMES.items():
        images_all = sum(1 for record in records if class_id in record.counts)
        instances_all = sum(record.counts[class_id] for record in records)
        images_included = sum(1 for record in included if class_id in record.counts)
        instances_included = sum(record.counts[class_id] for record in included)
        row = {
            "class_id": class_id,
            "name": name,
            "images_all": images_all,
            "instances_all": instances_all,
            "images_included": images_included,
            "instances_included": instances_included,
        }
        for split in SPLITS:
            row[f"{split}_images"] = sum(
                1 for record in included if record.new_split == split and class_id in record.counts
            )
            row[f"{split}_instances"] = sum(
                record.counts[class_id] for record in included if record.new_split == split
            )
        class_stats.append(row)
    write_csv(out / "class_stats.csv", list(class_stats[0].keys()), class_stats)

    source_stats = []
    for source in sorted({record.source for record in records}):
        all_records = [record for record in records if record.source == source]
        kept = [record for record in included if record.source == source]
        row = {
            "source": source,
            "images_all": len(all_records),
            "images_included": len(kept),
            "excluded": len(all_records) - len(kept),
        }
        for split in SPLITS:
            row[f"{split}_images"] = sum(1 for record in kept if record.new_split == split)
        row["instances_included"] = sum(len(record.boxes) for record in kept)
        source_stats.append(row)
    write_csv(out / "source_stats.csv", list(source_stats[0].keys()), source_stats)

    excluded_rows = []
    for record in excluded:
        reasons = record.issues + (["manual"] if "manual" in record.flags else [])
        excluded_rows.append(
            {
                "rel": record.rel,
                "abs": str(dataset / record.rel),
                "split": record.split,
                "source": record.source,
                "reason": ";".join(reasons),
                "person": record.counts.get(PERSON_ID, 0),
                "boxes": len(record.boxes),
                "classes": ";".join(CLASS_NAMES[class_id] for class_id in sorted(record.counts)),
            }
        )
    write_csv(out / "excluded.csv", list(excluded_rows[0].keys()) if excluded_rows else ["rel", "abs", "split", "source", "reason", "person", "boxes", "classes"], excluded_rows)

    review_rows = []
    for record in included:
        if not record.flags:
            continue
        review_rows.append(
            {
                "rel": record.rel,
                "abs": str(record.path),
                "split": record.split,
                "source": record.source,
                "flags": ";".join(record.flags),
                "person": record.counts.get(PERSON_ID, 0),
                "boxes": len(record.boxes),
                "width": record.width,
                "height": record.height,
                "person_area_max": round(record.person_area_max, 4),
                "white_ratio": round(record.white_ratio, 4),
                "classes": ";".join(CLASS_NAMES[class_id] for class_id in sorted(record.counts)),
            }
        )
    review_header = ["rel", "abs", "split", "source", "flags", "person", "boxes", "width", "height", "person_area_max", "white_ratio", "classes"]
    write_csv(out / "review.csv", list(review_rows[0].keys()) if review_rows else review_header, review_rows)
    for flag in ("no_person", "person_only", "closeup", "extreme_closeup", "product_like", "dense"):
        rows = [row for row in review_rows if flag in row["flags"].split(";")]
        write_csv(out / f"review_{flag}.csv", list(review_rows[0].keys()) if review_rows else ["rel"], rows)

    duplicate_rows = []
    duplicate_member_rows = []
    for group_id, members in sorted(multi_groups.items(), key=lambda item: (-len(item[1]), item[0])):
        representative = min(members, key=lambda member: member.rel)
        duplicate_rows.append(
            {
                "group_id": group_id,
                "size": len(members),
                "sources": ";".join(sorted({member.source for member in members})),
                "original_splits": ";".join(sorted({member.split for member in members})),
                "assigned_split": members[0].new_split,
                "representative": representative.rel,
            }
        )
        for member in sorted(members, key=lambda member: member.rel):
            duplicate_member_rows.append(
                {
                    "group_id": group_id,
                    "rel": member.rel,
                    "abs": str(member.path),
                    "source": member.source,
                    "original_split": member.split,
                    "assigned_split": member.new_split,
                }
            )
    write_csv(out / "duplicate_groups.csv", ["group_id", "size", "sources", "original_splits", "assigned_split", "representative"], duplicate_rows)
    write_csv(out / "duplicate_members.csv", ["group_id", "rel", "abs", "source", "original_split", "assigned_split"], duplicate_member_rows)

    manifest_rows = []
    for record in sorted(included, key=lambda record: record.rel):
        row = {
            "rel": record.rel,
            "abs": str(record.path),
            "source": record.source,
            "original_split": record.split,
            "assigned_split": record.new_split,
            "group_id": record.group_id,
            "boxes": len(record.boxes),
            "person_area_max": round(record.person_area_max, 4),
            "white_ratio": round(record.white_ratio, 4),
            "flags": ";".join(record.flags),
        }
        for class_id, name in CLASS_NAMES.items():
            row[name] = record.counts.get(class_id, 0)
        manifest_rows.append(row)
    write_csv(out / "split_manifest.csv", list(manifest_rows[0].keys()), manifest_rows)

    split_summary = {}
    for split in SPLITS:
        split_records = [record for record in included if record.new_split == split]
        split_summary[split] = {
            "images": len(split_records),
            "instances": sum(len(record.boxes) for record in split_records),
            "sources": dict(sorted(Counter(record.source for record in split_records).items())),
            "classes": {
                CLASS_NAMES[class_id]: sum(record.counts[class_id] for record in split_records)
                for class_id in CLASS_NAMES
            },
        }

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dataset": str(dataset),
        "out": str(out),
        "params": {
            "val_ratio": args.val_ratio,
            "test_ratio": args.test_ratio,
            "dup_threshold": args.dup_threshold,
            "seed": args.seed,
            "skip_dhash": args.skip_dhash,
        },
        "totals": {
            "images": len(records),
            "instances": sum(len(record.boxes) for record in records),
            "included": len(included),
            "excluded": len(excluded),
            "auto_excluded": sum(1 for record in excluded if "manual" not in record.flags),
            "manual_excluded": sum(1 for record in excluded if "manual" in record.flags),
            "review": len(review_rows),
            "review_flags": dict(Counter(flag for record in included for flag in record.flags)),
        },
        "groups": {
            "total": len(groups),
            "multi": len(multi_groups),
            "images_in_multi": sum(len(members) for members in multi_groups.values()),
            "cross_split_before": len(cross_split_before),
            "images_cross_split_before": sum(len(members) for members in cross_split_before.values()),
            "largest": sorted((len(members) for members in multi_groups.values()), reverse=True)[:10],
        },
        "splits": split_summary,
        "targets": targets,
        "actual": actual,
        "class_stats": class_stats,
        "source_stats": source_stats,
    }
    (out / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    validate_outputs(out, included)

    readme = f"""# 数据集整理产物

由 `scripts/curate_ppe_dataset.py` 生成。原始数据集只读，未移动或删除任何文件。

## 文件

| 文件 | 用途 |
| --- | --- |
| `dataset_curated.yaml` | 可直接传给 YOLO 的训练配置 |
| `splits/train.txt` 等 | 按近似重复组重划后的图片列表 |
| `summary.json` | 全部统计与参数 |
| `class_stats.csv` / `source_stats.csv` | 类别与来源分布 |
| `excluded.csv` | 自动隔离的图片及原因 |
| `review_*.csv` | 需要人工复核的图片（`abs` 列是绝对路径，可直接打开） |
| `duplicate_groups.csv` / `duplicate_members.csv` | 近似重复组 |
| `split_manifest.csv` | 每张图的新旧 split、组号、类别计数 |
| `manual_quarantine.csv` | 人工隔离清单（`abs,reason`）；`review.html` 导出的 `manual_quarantine.new.csv` 并进这里后重跑生效 |
| `review.html` | 由 `scripts/build_review_page.py` 生成的复核页，可逐张看图并导出隔离清单 |

## 用法

```bash
.venv/bin/python scripts/curate_ppe_dataset.py
.venv/bin/python scripts/build_review_page.py          # 生成 review.html
.venv/bin/python scripts/materialize_curated_dataset.py  # 落地成应用可选的数据集目录
```

训练：

```bash
.venv/bin/python -c "from ultralytics import YOLO; YOLO('pretrained_models/yolo11s.pt').train(data='{out / 'dataset_curated.yaml'}', imgsz=1280, epochs=100)"
```

## 注意

- 同一近似重复组只进一个 split，已消除跨 split 泄漏。
- `review_no_person.csv`、`review_person_only.csv`、`review_extreme_closeup.csv`、`review_product_like.csv` 需要人工确认后再决定是否加入 `manual_quarantine.csv`。
- `review_closeup.csv` 是宽口径清单（person 面积 ≥ 40%），优先看 `review_extreme_closeup.csv`（≥ 60%）。
- 当前是 9 类基线；`anchor` 需要补标后再加入。
"""
    (out / "README.md").write_text(readme, encoding="utf-8")

    manual_template = out / "manual_quarantine.csv"
    if not manual_template.exists():
        manual_template.write_text("abs,reason\n", encoding="utf-8")

    print("\n完成。")
    print(f"  进入划分: {len(included)} 张 ({len(records) - len(included)} 张被隔离)")
    for split in SPLITS:
        info = split_summary[split]
        print(f"  {split}: {info['images']} 张 / {info['instances']} 实例 / 来源 {info['sources']}")
    print(f"  近似重复: {len(multi_groups)} 组，覆盖 {summary['groups']['images_in_multi']} 张；"
          f"原来跨 split {len(cross_split_before)} 组 / {summary['groups']['images_cross_split_before']} 张")
    print(f"  输出目录: {out}")
    print(f"  训练配置: {out / 'dataset_curated.yaml'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
