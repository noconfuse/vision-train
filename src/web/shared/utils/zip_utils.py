"""提供 zip 文件的统一安全解压与打包入口。"""

import os
import tempfile
import zipfile


def safe_extract_zip(zip_path, target_dir):
    """安全解压 zip，阻止路径穿越写入。"""
    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            name = member.filename
            if name.startswith("/") or ".." in name.replace("\\", "/").split("/"):
                raise ValueError(f"压缩包内路径非法: {name}")
            archive.extract(member, target_dir)


def build_directory_zip(source_dir, bundle_name, skip_dirs=None):
    """把目录打包为临时 ZIP 并跳过指定子目录。"""
    source_real = os.path.realpath(source_dir)
    if not os.path.isdir(source_real):
        raise ValueError("待打包目录不存在")

    ignored_dirs = set(skip_dirs or ("__pycache__", ".git"))
    fd, tmp_zip = tempfile.mkstemp(prefix=f"{bundle_name}_", suffix=".zip")
    os.close(fd)

    with zipfile.ZipFile(tmp_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for root, dirs, files in os.walk(source_real):
            dirs[:] = [name for name in dirs if name not in ignored_dirs]
            for filename in files:
                file_path = os.path.join(root, filename)
                rel_path = os.path.relpath(file_path, source_real)
                archive.write(file_path, os.path.join(bundle_name, rel_path))
    return tmp_zip
