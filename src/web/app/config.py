"""集中定义 Web 端配置默认值、环境变量覆盖与派生路径。"""

import os

from shared.utils.value_utils import parse_bool
DB_DIRNAME = "data"
STORAGE_PATH_PREFIX_PROJECTS = "projects"
STORAGE_PATH_PREFIX_PRETRAINED_MODELS = "pretrained_models"
DATASET_CONFIG_FILENAME = "dataset.yaml"
DATASET_CONFIG_FILENAMES = (DATASET_CONFIG_FILENAME,)

_DEFAULTS = {
    "io": {
        "db_dir": DB_DIRNAME,
        "db_filename": "vision-train.db",
        "max_upload_bytes": 2 * 1024 * 1024 * 1024,
        "db_url": "",
    },
    "server": {
        "host": "0.0.0.0",
        "port": 8080,
        "debug": False,
        "cors_origins": "*",
    },
    "auth": {
        "enabled": False,
        "session_ttl_seconds": 7 * 24 * 3600,
        "bootstrap_admin_user": "admin",
        "bootstrap_admin_password": "",
        "bootstrap_admin_email": "admin@local",
        "allow_register": False,
    },
    "jwt": {
        "algorithm": "HS256",
        "issuer": "vision-train",
    },
}


def _apply_env(section_name, env_map):
    """按默认值类型解析并覆盖指定配置分组的环境变量。"""
    defaults = _DEFAULTS.get(section_name, {})
    out = dict(defaults)
    for key, env_name in env_map.items():
        value = os.environ.get(env_name)
        if value in (None, ""):
            continue
        default = defaults.get(key)
        if isinstance(default, bool):
            out[key] = parse_bool(value, default=default)
        elif isinstance(default, int):
            try:
                out[key] = int(value)
            except ValueError:
                pass
        else:
            out[key] = value
    return out


CONFIG = {
    **_DEFAULTS,
    "io": _apply_env(
        "io",
        {
            "db_dir": "VISION_TRAIN_DB_DIR",
            "db_filename": "VISION_TRAIN_DB_FILENAME",
            "db_url": "VISION_TRAIN_DB_URL",
        },
    ),
    "server": _apply_env(
        "server",
        {
            "host": "VISION_TRAIN_HOST",
            "port": "VISION_TRAIN_PORT",
            "debug": "VISION_TRAIN_DEBUG",
        },
    ),
    "auth": _apply_env(
        "auth",
        {
            "enabled": "VISION_TRAIN_AUTH_ENABLED",
            "session_ttl_seconds": "VISION_TRAIN_SESSION_TTL",
            "bootstrap_admin_user": "VISION_TRAIN_ADMIN_USER",
            "bootstrap_admin_password": "VISION_TRAIN_ADMIN_PASSWORD",
            "bootstrap_admin_email": "VISION_TRAIN_ADMIN_EMAIL",
            "allow_register": "VISION_TRAIN_AUTH_ALLOW_REGISTER",
        },
    ),
    "jwt": _apply_env(
        "jwt",
        {
            "algorithm": "VISION_TRAIN_JWT_ALGORITHM",
        },
    ),
}

IO = CONFIG["io"]
SERVER = CONFIG["server"]
AUTH = CONFIG["auth"]
JWT = CONFIG["jwt"]


def _resolve_relative_to_cwd(target):
    """把相对路径解析到当前工作目录下的绝对路径。"""
    if not target:
        target = ""
    if os.path.isabs(target):
        return os.path.abspath(target)
    return os.path.abspath(os.path.join(os.getcwd(), target))


def _resolve_dir_relative_to_cwd(config_key, default_relative):
    """从配置或环境变量解析目录配置项的最终路径。"""
    raw = IO.get(config_key) or os.environ.get("VISION_TRAIN_" + config_key.upper())
    target = raw if raw not in (None, "") else default_relative
    return _resolve_relative_to_cwd(target)


def _require_env_dir(env_name, description):
    """强制要求环境变量提供目录路径，并归一化为绝对路径。"""
    value = os.environ.get(env_name)
    if value in (None, ""):
        raise RuntimeError(f"必须设置环境变量 {env_name} 指向{description}")
    return os.path.abspath(value)


PROJECTS_DIR = _require_env_dir("VISION_TRAIN_PROJECTS_DIR", "项目根目录")
PRETRAINED_MODELS_DIR = _require_env_dir("VISION_TRAIN_PRETRAINED_MODELS_DIR", "预训练模型根目录")
DB_DIR = _resolve_dir_relative_to_cwd("db_dir", DB_DIRNAME)
DB_FILENAME = str(IO.get("db_filename") or "vision-train.db")
DB_PATH = os.path.join(DB_DIR, DB_FILENAME)


def get_server_config():
    """返回已归一化的服务监听与上传限制配置。"""
    port = SERVER.get("port", 8080)
    try:
        port = int(port)
    except (TypeError, ValueError):
        port = 8080
    return {
        "host": SERVER.get("host", "0.0.0.0"),
        "port": port,
        "debug": parse_bool(SERVER.get("debug", False)),
        "cors_origins": SERVER.get("cors_origins", "*"),
        "max_upload_bytes": int(IO.get("max_upload_bytes", 2 * 1024 * 1024 * 1024)),
    }


def get_storage_config():
    """返回存储目录、数据库与数据集文件名配置。"""
    return {
        "projects_dir": PROJECTS_DIR,
        "pretrained_models_dir": PRETRAINED_MODELS_DIR,
        "db_dir": DB_DIR,
        "db_filename": DB_FILENAME,
        "db_path": DB_PATH,
        "db_url": (IO.get("db_url") or f"sqlite:///{DB_PATH}"),
        "dataset_config_filename": DATASET_CONFIG_FILENAME,
        "dataset_config_filenames": list(DATASET_CONFIG_FILENAMES),
        "auth_enabled": parse_bool(AUTH.get("enabled", False)),
    }
