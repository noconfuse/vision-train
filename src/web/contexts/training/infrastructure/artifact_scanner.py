"""扫描训练与导出目录中的实际产物文件。"""

import os

from contexts.training.infrastructure.runtime_profile import get_device


EXPORT_FORMAT_OPTION_SUPPORT = {
    "onnx": {"half": True, "int8": False},
    "openvino": {"half": True, "int8": True},
    "engine": {"half": True, "int8": True},
}


def validate_export_request(export_format, export_half=False, export_int8=False):
    """校验导出格式、量化选项与硬件支持是否匹配。"""
    option_support = EXPORT_FORMAT_OPTION_SUPPORT.get(export_format, {"half": True, "int8": False})
    if export_half and not option_support.get("half", False):
        raise ValueError(f"导出格式 {export_format} 不支持 FP16。")
    if export_int8 and not option_support.get("int8", False):
        raise ValueError(f"导出格式 {export_format} 不支持 INT8。")
    if export_format == "engine" and not str(get_device()).isdigit():
        raise ValueError("当前主机环境不支持 TensorRT 导出，需要 NVIDIA 支持。")


def scan_export_outputs(output_path):
    """扫描导出结果目录并返回文件清单。"""
    files = []
    if not output_path:
        return files
    if os.path.isfile(output_path):
        files.append({"name": os.path.basename(output_path), "path": output_path, "size_bytes": os.path.getsize(output_path)})
        return files
    if not os.path.isdir(output_path):
        return files
    for root, dirs, filenames in os.walk(output_path):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git")]
        for filename in filenames:
            file_path = os.path.join(root, filename)
            if os.path.isfile(file_path):
                files.append({"name": filename, "path": file_path, "size_bytes": os.path.getsize(file_path)})
    files.sort(key=lambda item: item["path"])
    return files


def scan_training_run_artifacts(out_dir):
    """扫描训练输出目录中的图片、权重和配置文件。"""
    images, weights = [], []
    config = None
    if not os.path.isdir(out_dir):
        return {"images": [], "weights": [], "config": None}
    for file_name in os.listdir(out_dir):
        file_path = os.path.join(out_dir, file_name)
        if file_name.endswith(".png"):
            images.append(file_path)
        elif file_name.endswith(".pt"):
            weights.append(file_path)
        elif file_name == "training_config.json":
            config = file_path
    return {"images": sorted(images), "weights": sorted(weights), "config": config}
