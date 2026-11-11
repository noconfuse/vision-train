#!/usr/bin/env python3
"""把金标清单里的图片+标签从 dataset/ 移出来，落成独立数据集 dataset_gold/。

移动而不是复制：移走后 dataset/ 剩下的 12,359 张就是「教师自动标注」的池子，
不会和手工精标的这批重复，也不会出现同一张图同时训练又验证。
标签跟着走：这批图的旧标签大多不全或标错，但形状是对的，改起来比从零画快。

目录结构沿用原图在 dataset/ 里的 split（train/val/test），所以 dataset_gold 自己
也能直接训一个模型看指标；gold_manifest.csv 记每张图原来的位置，标完回写用。

默认只打印计划，加 --apply 才真移动。
"""

import argparse
import csv
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = REPO_ROOT / "projects/project-1/training/dataset"
DEFAULT_CURATION = REPO_ROOT / "projects/project-1/training/curation"
DEFAULT_OUT = REPO_ROOT / "projects/project-1/training/dataset_gold"

SPLITS = ("train", "val", "test")
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
META_FILENAME = ".vision-train.meta.json"
MANIFEST_FILENAME = "gold_manifest.csv"


def read_gold_rows(curation: Path) -> list:
    path = curation / "gold_set.csv"
    if not path.is_file():
        raise SystemExit(f"缺少 {path}，请先运行 scripts/sample_gold_set.py")
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_class_names(dataset: Path) -> list:
    """从原数据集的 dataset.yaml 抄类别表，保证两边类别 ID 一致。

    只认 `N: name` 这种扁平结构（本项目所有 dataset.yaml 都这么写），不引第三方依赖。
    """
    names = {}
    inside = False
    for line in (dataset / "dataset.yaml").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("names:"):
            inside = True
            continue
        if not inside:
            continue
        if ":" not in stripped or stripped.startswith("-"):
            break
        key, _, value = stripped.partition(":")
        try:
            names[int(key.strip())] = value.strip().strip("'\"")
        except ValueError:
            break
    if not names:
        raise SystemExit(f"没能从 {dataset / 'dataset.yaml'} 读出 names 表")
    return [names[index] for index in sorted(names)]


def label_for(image: Path) -> Path:
    return image.parent.parent / "labels" / f"{image.stem}.txt"


def plan_moves(rows, dataset: Path, out_dir: Path):
    """把清单里的每条映射成 (图片当前位置, 原 split, 是否已在目标目录)。

    已经在目标目录里的算「上次移过去了」，跳过移动但仍然补齐元数据，脚本可重入。
    """
    def index_images(root: Path) -> dict:
        found = {}
        for split in SPLITS:
            images_dir = root / split / "images"
            if not images_dir.is_dir():
                continue
            for image in images_dir.iterdir():
                if image.suffix.lower() in IMAGE_EXTS:
                    found.setdefault(image.stem, image)
        return found

    in_dataset = index_images(dataset)
    in_gold = index_images(out_dir)
    moves = []
    missing = []
    for row in rows:
        stem = Path(row["abs"]).stem
        source = in_dataset.get(stem)
        already_there = False
        if source is None:
            source = in_gold.get(stem)
            already_there = source is not None
        if source is None:
            missing.append(row["abs"])
            continue
        split = row["split"] if already_there else source.parent.parent.name
        moves.append(
            {
                "image": source,
                "label": label_for(source),
                "original_split": split,
                "already_there": already_there,
                "row": row,
            }
        )
    return moves, missing


