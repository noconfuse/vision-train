"""提供认证状态、登录登出与用户管理接口。"""

from flask import Blueprint

from app.http import json_body_endpoint, json_endpoint, param
from contexts.auth.api.decorators import require_admin, require_auth
from contexts.auth.application.use_cases import (
    change_password,
    delete_user,
    get_auth_status,
    get_me,
    list_users,
    login,
    logout,
    register_user,
)

bp = Blueprint("auth", __name__, url_prefix="/api/auth")

bp.add_url_rule(
    "/login",
    view_func=json_body_endpoint(
        login,
        silent=True,
        username=param("username", required=True),
        password=param("password", required=True),
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/register",
    view_func=require_admin(
        json_body_endpoint(
            register_user,
            silent=True,
            username=param("username", required=True),
            password=param("password", required=True),
            email=param("email"),
            role=param("role", default="user"),
        )
    ),
    methods=["POST"],
)
bp.add_url_rule(
    "/change_password",
    view_func=require_auth(
        json_body_endpoint(
            change_password,
            silent=True,
            old_password=param("old_password", required=True),
            new_password=param("new_password", required=True),
        )
    ),
    methods=["POST"],
)
bp.add_url_rule("/status", view_func=json_endpoint(get_auth_status), methods=["GET"])
bp.add_url_rule("/logout", view_func=json_endpoint(logout), methods=["POST"])
bp.add_url_rule("/me", view_func=require_auth(json_endpoint(get_me)), methods=["GET"])
bp.add_url_rule("/users", view_func=require_admin(json_endpoint(list_users)), methods=["GET"])
bp.add_url_rule("/users/<user_id>", view_func=require_admin(json_endpoint(delete_user)), methods=["DELETE"])
