"""提供当前时间与 ISO 字符串转换助手。"""

from datetime import datetime


def now_dt():
    """返回当前本地时间对象。"""
    return datetime.now()


def to_iso(dt):
    """把时间对象转换为 ISO 字符串。"""
    return dt.isoformat()


def now_iso():
    """返回当前时间的 ISO 字符串。"""
    return to_iso(now_dt())
