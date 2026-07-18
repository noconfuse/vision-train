"""提供训练任务启动前的公共校验、参数和 worker 启动支持。"""

import os

from contexts.dataset.infrastructure.dataset_import_yolo import ensure_dataset_yaml
from contexts.task.domain.task_types import TASK_TYPE_BATCH_CALIBRATION
from contexts.dataset.infrastructure.dataset_repository import find_dataset_config, resolve_project_dataset_root
from contexts.dataset.infrastructure.dataset_schema import (
    normalize_dataset_yaml_for_training,
)
from contexts.task.domain.task_artifact_keys import ARTIFACT_LOG_PATH
from contexts.task.infrastructure.task_repository import (
    update_task as update_task_status,
)
from contexts.task.infrastructure.task_runtime import list_project_tasks, load_task
from contexts.task.infrastructure.worker_task_ops import mark_worker_started
from contexts.training.domain.training_constants import WORKFLOW_TYPE_TRAINING
from contexts.training.infrastructure.model_gateway import ensure_pretrained_model
from contexts.training.infrastructure.runtime_profile import get_device
from shared.infra.worker_process import spawn_worker_process
from shared.utils.path_utils import project_name_from_path, resolve_storage_path
from shared.utils.time_utils import now_iso
from shared.utils.value_utils import parse_bool
from task_status import TASK_STATUS_FAILED, TASK_STATUS_RUNNING, is_active_task_status

BATCH_CALIBRATION_TYPE = TASK_TYPE_BATCH_CALIBRATION
TRAINING_WORKFLOW_TYPE = WORKFLOW_TYPE_TRAINING
BATCH_CALIBRATION_MAX_BATCH = 128
BATCH_CALIBRATION_FRACTION = 0.01
BATCH_CALIBRATION_TIME_HOURS = 0.002
BATCH_CALIBRATION_WORKERS = 0
BATCH_CALIBRATION_MAX_ATTEMPTS = 16


def new_run_token():
    """生成训练运行目录使用的时间戳令牌。"""
    return now_iso().replace(":", "").replace("-", "").split(".")[0].replace("T", "_")


def normalize_training_config(training_config):
    """规范化并校验训练配置中的关键数值项。"""
    cfg = dict(training_config or {})
    for key in ("epochs", "batch"):
        if cfg.get(key) in (None, ""):
            raise ValueError(f"training_config.{key} 必填")
        try:
            cfg[key] = int(cfg[key])
        except (TypeError, ValueError):
            raise ValueError(f"training_config.{key} 必须为整数")
        if cfg[key] < 1:
            raise ValueError(f"training_config.{key} 必须大于等于 1")
    return cfg


def resolve_and_validate_dataset(project_path, dataset_name, dataset_path):
    """解析并校验训练所用数据集根目录。"""
    candidate = resolve_project_dataset_root(project_path, dataset_name=dataset_name, dataset_path=dataset_path)
    if candidate:
        return candidate
    project_name = project_name_from_path(project_path)
    raise ValueError(f"训练数据集 {dataset_name} 不存在（项目：{project_name}，数据集：{dataset_name}）")
def normalize_dataset_yaml_in_place(data_yaml, dataset_root):
    """原地规范 dataset.yaml 的 path 和 split 路径写法。"""
    if not data_yaml:
        return data_yaml
    normalized_path = resolve_storage_path(data_yaml)
    normalize_dataset_yaml_for_training(normalized_path, dataset_root)
    return normalized_path


def build_training_args(training_config, data_yaml, save_dir):
    """将前端训练配置转换为 Ultralytics 训练参数。"""
    args = {
        "data": data_yaml,
        "device": get_device(),
        "project": os.path.dirname(save_dir),
        "name": os.path.basename(save_dir),
        "exist_ok": True,
        "patience": 50,
        "save": True,
    }

    def add_arg(key, type_func):
        """按目标类型提取并写入单个训练参数。"""
        val = training_config.get(key)
        if val in (None, ""):
            return
        try:
            args[key] = type_func(val)
        except (ValueError, TypeError):
            pass

    for key, type_func in (
        ("epochs", int),
        ("imgsz", int),
        ("batch", int),
        ("rect", parse_bool),
        ("cos_lr", parse_bool),
        ("mosaic", float),
        ("mixup", float),
        ("copy_paste", float),
        ("degrees", float),
        ("translate", float),
        ("scale", float),
        ("shear", float),
        ("perspective", float),
        ("flipud", float),
        ("fliplr", float),
        ("hsv_h", float),
        ("hsv_s", float),
        ("hsv_v", float),
        ("close_mosaic", int),
        ("lr0", float),
        ("lrf", float),
    ):
        add_arg(key, type_func)

    if training_config.get("imbalance_optimization"):
        defaults = {
            "cos_lr": True,
            "mosaic": 1.0,
            "mixup": 0.15,
            "fliplr": 0.5,
            "degrees": 10.0,
            "hsv_s": 0.7,
            "hsv_v": 0.4,
        }
        for key, value in defaults.items():
            if key not in args:
                args[key] = value

    freeze_val = training_config.get("freeze")
    if freeze_val not in (None, ""):
        if isinstance(freeze_val, str) and freeze_val.lower() == "backbone":
            args["freeze"] = 10
        else:
            try:
                args["freeze"] = int(freeze_val)
            except (ValueError, TypeError):
                pass
    return args


