"""按训练方式拆分运行时语义，避免在 runner 内混写 classify/detect 分支。"""

import os

from contexts.dataset.infrastructure.dataset_layout import extract_classification_class_name
from contexts.model.domain.capabilities import (
    MODEL_TRAINING_MODE_UNSUPPORTED,
    MODEL_TRAINING_MODE_YOLO_CLASSIFY,
    MODEL_TRAINING_MODE_YOLO_DETECT,
    MODEL_TRAINING_MODE_YOLO_POSE,
    MODEL_TRAINING_MODE_YOLO_SEGMENT,
)


def _read_metric_value(metrics, keys=(), attr=None, default=0.0):
    """从 dict/object 结构中读取训练或评估指标。"""
    if isinstance(metrics, dict):
        for key in keys:
            if key in metrics and metrics.get(key) is not None:
                try:
                    return float(metrics.get(key))
                except (TypeError, ValueError):
                    pass
    if attr:
        value = getattr(metrics, attr, None)
        if value is not None:
            try:
                return float(value)
            except (TypeError, ValueError):
                pass
    return float(default)


def _read_loss_item(loss_items, index=0, default=0.0):
    """兼容标量/向量 loss_items 结构，稳定读取单个损失值。"""
    if loss_items is None:
        return float(default)
    if hasattr(loss_items, "ndim") and getattr(loss_items, "ndim") == 0:
        try:
            return float(loss_items.item())
        except (TypeError, ValueError):
            return float(default)
    if hasattr(loss_items, "tolist"):
        try:
            values = loss_items.tolist()
            if isinstance(values, list) and len(values) > index:
                return float(values[index])
            if index == 0 and values is not None:
                return float(values)
        except (TypeError, ValueError):
            return float(default)
    try:
        if len(loss_items) > index:
            return float(loss_items[index])
    except (TypeError, ValueError):
        return float(default)
    return float(default)


def _build_classification_predictions(output, limit=5):
    """将分类推理结果转换为稳定的前端协议。"""
    probs = getattr(output, "probs", None)
    if probs is None:
        return {
            "top1_class_id": None,
            "top1_class_name": "",
            "top1_confidence": None,
            "predictions": [],
        }
    names = getattr(output, "names", {}) or {}
    top5_ids = list(getattr(probs, "top5", []) or [])[:limit]
    top5_conf_raw = getattr(probs, "top5conf", None)
    if hasattr(top5_conf_raw, "tolist"):
        top5_conf = list(top5_conf_raw.tolist())
    elif top5_conf_raw is None:
        top5_conf = []
    else:
        top5_conf = list(top5_conf_raw)
    predictions = []
    for index, class_id in enumerate(top5_ids):
        normalized_class_id = int(class_id)
        confidence = top5_conf[index] if index < len(top5_conf) else None
        predictions.append(
            {
                "class_id": normalized_class_id,
                "class_name": names.get(normalized_class_id, f"class_{normalized_class_id}"),
                "confidence": float(confidence) if confidence is not None else 0.0,
            }
        )
    top1_id = getattr(probs, "top1", None)
    top1_conf = getattr(probs, "top1conf", None)
    return {
        "top1_class_id": int(top1_id) if top1_id is not None else None,
        "top1_class_name": names.get(int(top1_id), f"class_{int(top1_id)}") if top1_id is not None else "",
        "top1_confidence": float(top1_conf) if top1_conf is not None else None,
        "predictions": predictions,
    }


def _resolve_class_name_id(class_names, class_name):
    """按类别名解析稳定 class id。"""
    for index, name in enumerate(class_names or []):
        if str(name) == class_name:
            return index
    return None


def _to_float_list(values):
    """尽量把张量/数组转成 float 列表。"""
    if values is None:
        return []
    if hasattr(values, "tolist"):
        values = values.tolist()
    if not isinstance(values, list):
        return []
    result = []
    for item in values:
        try:
            result.append(float(item))
        except (TypeError, ValueError):
            return []
    return result


