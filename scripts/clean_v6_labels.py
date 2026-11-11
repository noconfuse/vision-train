#!/usr/bin/env python3
"""清理 dataset_v6 的 hook/lanyard 错误框 + 田字格 F11 废图。

三个动作，范围不同，只动 dataset_v6：

1. 删 hook 框：把所有标签文件里 hook 类的框行删掉，图和文件都留（现状全在 F13）。
2. 删 lanyard 框：同样只删框行，图和文件都留（现状全在 F03 + 1 张 F01）。
3. 删田字格 F11：F11 是 2×2 拼图废图，图片 + 对应标签文件一起删。

类别表（dataset.yaml）一行都不动，仍然是 6 类；hook/lanyard 后面重新标。

默认只报告不改动，加 --apply 才动文件。执行后写一份清单到 curation/，
记录删了哪些文件、哪些框，方便追查。

用法：
    python3 scripts/clean_v6_labels.py                 # 演练，打印清单和计数
    python3 scripts/clean_v6_labels.py --apply         # 真正执行
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPLITS = ("train", "val", "test")
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
GRID_PREFIX = "F11_"


def read_names(dataset: Path) -> dict[int, str]:
    names: dict[int, str] = {}
    inside = False
    for line in (dataset / "dataset.yaml").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("names:"):
            inside = True
            continue
        if not inside:
            continue
        if ":" not in stripped:
            break
        key, _, value = stripped.partition(":")
        try:
            names[int(key.strip())] = value.strip().strip("'\"")
        except ValueError:
            break
    if not names:
        raise SystemExit(f"{dataset / 'dataset.yaml'} 里读不到 names 表")
    return names


def id_for(names: dict[int, str], wanted: str) -> int:
    for class_id, name in names.items():
        if name == wanted:
            return class_id
    raise SystemExit(f"类别表里找不到 {wanted!r}，先核对 dataset.yaml")


def plan_line_removal(dataset: Path, class_id: int, class_name: str) -> list[dict]:
    """扫描该类的框行，返回每个文件要删的行数。不删任何东西。"""
    rows = []
    for split in SPLITS:
        labels_dir = dataset / split / "labels"
        if not labels_dir.is_dir():
            continue
        for label in sorted(labels_dir.glob("*.txt")):
            lines = label.read_text(encoding="utf-8").splitlines()
            kept = []
            removed = 0
            for line in lines:
                fields = line.split()
                if len(fields) < 5:
                    kept.append(line)
                    continue
                if int(float(fields[0])) == class_id:
                    removed += 1
                else:
                    kept.append(line)
            if removed:
                rows.append({
                    "split": split,
                    "stem": label.stem,
                    "removed": removed,
                    "remaining": len(kept),
                })
    return rows


def plan_grid_removal(dataset: Path) -> list[dict]:
    """找出 F11 拼图的 图 + 标签 对。不删任何东西。"""
    rows = []
    for split in SPLITS:
        images_dir = dataset / split / "images"
        labels_dir = dataset / split / "labels"
        if not images_dir.is_dir():
            continue
        for image in sorted(images_dir.iterdir()):
            if image.suffix.lower() not in IMAGE_EXTS:
                continue
            if image.name.startswith(GRID_PREFIX):
                label = labels_dir / f"{image.stem}.txt"
                rows.append({
                    "split": split,
                    "image": image.name,
                    "label": label.name if label.is_file() else "",
                })
    return rows


def apply_line_removal(dataset: Path, class_id: int, manifest) -> int:
    removed_total = 0
    for row in manifest:
        label = dataset / row["split"] / "labels" / f"{row['stem']}.txt"
        lines = label.read_text(encoding="utf-8").splitlines()
        kept = []
        for line in lines:
            fields = line.split()
            if len(fields) >= 5 and int(float(fields[0])) == class_id:
                removed_total += 1
                continue
            kept.append(line)
        label.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
    return removed_total


def apply_grid_removal(dataset: Path, manifest) -> int:
    removed_files = 0
    for row in manifest:
        image = dataset / row["split"] / "images" / row["image"]
        if image.exists():
            image.unlink()
            removed_files += 1
        label = dataset / row["split"] / "labels" / row["label"]
        if label.exists():
            label.unlink()
            removed_files += 1
    return removed_files


def main() -> None:
    parser = argparse.ArgumentParser(description="清理 dataset_v6 的 hook/lanyard 错误框 + F11 拼图废图")
    parser.add_argument("--dataset", default=REPO_ROOT / "projects/project-1/training/dataset_v6", type=Path)
    parser.add_argument("--manifest", default=REPO_ROOT / "projects/project-1/training/curation/v6_label_cleanup.csv", type=Path)
    parser.add_argument("--apply", action="store_true", help="真正删除；不加只报告")
    args = parser.parse_args()

    dataset = args.dataset.resolve()
    if not dataset.is_dir():
        raise SystemExit(f"数据集不存在: {dataset}")

    names = read_names(dataset)
    hook_id = id_for(names, "hook")
    lanyard_id = id_for(names, "lanyard")

    hook_rows = plan_line_removal(dataset, hook_id, "hook")
    lanyard_rows = plan_line_removal(dataset, lanyard_id, "lanyard")
    grid_rows = plan_grid_removal(dataset)

    hook_boxes = sum(r["removed"] for r in hook_rows)
    lanyard_boxes = sum(r["removed"] for r in lanyard_rows)
    empty_after = len([r for r in hook_rows + lanyard_rows if r["remaining"] == 0])

    print(f"数据集: {dataset}")
    print(f"1) 删 hook 框：{hook_boxes} 个，涉及 {len(hook_rows)} 个文件")
    print(f"2) 删 lanyard 框：{lanyard_boxes} 个，涉及 {len(lanyard_rows)} 个文件")
    print(f"3) 删田字格 F11：{len(grid_rows)} 张图（图+标签一起删）")
    print(f"   删框后变成空标签的文件 {empty_after} 个（保留空文件，当背景图）")

    if not args.apply:
        print("\n演练模式，未改动任何文件。加 --apply 执行。")
        return

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    removed_hook = apply_line_removal(dataset, hook_id, hook_rows)
    removed_lanyard = apply_line_removal(dataset, lanyard_id, lanyard_rows)
    removed_files = apply_grid_removal(dataset, grid_rows)

    with args.manifest.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["op", "split", "stem", "removed_boxes", "image", "label"])
        for r in hook_rows:
            writer.writerow(["hook", r["split"], r["stem"], r["removed"], "", ""])
        for r in lanyard_rows:
            writer.writerow(["lanyard", r["split"], r["stem"], r["removed"], "", ""])
        for r in grid_rows:
            writer.writerow(["grid_f11", r["split"], "", "", r["image"], r["label"]])

    print(f"\n已删 hook 框 {removed_hook} 个、lanyard 框 {removed_lanyard} 个、F11 图+标签 {removed_files} 个文件")
    print(f"清单已写到: {args.manifest}")

    for split in SPLITS:
        images = len(list((dataset / split / "images").glob("*"))) if (dataset / split / "images").is_dir() else 0
        labels = len(list((dataset / split / "labels").glob("*.txt"))) if (dataset / split / "labels").is_dir() else 0
        print(f"  {split}: 图 {images} / 标签 {labels}")
        if images != labels:
            raise SystemExit(f"{split} 图片和标签数量不相等：{images} vs {labels}")


if __name__ == "__main__":
    main()