#!/usr/bin/env python3
"""把整理后的 split 列表落地为标准检测数据集目录，供应用训练链路直接选择。

图片使用硬链接（不额外占盘，且不会改动原数据集内容）；标签使用复制，避免
在应用里改标注时通过硬链接写回原数据集。原数据集只读，不移动、不删除。

用法：
    .venv/bin/python scripts/materialize_curated_dataset.py
    .venv/bin/python scripts/materialize_curated_dataset.py --check
"""

import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CURATION = REPO_ROOT / "projects/project-1/training/curation"
DEFAULT_OUT = REPO_ROOT / "projects/project-1/training/dataset_curated"
DEFAULT_DATASET = REPO_ROOT / "projects/project-1/training/dataset"

SPLITS = ("train", "val", "test")
META_FILENAME = ".vision-train.meta.json"
MANIFEST_FILENAME = "curation_manifest.csv"


def read_split_list(path):
    """读取 split txt，返回图片绝对路径列表。"""
    if not path.is_file():
        raise SystemExit(f"缺少 split 文件: {path}")
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    return [line for line in lines if line]


def label_path_for(image_path):
    """按 YOLO 目录约定把 images/xxx.jpg 映射到 labels/xxx.txt。"""
    parts = list(image_path.parts)
    if "images" not in parts:
        raise SystemExit(f"图片不在 images/ 目录下，无法定位标签: {image_path}")
    index = len(parts) - 1 - parts[::-1].index("images")
    parts[index] = "labels"
    return Path(*parts).with_suffix(".txt")


def resolve_source(manifest, rel):
    """从 split_manifest.csv 读取来源信息。"""
    row = manifest.get(rel)
    if row is None:
        return {"source": "", "original_split": "", "group_id": ""}
    return row


def unique_stem(stem, suffix, used):
    """处理重名：保留原名，必要时追加序号。"""
    candidate = stem + suffix
    if candidate not in used:
        return candidate
    counter = 2
    while True:
        candidate = f"{stem}__{counter}{suffix}"
        if candidate not in used:
            return candidate
        counter += 1


def file_digest(path: Path) -> str:
    """流式 md5，用于判断两份文件内容是否相同。"""
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relink(source: Path, target: Path):
    """断开旧链接，重新硬链接到源文件。"""
    target.unlink()
    os.link(source, target)


def link_image(source, target):
    """硬链接图片。

    DVC 入库会把工作区文件换成新 inode，所以「不是同一文件」不代表内容变了：
    先比内容，相同就重新硬链接回去，不同才按修改时间决定跟随源还是保护本地改动。
    """
    if target.exists():
        if os.path.samefile(source, target):
            return "skipped"
        if file_digest(source) == file_digest(target):
            relink(source, target)
            return "relinked"
        if source.stat().st_mtime > target.stat().st_mtime:
            relink(source, target)
            return "updated"
        raise SystemExit(f"输出目录里的图片与原数据集内容不同且更新，可能被单独改过: {target}")
    os.link(source, target)
    return "linked"


def copy_label(source, target):
    """复制标签；内容不同时按修改时间判断该跟随源还是保护本地改动。"""
    if target.exists():
        if source.read_bytes() == target.read_bytes():
            return "skipped"
        if source.stat().st_mtime >= target.stat().st_mtime:
            shutil.copy2(source, target)
            return "updated"
        raise SystemExit(f"输出目录里的标签比原数据集更新，可能被单独改过: {target}")
    shutil.copy2(source, target)
    return "copied"


