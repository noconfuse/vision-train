"""模型上下文的跨域用例门面。"""

from contexts.model.infrastructure.model_catalog import (
    load_openvino_metadata,
    resolve_model_vision_task_type,
)
from contexts.model.infrastructure.model_gateway import get_pretrained_status

__all__ = [
    "get_pretrained_status",
    "load_openvino_metadata",
    "resolve_model_vision_task_type",
]
