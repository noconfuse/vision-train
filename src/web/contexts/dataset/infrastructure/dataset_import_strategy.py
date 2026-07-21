"""按任务类型封装数据集导入流程策略。"""

from contexts.dataset.infrastructure.dataset_format_detector import detect_dataset_format
from contexts.dataset.infrastructure.dataset_import_formats import (
    convert_classification_imagefolder_to_yolo,
    convert_coco_to_yolo,
    convert_roboflow_to_yolo,
    convert_voc_to_yolo,
    format_import_progress_message,
)
from contexts.dataset.infrastructure.dataset_import_runtime import build_progress_callback, emit_import_event
from contexts.dataset.infrastructure.dataset_import_yolo import ensure_dataset_yaml, is_standard_yolo_dataset, normalize_yolo_layout
from protocols.vision_task_type import VISION_TASK_TYPE_CLASSIFY, VISION_TASK_TYPE_DETECT


class BaseDatasetImportStrategy:
    """定义任务类型导入策略基类。"""

    vision_task_type = ""
    format_labels = {}
    format_converters = {}

    def detect_source_format(self, dataset_root):
        """识别当前任务类型支持的输入数据集格式。"""
        return detect_dataset_format(dataset_root, vision_task_type=self.vision_task_type)

    def _build_progress_callback(self, job, progress_lock, fmt):
        """构造当前导入策略使用的统一进度回调。"""
        return build_progress_callback(job, progress_lock, "converting", 30, 95, fmt, format_import_progress_message)

    def _import_yolo_dataset(self, dataset_root, dest, job_id):
        """导入原生 YOLO 数据集并归一化为项目内部标准目录。"""
        from shared.utils.fs_utils import move_path

        move_path(dataset_root, dest)
        if not is_standard_yolo_dataset(dest):
            emit_import_event(job_id, phase="converting", progress=60, message="规范化 YOLO 目录布局...")
            normalize_yolo_layout(dest)
            emit_import_event(job_id, phase="converting", progress=75, message="写入标准 dataset.yaml...")
            ensure_dataset_yaml(dest, force=True)
            if not is_standard_yolo_dataset(dest):
                raise ValueError("YOLO 数据集未能归一化为项目标准目录协议")

    def import_detected_format(self, source_format, dataset_root, dest, job, progress_lock):
        """按已识别格式执行导入转换，并屏蔽具体格式实现差异。"""
        if source_format == "yolo":
            self._import_yolo_dataset(dataset_root, dest, job["id"])
            return
        converter = self.format_converters.get(source_format)
        if not converter:
            raise ValueError(f"当前任务类型不支持导入格式: {source_format}")
        converter(
            dataset_root,
            dest,
            progress_cb=self._build_progress_callback(job, progress_lock, self.format_labels[source_format]),
        )


class DetectDatasetImportStrategy(BaseDatasetImportStrategy):
    """目标检测任务的导入策略。"""

    vision_task_type = VISION_TASK_TYPE_DETECT
    format_labels = {
        "roboflow": "ROBOFLOW",
        "coco": "COCO",
        "voc": "VOC",
    }
    format_converters = {
        "roboflow": convert_roboflow_to_yolo,
        "coco": convert_coco_to_yolo,
        "voc": convert_voc_to_yolo,
    }


class ClassifyDatasetImportStrategy(BaseDatasetImportStrategy):
    """图像分类任务的导入策略。"""

    vision_task_type = VISION_TASK_TYPE_CLASSIFY
    format_labels = {
        "classification_imagefolder": "CLASSIFY",
    }
    format_converters = {
        "classification_imagefolder": convert_classification_imagefolder_to_yolo,
    }


_DATASET_IMPORT_STRATEGIES = {
    VISION_TASK_TYPE_DETECT: DetectDatasetImportStrategy(),
    VISION_TASK_TYPE_CLASSIFY: ClassifyDatasetImportStrategy(),
}


def resolve_dataset_import_strategy(vision_task_type):
    """按任务类型解析导入策略。"""
    strategy = _DATASET_IMPORT_STRATEGIES.get(vision_task_type)
    if not strategy:
        raise ValueError(f"当前任务类型暂未接入导入策略: {vision_task_type}")
    return strategy
