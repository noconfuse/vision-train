"""解析评估数据集配置并生成结果建议。"""

import hashlib
import os

from contexts.dataset.application.dataset_service import load_dataset_yaml_ref
from protocols.capabilities.result_profile import build_profile_evaluate_recommendations
from protocols.vision_task_type import VISION_TASK_TYPE_SET

EVALUABLE_SPLITS = ("test", "val")


def resolve_evaluate_split(data_yaml, split=None):
    """选定评估 split：显式指定优先，否则 test 优先、val 兜底。

    只能用 dataset.yaml 里真实声明过的 split——评估集是收敛曲线的尺子，
    悄悄退回到一个不存在的 split 会让指标失去意义。
    """
    config = load_dataset_yaml_ref(data_yaml, default={})
    declared = {name: str(config.get(name) or "").strip() for name in EVALUABLE_SPLITS}
    wanted = str(split or "").strip()
    if wanted:
        if wanted not in declared:
            raise ValueError(f"评估 split 只能是 {' 或 '.join(EVALUABLE_SPLITS)}，收到「{wanted}」")
        if not declared[wanted]:
            raise ValueError(f"dataset.yaml 没有声明 {wanted} split，无法用它评估")
        return wanted
    for name in EVALUABLE_SPLITS:
        if declared[name]:
            return name
    raise ValueError("dataset.yaml 既没有声明 test 也没有声明 val split，无法评估")


def build_split_label(split):
    """返回 split 的中文展示名，用于任务进度文案。"""
    return "测试集" if str(split) == "test" else "验证集"


def build_eval_fingerprint(image_paths):
    """给参与评估的图片清单做稳定指纹。

    曲线只有在同一把尺子上才可比：评估图集合一变，指纹随之变化，台账据此标出断点。
    取文件名而非绝对路径，项目整体搬家不算换尺子。
    """
    names = sorted({
        os.path.basename(str(path).replace("\\", "/"))
        for path in image_paths or []
        if str(path or "").strip()
    })
    if not names:
        return ""
    digest = hashlib.sha1("\n".join(names).encode("utf-8")).hexdigest()
    return f"{len(names)}-{digest[:16]}"


def build_evaluate_recommendations(results, vision_task_type):
    """Generate lightweight product-facing suggestions from evaluation metrics."""
    if vision_task_type not in VISION_TASK_TYPE_SET:
        raise ValueError("评估结果缺少合法的 vision_task_type")
    return build_profile_evaluate_recommendations(results, vision_task_type)