class TrainingRuntimeAdapter:
    """训练运行时策略基类。"""

    training_mode = MODEL_TRAINING_MODE_UNSUPPORTED

    def build_epoch_update(self, _trainer, _epoch, _epochs):
        raise NotImplementedError

    def build_evaluate_results(self, _metrics, _split):
        raise NotImplementedError

    def build_inference_result(self, _output, _image_path, _img_dir, _class_names):
        """将单张推理输出转换为当前训练方式对应的结果协议。"""
        raise NotImplementedError


class DetectTrainingRuntimeAdapter(TrainingRuntimeAdapter):
    """YOLO 检测训练运行时语义。"""

    training_mode = MODEL_TRAINING_MODE_YOLO_DETECT

    def build_epoch_update(self, trainer, epoch, epochs):
        metrics = trainer.metrics
        box_loss = _read_loss_item(trainer.loss_items, index=0)
        cls_loss = _read_loss_item(trainer.loss_items, index=1)
        dfl_loss = _read_loss_item(trainer.loss_items, index=2)
        map50 = _read_metric_value(metrics, keys=("metrics/mAP50(B)",))
        map50_95 = _read_metric_value(metrics, keys=("metrics/mAP50-95(B)",))
        return {
            "message": f"Epoch {epoch}/{epochs} box_loss:{box_loss:.4f} mAP50:{map50:.4f}",
            "history": {
                "epoch": epoch,
                "box_loss": box_loss,
                "cls_loss": cls_loss,
                "dfl_loss": dfl_loss,
                "map50": map50,
                "map50_95": map50_95,
            },
        }

    def build_evaluate_results(self, metrics, split):
        return {
            "split": split,
            "map50": float(getattr(metrics.box, "map50", 0)),
            "map50_95": float(getattr(metrics.box, "map", 0)),
            "precision": float(getattr(metrics.box, "mp", 0)),
            "recall": float(getattr(metrics.box, "mr", 0)),
        }

    def build_inference_result(self, output, _image_path, _img_dir, _class_names):
        names = getattr(output, "names", {}) or {}
        boxes = []
        if output.boxes is not None:
            for box in output.boxes:
                class_id = int(box.cls[0])
                boxes.append(
                    {
                        "xyxy": [float(value) for value in box.xyxy[0].tolist()],
                        "conf": float(box.conf[0]),
                        "cls": class_id,
                        "class_name": names.get(class_id, f"class_{class_id}"),
                    }
                )
        return {"boxes": boxes}


class ClassifyTrainingRuntimeAdapter(TrainingRuntimeAdapter):
    """YOLO 分类训练运行时语义。"""

    training_mode = MODEL_TRAINING_MODE_YOLO_CLASSIFY

    def build_epoch_update(self, trainer, epoch, epochs):
        metrics = trainer.metrics
        train_loss = _read_loss_item(trainer.loss_items)
        top1 = _read_metric_value(metrics, keys=("metrics/accuracy_top1", "metrics/top1"), attr="top1")
        top5 = _read_metric_value(metrics, keys=("metrics/accuracy_top5", "metrics/top5"), attr="top5")
        return {
            "message": f"Epoch {epoch}/{epochs} loss:{train_loss:.4f} top1:{top1:.4f}",
            "history": {
                "epoch": epoch,
                "cls_loss": train_loss,
                "extra": {"train_loss": train_loss, "top1": top1, "top5": top5},
            },
        }

    def build_evaluate_results(self, metrics, split):
        return {
            "split": split,
            "top1": _read_metric_value(metrics, attr="top1"),
            "top5": _read_metric_value(metrics, attr="top5"),
        }

    def build_inference_result(self, output, image_path, img_dir, class_names):
        result = _build_classification_predictions(output)
        relative_path = os.path.relpath(image_path, img_dir)
        class_name = extract_classification_class_name(relative_path)
        true_class_id = _resolve_class_name_id(class_names, class_name)
        result.update(
            {
                "true_class_id": true_class_id,
                "true_class_name": class_names[true_class_id] if true_class_id is not None and 0 <= true_class_id < len(class_names) else "",
                "has_ground_truth": true_class_id is not None,
            }
        )
        result["is_correct"] = bool(
            result.get("has_ground_truth")
            and result.get("true_class_id") == result.get("top1_class_id")
        )
        return result


