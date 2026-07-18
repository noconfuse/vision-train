# Vision Train

Vision Train 是一个面向目标检测数据与训练流程的本地工作台，用来把项目、数据集、视频抽帧、标注、训练、评估和导出收口到同一套 Web UI。

在线文档地址：<https://vision-train-docs.netlify.app>

![训练工作流示意](docs/assets/train_step.png)

## 当前能力

- 项目管理：新建、编辑、删除、切换项目，按项目隔离数据与训练记录
- 数据准备：导入现成数据集、整理训练数据、下载或删除数据集
- 视频处理：上传视频、预览视频、抽取候选图片并导入到数据集中
- 图片标注：框选目标、修改类别、删除错误标注、批量清理图片
- 智能辅助：用已有模型先生成标注草稿，再由人工复核确认
- 数据整理：调整类别顺序、清理重复图片、合并数据集、删除无用标签
- 数据增强：针对样本少的类别生成补强数据集，减少类别不平衡
- 训练工作流：创建训练流程、查看进度、继续训练、回看历史记录
- 效果检查：查看测试结果，判断当前模型是否达到使用预期
- 模型导出：生成适合不同部署环境的模型文件并下载产物
- 任务中心：统一查看抽帧、标注、训练、测试、导出等后台任务状态

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

当前默认配置里：

- 后端端口是 `8090`
- 前端开发代理会把 `/api` 转发到 `http://127.0.0.1:8090`
- 认证默认开启，初始账号来自 `.env`

### 2. 安装后端依赖

建议使用 Python `3.10+`。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. 启动后端

```bash
bash scripts/start_backend.sh
```

脚本会自动读取根目录 `.env`，并要求至少配置以下目录：

- `VISION_TRAIN_PROJECTS_DIR`
- `VISION_TRAIN_PRETRAINED_MODELS_DIR`

### 4. 安装并启动前端

```bash
cd frontend
npm install
npm run dev
```

默认访问地址通常是：

```text
http://localhost:5173
```

如果你保留 `.env.example` 里的认证配置，首次可使用下面的默认账号登录：

```text
用户名：admin
密码：change_me
```

## 目录结构

```text
.
├── docs/                        # 用户文档与 SOP
├── frontend/                    # Vue 3 前端
├── scripts/                     # 启动脚本
├── src/web/                     # Flask 后端
├── .env.example                 # 环境变量示例
└── requirements.txt             # Python 依赖
```

## 运行配置

常用环境变量：

- `VISION_TRAIN_PROJECTS_DIR`：项目根目录
- `VISION_TRAIN_PRETRAINED_MODELS_DIR`：预训练模型根目录
- `VISION_TRAIN_DB_DIR`：数据库目录
- `VISION_TRAIN_DB_FILENAME`：数据库文件名
- `VISION_TRAIN_HOST`：后端监听地址
- `VISION_TRAIN_PORT`：后端监听端口
- `VISION_TRAIN_AUTH_ENABLED`：是否启用登录认证

更完整的说明见 [docs/deploy/config.md](docs/deploy/config.md)。

## 文档入口

- 用户使用手册：[docs/README.md](docs/README.md)
- 快速开始：[docs/guide/quickstart.md](docs/guide/quickstart.md)
- 标准操作流程：[docs/sop/01-project.md](docs/sop/01-project.md)
- 在线文档站：<https://vision-train-docs.netlify.app>

## 开发说明

- 前端技术栈：Vue 3、Vite、Pinia、Vue Router、Tailwind CSS
- 后端技术栈：Flask、Ultralytics、OpenVINO、Pillow、PyYAML
- 数据格式：YOLO 检测数据集格式

## 说明

- 当前仓库的用户文档位于 `docs/`，适合单独作为静态文档站发布
- 如果要发布为 GitHub Pages，建议直接使用仓库的 `docs/` 目录作为 Pages Source
