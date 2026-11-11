"""按数据集任务类型封装标注协议与标注列表策略。"""

import os

from contexts.annotation.infrastructure.annotation_io import (
    decode_classification_file,
    decode_detect_file,
    decode_pose_file,
    decode_segment_file,
    encode_classification_lines,
    encode_detect_lines,
    encode_pose_lines,
    encode_segment_lines,
    get_image_size,
    load_pose_annotation_meta,
    resolve_classification_class_id,
)
from constants.media import IMAGE_FILE_EXTENSIONS
from contexts.dataset.application.dataset_service import (
    build_label_relpath,
    get_dataset_auto_labels_dir,
    get_dataset_images_dir,
    get_dataset_labels_dir,
    get_dataset_unlabeled_dir,
)
from protocols.vision_task_type import VISION_TASK_TYPE_CLASSIFY, VISION_TASK_TYPE_DETECT, VISION_TASK_TYPE_POSE, VISION_TASK_TYPE_SEGMENT
from shared.utils.fs_utils import remove_empty_dirs_up_to
from shared.utils.path_utils import build_file_items, file_api_url, storage_path_ref, slice_items
from shared.utils.yolo_utils import read_yolo_lines, write_yolo_lines
from contexts.annotation.infrastructure.batch_helpers import (
    extract_prediction_boxes,
    load_existing_manual_boxes,
)
from contexts.annotation.infrastructure.auto_annotation_store import (
    attach_conf,
    describe_auto_items,
    drop_auto_annotation,
    load_auto_meta,
    write_auto_annotation,
)
from contexts.annotation.domain.services import filter_duplicate_boxes, filter_duplicate_polygons, polygon_area
from contexts.annotation.domain.class_alignment import (
    class_ids_from_label_lines,
    require_label_classes_writable,
)


class BaseAnnotationTaskStrategy:
    """定义标注协议策略基类。"""

    vision_task_type = ""
    supports_auto_annotation = False

    def get_annotation_payload(self, *_args, **_kwargs):
        """根据已解析的图片上下文构造标注载荷。"""
        raise NotImplementedError

    def save_manual_annotation(self, *_args, **_kwargs):
        """按当前任务类型保存人工标注。"""
        raise NotImplementedError

    def save_auto_annotation(self, *_args, **_kwargs):
        """按当前任务类型保存自动标注结果。"""
        raise NotImplementedError

    def commit_auto_annotation(self, context):
        """把这张图还没审的候选搬进人工标签，然后清掉候选——就是逐张点保存的那一下。

        接在现有标签后面：原来的框不动，一行都不重写。搬运走的是标签同一套编码，
        搬过去的内容和当初看到的内容才不会是两回事。
        """
        lines = read_yolo_lines(context["auto_label_path"])
        existing = read_yolo_lines(context["manual_label_path"])
        write_yolo_lines(context["manual_label_path"], existing + lines)
        drop_auto_annotation(context)
        return {"written_items": len(lines), "label_items": len(existing) + len(lines)}

    def encode_label_lines(self, _context, _annotation):
        """把一批结果编码成可直接写进标签文件的文本行。

        落盘到待确认目录和并入人工标签走的是同一条编码路径：两处各算一遍，
        人点保存时写进去的内容就可能和当初看到的不是一回事。
        """
        raise NotImplementedError

    def decode_pending_items(self, *_args, **_kwargs):
        """按标签行序解码待确认结果，并贴回逐条置信度。"""
        raise NotImplementedError

    def list_missing_annotations(self, *_args, **_kwargs):
        """列出当前任务类型下缺少人工标注的样本。"""
        raise NotImplementedError

    def list_pending_auto_annotations(self, *_args, **_kwargs):
        """列出当前任务类型下待确认的自动标注样本。"""
        raise NotImplementedError

    def get_auto_annotation_image_dir(self, *_args, **_kwargs):
        """返回批量自动标注任务要扫描的图片目录。"""
        raise NotImplementedError

    def extract_auto_annotation(self, *_args, **_kwargs):
        """把模型输出转换为当前任务类型的自动标注载荷。"""
        raise NotImplementedError

    def select_auto_annotation_classes(self, annotation, class_ids):
        """只留下选定类别的候选；没给选定类别就原样返回。

        漏标探测按类别一轮一轮跑：一次探六个类，候选队列会涨到人审不动的量。
        """
        payload = annotation or {}
        if not class_ids:
            return payload
        if payload.get("class_id") is not None:
            return payload if int(payload["class_id"]) in class_ids else {}
        pruned = dict(payload)
        for key in ("boxes", "polygons", "instances"):
            if key in payload:
                pruned[key] = [
                    item for item in payload[key] or []
                    if int(item.get("class", -1)) in class_ids
                ]
        return pruned

    def refine_auto_annotation(self, _context, annotation, _iou_thresh):
        """在写入待确认结果前，对自动标注载荷执行任务类型特有的清洗。"""
        return annotation

    def has_auto_annotation_content(self, _annotation):
        """判断自动标注载荷是否包含可写入内容。"""
        raise NotImplementedError

    def count_auto_annotation_items(self, _annotation):
        """返回一次自动标注实际新增的结果数量。"""
        raise NotImplementedError


