"""统一处理项目存储路径解析、引用转换与边界校验。"""

import os

from shared.utils.value_utils import require_present

from app.config import (
    PRETRAINED_MODELS_DIR,
    PROJECTS_DIR,
    STORAGE_PATH_PREFIX_PRETRAINED_MODELS,
    STORAGE_PATH_PREFIX_PROJECTS,
)

SYSTEM_STORAGE_ROOTS = (
    (PROJECTS_DIR, STORAGE_PATH_PREFIX_PROJECTS),
    (PRETRAINED_MODELS_DIR, STORAGE_PATH_PREFIX_PRETRAINED_MODELS),
)


def normalize_path_ref(path):
    """统一路径引用的分隔符与首尾斜杠。"""
    return str(path or "").replace("\\", "/").strip().strip("/")


def _split_storage_ref(path):
    """拆分存储引用的前缀与相对路径部分。"""
    normalized = normalize_path_ref(path)
    for _base, prefix in SYSTEM_STORAGE_ROOTS:
        if normalized == prefix:
            return prefix, ""
        marker = f"{prefix}/"
        if normalized.startswith(marker):
            return prefix, normalized[len(marker):]
    return "", normalized


def _strip_known_prefix(path):
    """移除项目存储引用的已知前缀。"""
    prefix, rel = _split_storage_ref(path)
    if prefix == STORAGE_PATH_PREFIX_PROJECTS:
        return rel
    normalized = normalize_path_ref(path)
    return normalized


def resolve_project_path(project_ref):
    """把项目引用解析为项目根目录下的绝对路径。"""
    if not project_ref:
        return project_ref
    project_ref = str(project_ref)
    if os.path.isabs(project_ref):
        return os.path.abspath(project_ref)
    rel = _strip_known_prefix(project_ref)
    return os.path.abspath(os.path.join(PROJECTS_DIR, rel))


def project_path_ref(project_path):
    """把项目绝对路径转换为对外暴露的相对引用。"""
    if not project_path:
        return project_path
    abs_path = os.path.abspath(project_path)
    try:
        rel = os.path.relpath(abs_path, PROJECTS_DIR)
        if rel == ".":
            return ""
        if not rel.startswith(".."):
            return rel.replace(os.sep, "/")
    except ValueError:
        pass
    return str(project_path).replace("\\", "/")


def resolve_storage_path(path):
    """把存储引用解析为受控根目录下的真实绝对路径。"""
    if not path:
        return path
    path = str(path)
    if os.path.isabs(path):
        return os.path.abspath(path)
    prefix, rel = _split_storage_ref(path)
    for base, expected_prefix in SYSTEM_STORAGE_ROOTS:
        if prefix == expected_prefix:
            return os.path.abspath(os.path.join(base, rel))
    raise ValueError("非法路径引用")


def storage_path_ref(path):
    """把绝对路径转换为可回传给接口的存储引用。"""
    if not path:
        return path
    abs_path = os.path.abspath(path)
    for base, prefix in SYSTEM_STORAGE_ROOTS:
        try:
            rel = os.path.relpath(abs_path, base)
            if rel == ".":
                return prefix or "."
            if not rel.startswith(".."):
                rel = rel.replace(os.sep, "/")
                return f"{prefix}/{rel}" if prefix else rel
        except ValueError:
            continue
    return str(path).replace("\\", "/")


def file_api_url(path):
    """为给定路径构造文件下载接口 URL。"""
    return f"/api/file?path={storage_path_ref(path)}"


def build_file_item(path, *, url=None, name=None, path_ref=None, size_bytes=None, relative_path=None):
    """把文件路径转换为统一的展示项结构。"""
    item = {
        "name": name or os.path.basename(str(path or "")),
        "url": url or file_api_url(path),
        "path": storage_path_ref(path) if path_ref is None else path_ref,
    }
    if size_bytes is not None:
        item["size_bytes"] = int(size_bytes)
    if relative_path is not None:
        item["relative_path"] = str(relative_path)
    return item


def build_file_items(items, *, relative_to=None, url_builder=None):
    """把路径列表或扫描记录列表批量转换为统一文件项结构。"""
    result = []
    for raw in items or []:
        if isinstance(raw, dict):
            file_path = raw.get("path")
            if not file_path:
                continue
            relative_path = raw.get("relative_path")
            if relative_path is None and relative_to:
                relative_path = os.path.relpath(file_path, relative_to)
            url = raw.get("url")
            if url is None and callable(url_builder):
                url = url_builder(file_path, raw)
            item = build_file_item(
                file_path,
                url=url,
                name=raw.get("name"),
                path_ref=raw.get("path_ref"),
                size_bytes=raw.get("size_bytes"),
                relative_path=relative_path,
            )
            for key, value in raw.items():
                if key in {"path", "url", "name", "path_ref", "size_bytes", "relative_path"}:
                    continue
                item[key] = value
            result.append(item)
            continue
        if not raw:
            continue
        file_path = str(raw)
        relative_path = os.path.relpath(file_path, relative_to) if relative_to else None
        url = url_builder(file_path, raw) if callable(url_builder) else None
        result.append(build_file_item(file_path, url=url, relative_path=relative_path))
    return result