def load_manifest(curation_dir):
    """读取 split_manifest.csv，按原始相对路径建立索引。"""
    manifest_path = curation_dir / "split_manifest.csv"
    rows = {}
    if not manifest_path.is_file():
        return rows
    with manifest_path.open(encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            rows[row["rel"]] = row
    return rows


def read_class_names(curation_dir, dataset_dir):
    """优先使用整理产物里的类别名，缺失时回退原数据集配置。"""
    for candidate in (curation_dir / "dataset_curated.yaml", dataset_dir / "dataset.yaml"):
        if not candidate.is_file():
            continue
        data = yaml.safe_load(candidate.read_text(encoding="utf-8")) or {}
        names = data.get("names")
        if isinstance(names, dict):
            return {int(key): str(value) for key, value in names.items()}
        if isinstance(names, list):
            return {index: str(value) for index, value in enumerate(names)}
    raise SystemExit("找不到可用的类别名定义")


def write_dataset_yaml(out_dir, names):
    """写标准检测配置；path 用相对目录，便于整个项目迁移。"""
    config = {
        "path": ".",
        "train": "train/images",
        "val": "val/images",
        "test": "test/images",
        "names": {class_id: names[class_id] for class_id in sorted(names)},
        "nc": len(names),
    }
    target = out_dir / "dataset.yaml"
    target.write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return target


def write_identity_meta(out_dir):
    """确保数据集有稳定 dataset_id 与任务类型，重复执行时复用原身份。"""
    target = out_dir / META_FILENAME
    now = datetime.now(timezone.utc).astimezone().isoformat()
    meta = {}
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


def ensure_project_dvcignore(out_dir: Path):
    """在项目根 `.dvcignore` 里补上训练缓存规则。

    规则不能写进数据集目录内部：DVC 会拒绝 `.dvcignore` 出现在被收集的路径里。
    """
    project_root = out_dir.parent.parent
    target = project_root / ".dvcignore"
    rules = ["*.cache", "*.npy"]
    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    missing = [rule for rule in rules if rule not in existing]
    if not missing:
        return target
    with target.open("a", encoding="utf-8") as handle:
        if existing and not existing.endswith("\n"):
            handle.write("\n")
        handle.write("".join(f"{rule}\n" for rule in missing))
    return target


IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def prune_stale(out_dir, expected_per_split, stats):
    """删除上一次落地留下、但本次 split 列表里已不存在的图片与标签。"""
    for split in SPLITS:
        expected = expected_per_split[split]
        removed = 0
        for sub, keep in (("images", expected), ("labels", {Path(name).stem for name in expected})):
            directory = out_dir / split / sub
            if not directory.is_dir():
                continue
            for path in directory.iterdir():
                if not path.is_file():
                    continue
                if sub == "labels" and path.suffix != ".txt":
                    continue
                if sub == "images" and path.suffix.lower() not in IMAGE_EXTS:
                    continue
                key = path.stem if sub == "labels" else path.name
                if key not in keep:
                    path.unlink()
                    removed += 1
        stats[split]["pruned"] = removed


def materialize(curation_dir, out_dir, dataset_dir, check_only=False, prune=True):
    """按 split 列表落地目录，返回统计信息。"""
    manifest = load_manifest(curation_dir)
    names = read_class_names(curation_dir, dataset_dir)
    stats = {}
    manifest_rows = []
    used_names = set()
    expected_per_split = {}

    for split in SPLITS:
        images = read_split_list(curation_dir / "splits" / f"{split}.txt")
        image_dir = out_dir / split / "images"
        label_dir = out_dir / split / "labels"
        counts = {
            "images": 0, "labels": 0, "linked": 0, "copied": 0,
            "skipped": 0, "updated": 0, "relinked": 0, "renamed": 0, "pruned": 0,
        }
        expected = set()
        expected_per_split[split] = expected
        if not check_only:
            image_dir.mkdir(parents=True, exist_ok=True)
            label_dir.mkdir(parents=True, exist_ok=True)

        for image_path in images:
            source = Path(image_path)
            if not source.is_file():
                raise SystemExit(f"图片不存在: {source}")
            label_source = label_path_for(source)
            if not label_source.is_file():
                raise SystemExit(f"标签不存在: {label_source}")
            try:
                rel = source.relative_to(dataset_dir).as_posix()
            except ValueError:
                raise SystemExit(f"图片不在原数据集目录下: {source}")

            if check_only:
                counts["images"] += 1
                counts["labels"] += 1
                continue

            name = unique_stem(source.stem, source.suffix, used_names)
            used_names.add(name)
            expected.add(name)
            if name != source.name:
                counts["renamed"] += 1
            target_image = image_dir / name
            target_label = label_dir / Path(name).with_suffix(".txt")
            link_state = link_image(source, target_image)
            copy_state = copy_label(label_source, target_label)
            if link_state == "linked":
                counts["linked"] += 1
            if copy_state == "copied":
                counts["copied"] += 1
            if "updated" in (link_state, copy_state):
                counts["updated"] += 1
            if link_state == "relinked":
                counts["relinked"] += 1
            if link_state == "skipped" and copy_state == "skipped":
                counts["skipped"] += 1
            counts["images"] += 1
            counts["labels"] += 1

            source_row = resolve_source(manifest, rel)
            manifest_rows.append(
                {
                    "new_rel": f"{split}/images/{name}",
                    "original_rel": rel,
                    "split": split,
                    "source": source_row["source"],
                    "original_split": source_row["original_split"],
                    "group_id": source_row["group_id"],
                }
            )

        stats[split] = counts

    if not check_only and prune:
        prune_stale(out_dir, expected_per_split, stats)

    if check_only:
        return stats, manifest_rows

    write_dataset_yaml(out_dir, names)
    meta = write_identity_meta(out_dir)
    ensure_project_dvcignore(out_dir)

    manifest_path = out_dir / MANIFEST_FILENAME
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["new_rel", "original_rel", "split", "source", "original_split", "group_id"],
        )
        writer.writeheader()
        writer.writerows(manifest_rows)

    stats["dataset_id"] = meta["dataset_id"]
    stats["class_names"] = names
    stats["manifest"] = str(manifest_path)
    return stats, manifest_rows


