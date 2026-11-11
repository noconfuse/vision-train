"""样例检索能不能捞出检测器看不见的类？只读实验，不写任何数据集文件。

三个客观数：
  1. 天花板 —— 把置信度压到 0.03，金标 test 里的真目标有多少被「任意一个提议框」盖住。
     盖不住的话检索再准也召回不了，这条线决定整件事值不值得做。
  2. 排序质量 —— 同一个提议池，按「与手标样例的相似度」排 vs 按检测器自己的置信度排，
     同样精度下谁多捞出真目标。
  3. 审阅负担 —— 到那个操作点上，每张图要人判几条。

样例来自 dataset_v6/val，考题来自 dataset_gold_v6/test（手工金标、从没被模型扫过，
与 v6 无同名图，已核）。vest 当正对照：它在 v6/val 标得最足，检索连它都捞不动就说明
是管线坏了，不是结论。
"""

import base64
import io
import json
import os
import sys
from collections import defaultdict

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image, ImageDraw

ROOT = "/Users/baolei/workspace/vision-train/projects/project-1/training"
GOLD_TEST = os.path.join(ROOT, "dataset_gold_v6", "test")
V6_VAL = os.path.join(ROOT, "dataset_v6", "val")
WAVE1 = os.path.abspath(os.path.join(ROOT, "..", "training_outputs", "dataset_gold_v6", "20261102_115423", "weights", "best.pt"))
CLASSES = {3: "vest", 4: "lanyard", 5: "hook"}
OUT_DIR = "/tmp/vt-retrieval"

CONF_FLOOR = 0.03
IOU_MATCH = 0.5
MAX_PROPOSALS_PER_IMAGE = 150
MAX_EXEMPLARS = 200
KNN_K = 5
BATCH = 32
IMG_EXT = (".jpg", ".jpeg", ".png")

torch.manual_seed(0)
DEV = torch.device("mps" if torch.backends.mps.is_available() else "cpu")


def list_images(split_dir):
    images_dir = os.path.join(split_dir, "images")
    out = []
    for root, _, files in os.walk(images_dir):
        for name in sorted(files):
            if name.lower().endswith(IMG_EXT):
                out.append(os.path.join(root, name))
    return sorted(out)


def read_boxes(split_dir, class_id):
    labels_dir = os.path.join(split_dir, "labels")
    images_dir = os.path.join(split_dir, "images")
    by_image = defaultdict(list)
    for root, _, files in os.walk(labels_dir):
        for name in sorted(files):
            if not name.endswith(".txt"):
                continue
            rel = os.path.relpath(os.path.join(root, name), labels_dir)
            img_path = next((os.path.join(images_dir, os.path.splitext(rel)[0] + ext)
                             for ext in IMG_EXT if os.path.isfile(os.path.join(images_dir, os.path.splitext(rel)[0] + ext))), None)
            if img_path is None:
                continue
            with open(os.path.join(root, name), encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    parts = line.strip().split()
                    if len(parts) < 5:
                        continue
                    try:
                        cid = int(float(parts[0]))
                    except ValueError:
                        continue
                    if cid == class_id:
                        by_image[img_path].append([float(x) for x in parts[1:5]])
    return dict(by_image)


def crop_of(image_path, box, pad=0.08):
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    cx, cy, bw, bh = box
    x1 = max(0, int(cx * w - bw * w / 2 - bw * w * pad))
    y1 = max(0, int(cy * h - bh * h / 2 - bh * h * pad))
    x2 = min(w, int(cx * w + bw * w / 2 + bw * w * pad))
    y2 = min(h, int(cy * h + bh * h / 2 + bh * h * pad))
    if x2 - x1 < 6 or y2 - y1 < 6:
        return None
    return img.crop((x1, y1, x2, y2))


def iou(a, b):
    ax1, ay1 = a[0] - a[2] / 2, a[1] - a[3] / 2
    ax2, ay2 = a[0] + a[2] / 2, a[1] + a[3] / 2
    bx1, by1 = b[0] - b[2] / 2, b[1] - b[3] / 2
    bx2, by2 = b[0] + b[2] / 2, b[1] + b[3] / 2
    iw = max(0.0, min(ax2, bx2) - max(ax1, bx1))
    ih = max(0.0, min(ay2, by2) - max(ay1, by1))
    inter = iw * ih
    union = a[2] * a[3] + b[2] * b[3] - inter
    return inter / union if union > 0 else 0.0


def to_tensor_224(im):
    im = im.resize((224, 224))
    arr = np.asarray(im).astype("float32") / 255.0
    return torch.from_numpy(arr).permute(2, 0, 1)


class ResNetEncoder:
    """通用外观特征：ImageNet resnet50 去掉分类头，全局平均池化。"""

    name = "resnet50(通用)"

    def __init__(self):
        from torchvision import models

        net = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V2)
        net = torch.nn.Sequential(*list(net.children())[:-1]).eval().to(DEV)
        for p in net.parameters():
            p.requires_grad_(False)
        self.net = net
        self.size = 224

    @torch.no_grad()
    def _forward(self, tensors):
        mean = torch.tensor([0.485, 0.456, 0.406], device=tensors.device).view(1, 3, 1, 1)
        std = torch.tensor([0.229, 0.224, 0.225], device=tensors.device).view(1, 3, 1, 1)
        return self.net((tensors - mean) / std).flatten(1)


