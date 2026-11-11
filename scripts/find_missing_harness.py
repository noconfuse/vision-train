#!/usr/bin/env python3
"""找出「标签里没有 harness、但模型看到了 harness」的图，用来判断 test 分数被多少漏标拖着。

只做一件事：把候选图的候选框画出来，按模型置信度排序。判定留给人。
候选 = 该 split 里标签没有 class 1 的图；--prod-only 时只看 production 帧（video_fNNNN）。

输出到 --out 目录：overlays/*.jpg + index.html + hits.json，index.html 可直接打开。
"""

import argparse
import json
import os
import re
from pathlib import Path

PROD_RE = re.compile(r"^video_f\d+$")
HARNESS = 1
PERSON = 0


def label_classes(label_path):
    if not label_path.is_file():
        return []
    out = []
    for line in label_path.read_text().splitlines():
        parts = line.split()
        if parts:
            out.append(int(parts[0]))
    return out


def collect(dataset, splits, prod_only):
    rows = []
    for split in splits:
        img_dir = dataset / split / "images"
        lbl_dir = dataset / split / "labels"
        if not img_dir.is_dir():
            continue
        for name in sorted(os.listdir(img_dir)):
            path = img_dir / name
            if not path.is_file():
                continue
            stem = Path(name).stem
            is_prod = bool(PROD_RE.match(stem))
            if prod_only and not is_prod:
                continue
            classes = label_classes(lbl_dir / (stem + ".txt"))
            if HARNESS in classes:
                continue
            rows.append({"split": split, "name": name, "path": str(path), "prod": is_prod})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--dataset", default="projects/project-1/training/dataset_train_v8")
    ap.add_argument("--splits", default="test")
    ap.add_argument("--prod-only", action="store_true")
    ap.add_argument("--imgsz", type=int, default=960)
    ap.add_argument("--conf", type=float, default=0.10)
    ap.add_argument("--report-conf", type=float, default=0.25, help="算作「看到了」的下限")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    dataset = Path(args.dataset)
    splits = [s.strip() for s in args.splits.split(",") if s.strip()]
    rows = collect(dataset, splits, args.prod_only)
    print(f"候选（无 harness 标签）：{len(rows)} 张 · splits={splits} prod_only={args.prod_only}")
    if not rows:
        return

    from ultralytics import YOLO

    model = YOLO(args.weights)
    out = Path(args.out)
    overlay_dir = out / "overlays"
    overlay_dir.mkdir(parents=True, exist_ok=True)

    by_path = {r["path"]: r for r in rows}
    hits = []
    # 列表输入时结果顺序与输入一致；流式结果的 res.path 会被改写成 imageN.jpg，不能用它回查。
    for row, res in zip(
        rows,
        model.predict(
            [r["path"] for r in rows],
            imgsz=args.imgsz,
            conf=args.conf,
            classes=[PERSON, HARNESS],
            device="mps",
            stream=True,
            verbose=False,
        ),
    ):
        boxes = res.boxes
        cls = boxes.cls.tolist() if boxes is not None else []
        conf = boxes.conf.tolist() if boxes is not None else []
        harness_confs = [c for k, c in zip(cls, conf) if int(k) == HARNESS]
        top = max(harness_confs) if harness_confs else 0.0
        n_seen = sum(1 for c in harness_confs if c >= args.report_conf)
        row.update(top_harness_conf=round(top, 3), n_harness_at_report=len(
            [c for c in harness_confs if c >= args.report_conf]))
        if n_seen:
            split = row["split"]
            stem = Path(row["name"]).stem
            rel = f"overlays/{split}__{stem}.jpg"
            plotted = res.plot(labels=True, conf=True)
            from PIL import Image

            Image.fromarray(plotted[:, :, ::-1]).save(out / rel, quality=88)
            row["overlay"] = rel
        hits.append(row)

    hits.sort(key=lambda r: r["top_harness_conf"], reverse=True)

    with open(out / "hits.json", "w", encoding="utf-8") as fh:
        json.dump({"dataset": str(dataset), "weights": args.weights, "rows": hits},
                  fh, ensure_ascii=False, indent=1)

    found = [r for r in hits if r["n_harness_at_report"] > 0]
    print(f"模型看到 harness（>= {args.report_conf}）：{len(found)} 张 / {len(hits)} 张")
    for lo, hi in ((0.7, 1.01), (0.5, 0.7), (0.35, 0.5), (args.report_conf, 0.35)):
        n = sum(1 for r in found if lo <= r["top_harness_conf"] < hi)
        print(f"  {lo:.2f}~{hi:.2f}: {n} 张")
    prod_found = [r for r in found if r["prod"]]
    if prod_found:
        print("production 命中：")
        for r in prod_found:
            print(f"  {r['split']} {r['name']} top={r['top_harness_conf']}")

    cards = "\n".join(
        f'<figure><img src="{r["overlay"]}" loading="lazy"><figcaption>'
        f'<b>{r["split"]}/{r["name"]}</b><br>harness top={r["top_harness_conf"]}'
        f' · ≥{args.report_conf} 的 {r["n_harness_at_report"]} 个'
        f'{" · production" if r["prod"] else ""}</figcaption></figure>'
        for r in found
    )
    skipped = [r for r in hits if not r["n_harness_at_report"]]
    skipped_list = "".join(f"<li>{r['split']}/{r['name']} (top={r['top_harness_conf']})</li>"
                           for r in skipped)
    html = f"""<!doctype html><meta charset="utf-8"><title>漏标 harness 候选</title>
<style>
body{{font:14px/1.5 -apple-system,sans-serif;margin:24px;background:#fafafa}}
h1{{font-size:18px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}}
figure{{margin:0;background:#fff;border:1px solid #ddd;border-radius:6px;overflow:hidden}}
figure img{{width:100%;display:block}}
figcaption{{padding:6px 8px;color:#333}}
details{{margin-top:24px}}
</style>
<h1>模型看到 harness、但标签里没有：{len(found)} / {len(hits)}</h1>
<p>红框=harness，蓝框=person。按模型置信度排序；置信度高的是真漏标的可能性大。</p>
<div class="grid">{cards}</div>
<details><summary>模型完全没看到的 {len(skipped)} 张</summary><ul>{skipped_list}</ul></details>
"""
    (out / "index.html").write_text(html, encoding="utf-8")
    print(f"报告：{(out / 'index.html').resolve()}")


if __name__ == "__main__":
    main()