def validate(out_dir, expected):
    """独立复核文件数量与标签完整性。"""
    problems = []
    for split in SPLITS:
        image_dir = out_dir / split / "images"
        label_dir = out_dir / split / "labels"
        images = sorted(path.name for path in image_dir.iterdir() if path.is_file())
        labels = sorted(path.name for path in label_dir.iterdir() if path.is_file())
        if len(images) != expected[split]:
            problems.append(f"{split}: 图片 {len(images)} != 期望 {expected[split]}")
        image_stems = {Path(name).stem for name in images}
        label_stems = {Path(name).stem for name in labels}
        if image_stems != label_stems:
            problems.append(f"{split}: 图片与标签文件名不匹配")
        for name in labels:
            for line_no, line in enumerate((label_dir / name).read_text(encoding="utf-8").splitlines(), 1):
                if not line.strip():
                    continue
                fields = line.split()
                if len(fields) != 5:
                    problems.append(f"{split}/labels/{name}:{line_no} 列数 {len(fields)} != 5")
                    break
                try:
                    class_id = int(fields[0])
                except ValueError:
                    problems.append(f"{split}/labels/{name}:{line_no} 类别不是整数")
                    break
                if class_id not in range(9):
                    problems.append(f"{split}/labels/{name}:{line_no} 类别 {class_id} 越界")
                    break
    return problems


def main():
    parser = argparse.ArgumentParser(description="把整理后的 split 落地为标准数据集目录")
    parser.add_argument("--curation", default=str(DEFAULT_CURATION), help="整理产物目录")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="输出数据集目录")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET), help="原始数据集目录（只读）")
    parser.add_argument("--check", action="store_true", help="只校验 split 列表，不写文件")
    parser.add_argument("--no-prune", action="store_true", help="不清理上次落地残留的文件")
    args = parser.parse_args()

    curation_dir = Path(args.curation).resolve()
    out_dir = Path(args.out).resolve()
    dataset_dir = Path(args.dataset).resolve()

    if out_dir == dataset_dir:
        raise SystemExit("输出目录不能是原始数据集目录")
    if not args.check:
        out_dir.mkdir(parents=True, exist_ok=True)

    stats, _ = materialize(curation_dir, out_dir, dataset_dir, check_only=args.check, prune=not args.no_prune)

    expected = {split: stats[split]["images"] for split in SPLITS}
    print(f"输出目录: {out_dir}")
    for split in SPLITS:
        counts = stats[split]
        print(
            f"  {split}: {counts['images']} 张，新链接 {counts['linked']}，重新硬链接 {counts['relinked']}，"
            f"新复制 {counts['copied']}，跟随原数据集更新 {counts['updated']}，未变 {counts['skipped']}，清理残留 {counts['pruned']}"
        )

    if args.check:
        return

    problems = validate(out_dir, expected)
    if problems:
        for problem in problems[:20]:
            print(f"校验失败: {problem}", file=sys.stderr)
        raise SystemExit(1)
    print(f"dataset_id: {stats['dataset_id']}")
    print(f"清单: {stats['manifest']}")


if __name__ == "__main__":
    main()
