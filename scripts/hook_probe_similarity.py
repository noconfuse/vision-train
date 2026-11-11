"""样本检索可行性探针：拿一个已知的框当样本，在本 split 里找外观相似的区域。

只读，不写任何数据集文件；产物全部落在 --out（默认 /tmp/vt-hookprobe）。

做法：ImageNet 预训练 ResNet-50 当通用骨干（跟任务无关，所以模型认不认得这个类不影响它出特征），
整张图一次前向拿到 stride 8 / 16 两层特征图；样本框在它自己那张图上按同样的网格池化成一个向量；
然后对每张图、每个尺度窗口做余弦比对，过线的窗口聚成框，按分数全局排序。

判分对的是这张图的人工标签里的同类框（GT），命中/未命中都按 is_same_object_box 那条线（IoU>=0.7 或
较小框九成落在较大框里）算，跟产品里用的是同一把尺子。注意「没标」不等于「不存在」，
所以分数高但 GT 里没有的框，只能靠人看图判，脚本里一律标成 no_gt 而不是错。
"""

import argparse
import json
import math
import os
import sys
import time

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image, ImageDraw

os.environ.setdefault("OMP_NUM_THREADS", "4")

MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)
NET_SIDE = 512
SCALE_FACTORS = (0.6, 0.8, 1.0, 1.3, 1.7)


def same_object(box_a, box_b, iou_thresh=0.7, cover_thresh=0.9):
    """产品里那把尺子：IoU>=0.7，或者较小框九成落在较大框里（xyxy 归一化）。"""
    ax1, ay1, ax2, ay2 = box_a
    bx1, by1, bx2, by2 = box_b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    iou = inter / union if union > 0 else 0.0
    smaller = min(area_a, area_b) or 1e-9
    cover = inter / smaller
    return iou >= iou_thresh or cover >= cover_thresh, iou, cover


def yolo_to_xyxy(line):
    cx, cy, w, h = line[1], line[2], line[3], line[4]
    return [cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0]


def read_label_boxes(label_path, class_id):
    if not label_path or not os.path.isfile(label_path):
        return []
    boxes = []
    with open(label_path, encoding="utf-8") as handle:
        for raw in handle:
            parts = raw.strip().split()
            if len(parts) < 5:
                continue
            try:
                cid = int(float(parts[0]))
            except ValueError:
                continue
            if cid != class_id:
                continue
            boxes.append(yolo_to_xyxy([cid] + [float(p) for p in parts[1:5]]))
    return boxes


class Encoder:
    """ResNet-50 骨干，一次前向同时拿 stride 8 / 16 / 32 三层特征图。

    层号到步长的对应：layer2 出 1/8（64×64 网格，格子=图的 1.6%），layer3 出 1/16，layer4 出 1/32。
    浅层偏颜色纹理、深层偏语义，三层都试才知道这个类靠哪一层找得动。
    """

    def __init__(self, device):
        from torchvision.models import ResNet50_Weights, resnet50

        model = resnet50(weights=ResNet50_Weights.IMAGENET1K_V1).to(device).eval()
        self.stage8 = nn.Sequential(model.conv1, model.bn1, model.relu, model.maxpool,
                                    model.layer1, model.layer2)
        self.stage16 = model.layer3
        self.stage32 = model.layer4
        self.device = device

    @torch.no_grad()
    def maps(self, tensor):
        f8 = self.stage8(tensor)
        f16 = self.stage16(f8)
        f32 = self.stage32(f16)
        return {8: f8, 16: f16, 32: f32}

    def to_tensor(self, pil_image):
        array = np.asarray(pil_image.convert("RGB").resize((NET_SIDE, NET_SIDE), Image.BILINEAR), dtype=np.float32) / 255.0
        array = (array - np.array(MEAN, dtype=np.float32)) / np.array(STD, dtype=np.float32)
        return torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0).to(self.device)


