"""按任务类型封装数据集导入流程策略。"""

from contexts.dataset.infrastructure.dataset_format_detector import detect_dataset_format
from contexts.dataset.infrastructure.dataset_import_formats import (
    convert_classification_imagefolder_to_yolo,
    convert_coco_to_yolo,
    convert_coco_to_yolo_segment,
    convert_roboflow_to_yolo,
    convert_voc_to_yolo,
    format_import_progress_message,
)
from contexts.dataset.infrastructure.dataset_import_runtime import build_progress_callback, emit_import_event
from contexts.dataset.infrastructure.dataset_import_yolo import (
    build_pose_dataset_yaml_fields,
    ensure_dataset_yaml,
    looks_like_external_yolo_source,
    is_standard_yolo_dataset,
    looks_like_standard_yolo_dataset,
    normalize_external_yolo_source_layout,
    normalize_yolo_layout,
)
from protocols.vision_task_type import (
    VISION_TASK_TYPE_CLASSIFY,
    VISION_TASK_TYPE_DETECT,
    VISION_TASK_TYPE_POSE,
    VISION_TASK_TYPE_SEGMENT,
)


class BaseDatasetImportStrategy:
    """定义任务类型导入策略基类。"""

    vision_task_type = ""
    format_labels = {}
    format_converters = {}
    supports_native_yolo_source = False

    def detect_source_format(self, dataset_root):
        """识别当前任务类型支持的输入数据集格式。"""
        source_format = detect_dataset_format(dataset_root, vision_task_type=self.vision_task_type)
        if source_format != "unknown":
            return source_format
        if self.looks_like_yolo_source(dataset_root):
            return "yolo"
        return "unknown"

    def looks_like_yolo_source(self, _dataset_root):
        """判断当前任务类型下是否可把目录视为原生 YOLO 源格式。"""
        if not self.supports_native_yolo_source:
            return False
        return looks_like_standard_yolo_dataset(_dataset_root) or looks_like_external_yolo_source(_dataset_root)

    def build_dataset_yaml_extra_fields(self, _config, _dataset_root, _split_pairs, _normalized_names):
        """为标准 dataset.yaml 提供任务专属附加字段。"""
        return {}

    def _build_progress_callback(self, job, progress_lock, fmt):
        """构造当前导入策略使用的统一进度回调。"""
        return build_progress_callback(job, progress_lock, "converting", 30, 95, fmt, format_import_progress_message)

    def _import_yolo_dataset(self, dataset_root, dest, job):
        """导入原生 YOLO 数据集并归一化为项目内部标准目录。"""
        from shared.utils.fs_utils import move_path
        job_id = job["id"]

        move_path(dataset_root, dest)
        if is_standard_yolo_dataset(dest):
            return
        if looks_like_standard_yolo_dataset(dest):
            emit_import_event(job_id, phase="converting", progress=75, message="补齐标准 dataset.yaml...")
            ensure_dataset_yaml(
                dest,
                force=True,
                extra_yaml_builder=lambda config, dataset_root, split_pairs, normalized_names: self.build_dataset_yaml_extra_fields(
                    config,
                    dataset_root,
                    split_pairs,
                    normalized_names,
                ),
            )
            if not is_standard_yolo_dataset(dest):
                raise ValueError("YOLO 数据集未能补齐为项目标准目录协议")
            return
        if looks_like_external_yolo_source(dest):
            emit_import_event(job_id, phase="converting", progress=60, message="规范化 YOLO 目录布局...")
            normalize_external_yolo_source_layout(dest)
            emit_import_event(job_id, phase="converting", progress=75, message="写入标准 dataset.yaml...")
            ensure_dataset_yaml(
                dest,
                force=True,
                extra_yaml_builder=lambda config, dataset_root, split_pairs, normalized_names: self.build_dataset_yaml_extra_fields(
                    config,
                    dataset_root,
                    split_pairs,
                    normalized_names,
                ),
            )
            if not is_standard_yolo_dataset(dest):
                raise ValueError("YOLO 数据集未能归一化为项目标准目录协议")
            return
        emit_import_event(job_id, phase="converting", progress=60, message="规范化 YOLO 目录布局...")
        normalize_yolo_layout(dest)
        emit_import_event(job_id, phase="converting", progress=75, message="写入标准 dataset.yaml...")
        ensure_dataset_yaml(
            dest,
            force=True,
            extra_yaml_builder=lambda config, dataset_root, split_pairs, normalized_names: self.build_dataset_yaml_extra_fields(
                config,
                dataset_root,
                split_pairs,
                normalized_names,
            ),
        )
        if not is_standard_yolo_dataset(dest):
            raise ValueError("YOLO 数据集未能归一化为项目标准目录协议")

    def import_detected_format(self, source_format, dataset_root, dest, job, progress_lock):
        """按已识别格式执行导入转换，并屏蔽具体格式实现差异。"""
        if source_format == "yolo":
            self._import_yolo_dataset(dataset_root, dest, job)
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
    supports_native_yolo_source = True
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


class SegmentDatasetImportStrategy(BaseDatasetImportStrategy):
    """实例分割任务的导入策略。"""

    vision_task_type = VISION_TASK_TYPE_SEGMENT
    supports_native_yolo_source = True
    format_labels = {
        "roboflow": "ROBOFLOW",
        "coco": "COCO",
    }
    format_converters = {
        "roboflow": convert_roboflow_to_yolo,
        "coco": convert_coco_to_yolo_segment,
    }

class PoseDatasetImportStrategy(BaseDatasetImportStrategy):
    """姿态估计任务的导入策略。"""

    vision_task_type = VISION_TASK_TYPE_POSE
    supports_native_yolo_source = True
    format_labels = {}
    format_converters = {}

    def build_dataset_yaml_extra_fields(self, config, dataset_root, split_pairs, normalized_names):
        return build_pose_dataset_yaml_fields(config, dataset_root, split_pairs, normalized_names)


_DATASET_IMPORT_STRATEGIES = {
    VISION_TASK_TYPE_DETECT: DetectDatasetImportStrategy(),
    VISION_TASK_TYPE_CLASSIFY: ClassifyDatasetImportStrategy(),
    VISION_TASK_TYPE_SEGMENT: SegmentDatasetImportStrategy(),
    VISION_TASK_TYPE_POSE: PoseDatasetImportStrategy(),
}


def resolve_dataset_import_strategy(vision_task_type):
    """按任务类型解析导入策略。"""
    strategy = _DATASET_IMPORT_STRATEGIES.get(vision_task_type)
    if not strategy:
        raise ValueError(f"当前任务类型暂未接入导入策略: {vision_task_type}")
    return strategy
