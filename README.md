# Vision Train

Vision Train 是一个面向 YOLO 目标检测项目的本地数据集与训练工作台。当前主入口是 Flask 后端 `src/web/main.py`，配套前端位于 `frontend/`，用于管理项目、预览和编辑数据集、自动标注、视频抽帧、启动训练、查看训练产物、评估和导出模型。

> 本 README 只覆盖主数据集/训练工具链，暂不包含 `src/web/inference_tool.py`。

## 功能概览

- 项目管理：扫描和创建 `projects/` 下的视觉训练项目。
- 数据集管理：识别 YOLO 数据集，查看图片、标注率、类别统计和标签信息。
- 数据集整理：上传图片、删除图片、批量删除、删除类别、重排类别 ID、更新标签、拆分数据集、合并数据集、去重、下载数据集压缩包。
- 数据增强和子集构建：从已有数据集创建子集，支持按目标类别筛选和增强。
- 标注能力：读取/保存 YOLO 标注，支持单图和批量自动标注。
- 视频处理：扫描项目视频，生成缩略图，按时间间隔或数量抽帧，将抽帧结果导入数据集。
- 模型训练：使用 Ultralytics YOLO 启动训练、停止训练、轮询训练状态、继续训练、从断点恢复训练。
- 训练产物：查看训练历史、权重、曲线图、配置文件和最近产物。
- 模型评估和导出：评估模型，导出 ONNX/OpenVINO 等格式，支持导出包下载。
- 测试推理：对项目内测试目录或指定权重执行批量推理并查看可视化结果。

## 技术栈

- 后端：Flask、Flask-CORS、Ultralytics、OpenVINO、Pillow、PyYAML
- 前端：Vue 3、Vite、Pinia、Vue Router、Axios、Tailwind CSS
- 数据格式：YOLO detection 数据集格式

## 目录结构

```text
.
├── src/web/
│   ├── main.py                  # 后端入口，默认监听 8080
│   ├── app/                     # 应用装配、配置、生命周期、公共 HTTP 蓝图
│   ├── contexts/                # 按业务域分包的后端模块
│   ├── shared/                  # 跨域共享能力
│   └── db/                      # ORM / 会话 / 表模型
├── frontend/
│   ├── src/                     # Vue 前端源码
│   ├── package.json
│   └── vite.config.js           # 开发代理 /api -> 127.0.0.1:8080
├── config/                      # 运行配置（默认 config.default.yaml，用户可复制 config.yaml）
├── projects/                    # 本地项目目录，运行时创建
├── pretrained_models/           # 全局预训练模型目录，可选
└── requirements.txt
```

单个项目通常长这样：

```text
projects/<project_name>/
├── project_config.json          # 可选；没有时会用目录名恢复项目信息
├── training/                    # 标准训练数据集
├── videos/                      # 待抽帧视频
├── models/                      # 项目模型目录
├── training_outputs/            # 训练、评估、导出产物
└── temp_tasks/                  # 视频抽帧等临时任务
```

## 数据集格式

训练数据集建议放在 `projects/<project_name>/training/<dataset_name>/`，并使用标准 YOLO 目录：

```text
training/<dataset_name>/
├── dataset.yaml
├── train/
│   ├── images/
│   └── labels/
├── val/
│   ├── images/
│   └── labels/
└── test/                        # 可选
    ├── images/
    └── labels/
```

`dataset.yaml` 至少应包含类别名：

```yaml
names:
  - class_0
  - class_1
```

标注文件使用 YOLO txt 格式：

```text
<class_id> <x_center> <y_center> <width> <height>
```

坐标为归一化值，范围通常是 `0` 到 `1`。

## 本地开发启动

### 1. 安装后端依赖

建议使用 Python 3.10+。

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

如果需要视频抽帧，系统中还应安装 OpenCV 可用的运行库；部分路径会优先使用 `ffmpeg` / `ffprobe` 获取视频信息和抽帧。

### 2. 启动后端

```bash
python3 src/web/main.py
```

后端默认监听（取自 `src/web/app/config.py`）：

```text
http://localhost:8080
```

### 3. 安装并启动前端

```bash
cd frontend
npm install
npm run dev
```

Vite 开发服务会把 `/api` 代理到 `http://127.0.0.1:8080`。启动后访问终端输出的前端地址，通常是：

```text
http://localhost:5173
```

## 运行配置

默认情况下，数据和模型都直接落在本机工作目录：

