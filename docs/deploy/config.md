# 运行配置

> 配置加载顺序、必填项与覆盖方法。

## 加载顺序

后 → 前覆盖：内置默认值（仅 server / db 等非存储根配置）→ 环境变量。

## 默认配置

默认值定义在 `src/web/app/config.py`：

```python
_DEFAULTS = {
    "io": {
        "db_dir": "data",
        "db_filename": "vision-train.db",
    },
    "server": {
        "host": "0.0.0.0",
        "port": 8090,
        "debug": False,
    },
    "auth": {
        "enabled": False,
        "session_ttl_seconds": 604800,
        "bootstrap_admin_user": "admin",
        "bootstrap_admin_password": "",
        "bootstrap_admin_email": "admin@local",
        "allow_register": False,
    },
}
```

## 选项

| 配置项                  | 环境变量                          | 含义                                   | 默认值         |
| ----------------------- | --------------------------------- | -------------------------------------- | -------------- |
| `projects_dir`          | `VISION_TRAIN_PROJECTS_DIR`       | 项目根路径（相对或绝对）               | 必须设置       |
| `pretrained_models_dir` | `VISION_TRAIN_PRETRAINED_MODELS_DIR` | 预训练模型目录（相对或绝对）        | 必须设置       |
| `db_dir`                | `VISION_TRAIN_DB_DIR`             | SQLite 数据库目录                      | `data`        |
| `db_filename`           | `VISION_TRAIN_DB_FILENAME`        | SQLite 数据库文件名                    | `vision-train.db` |
| `db_url`                | `VISION_TRAIN_DB_URL`             | 完整数据库连接串，优先级高于目录/文件名 | ``            |
| `host`                  | `VISION_TRAIN_HOST`               | Flask 监听地址                          | `0.0.0.0`     |
| `port`                  | `VISION_TRAIN_PORT`               | Flask 端口                              | `8090`        |
| `debug`                 | `VISION_TRAIN_DEBUG`              | Flask debug 模式                       | `false`       |
| `auth.enabled`          | `VISION_TRAIN_AUTH_ENABLED`       | 是否启用登录认证                       | `false`       |
| `auth.allow_register`   | `VISION_TRAIN_AUTH_ALLOW_REGISTER` | 是否允许匿名自助注册（仅创建普通用户） | `false`       |
| `auth.session_ttl_seconds` | `VISION_TRAIN_SESSION_TTL`     | 会话有效期，支持秒数或 `7d` / `12h`    | `604800`（7 天） |
| `auth.bootstrap_admin_user` | `VISION_TRAIN_ADMIN_USER`     | 首次启动时创建的管理员用户名           | `admin`       |
| `auth.bootstrap_admin_password` | `VISION_TRAIN_ADMIN_PASSWORD` | 初始管理员密码；留空则不自动创建管理员 | 空 |
| `auth.bootstrap_admin_email` | `VISION_TRAIN_ADMIN_EMAIL`    | 初始管理员邮箱                         | `admin@local` |

> `VISION_TRAIN_PROJECTS_DIR` 与 `VISION_TRAIN_PRETRAINED_MODELS_DIR` 都必须设置；路径既支持相对也支持绝对。相对路径以启动进程的工作目录为基准，推荐从仓库根目录启动后端。

## 认证说明

- 认证默认关闭；`VISION_TRAIN_AUTH_ENABLED=true` 后，除健康检查、登录、注册、认证状态外的接口都需要有效 token。
- 首次开启认证需通过 `VISION_TRAIN_ADMIN_PASSWORD` 提供初始管理员密码；留空且系统无管理员时只记录警告，不创建账号。
- 会话 token 由服务端生成并存数据库（非 JWT），退出登录、修改密码或停用用户后旧 token 立即失效。
- 管理员可通过 `POST /api/auth/register` 创建用户并指定角色；匿名注册仅在 `VISION_TRAIN_AUTH_ALLOW_REGISTER=true` 时开放，角色固定为 `user`。

## 覆盖方式

### .env（推荐）

启动脚本 `./scripts/start_backend.sh` 自动加载仓库根目录 `.env` 并导出到进程环境：

```bash
cp .env.example .env
./scripts/start_backend.sh
```

### 环境变量（不使用 .env 时）

```bash
export VISION_TRAIN_PROJECTS_DIR=/data/projects
export VISION_TRAIN_PRETRAINED_MODELS_DIR=/data/models
export VISION_TRAIN_PORT=9090
./scripts/start_backend.sh
```

## 调试 / 诊断

`/api/health` 返回当前生效的路径：

```bash
curl http://localhost:8090/api/health
```

```json
{
  "status": "ok",
  "service": "vision-train",
  "storage": {
    "projects_dir": "/Users/me/vision-train/projects",
    "pretrained_models_dir": "/Users/me/vision-train/pretrained_models",
    "project_root": "/Users/me/vision-train",
    "db_dir": "/Users/me/vision-train/data",
    "db_filename": "vision-train.db",
    "db_path": "/Users/me/vision-train/data/vision-train.db",
    "db_url": "sqlite:////Users/me/vision-train/data/vision-train.db",
    "dataset_config_filename": "dataset.yaml",
    "dataset_config_filenames": ["dataset.yaml"],
    "auth_enabled": false
  }
}
```

> 推荐在 `dataset.yaml` 中保持相对路径，避免把机器相关的绝对路径写死进去。

## 启动脚本输出

后端启动会打印：

```text
🎯 数据集工具后端启动中...
🌐 API 服务地址: http://0.0.0.0:8090
📁 projects_dir:         /Users/me/vision-train/projects
📁 pretrained_models_dir: /Users/me/vision-train/pretrained_models
📄 数据集配置:           dataset.yaml
```

## 端口冲突处理

默认端口是 `8090`。如被占用，修改环境变量 `VISION_TRAIN_PORT` 即可。