class SegmentTrainingRuntimeAdapter(TrainingRuntimeAdapter):
    """YOLO 实例分割训练运行时语义。"""

    training_mode = MODEL_TRAINING_MODE_YOLO_SEGMENT

    def build_epoch_update(self, trainer, epoch, epochs):
        metrics = trainer.metrics
        box_loss = _read_loss_item(trainer.loss_items, index=0)
        seg_loss = _read_loss_item(trainer.loss_items, index=1)
        cls_loss = _read_loss_item(trainer.loss_items, index=2)
        dfl_loss = _read_loss_item(trainer.loss_items, index=3)
        seg_map50 = _read_metric_value(metrics, keys=("metrics/mAP50(M)",))
        seg_map50_95 = _read_metric_value(metrics, keys=("metrics/mAP50-95(M)",))
        box_map50 = _read_metric_value(metrics, keys=("metrics/mAP50(B)",))
        box_map50_95 = _read_metric_value(metrics, keys=("metrics/mAP50-95(B)",))
        return {
            "message": f"Epoch {epoch}/{epochs} seg_loss:{seg_loss:.4f} mask mAP50:{seg_map50:.4f}",
            "history": {
                "epoch": epoch,
                "box_loss": box_loss,
                "cls_loss": cls_loss,
                "dfl_loss": dfl_loss,
                "map50": seg_map50,
                "map50_95": seg_map50_95,
                "extra": {
                    "seg_loss": seg_loss,
                    "box_map50": box_map50,
                    "box_map50_95": box_map50_95,
                    "seg_map50": seg_map50,
                    "seg_map50_95": seg_map50_95,
                },
            },
        }

    def build_evaluate_results(self, metrics, split):
        return {
            "split": split,
            "box_precision": float(getattr(metrics.box, "mp", 0)),
            "box_recall": float(getattr(metrics.box, "mr", 0)),
            "box_map50": float(getattr(metrics.box, "map50", 0)),
            "box_map50_95": float(getattr(metrics.box, "map", 0)),
            "seg_precision": float(getattr(metrics.seg, "mp", 0)),
            "seg_recall": float(getattr(metrics.seg, "mr", 0)),
            "seg_map50": float(getattr(metrics.seg, "map50", 0)),
            "seg_map50_95": float(getattr(metrics.seg, "map", 0)),
        }

    def build_inference_result(self, output, _image_path, _img_dir, _class_names):
        names = getattr(output, "names", {}) or {}
        boxes = []
        segments = list(getattr(getattr(output, "masks", None), "xy", []) or [])
        if output.boxes is not None:
            for index, box in enumerate(output.boxes):
                class_id = int(box.cls[0])
                polygon = []
                if index < len(segments):
                    polygon = [[float(x), float(y)] for x, y in segments[index].tolist()]
                boxes.append(
                    {
                        "xyxy": [float(value) for value in box.xyxy[0].tolist()],
                        "conf": float(box.conf[0]),
                        "cls": class_id,
                        "class_name": names.get(class_id, f"class_{class_id}"),
                        "segment": polygon,
                    }
                )
        return {"boxes": boxes}