def _scalar_to_float(value, default=0.0):
    """把 tensor / numpy scalar / Python 标量统一转成 float。"""
    try:
        if hasattr(value, "item"):
            value = value.item()
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _tolist(value):
    """把支持 tolist 的容器统一转成 Python list。"""
    if value is None:
        return None
    if hasattr(value, "tolist"):
        try:
            return value.tolist()
        except Exception:
            return None
    return value


def _normalize_box_xyxy(box):
    """把单个预测框归一化为 x1/y1/x2/y2 结构。"""
    xyxy = getattr(box, "xyxy", None)
    xyxy = _tolist(xyxy)
    if not xyxy:
        return None
    if isinstance(xyxy, list) and xyxy and isinstance(xyxy[0], list):
        xyxy = xyxy[0]
    if not isinstance(xyxy, list) or len(xyxy) < 4:
        return None
    x1 = _scalar_to_float(xyxy[0])
    y1 = _scalar_to_float(xyxy[1])
    x2 = _scalar_to_float(xyxy[2])
    y2 = _scalar_to_float(xyxy[3])
    if x2 <= x1 or y2 <= y1:
        return None
    return {
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
    }


def _normalize_pose_keypoint_rows(keypoints_obj):
    """从 Ultralytics keypoints 对象中提取逐实例关键点行。"""
    if keypoints_obj is None:
        return []
    data_rows = _tolist(getattr(keypoints_obj, "data", None))
    if isinstance(data_rows, list):
        return data_rows
    xy_rows = _tolist(getattr(keypoints_obj, "xy", None))
    conf_rows = _tolist(getattr(keypoints_obj, "conf", None))
    if not isinstance(xy_rows, list):
        return []
    rows = []
    for index, xy_row in enumerate(xy_rows):
        xy_points = xy_row if isinstance(xy_row, list) else _tolist(xy_row)
        conf_row = conf_rows[index] if isinstance(conf_rows, list) and index < len(conf_rows) else None
        conf_points = conf_row if isinstance(conf_row, list) else _tolist(conf_row)
        merged_points = []
        for point_index, point in enumerate(xy_points or []):
            point_values = point if isinstance(point, list) else _tolist(point)
            if not isinstance(point_values, list) or len(point_values) < 2:
                continue
            merged_point = [point_values[0], point_values[1]]
            if isinstance(conf_points, list) and point_index < len(conf_points):
                merged_point.append(conf_points[point_index])
            merged_points.append(merged_point)
        rows.append(merged_points)
    return rows


def _build_pose_instance_from_prediction(box, keypoint_row):
    """把单个 pose 预测结果转换成统一实例结构。"""
    bbox = _normalize_box_xyxy(box)
    if not bbox:
        return None
    class_id = 0
    if getattr(box, "cls", None) is not None:
        class_id = int(_scalar_to_float(getattr(box, "cls", None), default=0))
    keypoints = []
    for point in keypoint_row or []:
        values = point if isinstance(point, list) else _tolist(point)
        if not isinstance(values, list) or len(values) < 2:
            continue
        x = _scalar_to_float(values[0])
        y = _scalar_to_float(values[1])
        visible = 0
        if len(values) >= 3:
            visible = 2 if _scalar_to_float(values[2]) > 0 else 0
        elif x > 0 or y > 0:
            visible = 2
        keypoints.append({"x": x, "y": y, "visible": visible})
    if not any(int(point.get("visible", 0) or 0) > 0 for point in keypoints):
        return None
    raw_conf = getattr(box, "conf", None)
    return {
        "class": class_id,
        **bbox,
        "keypoints": keypoints,
        "conf": round(_scalar_to_float(raw_conf), 6) if raw_conf is not None else None,
    }


