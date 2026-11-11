"""以「手上这个框」为样本，在一个 split 里检索外观相似的区域，命中当候选写进 auto_labels。

跟自动标注分开的理由：自动标注问的是「这个训练过的模型认不认得这一类」，这里问的是
「这张图里有没有跟样本长得像的东西」。用的是一台跟本任务无关的 ImageNet 预训练骨干，
所以本地权重还不认识这个类别时它照样出特征、照样比。

它只比外观，判不了关系（挂没挂上、在不在谁里面），所以出来的框一律当候选，由人审。
命中的分数是窗口特征和样本向量的余弦，不是「是这个类」的概率，别拿它当置信度排序用。
"""

import os
import threading

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from PIL import Image

from protocols.task_status import TASK_STATUS_COMPLETED, TASK_STATUS_FAILED, TASK_STATUS_RUNNING
from protocols.task_type import TASK_TYPE_SIMILAR_PROBE

from contexts.annotation.infrastructure.annotation_io import (
    build_dataset_image_context,
    get_dataset_root,
    get_image_size,
)
from contexts.annotation.infrastructure.annotation_task_strategy import resolve_annotation_task_strategy
from contexts.annotation.infrastructure.auto_annotation_runner import round_artifacts, round_message
from contexts.annotation.infrastructure.batch_helpers import list_batch_image_paths
from contexts.annotation.domain.services import SAME_OBJECT_IOU_THRESH, is_same_object_box
from contexts.dataset.application.dataset_service import (
    ensure_dataset_task_identity,
    load_dataset_names,
    load_dataset_vision_task_type,
)
from contexts.task.application.task_service import (
    create_task as start_task,
    update_task as update_task_status,
    list_tasks as list_task_items,
    load_task,
)
from shared.utils.device_utils import pick_torch_device
from shared.utils.path_utils import project_name_from_path, storage_path_ref
from shared.utils.time_utils import now_iso

MEAN = (0.485, 0.456, 0.406)
STD = (0.229, 0.224, 0.225)
NET_SIDE = 512
# 窗口大小 = 样本框边长 × 这些系数。一张图里同类的目标不会都跟样本一样大，
# 所以每个尺度各比一遍；系数跨度按实测能盖住的尺寸范围取。
SCALE_FACTORS = (0.6, 0.8, 1.0, 1.3, 1.7)
# 浅层偏颜色纹理、深层偏语义；三层都留，哪一层找得动这个类由分数自己说。
STRIDES = (8, 16, 32)
TOPK_PER_COMBO = 6
DEFAULT_SCORE_THRESH = 0.45
DEFAULT_MAX_PER_IMAGE = 3


class ProbeEncoder:
    """ImageNet 预训练 ResNet-50 骨干，一次前向同时拿 stride 8 / 16 / 32 三层特征图。"""

    def __init__(self, device=None):
        import torchvision  # noqa: F401  缺包要在这里当场抛，不能等到第一张图才说跑不动

        from torchvision.models import ResNet50_Weights, resnet50

        runtime_device = pick_torch_device()
        self.device = torch.device(device or runtime_device)
        model = resnet50(weights=ResNet50_Weights.IMAGENET1K_V1).to(self.device).eval()
        self.stage8 = nn.Sequential(model.conv1, model.bn1, model.relu, model.maxpool,
                                    model.layer1, model.layer2)
        self.stage16 = model.layer3
        self.stage32 = model.layer4

    @torch.no_grad()
    def maps(self, tensor):
        f8 = self.stage8(tensor)
        f16 = self.stage16(f8)
        f32 = self.stage32(f16)
        return {8: f8, 16: f16, 32: f32}

    def to_tensor(self, pil_image):
        array = np.asarray(
            pil_image.convert("RGB").resize((NET_SIDE, NET_SIDE), Image.BILINEAR), dtype=np.float32
        ) / 255.0
        array = (array - np.array(MEAN, dtype=np.float32)) / np.array(STD, dtype=np.float32)
        return torch.from_numpy(array).permute(2, 0, 1).unsqueeze(0).to(self.device)


