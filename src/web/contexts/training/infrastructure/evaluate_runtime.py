"""解析评估数据集配置并生成结果建议。"""

from contexts.dataset.infrastructure.dataset_schema import load_dataset_yaml_ref
from contexts.training.domain.result_profile import build_profile_evaluate_recommendations
from protocols.vision_task_type import VISION_TASK_TYPE_SET


def resolve_evaluate_split(data_yaml):
    """Pick the evaluation split, preferring `test` when the dataset declares it."""
    config = load_dataset_yaml_ref(data_yaml, default={})
    test_split = str(config.get('test') or '').strip()
    if test_split:
        return 'test'
    return 'val'


def build_evaluate_recommendations(results, vision_task_type):
    """Generate lightweight product-facing suggestions from evaluation metrics."""
    if vision_task_type not in VISION_TASK_TYPE_SET:
        raise ValueError("评估结果缺少合法的 vision_task_type")
    return build_profile_evaluate_recommendations(results, vision_task_type)
