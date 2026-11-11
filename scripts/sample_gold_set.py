#!/usr/bin/env python3
"""从 dataset/ 里分层抽样出一批「金标」图片，交给人工标注。

用途：先用这批手工核准的图训练一个教师模型，再用教师去自动标注剩下的图，
最后只复核「教师标签和现有标签冲突」的那部分。

分层维度：split（train/val/test）× 来源（F01/F03/F04/F06/F07/F11/F13）
× 人数档位 × 躯干穿戴状态档位。稀有格子（有 harness 但背心状态未标、
背心和安全带同时出现、真实场景的 hook、有 lanyard 的图等）先按配额强制
取走，剩余名额按 sqrt(格子大小) 比例分配——既不让 F03 的密集人群吞掉整份
样本，也不把分布拉平到失真。

同一批近似重复图（dHash group）默认只取一张，避免把人工时间花在几乎相同的
画面上。

输出：
  curation/gold_set.csv      每张图一行，abs 是绝对路径，可直接点开
  curation/gold_unselected.csv 各格子的剩余候选，方便后续补量
"""

import argparse
import csv
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATASET = REPO_ROOT / "projects/project-1/training/dataset"
DEFAULT_CURATION = REPO_ROOT / "projects/project-1/training/curation"

SPLITS = ("train", "val", "test")
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
WORN = ("harness", "vest")
MISSING = ("no_harness", "no_vest")
HEAD = ("helmet", "no_helmet")
GEAR = ("lanyard", "hook")

DEFAULT_QUOTA = {"train": 500, "val": 100, "test": 100}

# 每个 split 内，先给每个来源保底这么多「填充」名额，剩下的按人群数量分摊
SOURCE_FLOOR = {"train": 40, "val": 8, "test": 8}

# 近似重复组最多取几张：组内画面几乎一样，标多了换不来信息
GROUP_PICK_LIMIT = 2

# 纯填充阶段各人数档位上限。0 人的图基本是 F13 的假人/产品特写，人工标它换不来
# 线上用得上的信息，只靠下面的强制格子按绳钩覆盖少量取入。
PERSON_CAPS = {"train": {"0人": 18}, "val": {"0人": 5}, "test": {"0人": 5}}

# 强制格子：(名称, 判定函数, 每个 split 的上限, 是否全取)
# 上限按 train/val/test 顺序给出；「全取」的格子不管配额先全部拉进来（本来就只剩几张）。
PRIORITY_SPECS = [
    ("已标安全带但背心状态完全未标", "harness_unjudged_vest", lambda r: r["harness"] > 0 and r["vest"] == 0 and r["no_vest"] == 0, (60, 12, 12), False),
    ("安全带+无背心解耦样本（稀有，全取）", "harness_and_no_vest", lambda r: r["harness"] > 0 and r["no_vest"] > 0, (30, 10, 10), True),
    ("背心+无安全带解耦样本（稀有，全取）", "vest_and_no_harness", lambda r: r["vest"] > 0 and r["no_harness"] > 0, (30, 10, 10), True),
    ("背心与安全带同框（重叠几何样本）", "vest_and_harness", lambda r: r["vest"] > 0 and r["harness"] > 0, (30, 10, 10), True),
    ("已标反光背心（全数据集只有 311 张，稀有类）", "vest_present", lambda r: r["vest"] > 0, (75, 18, 18), False),
    ("已标无背心（全数据集只有 404 张）", "no_vest_present", lambda r: r["no_vest"] > 0, (60, 15, 15), False),
    ("真实场景 hook（非 F13 产品图，全取）", "hook_real_scene", lambda r: r["hook"] > 0 and r["source"] != "F13", (40, 10, 10), True),
    ("hook 与 lanyard 同框（高挂低用几何，全取）", "hook_and_lanyard", lambda r: r["hook"] > 0 and r["lanyard"] > 0, (20, 10, 10), True),
    ("有安全绳且有人员（挂点高度可判）", "lanyard_with_person", lambda r: r["lanyard"] > 0 and r["person"] > 0, (45, 12, 12), False),
    ("已戴头盔与未戴同框（正负对照）", "helmet_and_no_helmet", lambda r: r["helmet"] > 0 and r["no_helmet"] > 0, (20, 8, 8), False),
    ("有人员但 PPE 全部未标（从零补标）", "person_no_ppe", lambda r: r["person"] > 0 and not any(r[n] for n in ("harness", "no_harness", "helmet", "no_helmet", "vest", "no_vest")), (40, 10, 10), False),
]


