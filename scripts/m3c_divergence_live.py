"""已标池分歧队列的真实后端实测：跑一轮推断，看分流、台账、两条出口是否都对得上。

用完即删，只在 test_datasets 下的临时数据集上做。
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, os.path.abspath("src/web"))
from shared.utils.path_utils import resolve_storage_path

PROJECT = os.path.abspath("projects/test_datasets")
DATASET = "m3c_scratch"
ROOT = os.path.join(PROJECT, "training", DATASET)
IMAGES = os.path.join(ROOT, "train", "images")
LABELS = os.path.join(ROOT, "train", "labels")
BASE = os.environ.get("M3C_BASE", "http://127.0.0.1:8090")
KEEP = "--keep" in sys.argv

COCO_NAMES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv", "laptop", "mouse",
    "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "refrigerator", "book", "clock", "vase", "scissors", "teddy bear", "hair drier",
    "toothbrush",
]


def call(path, payload=None, params=None):
    url = BASE + path
    if params:
        url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode() or "{}")


def report(label, value):
    print(f"{label}: {value}")


def main():
    if os.path.exists(ROOT):
        shutil.rmtree(ROOT)
    os.makedirs(IMAGES)
    os.makedirs(LABELS)

    source_dir = os.path.join(PROJECT, "training", "voc2007_test", "val", "images")
    picked = sorted(os.listdir(source_dir))[:8]
    for name in picked:
        shutil.copyfile(os.path.join(source_dir, name), os.path.join(IMAGES, name))
    print(f"图片：{picked}")

    with open(os.path.join(ROOT, "dataset.yaml"), "w", encoding="utf-8") as handle:
        handle.write("path: .\ntrain: train/images\nval: val/images\nnames:\n")
        for idx, name in enumerate(COCO_NAMES):
            handle.write(f"  {idx}: {name}\n")
    with open(os.path.join(ROOT, ".vision-train.meta.json"), "w", encoding="utf-8") as handle:
        json.dump({"vision_task_type": "detect"}, handle)
    os.makedirs(os.path.join(ROOT, "val", "images"), exist_ok=True)
    with open(os.path.join(ROOT, "val", "images", ".keep"), "w", encoding="utf-8") as handle:
        handle.write("")

    # 前两张当作已标池：只写一个 person 粗框，其余都是模型可能补的东西
    for name in picked[:2]:
        with open(os.path.join(LABELS, os.path.splitext(name)[0] + ".txt"), "w", encoding="utf-8") as handle:
            handle.write("0 0.5 0.55 0.35 0.55\n")
    manual_before = {n: open(os.path.join(LABELS, n)).read() for n in os.listdir(LABELS)}

    status, body = call(
        "/api/auto_annotate/batch",
        payload={
            "project_path": PROJECT,
            "dataset_name": DATASET,
            "model_path": "pretrained_models/yolo11n.pt",
            "split": "train",
            "conf": 0.3,
            "ingest_conf": 0.7,
            "drop_conf": 0.3,
        },
    )
    report("batch start", (status, body))
    task_id = (body.get("data") or {}).get("task_id") or (body.get("data") or {}).get("id")
    for _ in range(120):
        status, body = call("/api/auto_annotate/batch/status", params={"task_id": task_id})
        data = body.get("data") or {}
        if data.get("status") in ("completed", "failed"):
            break
        time.sleep(1)
    print(json.dumps(data, ensure_ascii=False, indent=2)[:2000])

    status, body = call(
        "/api/auto_annotate/disagreements",
        params={"project_path": PROJECT, "dataset_name": DATASET, "state": "open", "limit": 50},
    )
    listing = body.get("data") or {}
    report("disagreements total", (status, listing.get("total"), listing.get("counts")))
    report("per_class", listing.get("per_class"))
    for item in (listing.get("items") or [])[:6]:
        report(
            "  row",
            {
                "id": item["id"],
                "image": item.get("image_rel"),
                "class": item.get("class_name"),
                "conf": item.get("conf"),
                "nearest_class": item.get("nearest_class_name"),
                "nearest_iou": item.get("nearest_iou"),
                "same_class": item.get("same_class"),
                "seen_count": item.get("seen_count"),
                "line": item.get("line"),
                "image_resolves": os.path.isfile(resolve_storage_path(item.get("image_path"))),
            },
        )

    auto_files = []
    for split in ("train",):
        d = os.path.join(ROOT, "auto_labels", split)
        if os.path.isdir(d):
            auto_files += [n for n in os.listdir(d) if n.endswith(".txt")]
    report("auto_labels \u5df2\u6807\u56fe\u662f\u5426\u88ab\u5199\u5165", auto_files)
    report(
        "\u4eba\u5de5\u6807\u7b7e\u672a\u88ab\u673a\u5668\u6539\u52a8",
        all(open(os.path.join(LABELS, n)).read() == manual_before[n] for n in manual_before),
    )

    items = listing.get("items") or []
    if not items:
        print("\u6ca1\u6709\u5206\u6b67\uff0c\u65e0\u6cd5\u9a8c\u8bc1\u51fa\u53e3")
        return
    if KEEP:
        print("--keep\uff1a\u7559\u7ed9\u9875\u9762\u5b9e\u6d4b\uff0c\u8df3\u8fc7\u51fa\u53e3\u9a8c\u8bc1")
        return

    target = next((i for i in items if i.get("same_class") is False), items[0])
    status, body = call(
        "/api/auto_annotate/disagreements/resolve",
        payload={
            "project_path": PROJECT,
            "dataset_name": DATASET,
            "divergence_ids": [target["id"]],
            "action": "accept",
        },
    )
    accepted_line = target.get("line")
    report("accept", (status, body.get("error") or body.get("data")))
    label_file = os.path.join(LABELS, os.path.splitext(target["image_rel"])[0] + ".txt")
    lines_after = [l for l in open(label_file).read().splitlines() if l.strip()]
    report("\u91c7\u7eb3\u540e\u4eba\u5de5\u6807\u7b7e\u884c", lines_after)
    report("\u91c7\u7eb3\u7684\u884c\u5df2\u5e76\u5165", accepted_line in lines_after)

    ignore_targets = [i for i in items if i["id"] != target["id"]][:2]
    if ignore_targets:
        labels_after_accept = {n: open(os.path.join(LABELS, n)).read() for n in os.listdir(LABELS)}
        status, body = call(
            "/api/auto_annotate/disagreements/resolve",
            payload={
                "project_path": PROJECT,
                "dataset_name": DATASET,
                "divergence_ids": [i["id"] for i in ignore_targets],
                "action": "ignore",
            },
        )
        report(f"\u6279\u91cf\u5ffd\u7565 {len(ignore_targets)} \u6761", (status, body.get("error") or body.get("data")))
        scratch_id = str(json.load(open(os.path.join(ROOT, ".vision-train.meta.json"))).get("dataset_id") or "")
        path = os.path.join(PROJECT, "training", ".dataset-store", scratch_id, "auto_rejections.json")
        if os.path.isfile(path):
            entries = json.load(open(path)).get("items") or []
            report(f"\u62d2\u7edd\u8bb0\u5fc6 {scratch_id}", len(entries))
        report(
            "\u5ffd\u7565\u6ca1\u6709\u6539\u52a8\u4eba\u5de5\u6807\u7b7e",
            all(open(os.path.join(LABELS, n)).read() == labels_after_accept[n] for n in labels_after_accept),
        )

        status, body = call(
            "/api/auto_annotate/batch",
            payload={
                "project_path": PROJECT,
                "dataset_name": DATASET,
                "model_path": "pretrained_models/yolo11n.pt",
                "split": "train",
                "conf": 0.3,
                "ingest_conf": 0.7,
                "drop_conf": 0.3,
            },
        )
        task_id = (body.get("data") or {}).get("task_id") or (body.get("data") or {}).get("id")
        for _ in range(120):
            status, body = call("/api/auto_annotate/batch/status", params={"task_id": task_id})
            data = body.get("data") or {}
            if data.get("status") in ("completed", "failed"):
                break
            time.sleep(1)
        report("\u7b2c\u4e8c\u8f6e", {k: data.get(k) for k in ("divergences", "dropped", "ingested", "added", "failed_images")})
        status, body = call(
            "/api/auto_annotate/disagreements",
            params={"project_path": PROJECT, "dataset_name": DATASET, "state": "open", "limit": 50},
        )
        reopened = [
            i for i in ((body.get("data") or {}).get("items") or [])
            if i["id"] in {t["id"] for t in ignore_targets}
        ]
        report("\u5ffd\u7565\u7684\u6846\u662f\u5426\u53c8\u51fa\u73b0", bool(reopened))
        status, body = call(
            "/api/auto_annotate/disagreements",
            params={"project_path": PROJECT, "dataset_name": DATASET, "state": "ignored", "limit": 50},
        )
        report("ignored \u8ba1\u6570", (body.get("data") or {}).get("total"))
        ledger = os.path.join(PROJECT, "training", ".dataset-store", scratch_id, "disagreements.json")
        rows = json.load(open(ledger)).get("items") or []
        report("\u53f0\u8d26\u72b6\u6001", {r["id"]: (r["state"], r["seen_count"]) for r in rows})

        status, body = call(
            "/api/auto_annotate/disagreements/resolve",
            payload={
                "project_path": PROJECT,
                "dataset_name": DATASET,
                "divergence_ids": [ignore_targets[0]["id"]],
                "action": "ignore",
            },
        )
        report("\u91cd\u590d\u5224\u5b9a\u88ab\u8df3\u8fc7", (status, body.get("error") or body.get("data")))

    report("\u6ca1\u52fe\u9009", call("/api/auto_annotate/disagreements/resolve", payload={
        "project_path": PROJECT, "dataset_name": DATASET, "divergence_ids": [], "action": "ignore"}))
    report("\u975e\u6cd5\u51fa\u53e3", call("/api/auto_annotate/disagreements/resolve", payload={
        "project_path": PROJECT, "dataset_name": DATASET, "divergence_ids": [items[0]["id"]], "action": "delete"}))
    report("\u4e0d\u5b58\u5728\u7684\u7f16\u53f7", call("/api/auto_annotate/disagreements/resolve", payload={
        "project_path": PROJECT, "dataset_name": DATASET, "divergence_ids": ["nope"], "action": "ignore"}))
    report("\u672a\u77e5\u72b6\u6001", call("/api/auto_annotate/disagreements", params={
        "project_path": PROJECT, "dataset_name": DATASET, "state": "resolved"}))


if __name__ == "__main__":
    scratch_id = ""
    try:
        main()
    finally:
        if KEEP:
            print("--keep\uff1a\u8349\u7a3f\u6570\u636e\u96c6\u4e0e\u5206\u6b67\u53f0\u8d26\u7559\u5728 test_datasets \u4e0b\uff0c\u9875\u9762\u5b9e\u6d4b\u540e\u5220\u9664")
        else:
            meta_path = os.path.join(ROOT, ".vision-train.meta.json")
            if os.path.isfile(meta_path):
                scratch_id = str(json.load(open(meta_path)).get("dataset_id") or "")
            print("\n=== \u6e05\u7406 ===")
            if os.path.exists(ROOT):
                shutil.rmtree(ROOT)
                print(f"\u5df2\u5220\u9664 {ROOT}")
            if scratch_id:
                store = os.path.join(PROJECT, "training", ".dataset-store", scratch_id)
                if os.path.isdir(store):
                    shutil.rmtree(store)
                    print(f"\u5df2\u5220\u9664 {store}")
            subprocess.run(["git", "-C", ".", "status", "--short", "projects/test_datasets"], check=False)
