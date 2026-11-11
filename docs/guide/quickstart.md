# 快速开始

> 用最短路径把 Vision Train 跑起来，并进入第一个项目

## 1. 环境准备

```bash
git clone <your-repo> vision-train
cd vision-train
```

建议环境：

- Python 3.10+
- Node.js 18+
- npm 9+
- 宿主机已安装 `ffmpeg` / `ffprobe`

## 2. 环境变量

后端依赖以下环境变量，前两项必填：

| 变量 | 是否必填 | 含义 | 默认 |
| --- | --- | --- | --- |
| `VISION_TRAIN_PROJECTS_DIR` | 必填 | 项目根目录，绝对路径或相对仓库根目录的路径 | 无 |
| `VISION_TRAIN_PRETRAINED_MODELS_DIR` | 必填 | 预训练模型目录，绝对路径或相对仓库根目录的路径 | 无 |
| `VISION_TRAIN_PORT` | 选填 | Flask 监听端口 | `8090` |
| `VISION_TRAIN_HOST` | 选填 | Flask 监听地址 | `0.0.0.0` |
| `VISION_TRAIN_DB_DIR` | 选填 | SQLite 数据库目录 | `data` |
| `VISION_TRAIN_DB_FILENAME` | 选填 | SQLite 数据库文件名 | `vision-train.db` |
| `VISION_TRAIN_DB_URL` | 选填 | 完整数据库连接串，优先级高于 `DB_DIR / DB_FILENAME` | 空 |
| `VISION_TRAIN_DEBUG` | 选填 | Flask debug 模式 | `false` |
| `VISION_TRAIN_AUTH_ENABLED` | 选填 | 是否启用登录认证 | `false` |
| `VISION_TRAIN_AUTH_ALLOW_REGISTER` | 选填 | 是否允许匿名自助注册（仅普通用户） | `false` |
| `VISION_TRAIN_SESSION_TTL` | 选填 | 会话有效期，支持秒数或 `7d` / `12h` | `7d` |
| `VISION_TRAIN_ADMIN_USER` | 选填 | 初始管理员用户名 | `admin` |
| `VISION_TRAIN_ADMIN_PASSWORD` | 选填 | 初始管理员密码；开启认证时建议设置 | 空 |
| `VISION_TRAIN_ADMIN_EMAIL` | 选填 | 初始管理员邮箱 | `admin@local` |

> 完整配置项与覆盖规则参见 [运行配置](../deploy/config.md)。

`.env` 位于仓库根目录，`./scripts/start_backend.sh` 自动加载：

```bash
cat > .env <<'EOF'
VISION_TRAIN_PROJECTS_DIR=./projects
VISION_TRAIN_PRETRAINED_MODELS_DIR=./pretrained_models
VISION_TRAIN_PORT=8090
EOF
```

> 路径既支持绝对路径，也支持相对路径。相对路径以启动进程的工作目录为基准，推荐从仓库根目录启动后端。

## 3. 启动后端

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./scripts/start_backend.sh
```

> 如果还没有 `.env`，请先按 §2 完成环境变量配置再启动；`cp .env.example .env` 也可作为起点。

启动成功后，可访问：

- API 健康检查：<http://localhost:8090/api/health>

## 4. 启动前端

```bash
cd frontend
npm install
npm run dev
```

默认访问地址：

- Web UI：<http://localhost:5173>

开发模式下，前端会把 `/api` 自动代理到 `http://127.0.0.1:8090`。

## 5. 首次进入系统

浏览器打开前端地址，认证开启时先在登录页登录。系统围绕「当前项目」组织：

- 项目内导航「数据集 / 视频」两类资源
- 数据集详情页完成标注、候选审核与数据整理
- 训练页以工作流为中心完成训练、评估、导出与部署模板

## 6. 跑通第一条主流程

1. 按 [SOP-1 项目管理](../sop/01-project.md) 创建项目
2. 二选一准备数据：[导入 YOLO 数据集](../sop/03-annotation.md) 或 [视频抽帧导入](../sop/02-video-frame-extract.md)
3. 打开数据集详情页，检查标注、筛选与批量操作
4. 按 [SOP-7 模型训练](../sop/07-train.md) 新建工作流并启动训练
5. 训练完成后走 [SOP-8 评估与导出](../sop/08-eval-export.md)

## 7. 常见首次问题

| 现象 | 排查方向 |
| --- | --- |
| 一直停在登录页 | 后端是否启动、`/api/auth/status` 是否可访问 |
| 视频无法抽帧 | 宿主机是否安装 `ffmpeg` |
| 页面没有项目 | 正常现象，先新建项目 |
| 回看后台任务 | 顶部导航的任务中心入口（路由 `/tasks`） |

## 8. 停止服务

在前后端各自的终端终止进程即可。