def read_group_map(manifest: Path) -> dict:
    """从 split_manifest.csv 按文件名 stem 取 dHash group、来源和统计列。

    manifest 的 rel/abs 是重划前的旧路径，只有 stem、source、group_id、
    person_area_max、white_ratio 这几列仍然可信，split 以磁盘为准。
    """
    groups = {}
    if not manifest.is_file():
        return groups
    with manifest.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            stem = Path(row.get("rel") or "").stem
            if stem:
                groups[stem] = row
    return groups


def count_classes(label_path: Path) -> dict:
    counts = {name: 0 for name in CLASS_NAMES.values()}
    for line in label_path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) < 5:
            continue
        class_id = int(float(fields[0]))
        name = CLASS_NAMES.get(class_id)
        if name:
            counts[name] += 1
    return counts


def person_bucket(count: int) -> str:
    if count == 0:
        return "0人"
    if count == 1:
        return "1人"
    if count <= 4:
        return "2-4人"
    if count <= 8:
        return "5-8人"
    return "9+人"


def torso_state(record: dict) -> str:
    worn = any(record[name] for name in WORN)
    missing = any(record[name] for name in MISSING)
    if worn and missing:
        return "正负混合"
    if worn:
        return "有已穿戴"
    if missing:
        return "只有未穿戴"
    return "躯干未标"


def head_state(record: dict) -> str:
    if record["helmet"] and record["no_helmet"]:
        return "头盔正负混合"
    if record["helmet"]:
        return "有戴头盔"
    if record["no_helmet"]:
        return "有无头盔"
    return "头部未标"


def gear_state(record: dict) -> str:
    if record["lanyard"] and record["hook"]:
        return "绳+钩"
    if record["lanyard"]:
        return "只有绳"
    if record["hook"]:
        return "只有钩"
    return "无绳钩"


def collect(dataset: Path, manifest: Path) -> list:
    groups = read_group_map(manifest)
    records = []
    for split in SPLITS:
        images_dir = dataset / split / "images"
        labels_dir = dataset / split / "labels"
        if not images_dir.is_dir():
            continue
        for image in sorted(images_dir.iterdir()):
            if image.suffix.lower() not in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
                continue
            label = labels_dir / f"{image.stem}.txt"
            if not label.is_file():
                continue
            counts = count_classes(label)
            meta = groups.get(image.stem, {})
            name = image.name
            source = name.split("_", 1)[0] if "_" in name else meta.get("source", "NA")
            record = dict(counts)
            record.update(
                {
                    "abs": str(image),
                    "stem": image.stem,
                    "split": split,
                    "source": source,
                    "group_id": meta.get("group_id", ""),
                    "boxes": sum(counts.values()),
                    "person_area_max": meta.get("person_area_max", ""),
                    "white_ratio": meta.get("white_ratio", ""),
                    "person_bucket": person_bucket(counts["person"]),
                    "torso": torso_state(counts),
                    "head": head_state(counts),
                    "gear": gear_state(counts),
                    "priorities": [],
                }
            )
            records.append(record)
    return records


def allocate(cell_sizes: dict, quota: int) -> dict:
    """按 sqrt(格子大小) 用最大余数法把 quota 分给各格子，空格子不分。"""
    if quota <= 0 or not cell_sizes:
        return {}
    weights = {key: math.sqrt(size) for key, size in cell_sizes.items() if size > 0}
    total = sum(weights.values())
    if total <= 0:
        return {}
    raw = {key: quota * weight / total for key, weight in weights.items()}
    assigned = {key: int(math.floor(value)) for key, value in raw.items()}
    leftover = quota - sum(assigned.values())
    # 余数大的格子优先补齐；同样余数时小格子优先，保证稀有场景不被吞掉
    order = sorted(
        weights,
        key=lambda key: (-(raw[key] - assigned[key]), cell_sizes[key]),
    )
    for key in order[:leftover]:
        assigned[key] += 1
    for key in assigned:
        assigned[key] = min(assigned[key], cell_sizes[key])
    return assigned


def group_free(record: dict, used_groups) -> bool:
    """近似重复组最多取 GROUP_PICK_LIMIT 张：组内画面几乎一样，标多了是浪费人工。"""
    group_id = record["group_id"]
    return not group_id or used_groups.get(group_id, 0) < GROUP_PICK_LIMIT


def mark_used(record: dict, used_groups) -> None:
    if record["group_id"]:
        used_groups[record["group_id"]] += 1


def take_from_cell(cell_records: list, want: int, used_groups) -> list:
    picked = []
    for record in cell_records:
        if len(picked) >= want:
            break
        if not group_free(record, used_groups):
            continue
        picked.append(record)
        mark_used(record, used_groups)
    return picked


