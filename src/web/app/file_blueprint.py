"""提供受限文件读取接口并校验可访问路径。"""

import mimetypes
import os

from flask import Blueprint, abort, request, send_file

from app.config import PRETRAINED_MODELS_DIR, PROJECTS_DIR
from shared.utils.path_utils import resolve_allowed_file_path

bp = Blueprint("file", __name__)

_ALLOWED_BASES = [
    os.path.realpath(PROJECTS_DIR),
    os.path.realpath(PRETRAINED_MODELS_DIR),
]


@bp.route("/api/file")
def api_file():
    """按请求路径返回文件内容并映射常见错误状态码。"""
    try:
        file_path = resolve_allowed_file_path(request.args.get("path"), allowed_roots=_ALLOWED_BASES)
    except FileNotFoundError:
        abort(404)
    except Exception:
        abort(400)

    guessed_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
    return send_file(file_path, mimetype=guessed_type, conditional=True)
