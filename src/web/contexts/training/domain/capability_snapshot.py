"""构造训练链路统一能力快照。"""

from contexts.dataset.domain.capabilities import build_dataset_capabilities
from contexts.training.domain.export_profile import build_training_export_profile
from contexts.training.domain.result_profile import build_training_result_profile
from contexts.training.domain.training_profile import build_training_profile


def build_training_capabilities_snapshot(vision_task_type, dataset_metadata=None):
    """按任务类型构造前后端共享的训练能力快照。"""
    capabilities = build_dataset_capabilities(vision_task_type, dataset_metadata=dataset_metadata)
    return {
        **capabilities,
        "vision_task_type": vision_task_type,
        "training_profile": build_training_profile(capabilities["training_mode"]),
        "result_profile": build_training_result_profile(vision_task_type),
        "export_profile": build_training_export_profile(vision_task_type),
    }
