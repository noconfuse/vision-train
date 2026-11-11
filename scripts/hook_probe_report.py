"""把 hook_probe_similarity.py 的命中读成能拍板的数：真的那几个钩子，探针把它们排到哪。

口径：
- 一个 GT 框的「最好分数」= 落在它身上（同一把尺子：IoU>=0.7 或较小框九成落在较大框里）的所有命中里最高的分。
- 没被任何命中盖住的 GT 框记成 miss（分数为空），这代表探针在这张图上根本没指到它。
- 阈值扫描：某个分数之上，命中里有多少盖住了 GT（当准头看）、有多少没盖住（当噪声看）。
  「没盖住」不等于「错」——这一批图里没标钩子的图，可能只是没标；所以噪声只报数，不判死。
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hook_probe_similarity import same_object  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hits", default="/tmp/vt-hookprobe/hook_full/hits.json")
    ap.add_argument("--gt-dir", default="projects/project-1/training/dataset_v6/test/labels")
    ap.add_argument("--gt-class", type=int, default=5)
    args = ap.parse_args()

    from hook_probe_similarity import read_label_boxes

    payload = json.load(open(args.hits, encoding="utf-8"))
    hits = payload["hits"]
    summary = payload["summary"]

    gt_by_name = {}
    for name in sorted({h["name"] for h in hits}):
        stem = os.path.splitext(name)[0]
        gt_by_name[name] = read_label_boxes(os.path.join(args.gt_dir, stem + ".txt"), args.gt_class)
    # 只数扫过的图；没扫到的图不参与，免得把「没看」说成「没找到」
    gt_boxes = []
    for name, boxes in gt_by_name.items():
        for index, box in enumerate(boxes):
            gt_boxes.append({"name": name, "index": index, "box": box})

    best = {id(g): None for g in gt_boxes}
    for hit in hits:
        for g in gt_boxes:
            if g["name"] != hit["name"]:
                continue
            is_same, _, _ = same_object(hit["box"], g["box"])
            if is_same and (best[id(g)] is None or hit["score"] > best[id(g)]):
                best[id(g)] = hit["score"]

    found = sorted([v for v in best.values() if v is not None], reverse=True)
    missed = len(gt_boxes) - len(found)

    print(f"扫过的图：{summary['images_scanned']} 张 · GT class {args.gt_class} 框（在被扫到的图里）：{len(gt_boxes)} 个")
    print(f"被至少一个命中盖住的 GT 框：{len(found)} 个 · 完全没盖住：{missed} 个")
    if found:
        print("盖住的 GT 框，其最好分数的分布："
              + " ".join(f"p{p}={sorted(found)[int(len(found) * (1 - p / 100)) if p else 0]:.3f}"
                         for p in (10, 25, 50, 75, 90)))

    print("\n分数阈值 → 命中里盖住 GT 的 / 没盖住的（没盖住≠错，本图可能压根没标钩子）")
    all_scores = sorted({h["score"] for h in hits}, reverse=True)
    for thresh in [s for s in all_scores if s >= 0]:
        if not any(abs(thresh - t) < 1e-9 for t in (0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1)):
            continue
        above = [h for h in hits if h["score"] >= thresh]
        matched = sum(1 for h in above if h["hit_gt"])
        images = len({h["name"] for h in above})
        print(f"  >= {thresh:.1f}: 命中 {len(above):5d} 条 / {images:4d} 张图 · 盖住 GT {matched:4d} · 未盖住 {len(above) - matched:5d}")

    # 全局排名：每个 GT 框的最好命中排在第几位
    rank_of = {}
    for g, score in ((g, best[id(g)]) for g in gt_boxes):
        if score is None:
            continue
        rank_of[f"{g['name']}#{g['index']}"] = 1 + sum(1 for h in hits if h["score"] > score)
    ranked = sorted(rank_of.values())
    print("\n真钩子在命中总榜里的排名（越小越好）："
          f"前 50 名里 {sum(1 for r in ranked if r <= 50)} 个 / 前 200 名里 {sum(1 for r in ranked if r <= 200)} 个"
          f" / 前 500 名里 {sum(1 for r in ranked if r <= 500)} 个，共 {len(ranked)} 个能被盖住")

    # 按层和尺度拆开：哪一层找得动
    by_stride = {}
    for hit in hits:
        key = (hit.get("stride"), hit.get("scale"))
        stat = by_stride.setdefault(key, {"hits": 0, "match": 0, "best": 0.0})
        stat["hits"] += 1
        stat["match"] += 1 if hit["hit_gt"] else 0
        stat["best"] = max(stat["best"], hit["score"])
    print("\n按 (特征层步长 × 尺度) 拆开：")
    for (stride, scale), stat in sorted(by_stride.items(), key=lambda kv: -kv[1]["match"]):
        print(f"  stride {stride:>2} · scale {scale}: 命中 {stat['hits']:5d} · 盖住 GT {stat['match']:4d} · 最高分 {stat['best']:.3f}")


if __name__ == "__main__":
    main()
