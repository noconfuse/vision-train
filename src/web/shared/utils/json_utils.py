"""提供 JSON 文件的统一读写入口。"""

import json
import os
import tempfile


def load_json_file(file_path, default=None):
    """读取 JSON 文件，失败时返回默认值。"""
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default


def save_json_file(file_path, data, *, indent=2, ensure_ascii=False):
    """按统一编码参数写入 JSON 文件。"""
    parent_dir = os.path.dirname(file_path) or "."
    os.makedirs(parent_dir, exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".vt_json_", suffix=".tmp", dir=parent_dir)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=indent, ensure_ascii=ensure_ascii)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, file_path)
    except Exception:
        try:
            os.remove(temp_path)
        except FileNotFoundError:
            pass
        raise
    return file_path


def encode_json(data, *, ensure_ascii=False, indent=None):
    """按统一编码策略把对象序列化为 JSON 文本。"""
    return json.dumps(data, ensure_ascii=ensure_ascii, indent=indent)