def window_vectors(feat, kh, kw):
    """把特征图按 kh×kw 个格子滑一遍，每个窗口池化成一个向量，并减掉本图的直流分量。

    不减的话深层特征里那个「所有窗口都共享」的分量会把余弦顶到 0.87 上下，
    全 split 的分数挤成一条带，等于没有排序——减掉它比出来的才是「这个窗口跟样本的差异」。

    窗口不许大过这一层的网格：样本框一大（比如占了画面六成的整个人），
    深层的格子数根本放不下，硬算会得到一个负数的输出尺寸。收到网格大小为止，
    并把真正用上的尺寸还给调用方，框才按同一个窗口画。
    """
    feat = feat[0]
    kh = max(1, min(int(kh), feat.shape[-2]))
    kw = max(1, min(int(kw), feat.shape[-1]))
    pooled = F.avg_pool2d(feat, kernel_size=(kh, kw), stride=1)
    c, hh, ww = pooled.shape
    flat = pooled.reshape(c, -1)
    flat = flat - flat.mean(dim=1, keepdim=True)
    flat = flat / flat.norm(dim=0, keepdim=True).clamp_min(1e-6)
    return flat, hh, ww, kh, kw


def _window_shape(box, stride, factor):
    """样本框在某一层的网格上占几格，再乘尺度系数；至少 1 格。"""
    grid = NET_SIDE / stride
    kw = max(1, round((box[2] - box[0]) * grid * factor))
    kh = max(1, round((box[3] - box[1]) * grid * factor))
    return kh, kw


def sample_vector(feat, sample_box, stride, factor):
    """样本向量取「窗口中心离样本框中心最近」的那个窗口，跟后面每张图的窗口同一把口径。"""
    grid = NET_SIDE / stride
    cell = 1.0 / grid
    kh, kw = _window_shape(sample_box, stride, factor)
    flat, hh, ww, _, _ = window_vectors(feat, kh, kw)
    cx, cy = (sample_box[0] + sample_box[2]) / 2, (sample_box[1] + sample_box[3]) / 2
    j = min(max(int(round(cx / cell - (kw - 1) / 2.0)), 0), ww - 1)
    i = min(max(int(round(cy / cell - (kh - 1) / 2.0)), 0), hh - 1)
    return flat[:, i * ww + j]


def build_sample_plan(encoder, sample_image_path, sample_box):
    """样本图前向一次，按 (层 × 尺度) 各定一个样本向量；后面每张图用同一套组合去比。"""
    maps = image_maps(encoder, sample_image_path)
    return [
        {"stride": stride, "scale": factor, "vec": sample_vector(maps[stride], sample_box, stride, factor)}
        for stride in STRIDES
        for factor in SCALE_FACTORS
    ]


def collect_image_hits(sample_plan, maps, sample_box, score_thresh):
    """一张图上所有 (层 × 尺度) 的窗口，按样本向量算余弦，每个组合只留过线里最高的几个。

    逐行取最优会把几千次 GPU 同步塞进一张图，慢到跑不完，所以一次 topk 拿完。
    框回到原图是按归一化坐标给的（窗口左上角 + 窗口宽高）。
    """
    hits = []
    for entry in sample_plan:
        stride = entry["stride"]
        grid = NET_SIDE / stride
        cell = 1.0 / grid
        kh, kw = _window_shape(sample_box, stride, entry["scale"])
        # 后一组 kh/kw 是被网格夹过的真实窗口，画框要用它，不能用上面那个理想值
        flat, hh, ww, kh, kw = window_vectors(maps[stride], kh, kw)
        scores = (flat.T @ entry["vec"]).reshape(hh * ww)
        k = min(TOPK_PER_COMBO, int(scores.numel()))
        values, index = torch.topk(scores, k)
        for score, pos in zip(values.tolist(), index.tolist()):
            if float(score) < float(score_thresh):
                continue
            i, j = divmod(int(pos), ww)
            x1, y1 = j * cell, i * cell
            hits.append({
                "score": float(score),
                "box": {"x1": x1, "y1": y1, "x2": min(x1 + kw * cell, 1.0), "y2": min(y1 + kh * cell, 1.0)},
                "stride": stride,
                "scale": entry["scale"],
            })
    return hits


