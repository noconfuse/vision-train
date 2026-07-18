"""编排标注读写、自动标注和批处理的应用层用例。"""

from contexts.annotation.infrastructure.annotation_io import (
    decode_yolo_file,
    encode_yolo_lines,
    get_image_size,
    resolve_dataset_image_context,
)
from shared.utils.fs_utils import remove_file_silent
from shared.utils.path_utils import storage_path_ref
from shared.utils.yolo_utils import read_yolo_lines, write_yolo_lines


def get_annotation_payload(project_path, dataset_name, split, image_ref):
    """组合单张图片的尺寸、人工框和自动框。"""
    context = resolve_dataset_image_context(project_path, dataset_name, split, image_ref)
    width, height = get_image_size(context["image_path"])
    return {
        "boxes": decode_yolo_file(context["manual_label_path"], width, height),
        "auto_boxes": decode_yolo_file(context["auto_label_path"], width, height),
        "width": width,
        "height": height,
    }


def save_manual_annotation(project_path, dataset_name, split, image_ref, labels):
    """保存人工标注并清除对应自动标注。"""
    context = resolve_dataset_image_context(project_path, dataset_name, split, image_ref)
    width, height = get_image_size(context["image_path"])
    write_yolo_lines(context["manual_label_path"], encode_yolo_lines(labels, width, height))
    remove_file_silent(context["auto_label_path"])
    return {"label_path": storage_path_ref(context["manual_label_path"])}


def save_auto_annotation(project_path, dataset_name, split, image_ref, labels):
    """保存自动标注结果到待确认目录。"""
    context = resolve_dataset_image_context(project_path, dataset_name, split, image_ref)
    width, height = get_image_size(context["image_path"])
    write_yolo_lines(context["auto_label_path"], encode_yolo_lines(labels, width, height))
    return {"label_path": storage_path_ref(context["auto_label_path"])}


def commit_auto_annotation(project_path, dataset_name, split, image_ref):
    """把自动标注框并入人工标注文件。"""
    context = resolve_dataset_image_context(project_path, dataset_name, split, image_ref)
    merged = read_yolo_lines(context["manual_label_path"]) + read_yolo_lines(context["auto_label_path"])
    write_yolo_lines(context["manual_label_path"], merged)
    remove_file_silent(context["auto_label_path"])
    return {"label_path": storage_path_ref(context["manual_label_path"])}
