# SOP-1 项目管理

> 在 Vision Train 中**创建、导入、管理、删除**项目。理解目录规范，便于迁移与复用。

## 1.1 项目是什么

Vision Train 的“项目”是 `projects/` 下的一个**目录**。目录名就是项目名（与 `id` 一致），所有数据集、训练产物、模型、视频都以**项目为单位**隔离。

## 1.2 目录规范

```text
projects/<project_name>/
├── training/                  # 可选：YOLO 训练集（每子目录 = 一个数据集）
│   └── <dataset_name>/
│       ├── dataset.yaml       # 必填：类别名/split
│       ├── train/{images,labels}
│       ├── val/{images,labels}
│       └── test/{images,labels}    # 可选
├── training_outputs/          # 可选：训练 / 评估 / 导出产物
│   └── <dataset_name>/<run_id>/
│       ├── args.yaml
│       ├── results.csv
│       ├── weights/{best.pt,last.pt}
│       └── ...
├── videos/                    # 可选：待抽帧的原始视频
│   ├── cam1.mp4
│   └── cam2.mp4
└── .description               # 可选：项目描述（纯文本，仅供 UI 显示）
```

### 标准子目录的语义

| 子目录             | 用途                                       | 由谁写入                    |
| ------------------ | ------------------------------------------ | --------------------------- |
| `training/`        | 已规整的 YOLO 训练集（可被训练）            | 抽帧 / 数据集导入 / 手工放置 |
| `training_outputs/`| 训练 / 评估 / 导出产物（按 dataset 组织）   | 训练任务                     |
| `videos/`          | 待抽帧的原始视频                            | 手工放入                     |

> 新建项目时会**自动初始化**这三个空目录。导入 zip 时如果缺少会自动补齐。

### 项目名规范

- 仅允许：**字母、数字、下划线 `_`、短横线 `-`**
- 长度：**1~64** 字符
- **不以 `.` 开头**
- 不能使用保留名：`.git`、`__pycache__`、`pretrained_models`、`config`

> 如果项目名不符合规范，系统会在创建或重命名时直接提示。

### `.description`（可选）

新建项目时如果填写了描述，会落到 `projects/<name>/.description`。仅纯文本，扫描时不读取，只在 UI 显示。

## 1.3 创建项目

创建项目本质是在 `projects/` 下新建一个符合 §1.2 规范的目录：

- 后端自动建立 `projects/<name>/{training,training_outputs,videos}/` 三个空目录
- 创建后该目录被项目扫描器识别，立即出现在项目列表中（初始数据集数为 `0`）

> 创建项目后，必须**导入数据集**才能开始训练，参见 [SOP-3 数据标注](03-annotation.md)。

## 1.4 导入数据集（zip）

项目建立后，通过 zip 导入数据集。

### 打包方式

把已经规整好的 YOLO 数据集打成 zip：

```bash
# 形态 A：直接对数据集目录打包（推荐）
zip -r my_dataset.zip my_dataset/

# 形态 B：在数据集根目录内打（更通用）
cd path/to/datasets
zip -r my_dataset.zip my_dataset/
```

> ⚠️ 不要用 `zip -r my_dataset.zip datasets/my_dataset/` — 这样 zip 根会多一层 `datasets/`，导入会失败。

### zip 合法形态

- 形态 A：zip 根是**数据集目录**（含 `dataset.yaml` + `train/{images,labels}` + `val/{images,labels}`）
- 形态 B：zip 根是**单一数据集子目录**

### 导入结果

- 数据集落到 `projects/<project>/training/<dataset_name>/`
- 完成后数据集在项目数据集列表中立即可见

## 1.5 编辑 / 重命名

项目支持两种变更：

- **改描述**：写到 `.description`，**仅在 UI 显示**
- **改项目名**：物理**移动目录**，正在训练 / 导出中的任务会受影响

> 两种变更都会触发项目扫描器重新加载。

## 1.6 删除项目

项目删除是**项目级**操作：

- 默认**硬删除**：物理移除整个目录
- 删除范围：所有数据集、训练产物、模型、视频
- **不可恢复**——只删某个数据集请在项目内操作对应数据集卡

> 如想保留历史数据，请先到 [SOP-3 数据标注](03-annotation.md) 中按数据集导出 zip 归档。

## 1.7 选择项目

选中一个项目后，主区会展示该项目下的全部数据集与视频。后续所有 SOP（标注、训练、抽帧、评估…）都依赖"当前项目"上下文。

## 1.8 手工创建（高级）

如果数据已存在于磁盘上，直接创建标准子目录即可（无需写任何元数据文件）：

```bash
mkdir -p projects/my_proj/{training,training_outputs,videos}
# 放入数据
mv /path/to/dataset projects/my_proj/training/
```

刷新项目列表后即可识别。

> **注意**：项目识别现在只看两件事：目录是否位于 `VISION_TRAIN_PROJECTS_DIR` 指定的项目根目录下，以及目录名是否符合项目命名规则。标准子目录会在创建项目时自动建立，不再依赖“看起来像项目”的内容猜测。

## 1.9 常见问题

- **左侧列表不显示我新建的目录？** 确认它位于 `VISION_TRAIN_PROJECTS_DIR` 指定的项目根目录下，且目录名满足项目命名规则；不再要求目录里预先放入特定子目录才会被识别。
- **多用户协作？** 把 `VISION_TRAIN_PROJECTS_DIR` 指到共享盘 / NFS 即可（参见 [运行配置 - projects_dir](deploy/config.md)）。
- **能不能把项目放在其他盘？** 可以，参见 [运行配置](deploy/config.md) 中 `projects_dir` 的用法。
- **zip 导入失败：目录不含标准子目录** — zip 形态不对，请参考 §1.4 重新打包。
- **zip 导入失败：路径非法** — zip 内含 `..` 或绝对路径，被安全规则拒绝。请用干净方式打包。
