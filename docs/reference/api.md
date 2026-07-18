# API 参考

> 所有接口均位于 `/api/*`，基于 Flask 蓝图。响应统一 JSON。

## 通用约定

- 成功：`{"success": true, ...data}`
- 失败：`{"success": false, "error": "..."}`
- 文件路径字段（`project_path`、`dataset_path`）使用**项目内相对路径**（如 `my_proj`、`my_proj/training/dataset1`），不带绝对前缀

## 健康检查

### `GET /api/health`

```json
{
  "status": "ok",
  "service": "vision-train",
  "storage": {
    "projects_dir": "/Users/me/vision-train/projects",
    "pretrained_models_dir": "/Users/me/vision-train/pretrained_models",
    "project_root": "/Users/me/vision-train",
    "dataset_config_filename": "dataset.yaml"
  }
}
```

## 项目

### `GET /api/projects`

扫描 `VISION_TRAIN_PROJECTS_DIR` 指定的项目根目录，列出全部项目及子数据集。

```json
{
  "projects": [
    {
      "id": "my_proj",
      "name": "my_proj",
      "path": "my_proj",
      "created_at": "2026-07-09 10:00:00",
      "datasets": [
        { "name": "dataset_v1", "type": "training", "image_count": 1234, ... }
      ]
    }
  ]
}
```

### `POST /api/project/create`

```json
{ "name": "new_proj", "description": "可选" }
```

校验：
- 项目名匹配 `^[A-Za-z0-9_-]{1,64}$`
- 不可与已有项目同名
- 不可使用保留名（`.git` / `__pycache__` / `pretrained_models` / `config`）

### `POST /api/project/update`

修改项目描述 / 重命名：

```json
{ "name": "old_name", "new_name": "new_name", "description": "新描述" }
```

- `new_name` 不传则不改名
- 重命名会同步移动目录与 `project_config.json`

### `POST /api/project/delete`

```json
{ "name": "old_name", "confirm": true }
```

硬删除整个项目目录（含数据集 / 训练产物 / 模型），**不可恢复**。

### `POST /api/project/validate_name`

实时校验项目名是否合法（前端边输入边校验）：

```json
{ "name": "my_proj" }
```

返回：

```json
{ "success": true, "valid": true }
// 或
{ "success": true, "valid": false, "error": "项目 my_proj 已存在" }
```

### `POST /api/project/import`

> ⚠️ 已弃用。改用 `POST /api/dataset/import` 在已存在的项目下导入数据集。

## 数据集

### `POST /api/dataset/import`

上传 zip 导入数据集到指定项目的 `training/<name>/` 目录。

- 方式：`multipart/form-data`
- 字段：
  - `file`（必填）`.zip` 文件
  - `project_path`（必填）项目名
  - `target_name`（可选）重命名数据集

后端支持的 zip 形态：

- 形态 A：根是数据集（含 `dataset.yaml` 或 `train/{images,labels}`）
- 形态 B：根是单一数据集子目录

返回：

```json
{
  "success": true,
  "project": "my_proj",
  "dataset_name": "my_data_v1",
  "dataset": { ... }
}
```

### `GET /api/dataset/info?project_path=...&dataset_name=...`

返回 `image_count`、`class_stats`、`names`、`has_train/val/test` 等。

### `POST /api/dataset/merge`

合并两个数据集到新数据集。Body：

```json
{
  "project_path": "my_proj",
  "dataset_a": "ds1",
  "dataset_b": "ds2",
  "new_dataset_name": "ds1_plus_ds2"
}
```

### `POST /api/dataset/augment_subset`

弱类补偿采样，详见 [SOP-5](../sop/05-class-rebalance.md)。

### `POST /api/dataset/reorder_labels`

```json
{ "project_path": "...", "dataset_name": "...", "order": [2, 0, 1], "splits": ["train","val"] }
```

### `POST /api/dataset/delete_label`

按 class id 或 class name 删除某类。

### `GET /api/dataset/download?project_path=...&dataset_name=...`

下载 zip 压缩包。

## 标注

### `GET /api/annotation?dataset_path=...&split=train&limit=200&offset=0`

返回图片列表与每张图的标签。

### `POST /api/annotation/save`

```json
{
  "dataset_path": "my_proj/training/ds1",
  "image": "img_0001.jpg",
  "split": "train",
  "annotations": [
    { "class_id": 0, "x_center": 0.5, "y_center": 0.5, "width": 0.2, "height": 0.3 }
  ]
}
```

### `POST /api/auto_annotate/run`

```json
{
  "dataset_path": "...",
  "imgsz": 640,
  "conf": 0.25,
  "iou": 0.45,
  "max_det": 300,
  "only_unan": true
}
```

## 训练

### `POST /api/training/start`

```json
{
  "project_path": "my_proj",
  "dataset_name": "ds1",
  "model_name": "yolo11n.pt",
  "training_config": {
    "epochs": 100,
    "imgsz": 640,
    "batch": 16,
    "cos_lr": true,
    "imbalance_optimization": false
  }
}
```

### `GET /api/tasks/<task_id>`

读取任务详情与当前状态，适用于训练、评估、导出、推理、抽帧等所有长任务。

### `POST /api/tasks/<task_id>/stop`

向长任务发送停止请求。训练、推理、抽帧等可停止任务统一走这个入口。

### `GET /api/training/workflows?project_path=...&dataset_name=...`

列出当前项目或数据集下的训练工作流记录。每条工作流会聚合训练、校准、评估、导出等子任务。

### `GET /api/training/metrics_history?task_id=...`

读取某个训练任务的指标曲线历史。

### `POST /api/training/start_evaluate`

```json
{ "project_path": "...", "dataset_name": "...", "task_id": "..." }
```

## 模型

### `GET /api/models?project_path=...`

列出全局 + 项目内全部模型。

### `POST /api/training/export`

```json
{
  "project_path": "my_proj",
  "task_id": "20260709_120000",
  "format": "openvino",
  "int8": true,
  "imgsz": 640
}
```

## 视频

### `GET /api/videos?project_path=...`

### `POST /api/video/extract`

```json
{
  "project_path": "my_proj",
  "video_name": "cam1.mp4",
  "target_dataset": "cam1_frames",
  "strategy": "interval",   // or "count"
  "value": 1.0
}
```

### `GET /api/video/tasks?project_path=...`

### `DELETE /api/video/task`

## 文件

### `GET /api/file?path=projects/my_proj/training/ds1/train/images/001.jpg`

直接返回文件流（受配置的根目录保护）。

## 错误码

后端不会主动返回 4xx 状态码（Flask 默认），但 JSON 内的 `error` 字段会说明原因。如需 HTTP status，自行 wrapper。