def prepare_training_sources(project_path, dataset_name, model_name, dataset_path, model_path=None):
    """准备训练所需的数据集配置和训练入口模型路径。"""
    final_dataset_path = resolve_and_validate_dataset(project_path, dataset_name, dataset_path)
    if model_path:
        model_path = resolve_storage_path(model_path)
        if not model_path or not os.path.isfile(model_path):
            raise ValueError(f"模型文件不存在: {model_path}")
    else:
        try:
            model_path = ensure_pretrained_model(model_name)
        except Exception as exc:
            raise ValueError(f"模型准备失败: {exc}")
    data_yaml = find_dataset_config(final_dataset_path)
    if not data_yaml:
        ensure_dataset_yaml(final_dataset_path)
        data_yaml = find_dataset_config(final_dataset_path)
    if not data_yaml:
        raise ValueError("未找到 dataset.yaml")
    data_yaml = resolve_storage_path(data_yaml) if data_yaml else data_yaml
    try:
        data_yaml = normalize_dataset_yaml_in_place(data_yaml=data_yaml, dataset_root=final_dataset_path)
    except Exception:
        pass
    return {"dataset_path": final_dataset_path, "data_yaml": data_yaml, "model_path": model_path}


def start_worker_task(task_id, running_message, failure_message, module_name, progress=0):
    """启动任务 worker 并更新任务运行状态。"""
    task = load_task(task_id)
    if not task:
        raise ValueError(f"任务不存在: {task_id}")
    log_path = (task.get("artifacts") or {}).get(ARTIFACT_LOG_PATH)
    if not log_path:
        update_task_status(
            task_id,
            status=TASK_STATUS_FAILED,
            error="任务缺少日志路径",
            message=failure_message,
            finished_at=now_iso(),
        )
        raise ValueError("任务缺少日志路径")
    try:
        proc, _ = spawn_worker_process(task_id, log_path, module_name)
    except Exception as exc:
        update_task_status(
            task_id,
            status=TASK_STATUS_FAILED,
            error=str(exc),
            message=failure_message,
            finished_at=now_iso(),
        )
        raise ValueError(f"{failure_message}: {exc}")
    update_task_status(
        task_id,
        status=TASK_STATUS_RUNNING,
        started_at=task.get("started_at") or now_iso(),
        progress=progress,
        message=running_message,
    )
    mark_worker_started(task_id, proc.pid, module_name)
    return {"task_id": task_id, "workflow_id": task.get("workflow_id")}


def make_batch_calibration_key(project_path, dataset_name, model_name, imgsz, device_type):
    """生成批次校准结果复用键。"""
    return "|".join([project_name_from_path(project_path), dataset_name or "", os.path.basename(model_name or ""), str(int(imgsz or 640)), device_type or ""])


def find_existing_batch_calibration(project_path, dataset_name, model_name, imgsz):
    """查找同配置下可复用的批次校准任务。"""
    key = make_batch_calibration_key(project_path, dataset_name, model_name, imgsz, get_device())
    items = list_project_tasks(
        project_path,
        type_=BATCH_CALIBRATION_TYPE,
        dataset_name=dataset_name,
        limit=200,
        include_archived=True,
    )
    matched = [item for item in items if (item.get("payload") or {}).get("calibration_key") == key]
    if not matched:
        return None
    for item in matched:
        if is_active_task_status(item.get("status")):
            return item
    return matched[0]


def get_batch_calibration(project_path, dataset_name, model_name, imgsz):
    """返回指定模型的批次校准记录。"""
    if not project_path or not dataset_name or not model_name:
        return None
    try:
        imgsz = int(imgsz or 640)
    except (TypeError, ValueError):
        imgsz = 640
    return find_existing_batch_calibration(project_path, dataset_name, model_name, imgsz)
