"""提供登录校验与管理员校验装饰器。"""

from functools import wraps

from app.http import auth_error_response
from app.config import AUTH
from contexts.auth.infrastructure.auth_gateway import get_current_session, get_current_user, touch_auth_session


def require_auth(fn):
    """要求请求已登录，否则直接返回认证错误。"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        """在执行目标视图前校验登录态并续期会话。"""
        if not AUTH.get("enabled", False):
            return fn(*args, **kwargs)
        if get_current_user() is None:
            return auth_error_response("未登录或登录已过期", code="auth_required", status_code=401)
        sess = get_current_session()
        if sess:
            try:
                touch_auth_session(sess)
            except Exception:
                pass
        return fn(*args, **kwargs)

    return wrapper


def require_admin(fn):
    """要求请求具有管理员权限。"""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        """在执行目标视图前校验管理员身份。"""
        if not AUTH.get("enabled", False):
            return fn(*args, **kwargs)
        user = get_current_user()
        if user is None:
            return auth_error_response("未登录或登录已过期", code="auth_required", status_code=401)
        if user.role != "admin":
            return auth_error_response("需要管理员权限", code="admin_required", status_code=403)
        return fn(*args, **kwargs)

    return wrapper