def _sanitize_pose_instance(instance, width, height, keypoint_count):
    """按数据集关键点配置清洗 pose 实例并补齐有效 bbox。"""
    normalized_points = []
    raw_points = (instance or {}).get("keypoints") or []
    target_count = max(int(keypoint_count or 0), len(raw_points))
    for index in range(target_count):
        point = {}
        if index < len(raw_points) and isinstance(raw_points[index], dict):
            point = raw_points[index]
        visible = int(_scalar_to_float(point.get("visible", 0), default=0))
        visible = max(0, min(2, visible))
        if visible > 0:
            x = max(0.0, min(float(width), _scalar_to_float(point.get("x", 0.0))))
            y = max(0.0, min(float(height), _scalar_to_float(point.get("y", 0.0))))
        else:
            x = 0.0
            y = 0.0
        normalized_points.append({"x": x, "y": y, "visible": visible})
    if not any(point["visible"] > 0 for point in normalized_points):
        return None

    x1 = max(0.0, min(float(width), _scalar_to_float((instance or {}).get("x1", 0.0))))
    y1 = max(0.0, min(float(height), _scalar_to_float((instance or {}).get("y1", 0.0))))
    x2 = max(0.0, min(float(width), _scalar_to_float((instance or {}).get("x2", 0.0))))
    y2 = max(0.0, min(float(height), _scalar_to_float((instance or {}).get("y2", 0.0))))
    if x2 <= x1 or y2 <= y1:
        visible_points = [point for point in normalized_points if point["visible"] > 0]
        xs = [point["x"] for point in visible_points]
        ys = [point["y"] for point in visible_points]
        x1 = min(xs)
        y1 = min(ys)
        x2 = max(xs)
        y2 = max(ys)
        if x2 <= x1:
            x2 = min(float(width), x1 + 1.0)
        if y2 <= y1:
            y2 = min(float(height), y1 + 1.0)

    return {
        "class": int(_scalar_to_float((instance or {}).get("class", 0), default=0)),
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        # 清洗会重建实例，置信度不带就丢了审核依据
        "conf": (instance or {}).get("conf"),
        "keypoints": normalized_points,
    }


