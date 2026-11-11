"""训练上下文的跨域用例门面。"""

from contexts.training.infrastructure.training_artifacts import (
    get_training_best_weight_path,
    resolve_training_resume_weight,
)

__all__ = [
    "get_training_best_weight_path",
    "resolve_training_resume_weight",
]
