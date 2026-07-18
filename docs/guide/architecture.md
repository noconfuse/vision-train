# 产品架构

## 总体结构

![架构总览](../assets/placeholder.svg)

```
┌──────────────────────────────────────────────────────┐
│                    浏览器 (Vue 3)                    │
│  Sidebar / DatasetList / DatasetPreview / Training   │
└──────────┬───────────────────────────────────────────┘
           │ /api/*
┌──────────▼───────────────────────────────────────────┐
│             Vite Dev Server / 静态前端                │
│      开发期代理 /api → 127.0.0.1:8080                │
└──────────┬───────────────────────────────────────────┘
           │ http
┌──────────▼───────────────────────────────────────────┐
│                 Flask Backend                        │
│  app/ → contexts/* → shared/ + db/                  │
└──────────┬───────────────────────────────────────────┘
           │ 本机文件系统
   ┌───────┴────────┐
   │  projects/     │  pretrained_models/
   │  ├ <project>/  │  ├ yolo11n.pt
   │  │  ├ training │  ├ yolov8s.pt
   │  │  ├ videos   │  └ ...
   │  │  └ ...      │
   └────────────────┘
```

## 目录约定

```text
vision-train/
├── src/web/                # 后端代码
│   ├── main.py             # Flask 入口
│   ├── app/                # 应用装配与配置
│   ├── contexts/           # 按业务域分包
│   ├── shared/             # 跨域共享能力
│   └── db/                 # ORM / 会话 / 表
├── frontend/               # 前端
│   ├── src/
│   ├── public/logo.svg
│   └── vite.config.js
├── docs/                   # 本文档（Docsify 源）
├── projects/               # ★ 示例项目根目录（由环境变量指定）
├── pretrained_models/      # ★ 示例预训练模型根目录（由环境变量指定）
├── config/                 # 运行时配置
└── requirements.txt
```

`VISION_TRAIN_PROJECTS_DIR` 与 `VISION_TRAIN_PRETRAINED_MODELS_DIR` 指向**唯一会被改写的数据目录**。文中的 `projects/`、`pretrained_models/` 仅是存储命名空间与示例目录名，不再代表仓库内置默认路径。

## 数据集目录约定

```text
projects/<project_name>/training/<dataset_name>/
├── dataset.yaml            # 唯一的类别/split 声明
├── train/
│   ├── images/
│   └── labels/
├── val/
│   ├── images/
│   └── labels/
└── test/                   # 可选
    ├── images/
    └── labels/
```

`dataset.yaml` 示例：

```yaml
path: .                     # 建议保持相对路径
train: train/images
val: val/images
test: test/images           # 可选
names:
  0: 清扫整理
  1: 装瓶称重
  2: 研磨2mm
```

> 项目同时支持 `dataset.yml` / `dataset.yaml` 两种后缀；`dataset.yaml` 优先。

## 后端模块分工

| 模块                           | 职责                                  |
| ------------------------------ | ------------------------------------- |
| `app/`                         | Flask 装配、配置、生命周期、公共蓝图  |
| `contexts/project`             | 项目扫描、创建、更新、删除            |
| `contexts/dataset`             | 数据集 CRUD、子集/合并/去重/下载      |
| `contexts/annotation`          | 标注读写、自动标注、批量提交          |
| `contexts/training`            | 训练、评估、导出、工作流与产物        |
| `contexts/model`               | 模型扫描、预训练模型状态与下载        |
| `contexts/video`               | 视频扫描、缩略图、抽帧任务、抽帧导入  |
| `contexts/task`                | 通用任务状态、停止、历史              |
| `shared/` + `db/`              | 路径、worker、zip、ORM 与数据库会话   |

## 配置加载顺序（后 → 前覆盖）

1. `src/web/app/config.py` 内置默认值
2. 环境变量 `VISION_TRAIN_*`

详见 [运行配置](deploy/config.md)。
