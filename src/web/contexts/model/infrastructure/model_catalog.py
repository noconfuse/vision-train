"""解析预训练模型目录并生成模型目录元数据。"""

import logging
import os
import sys

from app.config import PRETRAINED_MODELS_DIR
from shared.utils.fs_utils import directory_size, safe_size
from shared.utils.path_utils import storage_path_ref
from shared.utils.yaml_utils import load_yaml_file

logger = logging.getLogger(__name__)

_DETECT_SUFFIXES = ("-cls", "-seg", "-pose", "-obb", "-sem", "-grayscale", "-pf")
_MODEL_FILE_EXTENSIONS = (".pt", ".onnx", ".xml")
_SIZE_LABELS = {
    "n": "nano",
    "s": "small",
    "m": "medium",
    "l": "large",
    "x": "xlarge",
    "b": "wide",
    "c": "compact",
    "e": "xextended",
    "t": "tiny",
    "6": "640",
    "spp": "spp",
    "tiny": "tiny",
}

_catalog_cache = None

def pick_openvino_xml(path):
    """从文件或目录中选出最合适的 OpenVINO XML。"""
    if not path:
        return None
    if os.path.isfile(path) and path.lower().endswith(".xml"):
        return os.path.abspath(path)
    if os.path.isdir(path):
        best_xml = os.path.join(path, "best.xml")
        if os.path.exists(best_xml):
            return os.path.abspath(best_xml)
        xmls = []
        for root, _, files in os.walk(path):
            for file_name in files:
                if file_name.lower().endswith(".xml"):
                    xmls.append(os.path.abspath(os.path.join(root, file_name)))
        if not xmls:
            return None
        xmls.sort(key=lambda item: (0 if os.path.basename(item) == "best.xml" else 1, len(item), item))
        return xmls[0]
    return None


def load_openvino_metadata(xml_path):
    """读取 OpenVINO 模型目录旁的 metadata.yaml。"""
    metadata = os.path.join(os.path.dirname(str(xml_path or "")), "metadata.yaml")
    return load_yaml_file(metadata, default={})


def describe_model_path(path, default_name=None):
    """把一个模型文件或目录解析为统一的展示元数据。"""
    if not path or not os.path.exists(path):
        return None
    abs_path = os.path.abspath(path)
    if os.path.isfile(abs_path):
        if not abs_path.lower().endswith(_MODEL_FILE_EXTENSIONS):
            return None
        if abs_path.lower().endswith(".xml"):
            return {
                "name": format_openvino_name(abs_path),
                "path": storage_path_ref(abs_path),
                "size": directory_size(os.path.dirname(abs_path), exts={".xml", ".bin"}),
            }
        return {
            "name": default_name or os.path.basename(abs_path),
            "path": storage_path_ref(abs_path),
            "size": safe_size(abs_path),
        }
    ov_xml = pick_openvino_xml(abs_path)
    if not ov_xml:
        return None
    return {
        "name": format_openvino_name(ov_xml),
        "path": storage_path_ref(ov_xml),
        "size": directory_size(os.path.dirname(ov_xml), exts={".xml", ".bin"}),
    }


def format_openvino_name(xml_path):
    """根据 metadata 生成 OpenVINO 展示名。"""
    try:
        base_dir = os.path.dirname(xml_path)
        data = load_openvino_metadata(xml_path)
        args = data.get("args") or {}
        if isinstance(args, dict) and args.get("int8") is True:
            return f"{os.path.basename(base_dir)} (OpenVINO INT8)"
        return f"{os.path.basename(base_dir)} (OpenVINO)"
    except Exception:
        return f"{os.path.basename(os.path.dirname(xml_path))} (OpenVINO)"


def load_pretrained_model_config_items(project_root):
    """读取并归一化全局预训练模型配置项。"""
    config_path = os.path.join(PRETRAINED_MODELS_DIR, "config.yaml")
    cfg = load_yaml_file(config_path, default={})
    items = {}
    configured = cfg.get("pretrained_models") or {}
    if not isinstance(configured, dict):
        return items
    for key, item in configured.items():
        name = item.get("name") or key
        path = item.get("path")
        if path and not os.path.isabs(path):
            path = os.path.abspath(os.path.join(project_root, path))
        items[str(key)] = {
            "id": str(key),
            "name": name,
            "path": path,
            "description": item.get("description", "预训练模型"),
            "size": item.get("size"),
        }
    return items


def derive_family_and_size(name):
    """从模型名解析家族与尺寸标签。"""
    stem = name[:-3] if name.endswith(".pt") else name
    if stem.startswith("yolo_nas"):
        size_key = stem.split("_")[-1]
        return "yolo_nas", _SIZE_LABELS.get(size_key, size_key)
    if stem.startswith("yolov5") and stem.endswith("u"):
        core = stem[:-1]
        size = core[-2] + "6" if "6" in core else core[-1]
        return "yolov5u", _SIZE_LABELS.get(size, size)
    if stem.startswith("yolov3") and stem.endswith("u"):
        tail = stem[6:-1]
        return "yolov3u", _SIZE_LABELS.get(tail, tail or "default")
    family = None
    for prefix in ("yolo11", "yolo12", "yolo26", "yolov10", "yolov9", "yolov8"):
        if stem.startswith(prefix):
            family = prefix
            break
    if not family:
        return stem, ""
    suffix = stem[len(family) :]
    size = ""
    for char in suffix:
        if char.isalpha() and char in _SIZE_LABELS:
            size = char
        else:
            break
    return family, _SIZE_LABELS.get(size, size or "default")


def load_ultralytics_catalog():
    """加载并缓存 Ultralytics 预训练模型目录。"""
    global _catalog_cache
    if _catalog_cache is not None:
        return _catalog_cache
    try:
        from ultralytics.utils.downloads import GITHUB_ASSETS_STEMS
    except Exception as exc:
        logger.error("读取 ultralytics 预训练清单失败: %s", exc)
        _catalog_cache = []
        return _catalog_cache

    items = []
    for stem in sorted(GITHUB_ASSETS_STEMS):
        if not stem.startswith("yolo") and not stem.startswith("rtdetr"):
            continue
        if stem.startswith("yolo") and any(suffix in stem for suffix in _DETECT_SUFFIXES):
            continue
        name = stem + ".pt"
        family, size = derive_family_and_size(name)
        items.append({"name": name, "family": family, "size": size, "params": None})
    _catalog_cache = items
    return items


def local_path_for_name(name):
    """返回预训练模型在本地缓存目录中的路径。"""
    os.makedirs(PRETRAINED_MODELS_DIR, exist_ok=True)
    return os.path.join(PRETRAINED_MODELS_DIR, name)


def resolve_ultralytics_download_path(name):
    """查找 Ultralytics 默认下载落点。"""
    candidates = [
        os.path.join(os.getcwd(), name),
        os.path.expanduser(f"~/.config/Ultralytics/{name}"),
    ]
    if sys.platform == "win32":
        candidates.append(os.path.expanduser(f"~/AppData/Roaming/Ultralytics/{name}"))
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None
