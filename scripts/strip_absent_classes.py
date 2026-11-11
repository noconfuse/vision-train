#!/usr/bin/env python3
"""把一个检测数据集复制成新数据集，并去掉 no_*（未穿戴）类。

为什么要去掉：未穿戴不是一个能框的东西，它是「person 框划出的头/躯干区域看得见、
但对应的穿戴类没出框」，这个判断用规则算就行。留着 no_* 等于让模型重学一遍规则
免费给的东西，还学得更差。

类别 ID 会重排成连续的 0..N-1（Ultralytics 要求），所以新数据集和旧的 9 类权重
不通用；原数据集一个字节都不改，只新增目录。

用法：
    python3 scripts/strip_absent_classes.py --src <数据集目录> --dst <新目录>
"""

import argparse
import csv
import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SPLITS = ("train", "val", "test")
IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
META_FILENAME = ".vision-train.meta.json"
ABSENT_PREFIX = "no_"


def read_names(dataset: Path) -> dict:
    """读 dataset.yaml 的 names 表，只认 `N: name` 这种扁平写法。"""
    names = {}
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


def rewrite_label(src: Path, dst: Path, keep: dict) -> tuple:
    """按 keep 映射重写标签，返回 (保留框数, 丢弃框数)。"""
    kept = dropped = 0
    lines = []
    for line in src.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) < 5:
            continue
        class_id = int(float(fields[0]))
        if class_id in keep:
            lines.append(" ".join([str(keep[class_id])] + fields[1:5]))
            kept += 1
        else:
            dropped += 1
    dst.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return kept, dropped


def write_dataset_yaml(dst_dir: Path, names: list) -> None:
    lines = [f"{split}: {split}/images" for split in SPLITS]
    lines.append("names:")
    lines += [f"  {index}: {name}" for index, name in enumerate(names)]
    lines.append(f"nc: {len(names)}")
    (dst_dir / "dataset.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_meta(dst_dir: Path) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    meta = {
        "vision_task_type": "detect",
        "dataset_id": uuid.uuid4().hex[:12],
        "created_at": now,
        "updated_at": now,
    }
    (dst_dir / META_FILENAME).write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return meta


def copy_image(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        raise SystemExit(f"目标已存在，拒绝覆盖: {dst}")
    shutil.copy2(src, dst)


def main():
    parser = argparse.ArgumentParser(description="复制数据集并去掉 no_* 类")
    parser.add_argument("--src", required=True)
    parser.add_argument("--dst", required=True)
    args = parser.parse_args()

    src = Path(args.src).resolve()
    dst = Path(args.dst).resolve()
    if not src.is_dir():
        raise SystemExit(f"源数据集不存在: {src}")
    if dst.exists():
        raise SystemExit(f"目标目录已经存在，不想覆盖: {dst}")

    old_names = read_names(src)
    keep = {}
    new_names = []
    dropped_classes = []
    for old_id in sorted(old_names):
        name = old_names[old_id]
        if name.startswith(ABSENT_PREFIX):
            dropped_classes.append(name)
            continue
        keep[old_id] = len(new_names)
        new_names.append(name)
    print(f"{src.name} → {dst.name}")
    print(f"  保留类别: {', '.join(f'{i}={n}' for i, n in enumerate(new_names))}")
    print(f"  去掉类别: {', '.join(dropped_classes)}")

    totals = {"images": 0, "kept": 0, "dropped": 0, "empty": 0, "no_label": 0}
    for split in SPLITS:
        images_dir = src / split / "images"
        labels_dir = src / split / "labels"
        if not images_dir.is_dir():
            continue
        (dst / split / "labels").mkdir(parents=True, exist_ok=True)
        for image in sorted(images_dir.iterdir()):
            if image.suffix.lower() not in IMAGE_EXTS:
                continue
            copy_image(image, dst / split / "images" / image.name)
            totals["images"] += 1
            label = labels_dir / f"{image.stem}.txt"
            if not label.is_file():
                totals["no_label"] += 1
                continue
            kept, dropped = rewrite_label(label, dst / split / "labels" / f"{image.stem}.txt", keep)
            totals["kept"] += kept
            totals["dropped"] += dropped
            totals["empty"] += 1 if kept == 0 else 0

    write_dataset_yaml(dst, new_names)
    meta = write_meta(dst)
    for extra in ("gold_manifest.csv",):
        if (src / extra).is_file():
            shutil.copy2(src / extra, dst / extra)
            print(f"  带过去 {extra}（回写映射）")

    print(f"  图片 {totals['images']} 张 | 保留框 {totals['kept']} | 丢弃框 {totals['dropped']}")
    print(f"  去掉 no_* 后变成空标签的图 {totals['empty']} 张（保留空文件，训练时当背景图）")
    if totals["no_label"]:
        print(f"  源数据集里有 {totals['no_label']} 张图没有标签文件")
    for split in SPLITS:
        images = len(list((dst / split / "images").glob("*"))) if (dst / split / "images").is_dir() else 0
        labels = len(list((dst / split / "labels").glob("*.txt"))) if (dst / split / "labels").is_dir() else 0
        if images != labels:
            raise SystemExit(f"{split} 图和标签数量不相等：{images} vs {labels}")
        print(f"  {split}: 图 {images} / 标签 {labels}")
    print(f"  dataset_id: {meta['dataset_id']}")


if __name__ == "__main__":
    main()