class ClassifyAnnotationTaskStrategy(BaseAnnotationTaskStrategy):
    """图像分类标注策略。"""

    vision_task_type = VISION_TASK_TYPE_CLASSIFY
    supports_auto_annotation = True

    def get_annotation_payload(self, context):
        """根据类别目录归属生成分类标注载荷。"""
        width, height = get_image_size(context["image_path"])
        auto_meta = load_auto_meta(context)
        first_item = auto_meta["items"][0] if auto_meta["items"] else {}
        return {
            "vision_task_type": self.vision_task_type,
            "manual_annotation": {"class_id": resolve_classification_class_id(context)},
            "auto_annotation": {
                "class_id": decode_classification_file(context["auto_label_path"]),
                "conf": (first_item or {}).get("conf"),
                "source": auto_meta["source"],
            },
            "width": width,
            "height": height,
        }

    def commit_auto_annotation(self, context):
        """分类的候选是一个类别答案，不是一批标签行：按行搬进标签文件会造出没人认得的标签。
        它的判定就是把答案落到类别目录里，走逐张保存那一条路。
        """
        raise NotImplementedError("分类任务没有标签文件可搬，请逐张保存")

    def save_manual_annotation(self, context, annotation):
        """通过移动图片到目标类别目录保存分类人工标注。"""
        lines = encode_classification_lines(annotation or {})
        require_label_classes_writable(context.get("class_names") or [], class_ids_from_label_lines(lines))
        target_image_path = context["image_path"]
        if not lines:
            if context.get("is_unlabeled"):
                drop_auto_annotation(context)
                return {
                    "image_path": storage_path_ref(target_image_path),
                    "image_url": file_api_url(target_image_path),
                    "label_path": storage_path_ref(target_image_path),
                }
            target_image_path = os.path.join(context["unlabeled_dir"], context["sample_relative_path"])
            os.makedirs(os.path.dirname(target_image_path), exist_ok=True)
            os.replace(context["image_path"], target_image_path)
            remove_empty_dirs_up_to(context["image_path"], context["split_dir"])
            drop_auto_annotation(context)
            return {
                "image_path": storage_path_ref(target_image_path),
                "image_url": file_api_url(target_image_path),
                "label_path": storage_path_ref(target_image_path),
            }
        class_id = int(lines[0])
        class_names = context.get("class_names") or []
        if class_id < 0 or class_id >= len(class_names):
            raise ValueError("分类类别无效")
        target_class_name = str(class_names[class_id])
        current_class_name = context.get("class_name") or ""
        if current_class_name != target_class_name:
            target_image_path = os.path.join(context["split_dir"], target_class_name, context["sample_relative_path"])
            os.makedirs(os.path.dirname(target_image_path), exist_ok=True)
            os.replace(context["image_path"], target_image_path)
            remove_empty_dirs_up_to(context["image_path"], context["unlabeled_dir"] if context.get("is_unlabeled") else context["split_dir"])
        drop_auto_annotation(context)
        return {
            "image_path": storage_path_ref(target_image_path),
            "image_url": file_api_url(target_image_path),
            "label_path": storage_path_ref(target_image_path),
        }

    def encode_label_lines(self, _context, annotation):
        """分类候选整图一个判断，编码成一行的候选类别。"""
        return encode_classification_lines(annotation or {})

    def save_auto_annotation(self, context, annotation, source=None):
        """把分类自动标注候选类别写入待确认目录。"""
        lines = self.encode_label_lines(context, annotation)
        if not lines:
            raise ValueError("自动标注结果为空")
        # 分类的候选是一张图一个答案，合并写入会变成两个答案，所以只有这一类覆盖写
        write_auto_annotation(context, lines, describe_auto_items(annotation), source, merge_existing=False)
        return {"label_path": storage_path_ref(context["auto_label_path"])}

    def decode_pending_items(self, context, _width, _height, meta=None):
        """分类候选解码为单条整图结果，没有待确认候选时为空。"""
        class_id = decode_classification_file(context["auto_label_path"])
        if class_id is None:
            return []
        meta_items = (meta if meta is not None else load_auto_meta(context))["items"]
        return [{"class": class_id, "conf": meta_items[0].get("conf") if meta_items else None}]

    def list_missing_annotations(self, dataset_root, split, offset=0, limit=50):
        """扫描分类未标注工作区，返回仍未归类的图片。"""
        img_dir = get_dataset_unlabeled_dir(dataset_root, split)
        items = []
        for root, _, files in os.walk(img_dir):
            for file_name in files:
                if file_name.lower().endswith(IMAGE_FILE_EXTENSIONS):
                    items.append(os.path.join(root, file_name))
        return slice_items(build_file_items(sorted(items)), offset=offset, limit=limit)

    def list_pending_auto_annotations(self, dataset_root, split, offset=0, limit=50):
        """扫描分类未标注工作区中已有候选类别的图片。"""
        img_dir = get_dataset_unlabeled_dir(dataset_root, split)
        auto_dir = get_dataset_auto_labels_dir(dataset_root, split)
        items = []
        for root, _, files in os.walk(img_dir):
            for file_name in files:
                if not file_name.lower().endswith(IMAGE_FILE_EXTENSIONS):
                    continue
                image_path = os.path.join(root, file_name)
                rel = os.path.relpath(image_path, img_dir)
                auto_label_path = os.path.join(auto_dir, "unlabeled", build_label_relpath(rel))
                if os.path.exists(auto_label_path):
                    items.append(image_path)
        return slice_items(build_file_items(sorted(items)), offset=offset, limit=limit)

    def get_auto_annotation_image_dir(self, dataset_root, split):
        """分类自动标注仅扫描未标注工作区。"""
        return get_dataset_unlabeled_dir(dataset_root, split)

    def extract_auto_annotation(self, prediction):
        """把分类模型输出解析为单个候选 class_id。"""
        probs = getattr(prediction, "probs", None)
        top1 = getattr(probs, "top1", None) if probs is not None else None
        if top1 is None:
            return {}
        top1_conf = getattr(probs, "top1conf", None)
        return {
            "class_id": int(top1),
            "conf": round(_scalar_to_float(top1_conf), 6) if top1_conf is not None else None,
        }

    def has_auto_annotation_content(self, annotation):
        """分类候选结果以单个 class_id 为准。"""
        return isinstance(annotation, dict) and annotation.get("class_id") is not None

    def count_auto_annotation_items(self, annotation):
        """分类一次自动标注至多新增一个候选类别。"""
        return 1 if self.has_auto_annotation_content(annotation) else 0


