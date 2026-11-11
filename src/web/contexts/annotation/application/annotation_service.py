"""标注上下文的跨域用例门面。"""

from contexts.annotation.domain.services import (
    SAME_OBJECT_COVER_THRESH,
    SAME_OBJECT_IOU_THRESH,
    box_min_cover_ratio,
    is_same_object_box,
)
from contexts.annotation.infrastructure.annotation_io import decode_classification_file

__all__ = [
    "SAME_OBJECT_COVER_THRESH",
    "SAME_OBJECT_IOU_THRESH",
    "box_min_cover_ratio",
    "is_same_object_box",
    "decode_classification_file",
]
