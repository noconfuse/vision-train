"""定义任务工件字段名的共享常量。"""

ARTIFACT_RUN_ID = "run_id"
ARTIFACT_OUTPUT_DIR = "output_dir"
ARTIFACT_TASK_DIR = "task_dir"
ARTIFACT_DATASET_YAML = "dataset_yaml"
ARTIFACT_MODEL_PATH = "model_path"
ARTIFACT_BEST_WEIGHT_PATH = "best_weight_path"
ARTIFACT_LAST_WEIGHT_PATH = "last_weight_path"
ARTIFACT_IMAGES_DIR = "images_dir"
ARTIFACT_EXPORT_PATH = "export_path"
ARTIFACT_TEMPLATE_DIR = "template_dir"
ARTIFACT_TEMPLATE_MANIFEST_PATH = "template_manifest_path"
ARTIFACT_TEMPLATE_SOURCE_MODEL_PATH = "template_source_model_path"
ARTIFACT_TEMPLATE_SOURCE_FORMAT = "template_source_format"
ARTIFACT_TEMPLATE_TYPE = "template_type"
ARTIFACT_LOG_PATH = "log_path"
ARTIFACT_STOP_SIGNAL_PATH = "stop_signal_path"
ARTIFACT_WORKER_MODULE_NAME = "worker_module_name"
ARTIFACT_WORKER_PID = "worker_pid"
ARTIFACT_WORKER_STARTED_AT = "worker_started_at"
ARTIFACT_WORKER_EXITED_AT = "worker_exited_at"

# 远端训练的运行时句柄：都是服务器上的路径/进程号，只在续接与清理时用，
# 因此不进 TASK_STORAGE_ARTIFACT_KEYS（那组是本地目录，删除任务时会整棵删）。
ARTIFACT_REMOTE_HOST = "remote_host"
ARTIFACT_REMOTE_RUN_DIR = "remote_run_dir"
ARTIFACT_REMOTE_DATA_DIR = "remote_data_dir"
ARTIFACT_REMOTE_LOG_PATH = "remote_log_path"
ARTIFACT_REMOTE_PID = "remote_pid"

TASK_STORAGE_ARTIFACT_KEYS = (ARTIFACT_OUTPUT_DIR, ARTIFACT_TASK_DIR)