class DetectAnnotationTaskStrategy(BaseAnnotationTaskStrategy):
    """目标检测标注策略。"""

    vision_task_type = VISION_TASK_TYPE_DETECT
    supports_auto_annotation = True

    def get_annotation_payload(self, context):
        """读取检测人工框和自动框，构造标注载荷。"""
        width, height = get_image_size(context["image_path"])
        auto_meta = load_auto_meta(context)
        return {
            "vision_task_type": self.vision_task_type,
            "manual_annotation": {"boxes": decode_detect_file(context["manual_label_path"], width, height)},
            "auto_annotation": {"boxes": self.decode_pending_items(context, width, height, auto_meta), "source": auto_meta["source"]},
            "width": width,
            "height": height,
        }

    def decode_pending_items(self, context, width, height, meta=None):
        """按行序解码检测待确认框，并贴回逐框置信度。"""
        return attach_conf(decode_detect_file(context["auto_label_path"], width, height), meta if meta is not None else load_auto_meta(context))

    def save_manual_annotation(self, context, annotation):
        """把检测框写入人工标签文件。这张图的候选由保存它的用例一并判掉。"""
        width, height = get_image_size(context["image_path"])
        labels = (annotation or {}).get("boxes") or []
        write_yolo_lines(context["manual_label_path"], encode_detect_lines(labels, width, height))
        return {"label_path": storage_path_ref(context["manual_label_path"])}

    def encode_label_lines(self, context, annotation):
        """把检测框编码成 YOLO 行。"""
        width, height = get_image_size(context["image_path"])
        return encode_detect_lines((annotation or {}).get("boxes") or [], width, height)

    def save_auto_annotation(self, context, annotation, source=None):
        """把检测自动标注结果写入 auto_labels 目录，并留下逐框置信度与出处。"""
        write_auto_annotation(
            context,
            self.encode_label_lines(context, annotation),
            describe_auto_items(annotation),
            source,
        )
        return {"label_path": storage_path_ref(context["auto_label_path"])}

    def list_missing_annotations(self, dataset_root, split, offset=0, limit=50):
        """扫描检测图片目录，返回缺失或空人工标签的图片。"""
        img_dir = get_dataset_images_dir(dataset_root, split)
        lbl_dir = get_dataset_labels_dir(dataset_root, split)
        missing = []
        for root, _, files in os.walk(img_dir):
            for file_name in files:
                if not file_name.lower().endswith(IMAGE_FILE_EXTENSIONS):
                    continue
                image_path = os.path.join(root, file_name)
                rel = os.path.relpath(image_path, img_dir)
                label_path = os.path.join(lbl_dir, build_label_relpath(rel))
                if not os.path.exists(label_path) or os.path.getsize(label_path) == 0:
                    missing.append(image_path)
        return slice_items(build_file_items(missing), offset=offset, limit=limit)

    def list_pending_auto_annotations(self, dataset_root, split, offset=0, limit=50):
        """扫描检测 auto_labels 目录，返回存在待确认自动标签的图片。"""
        img_dir = get_dataset_images_dir(dataset_root, split)
        auto_dir = get_dataset_auto_labels_dir(dataset_root, split)
        items = []
        for root, _, files in os.walk(img_dir):
            for file_name in files:
                if not file_name.lower().endswith(IMAGE_FILE_EXTENSIONS):
                    continue
                image_path = os.path.join(root, file_name)
                rel = os.path.relpath(image_path, img_dir)
                auto_label_path = os.path.join(auto_dir, build_label_relpath(rel))
                if os.path.exists(auto_label_path):
                    items.append(image_path)
        return slice_items(build_file_items(items), offset=offset, limit=limit)

    def get_auto_annotation_image_dir(self, dataset_root, split):
        """检测自动标注扫描 split/images。"""
        return get_dataset_images_dir(dataset_root, split)

    def extract_auto_annotation(self, prediction):
        """把 Ultralytics 检测输出统一成检测框载荷。"""
        return {"boxes": extract_prediction_boxes(prediction)}

    def refine_auto_annotation(self, context, annotation, iou_thresh):
        """检测自动标注只清洗「跟已有框是同一个东西」的候选。

        判据只有一条，在 domain/services.is_same_object_box：重叠到七成以上，或一个
        九成以上落在另一个里。iou_thresh 就是那条里的重叠线，接口参数真的生效。
        """
        boxes = (annotation or {}).get("boxes") or []
        if not boxes:
            return {"boxes": []}
        width, height = get_image_size(context["image_path"])
        rel_noext = context["relative_noext"]
        existing_manual = load_existing_manual_boxes(context["dataset_root"], context.get("split"), rel_noext, width, height)
        existing_auto = decode_detect_file(context["auto_label_path"], width, height)
        return {"boxes": filter_duplicate_boxes(boxes, existing_manual, existing_auto, iou_thresh)}

    def has_auto_annotation_content(self, annotation):
        """检测候选结果以框列表非空为准。"""
        return bool((annotation or {}).get("boxes"))

    def count_auto_annotation_items(self, annotation):
        """返回检测自动标注新增框数。"""
        return len((annotation or {}).get("boxes") or [])


