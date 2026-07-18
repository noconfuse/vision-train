"""提供项目/数据集等简单名称的共享校验能力。"""

import re

TOKEN_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def validate_token_name(name, *, empty_message, invalid_message, reserved_names=None):
    """校验只允许字母数字下划线短横线的简单名称。"""
    text = str(name or "")
    if not text:
        return empty_message
    if len(text) > 64:
        return invalid_message
    if not TOKEN_NAME_PATTERN.match(text):
        return invalid_message
    if reserved_names and text in set(reserved_names):
        return f'"{text}" 是保留名称，请换一个'
    return None
