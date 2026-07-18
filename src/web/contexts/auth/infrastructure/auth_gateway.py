"""处理认证会话、密码散列与当前用户装载。"""

import hashlib
import hmac
import logging
import secrets
from datetime import datetime, timedelta

from flask import g, request

from app.config import AUTH
from db.models import AuthSession, User
from db.session import SessionLocal
from shared.utils.time_utils import now_dt, to_iso

logger = logging.getLogger(__name__)

_PBKDF2_ITER = 200_000
_PBKDF2_ALGO = "sha256"
_SALT_BYTES = 16

def extract_auth_token():
    """从请求头、Cookie 或查询参数提取 token。"""
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    cookie = request.cookies.get("auth_token")
    if cookie:
        return cookie
    return request.args.get("token")


def populate_current_user():
    """根据当前请求 token 装载登录用户与会话。"""
    g.current_user = None
    g.current_session = None
    if not AUTH.get("enabled", False):
        return
    token = extract_auth_token()
    if not token:
        return
    sess = find_session(token)
    if not sess:
        return
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=sess.user_id, is_active=True).first()
        if user:
            g.current_user = user
            g.current_session = sess
    finally:
        db.close()


def ensure_bootstrap_admin():
    """在系统首次启动时按配置创建管理员。"""
    if not AUTH.get("enabled", False):
        return
    password = (AUTH.get("bootstrap_admin_password") or "").strip()
    if not password:
        return
    db = SessionLocal()
    try:
        has_admin = db.query(User).filter_by(role="admin").first() is not None
        if has_admin:
            return
        username = (AUTH.get("bootstrap_admin_user") or "admin").strip()
        email = (AUTH.get("bootstrap_admin_email") or "").strip() or None
        user = User(
            username=username,
            email=email,
            password_hash=hash_user_password(password),
            role="admin",
            is_active=True,
            created_at=to_iso(now_dt()),
        )
        db.add(user)
        db.commit()
        logger.info("已创建初始管理员账号: %s", username)
    finally:
        db.close()


def build_session(user, ip=None, user_agent=None):
    """为用户创建一条新的认证会话记录。"""
    ttl = int(AUTH.get("session_ttl_seconds", 7 * 24 * 3600))
    now = now_dt()
    expires = now + timedelta(seconds=ttl)
    sess = AuthSession(
        user_id=user.id,
        token=secrets.token_urlsafe(32),
        created_at=to_iso(now),
        expires_at=to_iso(expires),
        ip=ip,
        user_agent=(user_agent or "")[:255],
    )
    db = SessionLocal()
    try:
        db.add(sess)
        db.commit()
        db.refresh(sess)
        return sess
    finally:
        db.close()


def revoke_auth_session(token):
    """撤销指定 token 对应的认证会话。"""
    db = SessionLocal()
    try:
        sess = db.query(AuthSession).filter_by(token=token).first()
        if not sess:
            return False
        sess.revoked = True
        db.commit()
        return True
    finally:
        db.close()


def get_current_user():
    """返回当前请求上下文中的用户对象。"""
    return getattr(g, "current_user", None)


def get_current_session():
    """返回当前请求上下文中的认证会话。"""
    return getattr(g, "current_session", None)


def verify_user_password(password, password_hash):
    """校验明文密码与存储散列是否匹配。"""
    try:
        algo, iter_s, salt_hex, hash_hex = password_hash.split("$", 3)
        if algo != "pbkdf2_sha256":
            return False
        iterations = int(iter_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, AttributeError):
        return False

    digest = hashlib.pbkdf2_hmac(_PBKDF2_ALGO, password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(digest, expected)


def hash_user_password(password):
    """生成密码的 PBKDF2 散列值。"""
    salt = secrets.token_bytes(_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(_PBKDF2_ALGO, password.encode("utf-8"), salt, _PBKDF2_ITER)
    return f"pbkdf2_sha256${_PBKDF2_ITER}${salt.hex()}${digest.hex()}"


def find_session(token):
    """查找仍然有效的认证会话。"""
    if not token:
        return None
    db = SessionLocal()
    try:
        sess = db.query(AuthSession).filter_by(token=token).first()
        if not sess or sess.revoked:
            return None
        try:
            expires = datetime.fromisoformat(sess.expires_at)
        except ValueError:
            return None
        if expires < now_dt():
            return None
        return sess
    finally:
        db.close()


def touch_auth_session(sess):
    """刷新认证会话的最近访问时间。"""
    db = SessionLocal()
    try:
        current = db.query(AuthSession).filter_by(id=sess.id).first()
        if current:
            current.last_seen_at = to_iso(now_dt())
            db.commit()
    finally:
        db.close()