def pick_priority(specs, pool, quota_per_split, used_paths, used_groups, rng) -> tuple:
    """先按强制格子取走样本，返回 ({split: [record]}, {key: 本次新取张数})。

    前面的格子已经选走的图如果也满足当前格子，只记账不重复占额度。
    """
    mandatory = {split: [] for split in SPLITS}
    taken = {}
    for name, key, predicate, caps, take_all in specs:
        fresh_count = 0
        for index, split in enumerate(SPLITS):
            already = sum(1 for record in mandatory[split] if predicate(record))
            candidates = [
                record
                for record in pool
                if predicate(record)
                and record["split"] == split
                and record["abs"] not in used_paths
                and group_free(record, used_groups)
            ]
            rng.shuffle(candidates)
            want = len(candidates) if take_all else min(caps[index] - already, len(candidates))
            if not take_all:
                want = min(want, quota_per_split[split] - len(mandatory[split]))
            want = max(0, want)
            fresh_picked = 0
            for record in candidates:
                if fresh_picked >= want:
                    break
                if not group_free(record, used_groups):
                    continue
                record["priorities"].append(key)
                mandatory[split].append(record)
                used_paths.add(record["abs"])
                if record["group_id"]:
                    mark_used(record, used_groups)
                fresh_picked += 1
            fresh_count += fresh_picked
        taken[key] = fresh_count
    return mandatory, taken


def tag_priorities(records, specs) -> None:
    """最终清单里每张图命中哪些格子，重新按判定函数打全（含填充阶段选进来的）。"""
    for record in records:
        record["priorities"] = [key for _n, key, predicate, _c, _a in specs if predicate(record)]


def cell_key(record: dict) -> tuple:
    return (record["source"], record["person_bucket"], record["torso"])


def fill_split(pool, split, quota, used_paths, used_groups, rng) -> list:
    """剩余名额先在来源间保底+按人群分摊，再在来源内按格子 sqrt 分摊。"""
    candidates = [record for record in pool if record["split"] == split and record["abs"] not in used_paths]
    if not candidates or quota <= 0:
        return []
    by_source = defaultdict(list)
    for record in candidates:
        by_source[record["source"]].append(record)
    source_quota = {
        source: min(len(records), SOURCE_FLOOR.get(split, 8)) for source, records in by_source.items()
    }
    leftover = quota - sum(source_quota.values())
    if leftover > 0:
        sizes = {source: len(records) for source, records in by_source.items()}
        extra = allocate(sizes, leftover)
        for source, count in extra.items():
            source_quota[source] = min(len(by_source[source]), source_quota[source] + count)
    elif leftover < 0:
        # 保底名额已经把额度用完：按来源人数从多到少收回
        for source in sorted(source_quota, key=lambda s: -len(by_source[s])):
            if sum(source_quota.values()) <= quota:
                break
            while source_quota[source] > 1 and sum(source_quota.values()) > quota:
                source_quota[source] -= 1

    person_caps = PERSON_CAPS.get(split, {})
    person_counts = Counter()
    selected = []
    for source, want in sorted(source_quota.items()):
        if want <= 0:
            continue
        records = by_source[source]
        cells = defaultdict(list)
        for record in records:
            cells[cell_key(record)].append(record)
        for cell_records in cells.values():
            rng.shuffle(cell_records)
        sizes = {key: len(value) for key, value in cells.items()}
        per_cell = allocate(sizes, min(want, len(records)))
        for key, count in sorted(per_cell.items(), key=lambda item: -item[1]):
            if count <= 0:
                continue
            cell_records = [
                record
                for record in cells[key]
                if person_counts.get(record["person_bucket"], 0) < person_caps.get(record["person_bucket"], 10 ** 9)
            ]
            picked = take_from_cell(cell_records, count, used_groups)
            for record in picked:
                person_counts[record["person_bucket"]] += 1
            selected.extend(picked)
        short = want - len([r for r in selected if r["source"] == source])
        if short > 0:
            chosen = {record["abs"] for record in selected}
            rest = [
                record
                for record in records
                if record["abs"] not in chosen
                and person_counts.get(record["person_bucket"], 0) < person_caps.get(record["person_bucket"], 10 ** 9)
                and group_free(record, used_groups)
            ]
            rng.shuffle(rest)
            filler = rest[:short]
            for record in filler:
                person_counts[record["person_bucket"]] += 1
                mark_used(record, used_groups)
            selected.extend(filler)
    for record in selected:
        used_paths.add(record["abs"])
    return selected


