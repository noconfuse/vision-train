"""提供 JSON 文件的统一读写入口。"""

import json


def load_json_file(file_path, default=None):
    """读取 JSON 文件，失败时返回默认值。"""
    try:
        with open(file_path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default


def save_json_file(file_path, data, *, indent=2, ensure_ascii=False):
    """按统一编码参数写入 JSON 文件。"""
    with open(file_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=indent, ensure_ascii=ensure_ascii)
    return file_path


def encode_json(data, *, ensure_ascii=False, indent=None):
    """按统一编码策略把对象序列化为 JSON 文本。"""
    return json.dumps(data, ensure_ascii=ensure_ascii, indent=indent)
