"""编排登录、会话、自助改密与用户管理用例。"""

import re

from flask import request

from app.config import AUTH
from contexts.auth.infrastructure.auth_gateway import (
    build_session,
    extract_auth_token,
    get_current_session,
    get_current_user,
    hash_user_password,
    revoke_auth_session,
    touch_auth_session,
    verify_user_password,
)
from db.models import AuthSession, User
from db.session import SessionLocal
from shared.utils.time_utils import now_iso

USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
def _client_info():
    """提取请求来源 IP 与 User-Agent。"""
    ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
    if "," in ip:
        ip = ip.split(",")[0].strip()
    return ip, (request.headers.get("User-Agent") or "")[:255]


def get_auth_status():
    """返回认证开关和当前用户状态。"""
    user = get_current_user()
    if not AUTH.get("enabled", False):
        return {"enabled": False, "authenticated": False, "user": None}
    return {"enabled": True, "authenticated": user is not None, "user": user.to_dict() if user else None}


def login(username, password):
    """校验用户凭据并创建登录会话。"""
    username = (username or "").strip()
    password = password or ""
    if not username or not password:
        raise ValueError("请提供用户名和密码")

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(username=username, is_active=True).first()
        if not user or not verify_user_password(password, user.password_hash):
            raise ValueError("用户名或密码错误")
        user.last_login_at = now_iso()
        db.commit()

        ip, user_agent = _client_info()
        session = build_session(user, ip=ip, user_agent=user_agent)
        return {"token": session.token, "expires_at": session.expires_at, "user": user.to_dict()}
    finally:
        db.close()


def logout():
    """撤销当前请求携带的认证会话。"""
    token = extract_auth_token()
    if not token:
        return {"logged_out": False}
    ok = revoke_auth_session(token)
    return {"logged_out": ok}


def get_me():
    """返回当前登录用户信息并续期会话。"""
    user = get_current_user()
    if user is None:
        raise ValueError("未登录或登录已过期")
    sess = get_current_session()
    if sess:
        try:
            touch_auth_session(sess)
        except Exception:
            pass
    return user.to_dict()


def register_user(username, password, email=None, role="user"):
    """校验参数后创建用户账号。"""
    if not AUTH.get("allow_register", False):
        raise ValueError("注册功能已关闭")
    username = (username or "").strip()
    password = password or ""
    email = (email or "").strip() or None
    role = (role or "user").strip()
    if not USERNAME_RE.match(username):
        raise ValueError("用户名必须 3~32 字符，只能包含字母/数字/._-")
    if len(password) < 6:
        raise ValueError("密码至少 6 位")
    if role not in ("user", "admin"):
        raise ValueError("role 必须是 user 或 admin")
    if email and not EMAIL_RE.match(email):
        raise ValueError("email 格式错误")

    db = SessionLocal()
    try:
        if db.query(User).filter_by(username=username).first():
            raise ValueError(f"用户名 {username} 已存在")
        user = User(
            username=username,
            email=email,
            password_hash=hash_user_password(password),
            role=role,
            is_active=True,
            created_at=now_iso(),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.to_dict()
    finally:
        db.close()


def change_password(old_password, new_password):
    """修改当前用户密码并撤销其他会话。"""
    if len(new_password or "") < 6:
        raise ValueError("新密码至少 6 位")
    user = get_current_user()
    sess = get_current_session()
    if user is None or sess is None:
        raise ValueError("未登录或登录已过期")
    if not verify_user_password(old_password or "", user.password_hash):
        raise ValueError("原密码错误")
    db = SessionLocal()
    try:
        u = db.query(User).filter_by(id=user.id).first()
        u.password_hash = hash_user_password(new_password)
        db.query(AuthSession).filter(AuthSession.user_id == u.id, AuthSession.token != sess.token).update({"revoked": True})
        db.commit()
        return {"changed": True}
    finally:
        db.close()


def list_users():
    """返回全部用户列表。"""
    db = SessionLocal()
    try:
        return [u.to_dict() for u in db.query(User).order_by(User.created_at).all()]
    finally:
        db.close()


def delete_user(user_id):
    """停用指定用户账号。"""
    current = get_current_user()
    if current is None:
        raise ValueError("未登录或登录已过期")
    if current.id == user_id:
        raise ValueError("不能删除自己")
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=user_id).first()
        if not user:
            raise ValueError("用户不存在")
        user.is_active = False
        db.commit()
        return {"deleted": user_id}
    finally:
        db.close()
