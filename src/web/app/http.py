"""把业务函数包装为统一 JSON 响应格式。"""

from dataclasses import dataclass
from functools import wraps
from itertools import count

from flask import Response, jsonify, request

from shared.kernel.errors import ApiError, ApplicationError, DomainError

_MISSING = object()
_LAMBDA_ENDPOINT_COUNTER = count(1)


@dataclass(frozen=True)
class ParamSpec:
    """声明式描述单个接口参数的绑定与校验规则。"""
    source_key: object = None
    required: bool = False
    default: object = _MISSING
    transform: object = None
    empty_as_missing: bool = True
    required_message: str | None = None
    location: str = "data"


def param(
    source_key=None,
    *,
    required=False,
    default=_MISSING,
    transform=None,
    empty_as_missing=True,
    required_message=None,
    location="data",
):
    """创建声明式接口参数规格。"""
    return ParamSpec(
        source_key=source_key,
        required=required,
        default=default,
        transform=transform,
        empty_as_missing=empty_as_missing,
        required_message=required_message,
        location=location,
    )


def _ensure_safe_endpoint_name(wrapper, original):
    """为 lambda 包装函数分配稳定且唯一的 endpoint 名。"""
    if getattr(original, "__name__", "") != "<lambda>":
        return wrapper
    wrapper.__name__ = f"lambda_endpoint_{next(_LAMBDA_ENDPOINT_COUNTER)}"
    wrapper.__qualname__ = wrapper.__name__
    return wrapper


def _is_missing_param_value(value, *, empty_as_missing):
    """判断参数值是否应视为缺失。"""
    if value is None:
        return True
    if not empty_as_missing:
        return False
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _resolve_param_default(default):
    """解析参数默认值，支持调用工厂函数。"""
    if callable(default):
        return default()
    return default


def _lookup_request_value(source, spec, field_name):
    """按声明的位置从请求对象或容器中读取原始值。"""
    if spec.location == "whole":
        return source
    keys = spec.source_key or field_name
    if not isinstance(keys, (list, tuple)):
        keys = [keys]
    key = keys[0]
    if spec.location == "files":
        return source.files.get(key)
    if spec.location == "files_list":
        return source.files.getlist(key)
    if spec.location == "form":
        return source.form.get(key)
    for key in keys:
        value = source.get(key)
        if not _is_missing_param_value(value, empty_as_missing=spec.empty_as_missing):
            return value
    return source.get(keys[0])


def _resolve_field_value(source, field_name, loader):
    """把字段 loader 或参数规格解析为最终绑定值。"""
    if isinstance(loader, ParamSpec):
        raw_value = _lookup_request_value(source, loader, field_name)
        if _is_missing_param_value(raw_value, empty_as_missing=loader.empty_as_missing):
            if loader.default is not _MISSING:
                return _resolve_param_default(loader.default)
            if loader.required:
                raise ValueError(loader.required_message or f"缺少 {loader.source_key or field_name}")
            return None
        return loader.transform(raw_value) if callable(loader.transform) else raw_value
    return loader(source)


def _bind_params(source, field_loaders):
    """按字段规格从给定数据源批量绑定参数。"""
    return {name: _resolve_field_value(source, name, loader) for name, loader in field_loaders.items()}


def json_body_params(*, silent=False, **field_loaders):
    """从 JSON body 读取并绑定参数，供非 JSON 响应路由复用。"""
    data = request.get_json(silent=silent) or {}
    return _bind_params(data, field_loaders)


def query_params(**field_loaders):
    """从 query 参数读取并绑定参数，供文件响应或 SSE 路由复用。"""
    return _bind_params(request.args, field_loaders)


def form_body_params(**field_loaders):
    """从 form/files 读取并绑定参数，供非 JSON 响应路由复用。"""
    return _bind_params(request, field_loaders)


def json_error_response(message, *, status_code=400, data=None, **extra):
    """按统一协议返回 JSON 错误响应。"""
    payload = {"success": False, "data": data, "error": str(message)}
    if extra:
        payload.update(extra)
    return jsonify(payload), int(status_code)


def auth_error_response(message, *, code, status_code):
    """按统一协议返回认证相关错误响应。"""
    return json_error_response(message, status_code=status_code, code=code)


def json_endpoint(fn):
    """把业务函数包装为统一的成功或失败 JSON 响应。"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        """捕获业务异常并序列化为约定的接口返回。"""
        try:
            result = fn(*args, **kwargs)
        except ApiError as exc:
            return json_error_response(str(exc), **exc.extra)
        except (ApplicationError, DomainError, ValueError) as exc:
            return json_error_response(str(exc))
        except Exception as exc:
            return json_error_response(f"操作失败: {exc}")

        if isinstance(result, Response):
            raise TypeError(f"{fn.__name__}: 业务代码不应直接返回 Response")
        return jsonify({"success": True, "data": result, "error": None})

    return _ensure_safe_endpoint_name(wrapper, fn)


def json_body_endpoint(fn, *, silent=False, **field_loaders):
    """从 JSON body 提取参数并转交业务函数。"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        """按声明的字段装配 JSON body 参数。"""
        return fn(*args, **kwargs, **json_body_params(silent=silent, **field_loaders))

    return json_endpoint(wrapper)

def query_params_endpoint(fn, **field_loaders):
    """从 query 参数提取命名参数并转交业务函数。"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        """按声明的字段装配 query 参数。"""
        return fn(*args, **kwargs, **query_params(**field_loaders))

    return json_endpoint(wrapper)


def form_body_endpoint(fn, **field_loaders):
    """从 form/files 提取参数并转交业务函数。"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        """按声明的字段装配 multipart/form-data 参数。"""
        return fn(*args, **kwargs, **form_body_params(**field_loaders))

    return json_endpoint(wrapper)