def class_coverage(records: list, pool: list) -> list:
    pool_counts = Counter({name: 0 for name in CLASS_NAMES.values()})
    for record in pool:
        for name in CLASS_NAMES.values():
            pool_counts[name] += record[name]
    rows = []
    for name in CLASS_NAMES.values():
        gold_instances = sum(record[name] for record in records)
        gold_images = sum(1 for record in records if record[name] > 0)
        rows.append(
            {
                "class": name,
                "gold_images": gold_images,
                "gold_instances": gold_instances,
                "pool_instances": pool_counts[name],
                "share_of_pool": round(gold_instances / pool_counts[name], 4) if pool_counts[name] else "",
            }
        )
    return rows


def write_csv(path: Path, rows: list, fieldnames: list) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="分层抽样出人工标注用的金标集")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--curation", default=str(DEFAULT_CURATION))
    parser.add_argument("--train", type=int, default=DEFAULT_QUOTA["train"])
    parser.add_argument("--val", type=int, default=DEFAULT_QUOTA["val"])
    parser.add_argument("--test", type=int, default=DEFAULT_QUOTA["test"])
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    dataset = Path(args.dataset).resolve()
    curation = Path(args.curation).resolve()
    rng = random.Random(args.seed)
    pool = collect(dataset, curation / "split_manifest.csv")
    quota = {"train": args.train, "val": args.val, "test": args.test}
    print(f"候选池 {len(pool)} 张：" + " / ".join(f"{s} {sum(1 for r in pool if r['split'] == s)}" for s in SPLITS))

    used_paths = set()
    used_groups = Counter()
    mandatory, taken = pick_priority(PRIORITY_SPECS, pool, quota, used_paths, used_groups, rng)
    gold = {split: list(mandatory[split]) for split in SPLITS}
    for split in SPLITS:
        remaining = quota[split] - len(gold[split])
        gold[split].extend(fill_split(pool, split, remaining, used_paths, used_groups, rng))

    selected = [record for split in SPLITS for record in gold[split]]
    tag_priorities(selected, PRIORITY_SPECS)
    print("\n抽样结果")
    for split in SPLITS:
        by_source = Counter(record["source"] for record in gold[split])
        by_person = Counter(record["person_bucket"] for record in gold[split])
        print(f"  {split}: {len(gold[split])} 张（目标 {quota[split]}，强制格子 {len(mandatory[split])}）")
        print(f"    来源 " + " ".join(f"{k}:{v}" for k, v in sorted(by_source.items())))
        print(f"    人数 " + " ".join(f"{k}:{v}" for k, v in sorted(by_person.items(), key=lambda item: item[0])))

    fieldnames = [
        "abs",
        "stem",
        "split",
        "source",
        "group_id",
        "priorities",
        "person",
        "classes",
        "boxes",
        "person_bucket",
        "torso",
        "head",
        "gear",
        "person_area_max",
        "white_ratio",
    ] + [CLASS_NAMES[i] for i in sorted(CLASS_NAMES)]
    rows = []
    for record in selected:
        row = {key: record.get(key, "") for key in fieldnames}
        row["priorities"] = ";".join(record["priorities"])
        row["person"] = record["person"]
        row["classes"] = " ".join(f"{name}{record[name]}" for name in CLASS_NAMES.values() if record[name])
        rows.append(row)
    rows.sort(key=lambda row: (row["split"] != "train", row["source"], row["abs"]))
    out = curation / "gold_set.csv"
    write_csv(out, rows, fieldnames)

    unselected_fieldnames = ["abs", "split", "source", "group_id", "person", "boxes", "person_bucket", "torso", "head", "gear"]
    unselected = [
        {key: record.get(key, "") for key in unselected_fieldnames}
        for record in pool
        if record["abs"] not in used_paths
    ]
    write_csv(curation / "gold_unselected.csv", unselected, unselected_fieldnames)

    coverage = class_coverage(selected, pool)
    print("\n金标集类别覆盖（gold_instances / pool_instances）")
    for row in coverage:
        print(f"  {row['class']:<11} 图 {row['gold_images']:>4}  框 {row['gold_instances']:>6}  占池 {row['share_of_pool']}")
    print("\n按强制格子统计（金标命中数 / 候选池总数，本次为该格子新取的张数）")
    for name, key, predicate, caps, take_all in PRIORITY_SPECS:
        hits = sum(1 for record in selected if key in record["priorities"])
        pool_size = sum(1 for record in pool if predicate(record))
        flag = "（全取）" if take_all else ""
        print(f"  {hits:>4} / {pool_size:<5} 新取 {taken[key]:>3}  {name}{flag} 上限 {caps}")

    print(f"\n清单: {out}")
    print(f"  共 {len(rows)} 张，绝对路径在 abs 列，可直接点开")
    print("  这批图之后要作为教师模型的训练料和金标评估料：从 val/test 里跑的指标只信这批复核过的")


if __name__ == "__main__":
    main()
