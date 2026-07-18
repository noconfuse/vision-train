# 运行配置

> 配置加载顺序、必填项与覆盖方法。

## 加载顺序（后 → 前覆盖）

1. **内置默认值**（仅 server / db 等非存储根配置）
2. **环境变量**

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

> `VISION_TRAIN_PROJECTS_DIR` 与 `VISION_TRAIN_PRETRAINED_MODELS_DIR` 都必须设置；路径既支持相对也支持绝对。相对路径以启动进程的工作目录为基准，推荐从仓库根目录启动后端。

## 覆盖方式

### .env（推荐）

启动脚本 `./scripts/start_backend.sh` 会自动加载仓库根目录的 `.env`，并把其中的配置导出到进程环境里。

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
    "dataset_config_filenames": ["dataset.yaml"]
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
