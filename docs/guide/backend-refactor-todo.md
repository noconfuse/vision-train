# 后端最终重构 TODO

## 执行规则

- 这份文档现在是后端职责收敛的唯一 TODO 真源。
- 后续每次复扫，不再从头口头汇总；先把新发现写进这份文档，再按文档逐项处理。
- 每次提交结果时，必须同时更新三类状态：
  - `已完成`
  - `进行中`
  - `待处理`
- 新发现的问题如果属于已有职责类型，直接追加到对应条目下，不新建散乱笔记。
- 只有在当前 TODO 清空或出现全新职责类型时，才允许做新的系统性复扫。

## 当前执行面板

### 已完成

- [x] 删除 `model/application/use_cases.py` 整层薄包装，`model/api/blueprint.py` 已直连真实实现
- [x] 删除 `training/application/use_cases.py` 中一批工作流、续训、测试推理单跳代理
- [x] 删除 `video/application/use_cases.py`，`video/api/blueprint.py` 已直连基础设施实现
- [x] 删除 `video_runtime.py` 中 `get_video_project_name`、`get_video_thumbnail_dir` 两个路径壳
- [x] 新增 [path_utils.py](file:///Users/baolei/workspace/vision-train/src/web/shared/utils/path_utils.py) 的 `resolve_safe_child_path()`，收口安全子路径拼接
- [x] 新增 [project_paths.py](file:///Users/baolei/workspace/vision-train/src/web/contexts/project/infrastructure/project_paths.py) 的 `get_project_video_thumbnails_dir()`
- [x] `video_access.py` 已改为直连共享/项目路径协议，不再自带本地 `_resolve_safe_child_path`
- [x] `dataset/use_cases.py` 已删除 `list_datasets`、`ensure_import_job`、`generate_import_stream` 三个空壳
- [x] `dataset/api/blueprint.py` 已改为直连 `scan_project_datasets` 与 import runtime
- [x] `dataset/use_cases.py` 中多处 `realpath + startswith(...)` 已改为统一走 `is_within_path()`
- [x] 新增 [fs_utils.py](file:///Users/baolei/workspace/vision-train/src/web/shared/utils/fs_utils.py) 的 `remove_tree()`，统一目录树删除
- [x] `dataset_layout.py`、`dataset_labels.py`、`training/evaluate_runtime.py`、`training/execution_support.py` 已回收至 `yaml_utils.py`
- [x] `training` 启动链中错误依赖 `workflow_state.project_name_from_path` 的旧壳引用已清理
- [x] 后端已通过虚拟环境启动验证，`/api/health` 返回 `200 OK`
- [x] `video_execution_gateway.py` 已改用 `get_project_task_images_dir()`，不再手拼任务图片目录
- [x] `training/start_training()` 与 `_validate_training_config()` 已并回基础设施，蓝图与续训链直连 `start_training_task()`
- [x] `dataset_augmentation.py`、`dataset_import_yolo.py`、`dataset_import_formats.py`、`dataset_mutations.py`、`model_catalog.py`、`model_gateway.py`、`openvino_gateway.py`、`inference_tool.py` 已回收至 `yaml_utils.py`
- [x] `dataset/use_cases.py` 的上传重名规避逻辑已下沉到 `fs_utils.allocate_nonconflicting_path()`
- [x] `dataset/use_cases.py` 的图片与标签删除已改为复用 `fs_utils.remove_file_silent()`
- [x] 删除 `training/application/use_cases.py` 剩余查询与重试中间层，训练蓝图已直连基础设施与 presenter
- [x] `retry_training_run()` 已并回 `execution_starters.py` 的真实启动入口，不再保留 application 壳
- [x] `video_execution_gateway.py` 最后一个项目视频路径拼接已改为 `get_project_video_path()`
- [x] 除 `yaml_utils.py` 外，代码库内已无新的 `yaml.safe_load/safe_dump` 散点
- [x] `dataset/use_cases.py` 的去重摘要计算已下沉到 `fs_utils.compute_file_md5()`
- [x] 新增 `task_runtime.list_project_tasks()` / `find_latest_project_task()`，训练与标注链路不再散落 `project_name + list_tasks + Python 过滤`
- [x] 新增 `path_utils.resolve_allowed_file_path()`、`validate_filename()`、`build_file_item()`、`slice_items()`，统一路径边界、文件名与列表 DTO 原语
- [x] 新增 `fs_utils.remove_path_silent()` 与 `name_utils.validate_token_name()`，继续收口 file/dir 删除和名称规则
- [x] `model_catalog.py` 已成为 OpenVINO metadata 与 `pretrained_models/config.yaml` 读取的统一入口
- [x] `training/query_gateway.py` 已承接训练产物、导出记录与最近训练任务查询装配，`training/api/blueprint.py` 不再堆积查询链路
- [x] `dataset_repository.py` 已提供单数据集摘要查询，导入链路不再为单项结果复用全量扫描
- [x] `auth/project/model/task/training/video/dataset_import` 本轮新增薄包装与纯转发路由已全部删除或直连真实实现
- [x] `app/http.py` 已提供共享 HTTP 参数绑定工厂，`model/project/auth/dataset` 蓝图中的取参与直调空壳已回收到统一入口
- [x] `training/api/blueprint.py` 已完成声明式参数绑定收口：大多数 route 已改为 `json_body_endpoint/query_params_endpoint`，仅保留 `continue/resume/model_export_bundle` 这类确有编排或文件响应语义的接口
- [x] `training/infrastructure/execution_support.py` 已删除本地 `generate_dataset_yaml()` 双轨入口，训练链路改为直接复用 dataset 域的标准 `dataset.yaml` 补写能力
- [x] `shared/utils/path_utils.py` 已补目录版安全原语与相对路径回推原语，`training/dataset` 下载、删除、路径回推里的手写 `realpath + is_within_path + relpath` 与 bundle name 清洗已收口
- [x] `annotation/api/blueprint.py` 已完成声明式参数绑定收口：缺图/待确认列表、自动标注、读取/保存/提交接口均已切到共享绑定工厂
- [x] `task/api/blueprint.py` 的 `/api/tasks` 已切到 `query_params_endpoint(...)`，任务查询入口不再保留手写 query 参数装配样板
- [x] `video/api/blueprint.py` 已完成声明式参数绑定收口：视频列表、上传、删除、抽帧、任务图片导入/删除接口已切到共享绑定工厂，仅保留文件响应类路由
- [x] 压缩包上传名与数据集名推导已下沉到共享路径原语：`dataset/application/use_cases.py` 不再手写 `.zip` 校验与 `basename/splitext` 推导
- [x] `model/infrastructure/model_gateway.py` 已补统一模型展示项 builder：全局预训练、项目模型、训练产物不再分别手写 `{name,type,path,size,...}` DTO
- [x] ZIP 目录打包能力已下沉到 `shared/utils/zip_utils.py`，`shared/infra/zip_download.py` 现仅保留 HTTP 发送与响应后清理
- [x] 已新增 `shared/utils/value_utils.py` 的 `require_present()`，并替换 `video/training/annotation/dataset` 一批散落的“缺参守卫”，把参数必填校验收口为共享原语
- [x] `app/http.py` 已补齐声明式参数 schema 与读参助手：`param()/ParamSpec`、`query_params()/json_body_params()/form_body_params()` 统一承接 `query/json/form/files` 的别名、必填、默认值、类型转换；各上下文蓝图与文件响应/SSE 路由的接口参数绑定已切到这套协议
- [x] 已删除 `project_repository.looks_like_project()` 的目录内容猜测逻辑：项目识别现在仅依赖 `PROJECTS_DIR` 根目录位置与合法项目名，不再根据子目录“看起来像项目”做模糊判断
- [x] 统一展示型文件结果 builder：已新增 `shared/utils/path_utils.py` 的 `build_file_items()`，`training/presenters.py`、`video/infrastructure/video_access.py`、`annotation/infrastructure/annotation_io.py`、`dataset/application/use_cases.py` 的文件列表 DTO 组装已收口到共享原语
- [x] 导入 SSE 的 JSON 文本序列化已并入 `shared/utils/json_utils.py`：`dataset_import_runtime.py` 已改为复用 `encode_json()`，代码库内 `json.dumps(...)` 仅保留统一 JSON 工具入口自身
- [x] `shared/utils/path_utils.py` 的 `resolve_storage_path()` 已删除 `PROJECTS_DIR + exists` 的磁盘探测式语义分流：无前缀相对路径现在统一按仓库相对路径解释，项目存储路径必须显式走 `projects/...` 前缀或 `resolve_project_path()` 协议
- [x] `dataset/infrastructure/dataset_import_formats.py` 已删除递归猜根式 `find_dataset_format_root()`：zip 导入现在只允许“数据集根目录本身”或“仅包一层目录”的显式包装规则，格式识别只在该根目录执行
- [x] `dataset/infrastructure/dataset_import_formats.py` / `dataset_import_yolo.py` 已删除数据集格式与 YOLO split 布局的启发式兜底：格式识别不再向下探测子目录，YOLO `path/train/val/test` 解析改为按配置唯一推导并对缺失目录显式报错
- [x] `dataset/infrastructure/dataset_repository.py` 的 `resolve_project_dataset_root()` 已删除“候选集 + exists” 命中：`dataset_name` 与 `dataset_path` 现改为独立解析，双字段并存时必须指向同一真实目录，否则显式报错
- [x] `task` / `training` 已建立对外 DTO presenter：`/api/tasks` 与 `/api/training/workflow(s)` 现统一通过 presenter 把 `project_path/dataset_path` 映射为存储引用，原始绝对路径仅保留在仓储 / worker 内部链路
- [x] `training/presenters.py` 已承接 workflow 对外 DTO 映射：`workflow_repository.py` 不再直接把 `workflow_state.py` 聚合结果裸返回，workflow 顶层与嵌套 task 列表的路径字段已统一走 presenter 协议
- [x] `dataset/infrastructure/dataset_repository.py` 的 `scan_project_datasets()` 已改回协议式枚举：当前只要目录存在标准配置 `dataset.yaml` 就纳入数据集列表，`train/val/test` 完整性仅作为摘要字段返回，不再由 repository 决定“算不算数据集”
- [x] `project/infrastructure/project_paths.py` 已收缩为核心项目路径原语：删除数据集 split/image/label、视频文件/缩略图、训练输出与临时任务等叶子薄包装，调用方改为“项目根目录原语 + 域内 layout/helper”组合
- [x] 存储根目录配置已收口为环境变量唯一基准：`PROJECTS_DIR`、`PRETRAINED_MODELS_DIR` 现仅由 `VISION_TRAIN_PROJECTS_DIR`、`VISION_TRAIN_PRETRAINED_MODELS_DIR` 提供；配置层默认兜底与启动脚本隐式回退已删除，`projects/...`、`pretrained_models/...` 仅保留为存储引用协议前缀

### 当前状态

- [x] 当前执行面板已清空

## 本轮全量复扫新增待办

### P0 立即收口

- [x] 删除 `training/application/use_cases.py` 已完成后遗留思路的同类点，继续避免在 `blueprint` 内堆积查询装配，考虑补真实 `training query` 入口收口“任务 -> output_dir -> artifacts/export records”链路
- [x] 收口 `task` 查询原语，替代各域散落的 `project_name_from_path + list_task_items + Python 过滤`
- [x] 删除 `annotation_io.remove_file_if_exists()`，统一改用 `fs_utils.remove_file_silent()`
- [x] 为路径边界校验补统一原语，收掉 `file_blueprint._resolve_file_path()`、`dataset_repository.resolve_project_dataset_root()`、`annotation/batch_helpers.list_batch_image_paths()` 中分散的 `startswith/commonpath/realpath` 判定
- [x] 把 `app/config.py` 中手写字符串布尔解析改为统一走 `value_utils.parse_bool()`

### P1 高优先

- [x] 收口 OpenVINO 两套解析入口：合并 `model_catalog.py` 与 `openvino_gateway.py` 中重复的 `xml` 选择与 `metadata.yaml` 读取
- [x] 收口 `pretrained_models/config.yaml` 两套读取入口：统一 `inference_tool.py` 与 `model_gateway.py` 的配置归一逻辑
- [x] 把 `evaluate_runtime.load_training_dataset_yaml()` 并回 `dataset_schema.py`，避免 training 再维护一套 dataset 配置入口
- [x] 为共享层补 `remove_path_silent(path)`，收口 `export_gateway.delete_export_task()`、`project_repository.delete_project()`、`dataset_import.run_import_job()` 的 file/dir 删除分支
- [x] 收口 `video_file_gateway._resolve_upload_name()`，避免视频文件名规则继续绕开 `path_utils.validate_leaf_name()`

### P1 薄包装与单跳代理

- [x] 删除 `auth/application/use_cases.py` 中 `auth_enabled()`、`bootstrap_auth_admin()` 这类单跳代理
- [x] 收口 `auth/api/blueprint.py` 中纯转发路由：`api_auth_status()`、`api_logout()`、`api_me()`、`api_list_users()`、`api_delete_user()`
- [x] 收口 `project/api/blueprint.py` 中纯转发路由 `api_projects()`
- [x] 收口 `model/api/blueprint.py` 中纯转发路由 `api_pretrained_options()`
- [x] 收口 `training/api/blueprint.py` 中纯转发路由 `api_training_runtime_profile()`、`api_training_metrics_history()`
- [x] 收口 `task/api/blueprint.py` 中纯转发路由 `api_task_stop()`
- [x] 删除 `video_task_gateway.list_extraction_tasks()` 这类只做 `project_name` 转换的单跳代理
- [x] 删除 `dataset_import.generate_import_events()` 这类仅转发到 `stream_import_events()` 的壳函数

### P2 查询装配与 DTO 拼装

- [x] 评估 `training/api/blueprint.py` 中训练产物、导出记录、最近训练任务查询是否应整体下沉为真实 `query service`
- [x] 收口文件列表 DTO 原语，减少 `dataset/use_cases.py`、`annotation/annotation_io.py`、`video/video_access.py` 中重复的 `url/path/name/items/total` 拼装
- [x] 收口展示型 URL 拼装，避免 repository/use_case 直接输出展示 DTO
- [x] 为数据集提供“单数据集摘要查询”能力，减少 `scan_project_datasets(project)` 被当作单项查询的全量扫描式复用

### P2 路径协议与命名规则

- [x] 继续压缩业务层对 `"images" / "labels" / ".thumbnails"` 等字面量目录协议的直接感知，统一走 `project_paths.py` 与 `dataset_layout.py`
- [x] 评估抽出 `dataset_path_utils`，统一 dataset/training 之间的 YAML 路径引用、split 引用归一化
- [x] 统一 `project/dataset/video` 三处名称校验的公共约束，减少正则、长度、stem 校验各写一套
- [x] 收口 `project_repository.py` 里直接 `basename(project_path)` 的项目名提取，统一走 `path_utils.project_name_from_path()`

### 文档规则

- [x] 后续若开始处理本节任一项，先把该项移入“当前执行面板”，处理完成后再移入“已完成”

## 本次复扫新增待办

### P0 立即收口

- [x] 收口 `task/api/blueprint.py` 的任务查询参数装配：把 `status=active` 语义转换、`include_archived/archived_only` 布尔解析、`limit` 默认值与 detail not-found 判定下沉到 task 查询入口，避免 Blueprint 继续拼查询语义
- [x] 继续下沉 `training/api/blueprint.py` 中 workflow / artifact 查询装配：把 `project_path/workflow_id/task_id/training_id` 兼容、`include_archived/archived_only` 默认值与 not-found 判定并入真实 query gateway，避免训练 Blueprint 继续堆积查询链路
- [x] 清理删除原语残留：将 `dataset_import_runtime.py`、`dataset_labels.py`、`dataset_import_yolo.py`、`batch_probe.py` 中剩余的 `os.remove/shutil.rmtree` 全部改为共享 `fs_utils` 删除原语
- [x] 统一视频上传返回路径协议：`video_file_gateway.save_uploaded_video()` 仍返回手写 `relpath`，需要改为共享 `storage_path_ref()`，避免接口层路径引用格式继续分叉

### P1 高优先

- [x] 扩展共享文件 DTO 原语：覆盖 `name/url/path/size_bytes/relative_path`，再替换 `training/presenters.py`、`video/video_access.py` 中手写文件展示项拼装，避免同类 DTO 再分叉
- [x] 收口上传文件命名校验：`dataset/application/use_cases.py` 的图片上传仍手写 `basename + 扩展名` 过滤，`video_file_gateway.py` 仍保留 `_resolve_upload_name()` 薄包装，需要统一到共享文件名校验协议
- [x] 继续下沉 dataset 配置写回链路：`dataset/application/use_cases.py` 中标签重排、标签删除、tags 更新仍手动定位 `dataset.yaml` 并直接读写，需收口到 `dataset_schema/repository` 真实入口

### P2 进一步收口

- [x] 删除 `app/file_blueprint.py` 中 `_resolve_file_path()` 单跳代理，路由直接调用 `resolve_allowed_file_path()`，避免文件访问入口保留无业务价值的薄包装

## 新一轮复扫新增待办

### P0 立即收口

- [x] 收口认证失败返回协议：`auth/api/decorators.py` 与 `app/lifecycle.py` 仍手写 `{"success": False, "error": ..., "code": ...}` 包体，需要统一到单一错误响应来源，避免未登录/无权限响应继续散落

### P1 高优先

- [x] 为数据集摘要补唯一组装入口：`dataset_repository.py` 中 `scan_project_datasets()` 与 `get_project_dataset_summary()` 仍重复展开同一批摘要字段，需要收口成单一 builder，避免字段演进漂移
- [x] 收口 `dataset.yaml` 的结构级写回策略：当前 `dataset_layout.py`、`dataset_mutations.py`、`dataset_schema.py`、`dataset_labels.py` 分别写回 `train/val/test`、`names/nc/tags` 等结构，需要统一到单点协议，而不是只统一底层 YAML IO
- [x] 删除 `delete_dataset_image()` 中字符串切片式路径兜底：改为纯 `resolve_storage_path + is_within_path + relpath` 协议，避免图片删除链保留非标准路径推断逻辑

### 暂不处理

- [ ] `inference_tool.py` 相关收口项暂不关注；后续复扫与落实时先忽略这条，除非你再单独点名处理

## 本轮深度复扫新增待办

### P0 立即收口

- [x] 修复 `task` 域项目过滤语义回退：`task_runtime.list_project_tasks()` 当前仅按 `project_name` 查询，丢失 `project_path` 精确过滤；需要恢复以 `project_path` 为准，避免同名项目间 task/workflow/artifact 串查
- [x] 统一 `/api/tasks` 的项目参数装配：`task/api/blueprint.py` 仍把 `request.args["project_path"]` 原样传给 `list_task_items()`，需要与 `training/video` 保持一致，先走 `resolve_project_path()` 再查询
- [x] 为训练产物查询补齐任务归属校验：`training/query_gateway.py` 中 `get_training_run_artifacts()`、`get_training_artifacts()`、`get_training_model_exports()` 命中 `task_id` 后必须校验 `task.project_path == project_path`，禁止跨项目读到别的任务产物
- [x] 统一训练链路的 `dataset.yaml` 写回协议：`training/infrastructure/execution_support.py` 中 `normalize_dataset_yaml_in_place()`、`generate_dataset_yaml()` 仍直接 `save_yaml_file()` 且自行处理 `path/split/names`，需要改为统一走 `dataset_schema.save_*`，避免训练链路旁路标准结构写回
- [x] 统一 API 路径引用协议：禁止继续在返回 DTO 中暴露绝对路径；`annotation/application/use_cases.py` 的 `label_path`、`training/presenters.py` 的 `export_dir/export_path/primary_model_path`、`model_catalog.py/model_gateway.py` 的模型 `path` 都要改为 `storage_path_ref()` 或统一文件 DTO

### P1 高优先

- [x] 收口 `training` 查询型薄包装：`training/api/blueprint.py` 与 `training/infrastructure/query_gateway.py` 里仍有一批“取参后直调 repository/runtime/presenter”的查询链，需要继续删除单跳代理，压缩 route -> query_gateway -> repo 的薄层
- [x] 收口 `task` 查询/详情薄包装：`task/api/blueprint.py` 的 `api_task_detail`、`/stop` 直连转发明显，`task_runtime.py` 中 `get_task_detail()`、`list_project_tasks()`、`find_latest_project_task()` 也存在别名式包装，需要继续精简公共原语
- [x] 收口下载/SSE/bundle 特殊接口的错误响应：`dataset/api/blueprint.py` 的 download / import SSE、`training/api/blueprint.py` 的 model export bundle 仍手写 `jsonify({"success": False, ...})`，需要补单一错误响应辅助层而不是蓝图散写
- [x] 删除 `dataset_layout.py` 与 `dataset_schema.py` 的标准 `dataset.yaml` builder 双轨：`build_standard_dataset_yaml()/write_dataset_yaml()` 与 `dataset_schema.build/save_*` 已形成重复职责，需要只保留一个标准构造/写回入口
- [x] 统一文件类 DTO 协议：数据集图片列表、上传结果、批量删除结果、训练导出结果目前仍存在 `URL-only / path-only / build_file_item` 多套返回结构，需要统一 presenter/DTO 原语
- [x] 收口 `video_access.py` 中路径空壳包装：`resolve_thumbnail_path()`、`resolve_video_stream_path()`、`resolve_task_image_path()` 仍只是 `project_paths + resolve_safe_child_path` 的单跳壳函数，应直接复用共享路径协议
- [x] 收口 `model/project/auth/dataset` 蓝图中的剩余薄包装：`model/api`、`project/api`、`auth/api`、`dataset/api` 仍有一批“取参后直调 use case/gateway”的轻薄路由，需要统一评估哪些保留 HTTP 绑定价值，哪些应删除
- [x] 收口 `resume_utils.py` 的简单续训代理：`resolve_task_resume_weight()`、`find_latest_resumable_training_task()` 仍偏别名式查询包装，可并回 task/training 真实查询服务

### P2 进一步收口

- [x] 收口 JSON 文件读写入口：`batch_probe.py`、`training/calibration_runtime.py`、`training/execution_starters.py`、`dataset_import_formats.py` 仍手写 `open()+json.load/dump`，需要补 `shared/utils/json_utils.py` 作为全局唯一 JSON 文件读写原语
- [x] 收口 zip 安全解压原语：`dataset_import_formats.safe_extract_zip()` 仍局部实现 `..` / 绝对路径检查，应下沉到共享层统一 zip 成员路径校验与解压策略
- [x] 评估把 `training/infrastructure/execution_support.py` 中 `_normalize_dataset_split_value()` 下沉到共享路径层，统一“绝对路径 rebasing 为相对 dataset/storage 引用”的协议

## 本轮全面复扫新增待办

### P0 立即收口

- [x] 收口 `training/api/blueprint.py` 的请求装配薄包装：当前仍大面积手写 `request.get_json()/args`、`resolve_project_path()`、`parse_bool()`、默认值与 not-found 判定；需要像 `dataset/model` 一样统一切到 `app/http.py` 的参数绑定工厂，压缩 route 层样板
- [x] 删除 `training/infrastructure/execution_support.py` 中残留的 `generate_dataset_yaml()` 弱化协议入口：训练链路仍自行扫描 label 并生成最小 `dataset.yaml`，与 `dataset_schema.py` / `dataset_import_yolo.ensure_dataset_yaml()` 形成双轨；需要只保留一个标准 dataset 协议入口
- [x] 为共享路径层补目录版安全原语：`training/api/blueprint.py` 的导出目录下载、`dataset/application/use_cases.py` 的下载/删除/路径回推仍散落 `realpath + is_within_path + relpath` 与 bundle name 清洗；需要在 `shared/utils/path_utils.py` 增加目录版 `resolve_allowed_*`、相对路径回推与包名清洗原语

### P1 高优先

- [x] 收口 `annotation/api/blueprint.py` 的请求装配薄包装：缺图/待确认列表、单图读取、自动标注、保存/提交接口仍在蓝图内重复做 query/body 取参、分页默认值与必填校验，需要对齐 `http.py` 绑定工厂
- [x] 收口 `video/api/blueprint.py` 的请求装配薄包装：视频列表、上传、删除、抽帧、任务图片导入/删除等接口仍手写 `resolve_and_validate_project()`、`request.get_json()/args/form` 与轻量结果组装，需要与其他已收口蓝图统一
- [x] 收口 `task/api/blueprint.py` 的 `/api/tasks` 查询装配：该路由仍手写 query 参数抽取后直调 `list_task_items()`，应改成 `query_params_endpoint(...)`，避免任务查询入口继续保留样板
- [x] 统一压缩包上传名与数据集名推导协议：`dataset/application/use_cases.py` 仍手写 `.zip` 扩展名校验、`basename/splitext` 推导与目标名冲突检测；需要下沉到共享文件名/归档校验原语，避免上传入口继续散落规则
- [x] 统一模型列表 DTO builder：`model/infrastructure/model_gateway.py` 的全局预训练扫描、项目模型扫描、训练产物扫描仍分别手写 `{name,type,path,size,...}` 拼装；需要收成唯一模型展示项构造入口，避免字段协议再漂移

### P2 进一步收口

- [x] 统一 ZIP 打包能力归属：当前 ZIP 解压已在 `shared/utils/zip_utils.py`，但目录打包仍放在 `shared/infra/zip_download.py`；可考虑把 `build_directory_zip()` 下沉到 `zip_utils.py`，让 `zip_download.py` 仅保留 HTTP 发送与响应后清理
- [x] 评估统一展示型文件结果 builder：已新增共享 `build_file_items()` 原语，并替换 `training/presenters.py`、`video/infrastructure/video_access.py` 等文件的列表型展示 DTO 组装
- [x] 评估把导入 SSE 的 `json.dumps(...)` 文本序列化并入 `shared/utils/json_utils.py`：`dataset_import_runtime.py` 已切到统一 `encode_json()` 入口

## 本轮一致性复扫新增待办

### P0 立即收口

- [x] 删除 `shared/utils/path_utils.py` 中 `resolve_storage_path()` 的磁盘探测式语义分流：无前缀相对路径不再通过 `PROJECTS_DIR + exists` 判定语义，现已统一按显式存储前缀、绝对路径或仓库相对路径协议解析
- [x] 删除 `dataset/infrastructure/dataset_import_formats.py` 的目录内容猜测式导入根定位：`find_dataset_format_root()` 已删除，zip 导入根目录现只按“数据集根目录本身”或“单层包装目录”规则解析
- [x] 删除 `dataset/infrastructure/dataset_import_formats.py` / `dataset_import_yolo.py` 中对数据集格式与 split 布局的启发式兜底：`detect_dataset_format()`、`_resolve_yolo_split_dirs()`、`_resolve_yolo_label_dir()` 已改为显式根目录规则与配置驱动的唯一解析

### P1 高优先

- [x] 收口 `dataset/infrastructure/dataset_repository.py` 的数据集标识解析协议：`resolve_project_dataset_root()` 已改为独立解析 `dataset_name/dataset_path`，双字段并存时必须一致，禁止“候选集 + exists” 命中
- [x] 收口任务 / 工作流的路径输出源头：`task/presenters.py` 与 `training/presenters.py` 已接管 `/api/tasks`、`/api/training/workflow(s)` 的对外 DTO 映射，`project_path/dataset_path` 现统一输出为存储引用，原始绝对路径仅保留内部运行链路
- [x] 收口训练工作流聚合 DTO：`training/infrastructure/workflow_repository.py` 已通过 `training/presenters.py` 统一映射 workflow 顶层字段与嵌套 task 列表，不再直接裸返回 `workflow_state.py` 的聚合结果

### P2 进一步收口

- [x] 评估 `dataset/infrastructure/dataset_repository.py` 的“可用数据集”判定标准：`scan_project_datasets()` 已改为仅以标准配置 `dataset.yaml` 作为数据集纳入条件，完整性状态只保留在摘要字段中
- [x] 评估 `project/infrastructure/project_paths.py` 的纯路径拼接薄包装：`project_paths.py` 已缩减到训练/模型/视频/数据集/任务等核心目录原语，叶子级路径包装已删除并回归域内 layout/helper

## 文档目的

这份文档不再讨论“渐进收口”方案，而是直接以最终目标架构为准，整理后端重构待办。

本次重构目标明确为：

1. 废弃全局 `routes / managers / core` 横切式组织方式
2. 改为“按业务域分包，域内再分层”的模块化单体
3. 建立稳定的单向依赖关系，彻底消除 `core` 膨胀和层次穿透

---

## 最终目标

### 顶层原则

- 顶层按业务域拆包，不再按技术层全局横切
- 每个业务域内部统一拆分为：
  - `api`
  - `application`
  - `domain`
  - `infrastructure`
- 全局只保留极少量 `shared`，且必须是纯公共能力
- 删除全局 `core/`
- 删除全局 `managers/` 作为模糊业务层的角色

### 目标目录

```text
src/web/
├── app/
│   ├── bootstrap.py
│   ├── flask_app.py
│   └── config.py
├── shared/
│   ├── kernel/
│   │   ├── errors.py
│   │   ├── result.py
│   │   └── types.py
│   ├── utils/
│   │   ├── path_utils.py
│   │   ├── yaml_utils.py
│   │   └── file_utils.py
│   └── infra/
│       ├── task_bus.py
│       ├── worker_runner.py
│       └── storage.py
├── contexts/
│   ├── project/
│   ├── dataset/
│   ├── annotation/
│   ├── video/
│   ├── training/
│   ├── task/
│   └── auth/
└── main.py
```

### 每个业务域的标准内部结构

```text
contexts/<domain>/
├── api/
├── application/
├── domain/
└── infrastructure/
```

---

## 依赖规则

### 必须遵守

- `api` 只能依赖本域 `application` 和少量 `shared.kernel`
- `application` 负责用例编排，可以调本域 `domain` 和本域 `infrastructure`
- `domain` 只能写业务规则，不允许依赖 Flask、SQLAlchemy、YOLO、OpenVINO、ffmpeg、TaskManager
- `infrastructure` 才能接触数据库、文件系统、模型推理、训练框架、子进程
- 域与域之间不允许直接穿透 `domain` 或 `infrastructure`
- 跨域调用只能通过对方 `application` 暴露的用例接口

### 明确禁止

- route 直接 import 全局 `core.*`
- `core -> managers` 反向依赖
- 任意模块直接 `TaskManager.create/update`
- 在 route 里拼接复杂返回结构
- 在多个文件里重复手写 `project_path/training/dataset_name`

---

## 重构总策略

### 核心决策

- 不做局部修补
- 不再试图给 `core` 继续减负
- 直接以目标结构重建后端目录
- 用“迁移 + 替换 + 删除旧目录”的方式完成切换

### 迁移顺序原则

- 先搭新骨架，再迁旧逻辑
- 先建立边界，再迁实现
- 先迁最重的业务域，再清理共享能力
- 最后统一删除旧 `routes / managers / core`

---

## P0 目标骨架

### 1. 建立新目录骨架

- 新建：
  - `src/web/app/`
  - `src/web/shared/kernel/`
  - `src/web/shared/utils/`
  - `src/web/shared/infra/`
  - `src/web/contexts/project/`
  - `src/web/contexts/dataset/`
  - `src/web/contexts/annotation/`
  - `src/web/contexts/video/`
  - `src/web/contexts/training/`
  - `src/web/contexts/task/`
  - `src/web/contexts/auth/`
- 每个 domain 下补齐：
  - `api/`
  - `application/`
  - `domain/`
  - `infrastructure/`

### 2. 建立统一的应用装配入口

- 新建 `app/bootstrap.py`
- 新建 `app/flask_app.py`
- 把蓝图注册从旧 `routes/__init__.py` 迁移到 `app/bootstrap.py`
- 让 `main.py` 只保留应用启动入口

### 3. 建立统一错误与响应模型

- 把当前 API 错误包装逻辑迁移到：
  - `shared/kernel/errors.py`
  - 各域 `api` 的 presenter/response mapper
- 不再把 HTTP 响应装饰器混入所谓 `core`
- 明确区分：
  - 领域错误
  - 应用错误
  - HTTP 响应映射

### 4. 建立统一任务执行基础设施

- 把 worker 启动、停止、日志路径、stop signal 逻辑收口到 `shared/infra/worker_runner.py`
- 把任务状态持久化能力收口到 `contexts/task/infrastructure/`
- 禁止其它域直接管理进程细节

---

## P1 共享层治理

### 5. 清空全局 `core` 的职责，按性质迁移

- 迁移纯公共工具到 `shared/utils/`
- 迁移进程与存储访问到 `shared/infra/`
- 迁移领域逻辑到各自 `contexts/*/domain/`
- 迁移应用编排到各自 `contexts/*/application/`
- 迁移返回结构组装到各自 `contexts/*/api/`

### 6. 收口路径与 YAML 能力

- 将路径工具统一收口到：
  - `shared/utils/path_utils.py`
- 将 YAML 读写与 names 解析统一收口到：
  - `shared/utils/yaml_utils.py`
- 所有域统一通过共享工具处理：
  - 项目路径解析
  - 数据集根目录定位
  - `dataset.yaml` 读写
  - `names` 规范化

### 7. 建立统一文件系统与压缩能力

- 将 zip 打包、临时文件清理、安全路径校验迁移到：
  - `shared/infra/storage.py`
  - 或 `shared/utils/file_utils.py`
- 删除 route 中各自维护的 zip 临时处理套路

---

## P2 Dataset 域重构

### 8. 建立 `dataset` 域目录

- `contexts/dataset/api/`
- `contexts/dataset/application/`
- `contexts/dataset/domain/`
- `contexts/dataset/infrastructure/`

### 9. 拆分当前 `dataset_routes.py`

- 目标：不保留“大一统数据集路由文件”
- 建议拆分为以下用例文件：
  - `application/list_datasets.py`
  - `application/get_dataset_info.py`
  - `application/create_subset.py`
  - `application/augment_subset.py`
  - `application/import_dataset.py`
  - `application/reorder_labels.py`
  - `application/delete_label.py`
  - `application/download_dataset.py`
  - `application/merge_datasets.py`
  - `application/split_dataset.py`

### 10. 抽出 Dataset 域模型与规则

- 建立：
  - `domain/entities.py`
  - `domain/policies.py`
  - `domain/services.py`
- 至少承接：
  - 数据集命名规则
  - `dataset.yaml` 规则
  - label map 规则
  - 标签重排规则
  - 类别删除规则
  - 子集与增强策略

### 11. 抽出 Dataset 基础设施

- 建立：
  - `infrastructure/repositories.py`
  - `infrastructure/fs_gateway.py`
  - `infrastructure/archive_gateway.py`
- 承接：
  - 目录扫描
  - 标签文件改写
  - zip 导入导出
  - 文件复制/移动/删除

### 12. Dataset 域验收标准

- `dataset` 相关 route 不再包含文件系统细节
- 不再出现重复的 `training/<dataset>` 路径拼接
- 不再出现 route 级别 YAML 解析
- `dataset_routes.py` 被删除

---

## P3 Annotation 域重构

### 13. 建立 `annotation` 域目录

- `contexts/annotation/api/`
- `contexts/annotation/application/`
- `contexts/annotation/domain/`
- `contexts/annotation/infrastructure/`

### 14. 统一标注域入口

- 删除 route 直接调多个 `core.annotation_*` 的做法
- 改为 route 只调 annotation 域用例
- 建议用例包括：
  - `application/get_annotation_payload.py`
  - `application/save_manual_annotation.py`
  - `application/save_auto_annotation.py`
  - `application/commit_auto_annotation.py`
  - `application/start_batch_auto_annotation.py`
  - `application/get_batch_status.py`

### 15. 抽出 Annotation 域规则

- 建立：
  - `domain/entities.py`
  - `domain/services.py`
  - `domain/policies.py`
- 承接：
  - 标注框模型
  - YOLO 行语义
  - 自动标注结果合并规则
  - 重复框过滤规则
  - 手工标注与自动标注的覆盖规则

### 16. 抽出 Annotation 基础设施

- 承接：
  - YOLO 标签文件读写
  - OpenVINO 推理适配
  - YOLO 推理适配
  - 图片尺寸读取
- 自动标注任务启动逻辑迁移到：
  - `application` 调 `task` 域
  - `infrastructure` 调模型推理与文件落盘

### 17. Annotation 域验收标准

- `annotation_routes.py` 不再直接 import 多个旧 `core` 模块
- `annotation_manager.py` 不再作为超重业务入口继续存在
- 标注任务、文件读写、推理适配职责分离完成

---

## P4 Video 域重构

### 18. 建立 `video` 域目录

- `contexts/video/api/`
- `contexts/video/application/`
- `contexts/video/domain/`
- `contexts/video/infrastructure/`

### 19. 拆分视频相关能力

- 建议用例包括：
  - `application/list_videos.py`
  - `application/upload_video.py`
  - `application/delete_video.py`
  - `application/start_extraction.py`
  - `application/list_extraction_tasks.py`
  - `application/get_task_images.py`
  - `application/import_task_images.py`
  - `application/delete_task_images.py`
  - `application/delete_extraction_task.py`

### 20. 抽出 Video 域规则与基础设施

- `domain` 承接：
  - 视频资源对象
  - 抽帧任务对象
  - 抽帧策略规则
- `infrastructure` 承接：
  - ffmpeg / ffprobe
  - 缩略图生成
  - 视频文件访问
  - 抽帧落盘

### 21. Video 域验收标准

- `video_routes.py` 只保留 HTTP 适配
- 旧 `video_manager.py` 被拆散或删除
- 视频任务不再自己维护任务状态与进程细节

---

## P5 Training 域重构

### 22. 建立 `training` 域目录

- `contexts/training/api/`
- `contexts/training/application/`
- `contexts/training/domain/`
- `contexts/training/infrastructure/`

### 23. 拆分训练域用例

- 建议至少拆成：
  - `application/create_workflow.py`
  - `application/start_training.py`
  - `application/resume_training.py`
  - `application/retry_training.py`
  - `application/start_evaluate.py`
  - `application/start_export.py`
  - `application/start_inference.py`
  - `application/list_workflows.py`
  - `application/get_workflow.py`
  - `application/list_artifacts.py`

### 24. 抽出训练域模型

- 建立：
  - `domain/entities.py`
  - `domain/state_machine.py`
  - `domain/services.py`
- 承接：
  - 训练工作流
  - 工作流状态流转
  - 导出记录
  - 评估建议规则
  - 训练恢复规则

### 25. 抽出训练基础设施

- 承接：
  - Ultralytics 训练适配
  - 导出运行时适配
  - 训练产物扫描
  - 校准逻辑
  - 本地输出目录结构访问

### 26. Training 域验收标准

- 全局 `core.training_*` 文件不再存在
- `training_routes.py` 只负责 HTTP 适配
- `training_manager.py` 不再承担状态机、产物扫描、导出、推理、任务编排的全集

---

## P6 Task / Auth / Project 域重构

### 27. Task 域独立

- 建立 `contexts/task/`
- 目标：
  - 任务实体
  - 任务状态枚举
  - 任务历史
  - 任务仓储
  - 统一任务应用服务
- 其它域只能通过 `task.application` 访问任务能力

### 28. Auth 域独立

- 建立 `contexts/auth/`
- 收口：
  - 登录
  - 当前用户
  - token 校验
  - bootstrap admin
- 认证白名单与 Flask before_request 逻辑迁入 `app/`

### 29. Project 域独立

- 建立 `contexts/project/`
- 收口：
  - 项目扫描
  - 项目创建
  - 项目重命名
  - 项目删除
  - 项目元信息
- `ProjectManager.analyze_dataset()` 中不属于 project 域的能力迁出到 `dataset` 域

---

## P7 API 层统一规范

### 30. 每个域建立独立 API 模块

- 每个域的 `api` 负责：
  - Blueprint
  - 参数解析
  - 调 application use case
  - 响应映射

### 31. 删除“全局统一业务装饰器”的滥用

- 可以保留公共异常转 HTTP 的轻量适配
- 但不再把业务规则和响应结构绑死在一个全局装饰器里
- Presenter / Response Mapper 按域维护

### 32. 响应组装按域下沉

- 当前类似“文件 URL 组装、artifact 列表组装、storage path 转换”的逻辑
- 全部迁移到各自域的 `api/presenters.py` 或 `application/dto.py`

---

## P8 旧结构下线

### 33. 删除旧 `routes/`

- 前提：所有蓝图都已迁入 `contexts/*/api/`
- 删除旧 `src/web/routes/`

### 34. 删除旧 `managers/`

- 前提：所有 use case 已迁入 `contexts/*/application/`
- 删除旧 `src/web/managers/`

### 35. 删除旧 `core/`

- 前提：纯公共能力已迁入 `shared/`
- 前提：业务逻辑已迁入各域
- 删除旧 `src/web/core/`

### 36. 更新文档与导入路径

- 更新：
  - `docs/guide/architecture.md`
  - 启动说明
  - 开发约定
- 清理所有旧 import

---

## 迁移执行顺序

### 第一阶段：先搭新架构骨架

- 建立 `app / shared / contexts`
- 建立统一依赖规则
- 建立任务与 worker 共享基础设施

### 第二阶段：先迁最重业务域

- 先迁 `dataset`
- 再迁 `annotation`
- 再迁 `video`

### 第三阶段：迁训练域

- 迁 `training`
- 同步整理 `task`

### 第四阶段：迁辅助域

- 迁 `project`
- 迁 `auth`

### 第五阶段：删除旧结构

- 删除旧 `routes / managers / core`
- 更新文档与启动装配

---

## 迁移约束

### 必须坚持

- 每迁完一个域，就让该域彻底脱离旧 `core`
- 每迁完一个域，就删除对应旧入口，不留双实现
- 所有新文件命名以职责为准，不再使用模糊 `manager`
- 优先“一用例一文件”，不要再制造超大文件

### 明确不接受

- 在新结构里复制一个新的“共享大杂烩”
- 在 `shared` 中放领域逻辑
- 为了过渡长期保留“双路实现”
- 把旧 `manager` 简单改名后原样搬到 `application`

---

## 完成标准

### 代码结构完成标准

- 仓库顶层不再存在全局 `core/`
- 仓库顶层不再存在全局 `managers/`
- 所有业务代码都位于 `contexts/*`
- 所有公共能力都位于 `shared/*`

### 架构完成标准

- 所有依赖方向单向可解释
- 不再有 `application -> api` 或 `domain -> infrastructure` 反向依赖
- 不再有跨域直接访问内部实现

### 维护性完成标准

- 每个领域都能独立定位其 API、用例、规则、基础设施
- 不再出现“一个文件承担一个领域的大多数能力”
- 新需求可以明确落到某个业务域内部，而不是先想“放哪个 core 文件”

---

## 文档结论

本次后端重构的目标不是“让 `core` 轻一点”，而是：

1. 彻底废弃全局横切目录
2. 改为按业务域分包
3. 在每个业务域内部建立清晰分层
4. 用删除旧结构作为重构完成标志

后续所有重构任务，都应以这份目标结构为唯一标准，不再回到旧的 `routes / managers / core` 思路。