```yaml
VISION_TRAIN_PROJECTS_DIR=projects
VISION_TRAIN_PRETRAINED_MODELS_DIR=pretrained_models
VISION_TRAIN_DB_DIR=data
VISION_TRAIN_DB_FILENAME=vision-train.db
VISION_TRAIN_HOST=0.0.0.0
VISION_TRAIN_PORT=8080
```

如需自定义目录或端口，直接使用环境变量覆盖：

- `VISION_TRAIN_PROJECTS_DIR`
- `VISION_TRAIN_PRETRAINED_MODELS_DIR`
- `VISION_TRAIN_DB_DIR`
- `VISION_TRAIN_DB_FILENAME`
- `VISION_TRAIN_DB_URL`
- `VISION_TRAIN_HOST`
- `VISION_TRAIN_PORT`
- `VISION_TRAIN_DEBUG`

## 常用工作流

### 创建或选择项目

1. 启动后端和前端。
2. 在左侧项目列表选择已有项目，或通过接口/前端创建项目。
3. 项目会存放在 `projects/<project_name>/`。

### 准备训练数据

1. 将 YOLO 数据集放到 `projects/<project_name>/training/<dataset_name>/`。
2. 确认包含 `dataset.yaml`。
3. 在前端选择项目后，数据集会出现在数据集列表中。

### 预览和编辑标注

1. 选择数据集。
2. 在“数据预览 & 标注”中按 split、类别、是否未标注等条件查看图片。
3. 可读取、保存、删除标注，也可批量自动标注。

### 从视频抽帧

1. 将视频放到 `projects/<project_name>/videos/`。
2. 在前端切换到 Videos 视图。
3. 按时间间隔或目标帧数创建抽帧任务。
4. 将抽出的帧导入指定数据集。

### 启动训练

1. 选择训练数据集。
2. 选择预训练模型或项目已有模型。
3. 设置训练参数并启动训练。
4. 训练状态会通过 `/api/tasks/<task_id>` 轮询更新。
5. 训练产物写入 `projects/<project_name>/training_outputs/`。

### 评估和导出

1. 在训练历史中选择训练 run。
2. 可执行评估，查看指标和示例图。
3. 可导出模型格式，导出结果会打包并提供下载链接。

## 预训练模型

系统会扫描项目模型和全局预训练模型。全局模型目录为：

```text
pretrained_models/
```

如果存在 `pretrained_models/config.yaml`，可按配置暴露模型；也可以直接放置常见权重文件。模型扫描逻辑位于 `src/web/contexts/model/infrastructure/model_gateway.py`。

## API 分组

后端 API 由 `src/web/app/bootstrap.py` 统一注册，各业务接口分布在 `src/web/contexts/*/api/blueprint.py`：

- `/api/projects`、`/api/project/create`：项目扫描和创建
- `/api/datasets`、`/api/dataset/*`：数据集列表、预览、上传、删除、拆分、合并、去重、诊断、下载
- `/api/annotation/*`、`/api/auto_annotate/*`：标注读取、保存、提交和自动标注
- `/api/training/*`：训练启动、停止、状态、历史、继续训练、恢复训练、训练产物
- `/api/models`、`/api/pretrained/*`：模型扫描与预训练模型管理
- `/api/videos`、`/api/video/*`：视频扫描、缩略图、播放、抽帧任务、抽帧导入
- `/api/file`：本地文件访问，用于图片、权重、导出包等下载或预览

## 当前注意事项

- 后端入口是 `src/web/main.py`，默认端口是 `8080`，可通过 `VISION_TRAIN_PORT` 覆盖。
- 数据集配置仅使用 `dataset.yaml`。
- `frontend/src/api/index.js` 中 `deleteTaskImages()` 指向 `/api/video/task/images/delete`，但后端当前提供的是 `/api/video/task/batch_delete`；前端如使用该方法需要修正。
- `/api/file` 会按传入路径返回本地文件，适合本地可信环境使用；不要直接暴露到不可信网络。
- 训练、导出、自动标注和测试推理都是全局状态管理，同一时间通常只适合运行一个对应任务。
- GPU 使用由 Ultralytics 和 `src/web/utils.py` 的设备选择逻辑决定；如果没有 CUDA 或 Apple MPS，会回退到 CPU。

## 开发建议

- 后端新增功能优先放到对应业务域的 `src/web/contexts/<domain>/api|application|domain|infrastructure/` 中。
- 前端 API 调用统一维护在 `frontend/src/api/index.js`。
- 数据集路径尽量保持在 `projects/` 下，避免手动传入不可控的系统路径。
- 运行生成的 `__pycache__/`、`tmp/`、`frontend/dist/`、`frontend/node_modules/` 不应提交到版本库。
