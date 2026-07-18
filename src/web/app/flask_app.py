"""组装 Flask 应用、健康检查与通用请求钩子。"""

from flask import Flask
from flask_cors import CORS

from app.bootstrap import register_blueprints
from app.config import get_server_config, get_storage_config
from app.lifecycle import attach_request_hooks, initialize_runtime


def create_app():
    """创建 Flask 应用并挂载健康检查与业务蓝图。"""
    initialize_runtime()
    app = Flask(__name__)
    server_cfg = get_server_config()
    app.config["MAX_CONTENT_LENGTH"] = server_cfg["max_upload_bytes"]
    CORS(app)
    attach_request_hooks(app)

    @app.route("/api/health")
    def api_health():
        """返回服务存活状态与当前存储配置。"""
        return {
            "status": "ok",
            "service": "vision-train",
            "storage": get_storage_config(),
        }

    register_blueprints(app)
    return app