class SegmentAnnotationTaskStrategy(BaseAnnotationTaskStrategy):
    """实例分割标注策略。"""

    vision_task_type = VISION_TASK_TYPE_SEGMENT
    supports_auto_annotation = True

    def get_annotation_payload(self, context):
        width, height = get_image_size(context["image_path"])
        auto_meta = load_auto_meta(context)
        return {
            "vision_task_type": self.vision_task_type,
            "manual_annotation": {"polygons": decode_segment_file(context["manual_label_path"], width, height)},
            "auto_annotation": {"polygons": self.decode_pending_items(context, width, height, auto_meta), "source": auto_meta["source"]},
            "width": width,
            "height": height,
        }

    def decode_pending_items(self, context, width, height, meta=None):
        """按行序解码待确认轮廓，并贴回逐条置信度。"""
        return attach_conf(decode_segment_file(context["auto_label_path"], width, height), meta if meta is not None else load_auto_meta(context))

    def save_manual_annotation(self, context, annotation):
        """把人工轮廓写入标签文件。这张图的候选由保存它的用例一并判掉。"""
        width, height = get_image_size(context["image_path"])
        labels = (annotation or {}).get("polygons") or []
        write_yolo_lines(context["manual_label_path"], encode_segment_lines(labels, width, height))
        return {"label_path": storage_path_ref(context["manual_label_path"])}

    def encode_label_lines(self, context, annotation):
        """把分割轮廓编码成 YOLO 行。"""
        width, height = get_image_size(context["image_path"])
        return encode_segment_lines((annotation or {}).get("polygons") or [], width, height)

    def save_auto_annotation(self, context, annotation, source=None):
        write_auto_annotation(
            context,
            self.encode_label_lines(context, annotation),
            describe_auto_items(annotation),
            source,
        )
        return {"label_path": storage_path_ref(context["auto_label_path"])}

    def list_missing_annotations(self, dataset_root, split, offset=0, limit=50):
        img_dir = get_dataset_images_dir(dataset_root, split)
        lbl_dir = get_dataset_labels_dir(dataset_root, split)
        missing = []
        for root, _, files in os.walk(img_dir):
            for file_name in files:
                if not file_name.lower().endswith(IMAGE_FILE_EXTENSIONS):
                    continue
                image_path = os.path.join(root, file_name)
                rel = os.path.relpath(image_path, img_dir)
                label_path = os.path.join(lbl_dir, build_label_relpath(rel))
                if not os.path.exists(label_path) or os.path.getsize(label_path) == 0:
                    missing.append(image_path)
        return slice_items(build_file_items(missing), offset=offset, limit=limit)

    def list_pending_auto_annotations(self, dataset_root, split, offset=0, limit=50):
        img_dir = get_dataset_images_dir(dataset_root, split)
        auto_dir = get_dataset_auto_labels_dir(dataset_root, split)
        items = []
        for root, _, files in os.walk(img_dir):
            for file_name in files:
                if not file_name.lower().endswith(IMAGE_FILE_EXTENSIONS):
                    continue
                image_path = os.path.join(root, file_name)
                rel = os.path.relpath(image_path, img_dir)
                auto_label_path = os.path.join(auto_dir, build_label_relpath(rel))
                if os.path.exists(auto_label_path):
                    items.append(image_path)
        return slice_items(build_file_items(items), offset=offset, limit=limit)

    def get_auto_annotation_image_dir(self, dataset_root, split):
        return get_dataset_images_dir(dataset_root, split)

    def extract_auto_annotation(self, prediction):
        polygons = []
        try:
            segments = list(getattr(getattr(prediction, "masks", None), "xy", []) or [])
            boxes = list(getattr(prediction, "boxes", []) or [])
            for index, segment in enumerate(segments):
                if segment is None:
                    continue
                class_id = 0
                conf = None
                if index < len(boxes) and getattr(boxes[index], "cls", None) is not None:
                    class_id = int(boxes[index].cls.item())
                if index < len(boxes) and getattr(boxes[index], "conf", None) is not None:
                    conf = _scalar_to_float(boxes[index].conf)
                points = []
                for point in segment.tolist():
                    if len(point) < 2:
                        continue
                    points.append({"x": float(point[0]), "y": float(point[1])})
                if len(points) >= 3:
                    polygons.append({"class": class_id, "points": points, "conf": conf})
        except Exception:
            return {"polygons": []}
        return {"polygons": polygons}

    def refine_auto_annotation(self, context, annotation, iou_thresh):
        width, height = get_image_size(context["image_path"])
        cleaned = []
        for polygon in (annotation or {}).get("polygons") or []:
            points = []
            last = None
            for point in (polygon.get("points") or []):
                x = max(0.0, min(float(width), float(point.get("x", 0.0))))
                y = max(0.0, min(float(height), float(point.get("y", 0.0))))
                pair = (round(x, 3), round(y, 3))
                if last == pair:
                    continue
                last = pair
                points.append({"x": x, "y": y})
            if len(points) >= 3 and points[0] == points[-1]:
                points = points[:-1]
            candidate = {
                "class": int(polygon.get("class", 0)),
                "points": points,
                # 置信度要一路跟到元信息：清洗会重建多边形，不带上就丢了审核依据
                "conf": polygon.get("conf"),
            }
            if len(points) < 3:
                continue
            if polygon_area(candidate) < 9.0:
                continue
            cleaned.append(candidate)
        existing_manual = decode_segment_file(context["manual_label_path"], width, height)
        existing_auto = decode_segment_file(context["auto_label_path"], width, height)
        return {
            "polygons": filter_duplicate_polygons(
                cleaned,
                existing_manual,
                existing_auto,
                float(iou_thresh),
            )
        }

    def has_auto_annotation_content(self, annotation):
        return bool((annotation or {}).get("polygons"))

    def count_auto_annotation_items(self, annotation):
        return len((annotation or {}).get("polygons") or [])