class YoloBackboneEncoder:
    """域内特征：wave-1 检测模型主干最后一层特征图的全局平均。"""

    name = "yolo主干(域内)"

    def __init__(self, weights):
        from ultralytics import YOLO

        # 多尺度路由在 DetectionModel.forward 里做，直接跑 .model.model 会让 Concat 收到单个张量
        det = YOLO(weights).model.eval().to(DEV)
        self.last = {}

        def hook(_m, _i, out):
            if isinstance(out, torch.Tensor) and out.dim() == 4:
                self.last["feat"] = out

        # 只挂 Detect 之前的层：挂到全模型的话，最后一段 4D 会是检测头的分类图，不是主干特征
        layers = list(det.model)
        stop = next((i for i, m in enumerate(layers)
                     if type(m).__name__ in ("Detect", "Segment", "Pose", "Classify")), len(layers))
        for module in layers[:stop]:
            module.register_forward_hook(hook)
        for p in det.parameters():
            p.requires_grad_(False)
        self.det = det
        self.size = 320

    @torch.no_grad()
    def _forward(self, tensors):
        out = []
        for start in range(0, tensors.shape[0], 8):
            self.last.clear()
            self.det(tensors[start:start + 8])
            feat = self.last.get("feat")
            if feat is None:
                raise RuntimeError("主干里没取到 4D 特征图，域内编码器不可用")
            out.append(feat.mean((2, 3)).flatten(1))
        return torch.cat(out, dim=0)


def encode(encoder, crops):
    """裁图 -> 特征矩阵（L2 归一化）；裁不出来的用灰图占位，不静默丢。"""
    tensors = torch.stack([to_tensor_224(c) if c is not None else torch.zeros(3, 224, 224) for c in crops])
    feats = []
    size = encoder.size
    if size != 224:
        tensors = F.interpolate(tensors, size=(size, size), mode="bilinear", align_corners=False)
    for start in range(0, tensors.shape[0], BATCH):
        feats.append(encoder._forward(tensors[start:start + BATCH].to(DEV)))
    return F.normalize(torch.cat(feats, dim=0).float(), dim=1)


def rank_scores(query_feats, exemplar_feats, k=KNN_K):
    if len(query_feats) == 0 or len(exemplar_feats) == 0:
        return np.zeros(len(query_feats))
    sim = query_feats @ exemplar_feats.T
    return torch.topk(sim, min(k, sim.shape[1]), dim=1).values.mean(1).cpu().numpy()


def curve(match, scores, gt_total):
    """按分数从高到低做一对一匹配：一个真目标只算被捞到一次，多框重叠不重复计召回。"""
    if gt_total == 0 or len(scores) == 0:
        return None
    order = np.argsort(-scores)
    taken = set()
    tp = 0
    rows = []
    for rank, idx in enumerate(order, start=1):
        free = next((g for g in match(idx) if g not in taken), None)
        if free is not None:
            taken.add(free)
            tp += 1
        precision = tp / rank
        recall = tp / gt_total
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        rows.append((rank, precision, recall, f1))
    best = max(rows, key=lambda r: r[3])

    def rec_at(pmin):
        hits = [r[2] for r in rows if r[1] >= pmin]
        return max(hits) if hits else 0.0

    at_p50_rank = max([r[0] for r in rows if r[1] >= 0.5], default=0)
    return {
        "positives": gt_total,
        "best_f1": round(best[3], 3),
        "recall_at_p50": round(rec_at(0.5), 3),
        "recall_at_p70": round(rec_at(0.7), 3),
        "picks_at_p50": at_p50_rank,
        "max_recall": round(len(taken) / gt_total, 3),
    }


