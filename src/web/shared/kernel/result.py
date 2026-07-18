"""定义跨层传递的通用结果对象。"""

from dataclasses import dataclass, field


@dataclass(slots=True)
class Result:
    ok: bool
    data: object = None
    error: str | None = None
    meta: dict = field(default_factory=dict)