def write_dataset_yaml(out_dir: Path, names: list) -> None:
    """照 dataset/dataset.yaml 的写法生成，不额外加 path: 键（应用会自己拼绝对路径）。"""
    lines = [
        "train: train/images",
        "val: val/images",
        "test: test/images",
        "names:",
    ]
    lines += [f"  {index}: {name}" for index, name in enumerate(names)]
    lines.append(f"nc: {len(names)}")
    (out_dir / "dataset.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_identity_meta(out_dir: Path) -> dict:
    target = out_dir / META_FILENAME
    meta = {}
    now = datetime.now(timezone.utc).isoformat()
    if target.is_file():
        try:
            meta = json.loads(target.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            meta = {}
    meta["vision_task_type"] = "detect"
    meta["dataset_id"] = str(meta.get("dataset_id") or "").strip() or uuid.uuid4().hex[:12]
    meta["created_at"] = meta.get("created_at") or now
    meta["updated_at"] = now
    target.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta


def count_pairs(root: Path) -> dict:
    stats = {}
    for split in SPLITS:
        images = [p for p in (root / split / "images").iterdir() if p.suffix.lower() in IMAGE_EXTS] if (root / split / "images").is_dir() else []
        labels = list((root / split / "labels").glob("*.txt")) if (root / split / "labels").is_dir() else []
        stats[split] = (len(images), len(labels))
    return stats


def main():
    parser = argparse.ArgumentParser(description="把金标集从 dataset/ 移到独立数据集")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--curation", default=str(DEFAULT_CURATION))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--apply", action="store_true", help="真的移动；不加只打印计划")
    args = parser.parse_args()

    dataset = Path(args.dataset).resolve()
    curation = Path(args.curation).resolve()
    out_dir = Path(args.out).resolve()
    rows = read_gold_rows(curation)
    moves, missing = plan_moves(rows, dataset, out_dir)
    pending = [move for move in moves if not move["already_there"]]
    already = [move for move in moves if move["already_there"]]
    print(f"清单 {len(rows)} 张 → 在 dataset/ 里 {len(pending)} 张，已在 dataset_gold/ 里 {len(already)} 张，两边都找不到 {len(missing)} 张")
    for abs_path in missing[:10]:
        print(f"  找不到: {abs_path}")
    if missing:
        raise SystemExit("有清单项在 dataset/ 和 dataset_gold/ 里都不存在，先确认图片没有丢")

    no_label = sum(1 for move in pending if not move["label"].is_file())
    print(f"  本次要移动的图 {len(pending)} 张，其中没有标签文件的 {no_label} 张")

    by_split = {}
    for move in moves:
        by_split[move["original_split"]] = by_split.get(move["original_split"], 0) + 1
    print("  按原 split：" + " ".join(f"{split}:{count}" for split, count in sorted(by_split.items())))

    if not args.apply:
        print("\n演练模式，没有动任何文件。加 --apply 执行。")
        return

    for split in SPLITS:
        (out_dir / split / "images").mkdir(parents=True, exist_ok=True)
        (out_dir / split / "labels").mkdir(parents=True, exist_ok=True)

    manifest_rows = []
    moved = 0
    for move in moves:
        split = move["original_split"]
        image_src, label_src = move["image"], move["label"]
        image_dst = out_dir / split / "images" / image_src.name
        label_dst = out_dir / split / "labels" / label_src.name
        if image_src == image_dst:
            pass
        elif image_dst.exists():
            raise SystemExit(f"目标已存在，拒绝覆盖: {image_dst}")
        else:
            shutil.move(str(image_src), str(image_dst))
            moved += 1
        if label_src.is_file() and not label_dst.exists():
            shutil.move(str(label_src), str(label_dst))
        row = move["row"]
        manifest_rows.append(
            {
                "name": image_src.name,
                "stem": image_src.stem,
                "gold_abs": str(image_dst),
                "original_split": split,
                "source": row["source"],
                "priorities": row.get("priorities", ""),
                "old_boxes": row.get("boxes", ""),
                "old_classes": row.get("classes", ""),
            }
        )

    names = read_class_names(dataset)
    write_dataset_yaml(out_dir, names)
    meta = write_identity_meta(out_dir)
    with (out_dir / MANIFEST_FILENAME).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0].keys()))
        writer.writeheader()
        writer.writerows(manifest_rows)

    gold_stats = count_pairs(out_dir)
    rest_stats = count_pairs(dataset)
    print(f"\n移动 {moved} 张图（标签跟着走）")
    print(f"  dataset_gold/ " + " ".join(f"{s} 图{v[0]}/标签{v[1]}" for s, v in sorted(gold_stats.items())))
    print(f"  dataset/      " + " ".join(f"{s} 图{v[0]}/标签{v[1]}" for s, v in sorted(rest_stats.items())))
    gold_total = sum(v[0] for v in gold_stats.values())
    rest_total = sum(v[0] for v in rest_stats.values())
    for label, stats in (("dataset_gold", gold_stats), ("dataset", rest_stats)):
        for split, (images, labels) in sorted(stats.items()):
            if images != labels:
                raise SystemExit(f"{label}/{split} 图和标签数量不相等：{images} vs {labels}")
    print(f"  合计 {gold_total} + {rest_total} = {gold_total + rest_total}")
    print(f"  dataset_id: {meta['dataset_id']}；回写映射 {out_dir / MANIFEST_FILENAME}")
    print("  在应用里选 dataset_gold 就是这 661 张的标注队列；dataset/ 剩下的是教师自动标注的池子")


if __name__ == "__main__":
    main()
