"""提供压缩文件的统一安全解压与打包入口。"""

import os
import tarfile
import tempfile
import zipfile

from constants.archive import ARCHIVE_FILE_EXTENSIONS
from shared.utils.fs_utils import resolve_safe_child_path

def split_archive_filename(filename):
    """解析压缩包文件名，返回 stem 与完整扩展名。"""
    text = str(filename or "").strip()
    lowered = text.lower()
    for ext in ARCHIVE_FILE_EXTENSIONS:
        if lowered.endswith(ext):
            stem = text[: -len(ext)].strip()
            if not stem:
                raise ValueError("文件名为空")
            return stem, ext
    raise ValueError("仅支持 .zip / .tar / .tar.gz / .tgz 格式")


def _validate_archive_member_path(name, *, target_dir):
    """校验压缩包内成员路径，阻止路径穿越写入。"""
    normalized = str(name or "").replace("\\", "/")
    try:
        resolve_safe_child_path(target_dir, normalized)
    except ValueError:
        raise ValueError(f"压缩包内路径非法: {name}")
    return normalized


def safe_extract_zip(zip_path, target_dir):
    """安全解压 zip，阻止路径穿越写入。"""
    with zipfile.ZipFile(zip_path, "r") as archive:
        for member in archive.infolist():
            _validate_archive_member_path(member.filename, target_dir=target_dir)
            archive.extract(member, target_dir)


def safe_extract_tar(tar_path, target_dir):
    """安全解压 tar/tar.gz/tgz，阻止路径穿越写入。"""
    with tarfile.open(tar_path, "r:*") as archive:
        for member in archive.getmembers():
            _validate_archive_member_path(member.name, target_dir=target_dir)
        archive.extractall(target_dir)


def safe_extract_archive(archive_path, target_dir, *, original_name=None):
    """按压缩包类型选择安全解压策略。"""
    _stem, ext = split_archive_filename(original_name or archive_path)
    if ext in {".tar", ".tar.gz", ".tgz"}:
        safe_extract_tar(archive_path, target_dir)
        return
    if ext == ".zip":
        safe_extract_zip(archive_path, target_dir)
        return
    raise ValueError("仅支持 .zip / .tar / .tar.gz / .tgz 格式")


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