class PoseTrainingRuntimeAdapter(TrainingRuntimeAdapter):
    """YOLO 姿态估计训练运行时语义。"""

    training_mode = MODEL_TRAINING_MODE_YOLO_POSE

    def build_epoch_update(self, trainer, epoch, epochs):
        metrics = trainer.metrics
        box_loss = _read_loss_item(trainer.loss_items, index=0)
        pose_loss = _read_loss_item(trainer.loss_items, index=1)
        kobj_loss = _read_loss_item(trainer.loss_items, index=2)
        cls_loss = _read_loss_item(trainer.loss_items, index=3)
        dfl_loss = _read_loss_item(trainer.loss_items, index=4)
        pose_map50 = _read_metric_value(metrics, keys=("metrics/mAP50(P)",))
        pose_map50_95 = _read_metric_value(metrics, keys=("metrics/mAP50-95(P)",))
        box_map50 = _read_metric_value(metrics, keys=("metrics/mAP50(B)",))
        box_map50_95 = _read_metric_value(metrics, keys=("metrics/mAP50-95(B)",))
        return {
            "message": f"Epoch {epoch}/{epochs} pose_loss:{pose_loss:.4f} pose mAP50:{pose_map50:.4f}",
            "history": {
                "epoch": epoch,
                "box_loss": box_loss,
                "cls_loss": cls_loss,
                "dfl_loss": dfl_loss,
                "map50": pose_map50,
                "map50_95": pose_map50_95,
                "extra": {
                    "pose_loss": pose_loss,
                    "kobj_loss": kobj_loss,
                    "box_map50": box_map50,
                    "box_map50_95": box_map50_95,
                    "pose_map50": pose_map50,
                    "pose_map50_95": pose_map50_95,
                },
            },
        }

    def build_evaluate_results(self, metrics, split):
        pose_metrics = getattr(metrics, "pose", None)
        if pose_metrics is None:
            pose_metrics = getattr(metrics, "box", None)
        return {
            "split": split,
            "precision": float(getattr(pose_metrics, "mp", 0)),
            "recall": float(getattr(pose_metrics, "mr", 0)),
            "map50": float(getattr(pose_metrics, "map50", 0)),
            "map50_95": float(getattr(pose_metrics, "map", 0)),
            "box_map50": float(getattr(getattr(metrics, "box", None), "map50", 0)),
            "box_map50_95": float(getattr(getattr(metrics, "box", None), "map", 0)),
        }

    def build_inference_result(self, output, _image_path, _img_dir, _class_names):
        names = getattr(output, "names", {}) or {}
        boxes = []
        keypoints_xy = list(getattr(getattr(output, "keypoints", None), "xy", []) or [])
        keypoints_conf = list(getattr(getattr(output, "keypoints", None), "conf", []) or [])
        if output.boxes is not None:
            for index, box in enumerate(output.boxes):
                class_id = int(box.cls[0])
                item = {
                    "xyxy": [float(value) for value in box.xyxy[0].tolist()],
                    "conf": float(box.conf[0]),
                    "cls": class_id,
                    "class_name": names.get(class_id, f"class_{class_id}"),
                    "keypoints": [],
                }
                xy_points = []
                if index < len(keypoints_xy):
                    raw_points = keypoints_xy[index]
                    if hasattr(raw_points, "tolist"):
                        raw_points = raw_points.tolist()
                    if isinstance(raw_points, list):
                        for point in raw_points:
                            if isinstance(point, list) and len(point) >= 2:
                                try:
                                    xy_points.append({"x": float(point[0]), "y": float(point[1])})
                                except (TypeError, ValueError):
                                    xy_points.append({"x": 0.0, "y": 0.0})
                conf_points = []
                if index < len(keypoints_conf):
                    conf_points = _to_float_list(keypoints_conf[index])
                for point_index, point in enumerate(xy_points):
                    item["keypoints"].append(
                        {
                            **point,
                            "conf": conf_points[point_index] if point_index < len(conf_points) else None,
                        }
                    )
                boxes.append(item)
        return {"boxes": boxes}


_RUNTIME_ADAPTERS = {
    MODEL_TRAINING_MODE_YOLO_DETECT: DetectTrainingRuntimeAdapter(),
    MODEL_TRAINING_MODE_YOLO_CLASSIFY: ClassifyTrainingRuntimeAdapter(),
    MODEL_TRAINING_MODE_YOLO_SEGMENT: SegmentTrainingRuntimeAdapter(),
    MODEL_TRAINING_MODE_YOLO_POSE: PoseTrainingRuntimeAdapter(),
}


def resolve_training_runtime_adapter(training_mode):
    """按训练方式返回唯一运行时策略。"""
    adapter = _RUNTIME_ADAPTERS.get(training_mode)
    if adapter is None:
        raise ValueError(f"当前训练方式暂未接入运行时策略: {training_mode}")
    return adapter


__all__ = ["resolve_training_runtime_adapter"]
