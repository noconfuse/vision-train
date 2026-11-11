#!/usr/bin/env python3
"""把整理结果真正落到原始数据集上：隔离图物理移出，保留图按新 split 归位。

默认只报告不改动，加 --apply 才动文件。
"""

from __future__ import annotations

import argparse
import csv
import shutil
import sys
from collections import Counter
from pathlib import Path

SPLITS = ("train", "val", "test")
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


def read_csv(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def find_image(dataset: Path, split: str, stem: str) -> Path | None:
    images = dataset / split / "images"
    for ext in IMAGE_EXTS:
        candidate = images / f"{stem}{ext}"
        if candidate.exists():
            return candidate
    return None


def plan(dataset: Path, curation: Path, quarantine: Path):
    excluded = read_csv(curation / "excluded.csv")
    manifest = read_csv(curation / "split_manifest.csv")

    quarantine_by_name = {}
    for row in excluded:
        rel = row["rel"]
        split, name = rel.split("/", 1)
        quarantine_by_name[Path(name).stem] = (split, Path(name).name, row.get("reason") or "excluded")

    keep_by_name = {}
    for row in manifest:
        rel = row["rel"]
        split, name = rel.split("/", 1)
        keep_by_name[Path(name).stem] = (split, Path(name).name, row.get("assigned_split") or split)

    moves_quarantine = []
    missing_quarantine = []
    for stem, (split, name, reason) in sorted(quarantine_by_name.items()):
        image = find_image(dataset, split, stem)
        if image is None:
            missing_quarantine.append(f"{split}/images/{name}")
            continue
        moves_quarantine.append((image, stem, name, split, reason))

    moves_resplit = []
    missing_keep = []
    for stem, (old_split, name, new_split) in sorted(keep_by_name.items()):
        image = find_image(dataset, old_split, stem)
        if image is None:
            # 文件可能已经被上一次运行挪到别的位置，兜底扫全部分区
            for split in SPLITS:
                image = find_image(dataset, split, stem)
                if image is not None:
                    old_split = split
                    break
        if image is None:
            missing_keep.append(f"{old_split}/images/{name}")
            continue
        if image.parent.parent.name != new_split:
            moves_resplit.append((image, stem, new_split))

    return moves_quarantine, moves_resplit, missing_quarantine, missing_keep, len(keep_by_name)


def move_pair(image: Path, stem: str, target_dir: Path) -> list[tuple[Path, Path]]:
    target_dir.mkdir(parents=True, exist_ok=True)
    pairs = [(image, target_dir / image.name)]
    label = image.parent.parent / "labels" / f"{stem}.txt"
    if label.exists():
        pairs.append((label, target_dir.parent / "labels" / f"{stem}.txt"))
    return pairs


def apply_moves(moves, target_root_of, dataset, quarantine):
    moved_files = 0
    for entry in moves:
        image, stem = entry[0], entry[1]
        target_dir = target_root_of(entry)
        target_dir.mkdir(parents=True, exist_ok=True)
        for src, dst in move_pair(image, stem, target_dir):
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                raise SystemExit(f"目标已存在，拒绝覆盖: {dst}")
            shutil.move(str(src), str(dst))
            moved_files += 1
    return moved_files


def verify(dataset: Path, quarantine: Path, expected_keep: int):
    problems = []
    counts = {}
    for split in SPLITS:
        images = list((dataset / split / "images").glob("*")) if (dataset / split / "images").exists() else []
        labels = list((dataset / split / "labels").glob("*")) if (dataset / split / "labels").exists() else []
        counts[split] = (len(images), len(labels))
        if len(images) != len(labels):
            problems.append(f"{split} 图片 {len(images)} 与标签 {len(labels)} 不一致")
    total = sum(n for n, _ in counts.values())
    if total != expected_keep:
        problems.append(f"dataset/ 现有 {total} 张，期望 {expected_keep} 张")
    q_images = sum(len(list((quarantine / s / "images").glob("*"))) for s in SPLITS) if quarantine.exists() else 0
    return counts, q_images, problems


def main() -> None:
    parser = argparse.ArgumentParser(description="把 curation 结果物理落到原始数据集上")
    default = Path("projects/project-1/training")
    parser.add_argument("--dataset", default=default / "dataset", type=Path)
    parser.add_argument("--curation", default=default / "curation", type=Path)
    parser.add_argument("--quarantine", default=default / "dataset_quarantine", type=Path)
    parser.add_argument("--apply", action="store_true", help="真正移动文件；不加只报告")
    args = parser.parse_args()

    dataset = args.dataset.resolve()
    curation = args.curation.resolve()
    quarantine = args.quarantine.resolve()

    if not (curation / "excluded.csv").exists() or not (curation / "split_manifest.csv").exists():
        raise SystemExit(f"缺少 excluded.csv 或 split_manifest.csv: {curation}")

    mq, mr, miss_q, miss_k, expected = plan(dataset, curation, quarantine)

    print(f"数据集: {dataset}")
    print(f"隔离待移出: {len(mq)} 张（清单 {len(mq) + len(miss_q)} 条，已不在原位 {len(miss_q)}）")
    print(f"保留待换 split: {len(mr)} 张")
    print(f"保留总数: {expected}")
    if miss_k:
        print(f"警告: {len(miss_k)} 张保留图在数据集里找不到，例如 {miss_k[:3]}")
    if not args.apply:
        print("演练模式，未改动任何文件。加 --apply 执行。")
        return

    moved_q = apply_moves(
        [(img, stem, split, reason) for img, stem, _name, split, reason in mq],
        lambda e: quarantine / e[2] / "images",
        dataset,
        quarantine,
    )
    with (quarantine / "QUARANTINE.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["stem", "original_split", "reason", "abs"])
        for _img, stem, _name, split, reason in mq:
            writer.writerow([stem, split, reason, str(quarantine / split / "images" / _img.name)])

    moved_r = apply_moves(
        [(img, stem, new_split) for img, stem, new_split in mr],
        lambda e: dataset / e[2] / "images",
        dataset,
        quarantine,
    )

    counts, q_total, problems = verify(dataset, quarantine, expected)
    print(f"已移出隔离 {moved_q} 个文件，换 split {moved_r} 个文件，隔离区现有 {q_total} 张")
    for split in SPLITS:
        print(f"  dataset/{split}: 图片 {counts[split][0]} / 标签 {counts[split][1]}")
    if problems:
        for problem in problems:
            print(f"校验失败: {problem}", file=sys.stderr)
        raise SystemExit(1)
    print("校验通过。")


if __name__ == "__main__":
    main()