def window_vectors(feat, kh, kw):
    """把特征图按 kh×kw 个格子滑一遍，每个窗口池化成一个向量，并减掉本图的直流分量。

    不减的话深层特征里那个「所有窗口都共享」的分量会把余弦顶到 0.87 上下，
    全 split 的分数挤成一条带，等于没有排序——减掉它比出来的才是「这个窗口跟样本的差异」。
    """
    if kh < 1 or kw < 1:
        return None, 0, 0
    feat = feat[0]
    pooled = F.avg_pool2d(feat, kernel_size=(int(kh), int(kw)), stride=1)
    c, hh, ww = pooled.shape
    flat = pooled.reshape(c, -1)
    flat = flat - flat.mean(dim=1, keepdim=True)
    flat = flat / flat.norm(dim=0, keepdim=True).clamp_min(1e-6)
    return flat, hh, ww


def sample_vector(feat, sample_box, stride, factor):
    """样本向量就取「窗口中心离样本框中心最近」的那个窗口，跟后面每张图的窗口同一把口径。"""
    grid = NET_SIDE / stride
    cell = 1.0 / grid
    kw = max(1, round((sample_box[2] - sample_box[0]) * grid * factor))
    kh = max(1, round((sample_box[3] - sample_box[1]) * grid * factor))
    flat, hh, ww = window_vectors(feat, kh, kw)
    if flat is None:
        return None
    cx, cy = (sample_box[0] + sample_box[2]) / 2, (sample_box[1] + sample_box[3]) / 2
    j = min(max(int(round(cx / cell - (kw - 1) / 2.0)), 0), ww - 1)
    i = min(max(int(round(cy / cell - (kh - 1) / 2.0)), 0), hh - 1)
    return flat[:, i * ww + j]


def collect_image_hits(sample_plan, maps, sample_box):
    """一张图上所有 (尺度 × 层) 的窗口，按样本向量算余弦，每个组合只留全局 top-k。

    逐行取最优会把几千次 GPU 同步塞进一张图，慢到跑不完，所以一次 topk 拿完。
    """
    hits = []
    sx1, sy1, sx2, sy2 = sample_box
    sw, sh = sx2 - sx1, sy2 - sy1
    for entry in sample_plan:
        stride, factor, vec = entry["stride"], entry["scale"], entry["vec"]
        if vec is None:
            continue
        grid = NET_SIDE / stride
        cell = 1.0 / grid
        kw = max(1, round(sw * grid * factor))
        kh = max(1, round(sh * grid * factor))
        flat, hh, ww = window_vectors(maps[stride], kh, kw)
        if flat is None:
            continue
        scores = (flat.T @ vec).reshape(hh * ww)
        k = min(entry["topk"], scores.numel())
        values, index = torch.topk(scores, k)
        for score, pos in zip(values.tolist(), index.tolist()):
            i, j = divmod(int(pos), ww)
            x1, y1 = j * cell, i * cell
            hits.append({"score": float(score),
                         "box": [x1, y1, min(x1 + kw * cell, 1.0), min(y1 + kh * cell, 1.0)],
                         "stride": stride, "scale": factor})
    return hits