def slice_items(items, offset=0, limit=50):
    """把列表按 offset/limit 包装为统一分页结构。"""
    return {"items": list(items)[offset : offset + limit], "total": len(items)}


def resolve_and_validate_project(project_ref):
    """解析项目引用并校验项目名与目录存在性。"""
    if not project_ref:
        raise ValueError("未指定 project_path")
    project_name = str(project_ref).strip()
    if project_name.startswith(f"{STORAGE_PATH_PREFIX_PROJECTS}/"):
        project_name = project_name[len(STORAGE_PATH_PREFIX_PROJECTS) + 1:]
    if "/" in project_name:
        project_name = project_name.split("/")[0]

    from contexts.project.domain.policies import validate_project_name

    err = validate_project_name(project_name)
    if err:
        raise ValueError(f"项目名不合法: {err}")
    abs_path = os.path.join(resolve_project_path(project_name), "")
    if not os.path.isdir(abs_path):
        raise ValueError(f"项目 {project_name} 不存在")
    return abs_path, project_name


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


def is_within_any_path(path, roots):
    """判断路径是否位于任一允许根目录内部。"""
    for root in roots or ():
        if is_within_path(path, root):
            return True
    return False


def resolve_allowed_file_path(path_ref, *, allowed_roots):
    """解析文件引用并限制在允许的根目录集合内。"""
    path = resolve_storage_path(path_ref)
    require_present(path=path)
    real_path = os.path.realpath(path)
    if not os.path.isfile(real_path):
        raise FileNotFoundError("文件不存在")
    if not is_within_any_path(real_path, allowed_roots):
        raise ValueError("非法路径")
    return real_path


def resolve_allowed_dir_path(path_ref, *, allowed_roots):
    """解析目录引用并限制在允许的根目录集合内。"""
    path = resolve_storage_path(path_ref)
    require_present(path=path)
    real_path = os.path.realpath(path)
    if not os.path.isdir(real_path):
        raise FileNotFoundError("目录不存在")
    if not is_within_any_path(real_path, allowed_roots):
        raise ValueError("非法路径")
    return real_path


def resolve_relative_child_path(path_ref, *, root):
    """把路径引用解析为指定根目录下的相对路径。"""
    path = resolve_storage_path(path_ref)
    require_present(path=path)
    real_root = os.path.realpath(root)
    real_path = os.path.realpath(path)
    if not is_within_path(real_path, real_root):
        raise ValueError("非法路径")
    return os.path.relpath(real_path, real_root)


def resolve_safe_child_path(root, *parts):
    """在指定根目录下拼接子路径并阻止路径逃逸。"""
    path = os.path.join(str(root or ""), *[str(part or "") for part in parts])
    if not is_within_path(path, root):
        raise ValueError("非法路径")
    return path


def validate_leaf_name(value, field_name="name"):
    """校验单段文件名或目录名并阻止路径穿越。"""
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"缺少 {field_name}")
    if os.path.sep in text or "/" in text or "\\" in text:
        raise ValueError(f"{field_name} 不合法")
    if os.path.basename(text) != text:
        raise ValueError(f"{field_name} 不合法")
    return text


def validate_filename(original_name, *, target_name=None, allowed_extensions=None, max_stem_length=None, field_name="name"):
    """规范化文件名并校验 stem 与扩展名。"""
    target_name = str(target_name or "").strip()
    base_name = target_name if target_name else str(original_name or "")
    ext = os.path.splitext(base_name)[1].lower()
    if allowed_extensions is not None and ext not in allowed_extensions:
        ext = os.path.splitext(str(original_name or ""))[1].lower()
        if ext not in allowed_extensions:
            raise ValueError(f'{field_name} 扩展名不支持')
    stem = validate_leaf_name(os.path.splitext(base_name)[0], field_name=field_name)
    if max_stem_length is not None and len(stem) > int(max_stem_length):
        raise ValueError(f"{field_name} 不能超过 {int(max_stem_length)} 字符")
    return f"{stem}{ext}"


def derive_file_stem(filename, *, allowed_extensions=None, field_name="name"):
    """校验文件名后返回不带扩展名的 stem。"""
    validated_name = validate_filename(filename, allowed_extensions=allowed_extensions, field_name=field_name)
    return os.path.splitext(validated_name)[0]


def sanitize_bundle_name(name, default="bundle"):
    """清洗下载包名中的路径分隔符并提供默认值。"""
    cleaned = str(name or "").strip().replace("\\", "/").strip("/").replace("/", "_")
    return cleaned or str(default or "bundle")


def project_name_from_path(project_path):
    """从项目绝对路径或引用中提取项目目录名。"""
    return os.path.basename(str(project_path or "").rstrip("/\\")) or ""