def nms_hits(hits, max_per_image):
    """按分数从高到低留框，跟已留的框是同一个东西就不再留。"""
    kept = []
    for hit in sorted(hits, key=lambda h: -h["score"]):
        if any(is_same_object_box(hit["box"], other["box"]) for other in kept):
            continue
        kept.append(hit)
        if len(kept) >= max_per_image:
            break
    return kept


def _require_sample(dataset_names, class_id, sample_box):
    """样本这一头当场校验：类别号得是数据集里真有的，框得画得出面积。"""
    if not dataset_names:
        raise ValueError("该数据集还没有类别表（dataset.yaml 缺 names），候选框落进去没人认得它是哪一类，先补类别再探测。")
    cid = int(class_id)
    if cid < 0 or cid >= len(dataset_names):
        raise ValueError(
            f"样本框的类别号 {cid} 在数据集类别表里没有；现有 {len(dataset_names)} 类（0..{len(dataset_names) - 1}）。"
        )
    if len(sample_box) != 4:
        raise ValueError("样本框需要四个数（x1 y1 x2 y2）")
    if float(sample_box[2]) <= float(sample_box[0]) or float(sample_box[3]) <= float(sample_box[1]):
        raise ValueError("样本框没有面积，取不出特征窗口")


def image_maps(encoder, image_path):
    """一张图解码 + 前向，拿到三层特征图。"""
    with Image.open(image_path) as handle:
        return encoder.maps(encoder.to_tensor(handle))


def _spawn(target):
    """后台线程只有一个出口，测试要它同步跑完再断言，就从这里换。"""
    thread = threading.Thread(target=target, name="similar-probe", daemon=True)
    thread.start()
    return thread


def get_similarity_probe_status(task_id=None):
    """返回一次相似探测的对外状态摘要。"""
    task = None
    if task_id:
        task = load_task(task_id)
        if not task or task.get("type") != TASK_TYPE_SIMILAR_PROBE:
            raise ValueError("相似探测任务不存在")
    else:
        tasks = list_task_items(type_=TASK_TYPE_SIMILAR_PROBE, limit=20)
        task = next((item for item in tasks if item.get("type") == TASK_TYPE_SIMILAR_PROBE), None)
        if not task:
            return {"task_id": None, "is_running": False, "progress": 0, "message": "", "added": 0, "pending": 0}

    artifacts = task.get("artifacts") or {}
    return {
        "task_id": task.get("id"),
        "status": task.get("status"),
        "is_running": task.get("status") == TASK_STATUS_RUNNING,
        "progress": int(task.get("progress") or 0),
        "message": task.get("message") or "",
        "error": task.get("error"),
        "added": int(artifacts.get("added") or 0),
        "pending": int(artifacts.get("pending") or 0),
        "failed_images": int(artifacts.get("failed_images") or 0),
        "errors": list(artifacts.get("errors") or []),
    }