def nms_hits(hits, iou_thresh=0.5, keep_per_image=3):
    hits = sorted(hits, key=lambda h: -h["score"])
    kept = []
    for hit in hits:
        dup = False
        for other in kept:
            is_dup, _, _ = same_object(hit["box"], other["box"], iou_thresh=iou_thresh, cover_thresh=0.9)
            if is_dup:
                dup = True
                break
        if not dup:
            kept.append(hit)
        if len(kept) >= keep_per_image:
            break
    return kept


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset-root", default="projects/project-1/training/dataset_v6")
    ap.add_argument("--split", default="test")
    ap.add_argument("--sample-image", default="F03_1125525766_jpg.rf.b745c00c4ab01d6e0d17a02ea8868233.jpg")
    ap.add_argument("--sample-class", type=int, default=5)
    ap.add_argument("--sample-from", choices=["labels", "auto_labels"], default="auto_labels")
    ap.add_argument("--limit", type=int, default=0, help="只扫前 N 张（0=全 split）")
    ap.add_argument("--topk", type=int, default=6, help="每个 (层×尺度) 组合在一张图上留几个窗口")
    ap.add_argument("--out", default="/tmp/vt-hookprobe")
    ap.add_argument("--tag", default="hook")
    args = ap.parse_args()

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    out_dir = os.path.join(args.out, args.tag)
    os.makedirs(out_dir, exist_ok=True)
    images_dir = os.path.join(args.dataset_root, args.split, "images")
    labels_dir = os.path.join(args.dataset_root, args.split, "labels")
    auto_dir = os.path.join(args.dataset_root, "auto_labels", args.split)

    stem = os.path.splitext(args.sample_image)[0]
    sample_label_src = labels_dir if args.sample_from == "labels" else auto_dir
    sample_boxes = read_label_boxes(os.path.join(sample_label_src, stem + ".txt"), args.sample_class)
    if not sample_boxes:
        sys.exit(f"样本图 {stem} 在 {sample_label_src} 里没有 class={args.sample_class} 的框")
    sample_box = sample_boxes[0]
    print(f"样本框（class {args.sample_class}，来自 {args.sample_from}）: "
          + " ".join(f"{v:.4f}" for v in sample_box))

    encoder = Encoder(device)

    names = sorted(n for n in os.listdir(images_dir) if n.lower().endswith((".jpg", ".jpeg", ".png")))
    if args.limit:
        names = names[: args.limit]

    # 样本图先前向一次，按 (层 × 尺度) 各定一个样本向量；后面每张图用同一套组合去比。
    sample_path = os.path.join(images_dir, args.sample_image)
    sample_maps = encoder.maps(encoder.to_tensor(Image.open(sample_path)))
    sample_plan = [
        {"stride": stride, "scale": factor, "topk": args.topk,
         "vec": sample_vector(sample_maps[stride], sample_box, stride, factor)}
        for stride in (8, 16, 32) for factor in SCALE_FACTORS
    ]

    all_hits = []
    gt_total = 0
    started = time.time()
    for index, name in enumerate(names, 1):
        if name == args.sample_image:
            continue  # 样本自己不算命中，否则它必然排第一，把命中率顶高
        image_path = os.path.join(images_dir, name)
        hits = collect_image_hits(sample_plan, encoder.maps(encoder.to_tensor(Image.open(image_path))), sample_box)
        kept = nms_hits(hits)
        gt = read_label_boxes(os.path.join(labels_dir, os.path.splitext(name)[0] + ".txt"), args.sample_class)
        gt_total += len(gt)
        for hit in kept:
            matched = None
            best_iou = 0.0
            for box in gt:
                is_same, iou, cover = same_object(hit["box"], box)
                if is_same and iou >= best_iou:
                    matched, best_iou = box, iou
            all_hits.append({
                "name": name,
                "box": [round(v, 4) for v in hit["box"]],
                "score": round(hit["score"], 4),
                "stride": hit["stride"],
                "scale": hit["scale"],
                "gt_hook_boxes": len(gt),
                "hit_gt": matched is not None,
            })
        if index % 100 == 0 or index == len(names):
            print(f"  {index}/{len(names)}  {time.time() - started:.0f}s  hits={len(all_hits)}", flush=True)

    all_hits.sort(key=lambda h: -h["score"])
    scores = np.array([h["score"] for h in all_hits]) if all_hits else np.array([0.0])

    summary = {
        "sample": {"image": args.sample_image, "class": args.sample_class, "box": sample_box, "from": args.sample_from},
        "split": args.split,
        "images_scanned": len(names),
        "gt_boxes_in_split": gt_total,
        "hits_kept": len(all_hits),
        "score_percentiles": {str(p): round(float(np.percentile(scores, p)), 4) for p in (50, 75, 90, 95, 99)},
    }
    for top_k in (50, 100, 200, 400, 800):
        slice_hits = all_hits[:top_k]
        if not slice_hits:
            break
        matched = sum(1 for h in slice_hits if h["hit_gt"])
        summary[f"top{top_k}"] = {
            "hits": len(slice_hits),
            "min_score": slice_hits[-1]["score"],
            "match_gt": matched,
            "no_gt": len(slice_hits) - matched,
        }
    matched_images = {h["name"] for h in all_hits if h["hit_gt"]}
    summary["images_with_hit_matching_gt"] = len(matched_images)

    with open(os.path.join(out_dir, "hits.json"), "w", encoding="utf-8") as handle:
        json.dump({"summary": summary, "hits": all_hits}, handle, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    build_page(args, out_dir, all_hits, sample_box)


def crop_with_box(image_path, box, gt_boxes, out_png, side=220, pad=2.2):
    """把命中框周围放大裁一块出来，绿框=探针给的框，红框=这张图人工标签里的同类框。"""
    im = Image.open(image_path).convert("RGB")
    w, h = im.size
    x1, y1, x2, y2 = box
    bw, bh = max(x2 - x1, 1e-4), max(y2 - y1, 1e-4)
    cx, cy = (x1 + x2) / 2 * w, (y1 + y2) / 2 * h
    half = max(bw * w, bh * h) * pad / 2
    left, top = max(0, int(cx - half)), max(0, int(cy - half * (h / w if w else 1)))
    right, bottom = min(w, int(cx + half)), min(h, int(cy + half * (h / w if w else 1)))
    crop = im.crop((left, top, right, bottom)).resize((side, side), Image.BILINEAR)
    draw = ImageDraw.Draw(crop)
    cw, ch = right - left, bottom - top

    def paint(norm_box, color, width):
        bx1 = (norm_box[0] * w - left) / cw * side
        by1 = (norm_box[1] * h - top) / ch * side
        bx2 = (norm_box[2] * w - left) / cw * side
        by2 = (norm_box[3] * h - top) / ch * side
        draw.rectangle([bx1, by1, bx2, by2], outline=color, width=width)

    for gt in gt_boxes:
        paint(gt, (255, 60, 60), 2)
    paint(box, (60, 230, 120), 3)
    crop.save(out_png, quality=82)


def build_page(args, out_dir, all_hits, sample_box):
    """本地交互页：按分数排的命中，每张带放大裁剪图，翻一眼就知道像不像。"""
    images_dir = os.path.join(args.dataset_root, args.split, "images")
    labels_dir = os.path.join(args.dataset_root, args.split, "labels")
    crops_dir = os.path.join(out_dir, "crops")
    os.makedirs(crops_dir, exist_ok=True)
    cells = []
    for i, hit in enumerate(all_hits[:160]):
        stem = os.path.splitext(hit["name"])[0]
        gt = read_label_boxes(os.path.join(labels_dir, stem + ".txt"), args.sample_class)
        png = f"{i:03d}.png"
        crop_with_box(os.path.join(images_dir, hit["name"]), hit["box"], gt, os.path.join(crops_dir, png))
        cells.append(
            f"<figure class='{'ok' if hit['hit_gt'] else 'bad'}'>"
            f"<img src='crops/{png}' loading='lazy'>"
            f"<figcaption>{hit['score']:.3f} · {'命中人工框' if hit['hit_gt'] else '本图无同类人工框'} · "
            f"{hit['name'][:34]}<br><span class='muted'>{hit['name']}</span></figcaption></figure>"
        )
    html = f"""<!doctype html><meta charset='utf-8'>
<title>样本检索探针 · {args.tag} · {args.split}</title>
<style>
body{{font:14px/1.4 -apple-system,sans-serif;margin:16px;background:#111;color:#eee}}
.legend{{position:sticky;top:0;background:#111;padding:8px 0;border-bottom:1px solid #333}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:12px;margin-top:12px}}
figure{{margin:0;border:2px solid #333;border-radius:8px;overflow:hidden;background:#1b1b1b}}
figure.ok{{border-color:#2f9e44}} figure.bad{{border-color:#8a1c1c}}
img{{display:block;width:100%}}
figcaption{{padding:6px 8px;font-size:12px}}
.muted{{color:#888;font-size:11px;word-break:break-all}}
</style>
<div class='legend'>
  样本：{args.sample_image} 的 class {args.sample_class} 框（来自 {args.sample_from}）·
  split={args.split} · 扫了 {len(set(h['name'] for h in all_hits))} 张 · 绿框=探针命中，红框=这张图人工标签里的同类框
</div>
<div class='grid'>{''.join(cells)}</div>
"""
    page = os.path.join(out_dir, "review.html")
    with open(page, "w", encoding="utf-8") as handle:
        handle.write(html)
    print("页面：" + page)


if __name__ == "__main__":
    main()
