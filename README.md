# Vision Train

Vision Train 是一个面向视觉模型的本地一体化工作台，把数据准备、标注、训练、评估、导出和部署模板收口在同一套 Web UI。

围绕项目 → 数据集 → 标注 → 训练工作流 → 评估 / 导出 / 部署模板的闭环，支持跨任务类型（detect / classify / segment / pose）。

在线文档地址：<https://vision-train-docs.netlify.app>

![训练工作流示意](docs/assets/train_step.png)

## 当前能力

### 数据准备

- 项目管理：新建、编辑、删除、切换项目，按项目隔离数据与训练记录
- 数据准备：导入现成数据、整理训练数据划分、下载或删除数据集
- 视频处理：上传视频、预览视频、抽取候选图片并导入到数据集中
- 图片标注：框选目标、修改类别、删除错误标注、批量清理图片
- 智能辅助：用已有模型先生成标注草稿，再由人工复核确认
- 数据整理：调整类别顺序、清理重复图片、合并数据集、删除无用标签
- 数据增强：针对样本少的类别生成补强数据集，减少类别不平衡
- 数据集版本：发布 / 恢复 / 自动引导数据集版本快照

### 模型训练与上线

- 模型训练：以工作流为中心管理多轮训练，跨任务类型（detect / classify / segment / pose）
- 效果检查：查看测试结果，判断当前模型是否达到使用预期
- 模型导出：生成适合不同部署环境的模型文件并下载产物
- 部署模板：基于 `pt` 或导出后产物生成 FastAPI / Python SDK / 批处理 模板包
- 工作流归档：归档 / 恢复训练工作流，保留历史任务与产物
- 任务中心：统一查看抽帧、标注、训练、测试、导出、部署模板等后台任务状态

## 仓库入口

- 用户文档：`docs/README.md`
- 后端入口：`src/web/main.py`
- 前端应用：`frontend/`
- 后端启动脚本：`scripts/start_backend.sh`

## 本地启动

### 1. 准备环境变量

```bash
cp .env.example .env
```

默认配置里：

- 后端端口是 `8090`
- 前端开发代理会把 `/api` 转发到 `http://127.0.0.1:8090`
- 认证默认关闭；如需开启，在 `.env` 里设置 `VISION_TRAIN_AUTH_ENABLED=true`

`.env` 里至少需要配置：

- `VISION_TRAIN_PROJECTS_DIR`：项目根目录
- `VISION_TRAIN_PRETRAINED_MODELS_DIR`：预训练模型根目录

完整的环境变量说明见 [docs/guide/quickstart.md](docs/guide/quickstart.md) 和 [docs/deploy/config.md](docs/deploy/config.md)。

### 2. 安装后端依赖

建议使用 Python `3.10+`。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

后端在运行时还会调用宿主机的 `ffmpeg` 命令做视频抽帧；`ffprobe` 可选，不装也能跑，只是部分视频的总帧数探测会降级。

### 3. 启动后端

```bash
bash scripts/start_backend.sh
```

启动后可通过 <http://localhost:8090/api/health> 检查健康状态。

### 4. 安装并启动前端

```bash
cd frontend
npm install
npm run dev
```

默认访问地址：

```text
http://localhost:5173
```

如果你开启了认证，可在登录页用 `.env` 里配置的 `VISION_TRAIN_ADMIN_USER` / `VISION_TRAIN_ADMIN_PASSWORD` 登录。

## 目录结构

```text
.
├── docs/                        # 用户文档与 SOP（docsify 静态站）
├── frontend/                    # Vue 3 前端
├── scripts/                     # 启动脚本
├── src/web/                     # Flask 后端
├── .env.example                 # 环境变量示例
└── requirements.txt             # Python 依赖
```

## 运行配置

常用环境变量：

- `VISION_TRAIN_PROJECTS_DIR`：项目根目录（必填）
- `VISION_TRAIN_PRETRAINED_MODELS_DIR`：预训练模型根目录（必填）
- `VISION_TRAIN_DB_DIR`：数据库目录（默认 `data`）
- `VISION_TRAIN_DB_FILENAME`：数据库文件名（默认 `vision-train.db`）
- `VISION_TRAIN_DB_URL`：完整数据库连接串，优先级高于 `DB_DIR / DB_FILENAME`
- `VISION_TRAIN_HOST`：后端监听地址（默认 `0.0.0.0`）
- `VISION_TRAIN_PORT`：后端监听端口（默认 `8090`）
- `VISION_TRAIN_DEBUG`：Flask debug 模式（默认 `false`）
- `VISION_TRAIN_AUTH_ENABLED`：是否启用登录认证（默认 `false`）
- `VISION_TRAIN_AUTH_ALLOW_REGISTER`：认证开启后是否允许注册（默认 `false`）
- `VISION_TRAIN_SESSION_TTL`：会话有效期（默认 `7d`）

更完整的说明见 [docs/deploy/config.md](docs/deploy/config.md)。

## 文档入口

- 用户使用手册：[docs/README.md](docs/README.md)
- 快速开始：[docs/guide/quickstart.md](docs/guide/quickstart.md)
- 标准操作流程：[docs/sop/01-project.md](docs/sop/01-project.md)
- 在线文档站：<https://vision-train-docs.netlify.app>

## 开发说明

- 前端技术栈：Vue 3、Pinia、Vue Router、Vite、Tailwind CSS、reka-ui
- 后端技术栈：Flask、SQLAlchemy、Ultralytics（PyTorch）、OpenCV、OpenVINO、Pillow、PyYAML、PyJWT
- 数据格式：YOLO 数据集格式，支持 `detect` / `classify` / `segment` / `pose` 四类任务
- 任务执行：worker 子进程模式，任务进度通过 SQLite 任务表回写
- 文档站：docsify（仓库 `docs/` 目录，零构建）

## 说明

- 仓库的用户文档位于 `docs/`，可以直接作为静态文档站发布（如 Netlify / GitHub Pages）。
- 本仓库默认运行在单机 / 单项目场景；多用户协同、生产部署、SaaS 化不在当前范围。

## License

本仓库以 [MIT License](LICENSE) 发布，Copyright (c) 2026 baolei。