def build_proposals(image_paths, proposal_model):
    from ultralytics import YOLO

    model = YOLO(proposal_model)
    flat = []
    per_image = []
    for path in image_paths:
        res = model.predict(path, conf=CONF_FLOOR, iou=0.7, verbose=False, imgsz=640, max_det=300)[0]
        boxes = res.boxes
        items = []
        if boxes is not None and len(boxes):
            xywhn = boxes.xywhn.cpu().numpy()
            cls = boxes.cls.cpu().numpy().astype(int)
            conf = boxes.conf.cpu().numpy()
            for i in np.argsort(-conf)[:MAX_PROPOSALS_PER_IMAGE]:
                items.append({"box": [float(x) for x in xywhn[i]], "pred_cls": int(cls[i]), "conf": float(conf[i])})
        per_image.append(len(items))
        for it in items:
            flat.append({**it, "image": path})
    return flat, float(np.mean(per_image)) if per_image else 0.0


def thumb(crop, size=72):
    if crop is None:
        return ""
    im = crop.copy()
    im.thumbnail((size, size))
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=72)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def write_sheet(sections, ceiling_info, sheet_path):
    parts = ["<meta charset='utf-8'><style>body{font-family:-apple-system;margin:24px;background:#fafafa}"
             "h2{font-size:15px;margin:22px 0 6px}.g{display:flex;flex-wrap:wrap;gap:6px}"
             ".c{width:78px;text-align:center;font-size:10px;color:#555}"
             ".tp img{outline:3px solid #22c55e}.fp img{outline:3px solid #ef4444}"
             ".ex img{outline:3px solid #3b82f6}img{width:72px;height:72px;object-fit:cover;border-radius:4px;background:#ddd}"
             ".note{color:#666;font-size:12px;margin:4px 0 12px}"]
    parts.append(f"<h1 style='font-size:19px'>样例检索实验 · 提议池与排序结果</h1>")
    parts.append(f"<div class='note'>conf≥{CONF_FLOOR}，每张最多 {MAX_PROPOSALS_PER_IMAGE} 条 · "
                 f"考题：dataset_gold_v6/test 72 张（手工金标）· 样例：dataset_v6/val · "
                 f"绿框=真的漏标（命中金标）红框=误报 蓝框=手标样例</div>")
    for class_name, ceiling, covered, gt_total, rows in sections:
        parts.append(f"<h2>{class_name}：天花板 {covered}/{gt_total} = {ceiling}</h2>")
        parts.append("<div class='g'>")
        for row in rows:
            cls = "tp" if row["is_tp"] else "fp"
            parts.append(f"<div class='c {cls}'><img src='{row['thumb']}'>{row['score']:.3f}<br>"
                         f"conf {row['conf']:.2f} 判 {row['pred_cls']}</div>")
        parts.append("</div>")
    parts.append(f"<div class='note'>{ceiling_info}</div>")
    with open(sheet_path, "w", encoding="utf-8") as handle:
        handle.write("".join(parts))


