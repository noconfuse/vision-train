"""按数据集任务类型封装标注协议与标注列表策略。"""

import os

from contexts.annotation.infrastructure.annotation_io import (
    decode_classification_file,
    decode_detect_file,
    encode_classification_lines,
    encode_detect_lines,
    get_image_size,
    resolve_classification_class_id,
)
from constants.media import IMAGE_FILE_EXTENSIONS
from contexts.dataset.infrastructure.dataset_layout import (
    build_label_relpath,
    get_dataset_auto_labels_dir,
    get_dataset_images_dir,
    get_dataset_labels_dir,
    get_dataset_unlabeled_dir,
)
from protocols.vision_task_type import VISION_TASK_TYPE_CLASSIFY, VISION_TASK_TYPE_DETECT
from shared.utils.fs_utils import remove_dir_if_empty, remove_file_silent
from shared.utils.path_utils import build_file_items, file_api_url, storage_path_ref, slice_items
from shared.utils.yolo_utils import read_yolo_lines, write_yolo_lines
from contexts.annotation.infrastructure.batch_helpers import (
    extract_prediction_boxes,
    load_existing_manual_boxes,
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

    def commit_auto_annotation(self, *_args, **_kwargs):
        """把自动标注结果合并到人工标注真源。"""
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

    def refine_auto_annotation(self, _context, annotation, _iou_thresh):
        """在写入待确认结果前，对自动标注载荷执行任务类型特有的清洗。"""
        return annotation

    def has_auto_annotation_content(self, _annotation):
        """判断自动标注载荷是否包含可写入内容。"""
        raise NotImplementedError

    def count_auto_annotation_items(self, _annotation):
        """返回一次自动标注实际新增的结果数量。"""
        raise NotImplementedError


def _remove_empty_dirs_up_to(path, stop_dir):
    """自下而上清理空目录，直到到达给定根目录。"""
    current_dir = os.path.dirname(path)
    stop_dir = os.path.realpath(stop_dir)
    while current_dir and os.path.realpath(current_dir).startswith(stop_dir) and os.path.realpath(current_dir) != stop_dir:
        remove_dir_if_empty(current_dir)
        parent_dir = os.path.dirname(current_dir)
        if parent_dir == current_dir:
            break
        current_dir = parent_dir


class ClassifyAnnotationTaskStrategy(BaseAnnotationTaskStrategy):
    """图像分类标注策略。"""

    vision_task_type = VISION_TASK_TYPE_CLASSIFY
    supports_auto_annotation = True

    def get_annotation_payload(self, context):
        """根据类别目录归属生成分类标注载荷。"""
        width, height = get_image_size(context["image_path"])
        return {
            "vision_task_type": self.vision_task_type,
            "manual_annotation": {"class_id": resolve_classification_class_id(context)},
            "auto_annotation": {"class_id": decode_classification_file(context["auto_label_path"])},
            "width": width,
            "height": height,
        }

    def save_manual_annotation(self, context, annotation):
        """通过移动图片到目标类别目录保存分类人工标注。"""
        lines = encode_classification_lines(annotation or {})
        target_image_path = context["image_path"]
        if not lines:
            if context.get("is_unlabeled"):
                remove_file_silent(context["auto_label_path"])
                _remove_empty_dirs_up_to(context["auto_label_path"], context["auto_dir"])
                return {
                    "image_path": storage_path_ref(target_image_path),
                    "image_url": file_api_url(target_image_path),
                    "label_path": storage_path_ref(target_image_path),
                }
            target_image_path = os.path.join(context["unlabeled_dir"], context["sample_relative_path"])
            os.makedirs(os.path.dirname(target_image_path), exist_ok=True)
            os.replace(context["image_path"], target_image_path)
            _remove_empty_dirs_up_to(context["image_path"], context["split_dir"])
            remove_file_silent(context["auto_label_path"])
            _remove_empty_dirs_up_to(context["auto_label_path"], context["auto_dir"])
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
            _remove_empty_dirs_up_to(context["image_path"], context["unlabeled_dir"] if context.get("is_unlabeled") else context["split_dir"])
        remove_file_silent(context["auto_label_path"])
        _remove_empty_dirs_up_to(context["auto_label_path"], context["auto_dir"])
        return {
            "image_path": storage_path_ref(target_image_path),
            "image_url": file_api_url(target_image_path),
            "label_path": storage_path_ref(target_image_path),
        }

    def save_auto_annotation(self, context, annotation):
        """把分类自动标注候选类别写入待确认目录。"""
        lines = encode_classification_lines(annotation or {})
        if not lines:
            raise ValueError("自动标注结果为空")
        write_yolo_lines(context["auto_label_path"], lines)
        return {"label_path": storage_path_ref(context["auto_label_path"])}

    def commit_auto_annotation(self, context):
        """把分类自动标注候选类别提升为最终人工标注。"""
        auto_class_id = decode_classification_file(context["auto_label_path"])
        if auto_class_id is None:
            raise ValueError("当前图片不存在待确认自动标注")
        return self.save_manual_annotation(context, {"class_id": auto_class_id})

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

    def extract_auto_annotation(self, prediction, use_openvino):
        """把分类模型输出解析为单个候选 class_id。"""
        if use_openvino:
            raise ValueError("当前暂未接入分类 OpenVINO 自动标注")
        probs = getattr(prediction, "probs", None)
        top1 = getattr(probs, "top1", None) if probs is not None else None
        return {"class_id": int(top1)} if top1 is not None else {}

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
        return {
            "vision_task_type": self.vision_task_type,
            "manual_annotation": {"boxes": decode_detect_file(context["manual_label_path"], width, height)},
            "auto_annotation": {"boxes": decode_detect_file(context["auto_label_path"], width, height)},
            "width": width,
            "height": height,
        }

    def save_manual_annotation(self, context, annotation):
        """把检测框写入人工标签文件，并清除待确认自动标签。"""
        width, height = get_image_size(context["image_path"])
        labels = (annotation or {}).get("boxes") or []
        write_yolo_lines(context["manual_label_path"], encode_detect_lines(labels, width, height))
        remove_file_silent(context["auto_label_path"])
        return {"label_path": storage_path_ref(context["manual_label_path"])}

    def save_auto_annotation(self, context, annotation):
        """把检测自动标注结果写入 auto_labels 目录。"""
        width, height = get_image_size(context["image_path"])
        labels = (annotation or {}).get("boxes") or []
        write_yolo_lines(context["auto_label_path"], encode_detect_lines(labels, width, height))
        return {"label_path": storage_path_ref(context["auto_label_path"])}

    def commit_auto_annotation(self, context):
        """把检测自动标注框并入人工标签文件。"""
        merged = read_yolo_lines(context["manual_label_path"]) + read_yolo_lines(context["auto_label_path"])
        write_yolo_lines(context["manual_label_path"], merged)
        remove_file_silent(context["auto_label_path"])
        return {"label_path": storage_path_ref(context["manual_label_path"])}

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

    def extract_auto_annotation(self, prediction, use_openvino):
        """把不同推理后端统一成检测框载荷。"""
        return {"boxes": extract_prediction_boxes(prediction, use_openvino=use_openvino)}

    def refine_auto_annotation(self, context, annotation, iou_thresh):
        """检测自动标注需去重已有人工框与待确认框。"""
        boxes = (annotation or {}).get("boxes") or []
        if not boxes:
            return {"boxes": []}
        width, height = get_image_size(context["image_path"])
        rel_noext = context["relative_noext"]
        existing_manual = load_existing_manual_boxes(context["dataset_root"], context.get("split"), rel_noext, width, height)
        existing_auto = decode_detect_file(context["auto_label_path"], width, height)
        from contexts.annotation.domain.services import filter_duplicate_boxes

        return {"boxes": filter_duplicate_boxes(boxes, existing_manual, existing_auto, float(iou_thresh))}

    def has_auto_annotation_content(self, annotation):
        """检测候选结果以框列表非空为准。"""
        return bool((annotation or {}).get("boxes"))

    def count_auto_annotation_items(self, annotation):
        """返回检测自动标注新增框数。"""
        return len((annotation or {}).get("boxes") or [])


_ANNOTATION_TASK_STRATEGIES = {
    VISION_TASK_TYPE_CLASSIFY: ClassifyAnnotationTaskStrategy(),
    VISION_TASK_TYPE_DETECT: DetectAnnotationTaskStrategy(),
}


def resolve_annotation_task_strategy(vision_task_type):
    """按任务类型解析标注协议策略。"""
    strategy = _ANNOTATION_TASK_STRATEGIES.get(vision_task_type)
    if not strategy:
        raise ValueError("当前任务类型暂不支持标注")
    return strategy
