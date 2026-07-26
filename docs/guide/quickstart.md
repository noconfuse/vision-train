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

启动后端前，需要先决定项目根目录和预训练模型目录的存放位置。后端依赖以下环境变量：

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

> 完整配置项与覆盖规则参见 [运行配置](../deploy/config.md)。

### 通过 `.env` 配置

`.env` 文件位于仓库根目录，`./scripts/start_backend.sh` 会自动加载它：

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

在浏览器打开前端地址后，通常会先看到登录页，使用账号密码登录后进入系统。系统整体围绕“当前项目”组织：

- 进入后默认在项目内导航“数据集 / 视频”两类资源
- 进入数据集后可以在数据预览页完成标注、自动标注复核与数据整理
- 进入训练页后以工作流为中心完成训练、评估、导出与部署模板

## 6. 跑通第一条主流程

推荐直接按下面顺序验证系统：

1. 按 [SOP-1 项目管理](../sop/01-project.md) 创建一个项目
2. 二选一准备数据：
   - 按 [SOP-3 数据标注](../sop/03-annotation.md) 导入一个现成的 YOLO 数据集
   - 按 [SOP-2 视频抽帧](../sop/02-video-frame-extract.md) 上传视频并抽帧导入数据集
3. 打开数据集详情页，检查标注、过滤和批量操作是否正常
4. 进入 [SOP-7 模型训练](../sop/07-train.md)，新建工作流并启动训练
5. 训练完成后，继续走 [SOP-8 评估与导出](../sop/08-eval-export.md)

## 7. 常见首次问题

- 打开前端后一直停在登录页：确认后端是否启动，以及 `/api/auth/status` 是否可访问
- 视频无法抽帧：优先检查宿主机是否已安装 `ffmpeg`
- 页面能打开但没有项目：这是正常情况，首次使用需要先新建项目
- 想回看后台任务：从侧边栏底部用户菜单进入“任务中心”

## 8. 停止服务

- 在后端终端停止后端进程
- 在前端终端停止 Vite 开发服务
