"""启动 Flask 服务并打印运行时配置信息。"""

import logging
import signal

from app.config import get_server_config, get_storage_config
from app.flask_app import create_app
from app.lifecycle import shutdown_runtime

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = create_app()


def _install_shutdown_signal_handlers():
    """把常见停机信号转换为受控退出，交给 finally 回收 worker。"""

    def _handle_shutdown_signal(signum, _frame):
        logger.warning("收到停机信号 %s，开始关闭服务", signum)
        raise SystemExit(0)

    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, _handle_shutdown_signal)


if __name__ == "__main__":
    _install_shutdown_signal_handlers()
    server_cfg = get_server_config()
    storage_cfg = get_storage_config()

    print("🎯 数据集工具后端启动中...")
    print(f"🌐 API 服务地址: http://{server_cfg['host']}:{server_cfg['port']}")
    print(f"📁 projects_dir:          {storage_cfg['projects_dir']}")
    print(f"📁 pretrained_models_dir: {storage_cfg['pretrained_models_dir']}")
    print(f"📄 数据集配置:            {storage_cfg['dataset_config_filename']}")
    print(f"🔐 认证启用:              {storage_cfg['auth_enabled']}")

    try:
        app.run(
            host=server_cfg["host"],
            port=server_cfg["port"],
            debug=server_cfg["debug"],
            use_reloader=False,
        )
    except SystemExit:
        raise
    except Exception:
        logger.exception("app.run raised unexpected exception")
        raise
    finally:
        shutdown_runtime()
