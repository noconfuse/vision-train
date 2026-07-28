"""封装文件删除、目录搬运与体积统计等文件系统助手。"""

import hashlib
import os
import shutil


_SYSTEM_HIDDEN_BASENAMES = frozenset({".ds_store", "thumbs.db", "desktop.ini"})


def is_system_hidden_file(name):
    """判断文件名是否属于系统隐藏文件（macOS AppleDouble / Windows 元数据等）。

    典型场景：用户在 macOS 上传的 zip 压缩包内会包含 ``._xxx.jpg`` 资源分叉
    文件（每个真图伴随一个 212 B 的元数据），如果不识别并跳过，这些文件会被
    当成普通图片入库、最终在前端展示为坏图。
    """
    if not name:
        return False
    base = os.path.basename(name)
    if base.startswith("._"):
        return True
    return base.lower() in _SYSTEM_HIDDEN_BASENAMES


def is_within_path(path, root):
    """判断路径是否位于指定根目录内部。"""
    if not path or not root:
        return False
    try:
        path_real = os.path.realpath(path)
        root_real = os.path.realpath(root)
        common = os.path.commonpath([path_real, root_real])
    except Exception:
        return False
    return common == root_real


def resolve_safe_child_path(root, *parts):
    """在指定根目录下拼接子路径并阻止路径逃逸。"""
    path = os.path.join(str(root or ""), *[str(part or "") for part in parts])
    if not is_within_path(path, root):
        raise ValueError("非法路径")
    return path


def remove_file_silent(file_path):
    """静默删除单个文件并忽略常见文件系统错误。"""
    if not file_path:
        return
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
    except OSError:
        pass


def remove_path_silent(path):
    """静默删除文件或目录。"""
    if not path or not os.path.exists(path):
        return
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path, ignore_errors=True)
            return
        os.remove(path)
    except OSError:
        pass


def safe_size(path):
    """安全读取文件大小，失败时返回 0。"""
    try:
        return os.path.getsize(path)
    except Exception:
        return 0


def directory_size(root_dir, exts=None):
    """统计目录中文件总大小，可按扩展名过滤。"""
    total = 0
    try:
        for root, _, files in os.walk(root_dir):
            for file_name in files:
                if exts and not any(file_name.lower().endswith(ext) for ext in exts):
                    continue
                total += safe_size(os.path.join(root, file_name))
    except Exception:
        return 0
    return total


def remove_dir_if_empty(dir_path):
    """仅在目录为空时删除目录。"""
    if not dir_path:
        return
    try:
        os.rmdir(dir_path)
    except OSError:
        pass


def remove_tree(dir_path, *, ignore_errors=True):
    """递归删除目录树，不存在时直接跳过。"""
    if not dir_path or not os.path.isdir(dir_path):
        return
    shutil.rmtree(dir_path, ignore_errors=ignore_errors)


def move_dir_contents(src_dir, dst_dir):
    """把源目录下的所有直接子项移动到目标目录。"""
    if not src_dir or not os.path.isdir(src_dir):
        return
    os.makedirs(dst_dir, exist_ok=True)
    for filename in os.listdir(src_dir):
        shutil.move(os.path.join(src_dir, filename), os.path.join(dst_dir, filename))


def move_path(src_path, dst_path, *, ensure_parent=False):
    """移动文件或目录，并在需要时预建父目录。"""
    if ensure_parent:
        parent_dir = os.path.dirname(str(dst_path or ""))
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
    return shutil.move(src_path, dst_path)


def allocate_nonconflicting_path(dst_path):
    """为目标文件分配一个不与现有文件冲突的路径。"""
    candidate = str(dst_path or "")
    if not candidate or not os.path.exists(candidate):
        return candidate
    base, ext = os.path.splitext(candidate)
    index = 1
    while True:
        candidate = f"{base}_{index}{ext}"
        if not os.path.exists(candidate):
            return candidate
        index += 1


def compute_file_md5(file_path, chunk_size=8 * 1024 * 1024):
    """计算单个文件的 MD5 摘要。"""
    digest = hashlib.md5()
    with open(file_path, "rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()