def main():
    proposal_model = sys.argv[1] if len(sys.argv) > 1 else WAVE1
    tag = os.path.splitext(os.path.basename(proposal_model))[0]
    os.makedirs(OUT_DIR, exist_ok=True)
    encoders = [YoloBackboneEncoder(WAVE1)]
    try:
        encoders.insert(0, ResNetEncoder())
    except Exception as err:
        print(f"[warn] 通用编码器起不来（不假装跑过）：{type(err).__name__}: {err}")

    image_paths = list_images(GOLD_TEST)
    from ultralytics import YOLO
    proposal_names = set(str(n).lower() for n in YOLO(proposal_model).names.values())
    print(f"提议源：{tag}，词表 {len(proposal_names)} 类")
    flat, per_image = build_proposals(image_paths, proposal_model)
    print(f"提议池：{len(image_paths)} 张图，平均每张 {per_image:.1f} 条，共 {len(flat)} 条")

    query_crops = [crop_of(item["image"], item["box"]) for item in flat]
    query_feats = {enc.name: encode(enc, query_crops) for enc in encoders}

    report = {"proposal_model": tag, "proposals_per_image": round(per_image, 1),
              "proposal_total": len(flat), "classes": {}}
    sections = []

    def overlaps_gt(index):
        item = flat[index]
        return [f"{item['image']}#{gi}"
                for gi, g in enumerate(gt_by_image_cache.get(item["image"], []))
                if iou(item["box"], g) >= IOU_MATCH]

    def evaluate(idxs, scores_full, gt_total):
        local = list(idxs)
        local_scores = np.array([scores_full[i] for i in local])
        def match(local_i):
            return overlaps_gt(local[local_i])
        return curve(match, local_scores, gt_total)

    for class_id, class_name in CLASSES.items():
        gt_by_image = read_boxes(GOLD_TEST, class_id)
        gt_by_image_cache = gt_by_image
        exemplar_by_image = read_boxes(V6_VAL, class_id)
        exemplar_pairs = [(p, b) for p, boxes in exemplar_by_image.items() for b in boxes][:MAX_EXEMPLARS]
        gt_total = sum(len(v) for v in gt_by_image.values())

        covered = 0
        for path, gts in gt_by_image.items():
            props = [it for it in flat if it["image"] == path]
            for g in gts:
                if any(iou(it["box"], g) >= IOU_MATCH for it in props):
                    covered += 1
        ceiling = round(covered / gt_total, 3) if gt_total else None
        print(f"\n== {class_name}: 样例 {len(exemplar_pairs)} / 真目标 {gt_total} / 天花板 {covered}/{gt_total}={ceiling}")

        exemplar_crops = [crop_of(p, b) for p, b in exemplar_pairs]
        all_idx = range(len(flat))
        knows_class = class_name in proposal_names
        same_idx = [i for i, it in enumerate(flat) if it["pred_cls"] == class_id] if knows_class else []
        entry = {"gt": gt_total, "exemplars": len(exemplar_pairs), "ceiling": ceiling,
                 "same_class_proposals": len(same_idx), "encoders": {}}

        for enc in encoders:
            feats = encode(enc, exemplar_crops)
            scores = rank_scores(query_feats[enc.name], feats)
            res = evaluate(all_idx, scores, gt_total)
            print(f"   {enc.name}: F1 {res['best_f1']}  R@P50 {res['recall_at_p50']}  R@P70 {res['recall_at_p70']}"
                  f"  取前 {res['picks_at_p50']} 条  最多召回 {res['max_recall']}")
            entry["encoders"][enc.name] = res

        conf_scores = np.array([item["conf"] for item in flat])
        base_all = evaluate(all_idx, conf_scores, gt_total)
        base_same = evaluate(same_idx, conf_scores, gt_total) if same_idx else None
        print(f"   基线·全部框按置信度: F1 {base_all['best_f1']}  R@P50 {base_all['recall_at_p50']}  最多召回 {base_all['max_recall']}")
        print(f"   基线·只留判对类的框({len(same_idx)} 条): F1 {base_same['best_f1'] if base_same else 'n/a'}  "
              f"R@P50 {base_same['recall_at_p50'] if base_same else 'n/a'}  "
              f"最多召回 {base_same['max_recall'] if base_same else 'n/a'}")
        entry["baseline_conf_all"] = base_all
        entry["baseline_conf_same_class"] = base_same
        report["classes"][class_name] = entry

        enc = encoders[-1]
        scores = rank_scores(query_feats[enc.name], encode(enc, exemplar_crops))
        rows = []
        taken = set()
        for i in np.argsort(-scores)[:24]:
            free = next((g for g in overlaps_gt(i) if g not in taken), None)
            if free is not None:
                taken.add(free)
            rows.append({"score": float(scores[i]), "is_tp": free is not None, "conf": flat[i]["conf"],
                         "pred_cls": flat[i]["pred_cls"], "thumb": thumb(query_crops[i])})
        sections.append((class_name, ceiling, covered, gt_total, rows))

    results_path = os.path.join(OUT_DIR, f"results-{tag}.json")
    sheet_path = os.path.join(OUT_DIR, f"sheet-{tag}.html")
    with open(results_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    write_sheet(sections, f"提议源：{tag} · 编码：{', '.join(e.name for e in encoders)} · 相似度=与样例 top{KNN_K} 余弦均值", sheet_path)
    print(f"\n结果：{results_path}")
    print(f"看图：file://{sheet_path}")


if __name__ == "__main__":
    sys.exit(main())