class PoseAnnotationTaskStrategy(BaseAnnotationTaskStrategy):
    """姿态估计标注策略。"""

    vision_task_type = VISION_TASK_TYPE_POSE
    supports_auto_annotation = True

    def get_annotation_payload(self, context):
        width, height = get_image_size(context["image_path"])
        pose_meta = load_pose_annotation_meta(context["dataset_root"], context.get("class_names"))
        auto_meta = load_auto_meta(context)
        return {
            "vision_task_type": self.vision_task_type,
            "manual_annotation": {
                "instances": decode_pose_file(
                    context["manual_label_path"],
                    width,
                    height,
                    kpt_shape=pose_meta.get("kpt_shape"),
                )
            },
            "auto_annotation": {"instances": self.decode_pending_items(context, width, height, auto_meta), "source": auto_meta["source"]},
            "pose_meta": pose_meta,
            "width": width,
            "height": height,
        }

    def decode_pending_items(self, context, width, height, meta=None):
        """按行序解码待确认姿态实例，并贴回逐条置信度。"""
        pose_meta = load_pose_annotation_meta(context["dataset_root"], context.get("class_names"))
        return attach_conf(
            decode_pose_file(context["auto_label_path"], width, height, kpt_shape=pose_meta.get("kpt_shape")),
            meta if meta is not None else load_auto_meta(context),
        )

    def save_manual_annotation(self, context, annotation):
        """把人工姿态实例写入标签文件。这张图的候选由保存它的用例一并判掉。"""
        write_yolo_lines(context["manual_label_path"], self.encode_label_lines(context, annotation))
        return {"label_path": storage_path_ref(context["manual_label_path"])}

    def encode_label_lines(self, context, annotation):
        """把姿态实例编码成带关键点的 YOLO 行。"""
        width, height = get_image_size(context["image_path"])
        pose_meta = load_pose_annotation_meta(context["dataset_root"], context.get("class_names"))
        return encode_pose_lines(
            (annotation or {}).get("instances") or [],
            width,
            height,
            kpt_shape=pose_meta.get("kpt_shape"),
        )

    def save_auto_annotation(self, context, annotation, source=None):
        write_auto_annotation(
            context,
            self.encode_label_lines(context, annotation),
            describe_auto_items(annotation),
            source,
        )
        return {"label_path": storage_path_ref(context["auto_label_path"])}

    def list_missing_annotations(self, dataset_root, split, offset=0, limit=50):
        img_dir = get_dataset_images_dir(dataset_root, split)
        lbl_dir = get_dataset_labels_dir(dataset_root, split)
        missing = []
        for root, _, files in os.walk(img_dir):
            for file_name in files:
                if not file_name.lower().endswith(IMAGE_FILE_EXTENSIONS):
                    continue
                image_path = os.path.join(root, file_name)
                rel = os.path.relpath(image_path, img_dir)
                label_path = os.path.join(lbl_dir, build_label_relpath(rel))
                if not os.path.exists(label_path) or os.path.getsize(label_path) == 0:
                    missing.append(image_path)
        return slice_items(build_file_items(missing), offset=offset, limit=limit)

    def list_pending_auto_annotations(self, dataset_root, split, offset=0, limit=50):
        img_dir = get_dataset_images_dir(dataset_root, split)
        auto_dir = get_dataset_auto_labels_dir(dataset_root, split)
        items = []
        for root, _, files in os.walk(img_dir):
            for file_name in files:
                if not file_name.lower().endswith(IMAGE_FILE_EXTENSIONS):
                    continue
                image_path = os.path.join(root, file_name)
                rel = os.path.relpath(image_path, img_dir)
                auto_label_path = os.path.join(auto_dir, build_label_relpath(rel))
                if os.path.exists(auto_label_path):
                    items.append(image_path)
        return slice_items(build_file_items(items), offset=offset, limit=limit)

    def get_auto_annotation_image_dir(self, dataset_root, split):
        return get_dataset_images_dir(dataset_root, split)

    def extract_auto_annotation(self, prediction):
        try:
            boxes = list(getattr(prediction, "boxes", []) or [])
            keypoint_rows = _normalize_pose_keypoint_rows(getattr(prediction, "keypoints", None))
            total = max(len(boxes), len(keypoint_rows))
            instances = []
            for index in range(total):
                box = boxes[index] if index < len(boxes) else None
                keypoint_row = keypoint_rows[index] if index < len(keypoint_rows) else []
                if box is None:
                    continue
                instance = _build_pose_instance_from_prediction(box, keypoint_row)
                if instance:
                    instances.append(instance)
            return {"instances": instances}
        except Exception:
            return {"instances": []}

    def refine_auto_annotation(self, context, annotation, iou_thresh):
        width, height = get_image_size(context["image_path"])
        pose_meta = load_pose_annotation_meta(context["dataset_root"], context.get("class_names"))
        keypoint_count = pose_meta.get("keypoint_count") or 0
        cleaned = []
        for instance in (annotation or {}).get("instances") or []:
            sanitized = _sanitize_pose_instance(instance, width, height, keypoint_count)
            if sanitized:
                cleaned.append(sanitized)
        existing_manual = decode_pose_file(
            context["manual_label_path"],
            width,
            height,
            kpt_shape=pose_meta.get("kpt_shape"),
        )
        existing_auto = decode_pose_file(
            context["auto_label_path"],
            width,
            height,
            kpt_shape=pose_meta.get("kpt_shape"),
        )
        return {
            "instances": filter_duplicate_boxes(
                cleaned,
                existing_manual,
                existing_auto,
                iou_thresh,
            )
        }

    def has_auto_annotation_content(self, annotation):
        return bool((annotation or {}).get("instances"))

    def count_auto_annotation_items(self, annotation):
        return len((annotation or {}).get("instances") or [])


_ANNOTATION_TASK_STRATEGIES = {
    VISION_TASK_TYPE_CLASSIFY: ClassifyAnnotationTaskStrategy(),
    VISION_TASK_TYPE_DETECT: DetectAnnotationTaskStrategy(),
    VISION_TASK_TYPE_SEGMENT: SegmentAnnotationTaskStrategy(),
    VISION_TASK_TYPE_POSE: PoseAnnotationTaskStrategy(),
}


def resolve_annotation_task_strategy(vision_task_type):
    """按任务类型解析标注协议策略。"""
    strategy = _ANNOTATION_TASK_STRATEGIES.get(vision_task_type)
    if not strategy:
        raise ValueError("当前任务类型暂不支持标注")
    return strategy