def start_similarity_probe(
    project_path,
    dataset_name,
    split,
    image_ref,
    class_id,
    sample_box=None,
    score_thresh=DEFAULT_SCORE_THRESH,
    max_per_image=DEFAULT_MAX_PER_IMAGE,
):
    """创建相似探测任务并启动后台线程；命中写进 auto_labels 当候选，人工标签一个字不动。

    sample_box 用像素 xyxy（跟标注画布同一套），这里换算成归一化，因为特征网格是归一化的。
    骨干权重和样本在这里同步准备好再回话：环境缺包、权重下不下来、框取不出特征，
    都要当场答复，不能跑到第 300 张才抛。
    """
    project_name = project_name_from_path(project_path)
    dataset_root = get_dataset_root(project_path, dataset_name)
    vision_task_type = load_dataset_vision_task_type(dataset_root)
    strategy = resolve_annotation_task_strategy(vision_task_type)
    if not strategy.supports_auto_annotation:
        raise ValueError("当前任务类型没有矩形框，相似探测给不出可审的候选")

    image_path = os.path.realpath(build_dataset_image_context(
        dataset_root, split, image_ref, project_path=project_path
    )["image_path"])
    dataset_names = load_dataset_names(dataset_root)
    width, height = get_image_size(image_path)
    normalized = [
        max(0.0, min(1.0, float(sample_box[0]) / width)),
        max(0.0, min(1.0, float(sample_box[1]) / height)),
        max(0.0, min(1.0, float(sample_box[2]) / width)),
        max(0.0, min(1.0, float(sample_box[3]) / height)),
    ]
    _require_sample(dataset_names, class_id, normalized)

    encoder = ProbeEncoder()
    sample_plan = build_sample_plan(encoder, image_path, normalized)

    class_name = str(dataset_names[int(class_id)])
    task = start_task(
        project_path=project_path,
        project_name=project_name,
        type_=TASK_TYPE_SIMILAR_PROBE,
        dataset_name=dataset_name,
        dataset_id=ensure_dataset_task_identity(dataset_root)["dataset_id"],
        dataset_path=dataset_root,
        vision_task_type=vision_task_type,
        payload={
            "split": split,
            "sample_image": storage_path_ref(image_path),
            "class_id": int(class_id),
            "class_name": class_name,
            "sample_box": [round(v, 6) for v in normalized],
            "score_thresh": float(score_thresh),
            "max_per_image": int(max_per_image),
        },
        message=f"以 {class_name} 的样本框探测相似目标...",
    )
    task_id = task["id"]
    update_task_status(task_id, status=TASK_STATUS_RUNNING, started_at=now_iso())

    def run_probe():
        """整 split 前向、把过线的窗口收成候选落盘，并持续更新任务进度。"""
        added = 0
        pending = 0
        errors = []
        try:
            run_source = {
                "task_id": task_id,
                "engine": "sample_similarity",
                "sample_image": storage_path_ref(image_path),
                "class_id": int(class_id),
                "class_name": class_name,
                "score_thresh": float(score_thresh),
                "started_at": now_iso(),
            }
            img_dir = strategy.get_auto_annotation_image_dir(dataset_root, split)
            images = [path for path in list_batch_image_paths(img_dir) if os.path.realpath(path) != image_path]
            total = len(images)
            update_task_status(
                task_id,
                progress=0,
                message=f"探测 {total} 张（不含样本自己）",
                payload={**(task.get("payload", {}) or {}), "image_count": total},
                artifacts=round_artifacts(added, pending, errors),
            )

            for index, path in enumerate(images, 1):
                context = build_dataset_image_context(dataset_root, split, path, project_path=project_path)
                try:
                    hits = nms_hits(
                        collect_image_hits(sample_plan, image_maps(encoder, path), normalized, score_thresh),
                        int(max_per_image),
                    )
                    image_width, image_height = get_image_size(path)
                    boxes = [{
                        "class": int(class_id),
                        "x1": hit["box"]["x1"] * image_width,
                        "y1": hit["box"]["y1"] * image_height,
                        "x2": hit["box"]["x2"] * image_width,
                        "y2": hit["box"]["y2"] * image_height,
                        "conf": round(hit["score"], 4),
                    } for hit in hits]
                    # 跟这张图已经标好的、或上一轮还没审的框是同一个东西的，不再提第二遍
                    refined = strategy.refine_auto_annotation(
                        context, {"boxes": boxes}, SAME_OBJECT_IOU_THRESH
                    )
                    if strategy.has_auto_annotation_content(refined):
                        strategy.save_auto_annotation(context, refined, source=run_source)
                        added += strategy.count_auto_annotation_items(refined)
                        pending += 1
                except Exception as exc:
                    errors.append(f"{os.path.basename(str(path))}: {exc}")

                if index % 10 == 0 or index == total:
                    update_task_status(
                        task_id,
                        progress=int(index / total * 100) if total else 100,
                        message=f"已处理 {index}/{total}",
                        artifacts=round_artifacts(added, pending, errors),
                    )

            update_task_status(
                task_id,
                status=TASK_STATUS_COMPLETED,
                progress=100,
                message=round_message(added, pending, errors, [class_name]),
                finished_at=now_iso(),
                artifacts=round_artifacts(added, pending, errors),
            )
        except Exception as exc:
            update_task_status(
                task_id,
                status=TASK_STATUS_FAILED,
                error=str(exc),
                message=f"出错: {exc}",
                finished_at=now_iso(),
            )

    _spawn(run_probe)
    return {"task_id": task_id}
