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
ARTIFACT_LOG_PATH = "log_path"
ARTIFACT_STOP_SIGNAL_PATH = "stop_signal_path"
ARTIFACT_WORKER_MODULE_NAME = "worker_module_name"
ARTIFACT_WORKER_PID = "worker_pid"
ARTIFACT_WORKER_STARTED_AT = "worker_started_at"
ARTIFACT_WORKER_EXITED_AT = "worker_exited_at"

TASK_STORAGE_ARTIFACT_KEYS = (ARTIFACT_OUTPUT_DIR, ARTIFACT_TASK_DIR)
