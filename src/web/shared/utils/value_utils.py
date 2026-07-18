"""提供布尔值与文本字段的基础归一化函数。"""


def is_missing_value(value):
    """判断值是否应视为“缺失”。"""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def require_present(message=None, **fields):
    """校验一组必填字段，缺失时抛出统一错误。"""
    missing = [name for name, value in fields.items() if is_missing_value(value)]
    if not missing:
        return fields
    if message:
        raise ValueError(str(message))
    raise ValueError(f'缺少 {" 或 ".join(missing)}')

def parse_bool(value, default=False):
    """把常见布尔表达归一化为布尔值。"""
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes", "y", "on")


def first_non_empty_text(value):
    """返回首个非空文本值并去除首尾空白。"""
    if isinstance(value, (list, tuple)):
        for item in value:
            text = str(item or "").strip()
            if text:
                return text
        return ""
    return str(value or "").strip()
