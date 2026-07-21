"""提供训练任务启动前的公共校验、参数和 worker 启动支持。"""

import os

from contexts.task.domain.task_types import TASK_TYPE_BATCH_CALIBRATION
from contexts.task.domain.task_artifact_keys import ARTIFACT_LOG_PATH
from contexts.task.infrastructure.task_repository import (
    update_task as update_task_status,
)
from contexts.task.infrastructure.task_runtime import list_project_tasks, load_task
from contexts.task.infrastructure.worker_task_ops import mark_worker_started
from contexts.training.domain.training_constants import WORKFLOW_TYPE_TRAINING
from contexts.training.infrastructure.runtime_profile import get_device
from shared.infra.worker_process import spawn_worker_process
from shared.utils.path_utils import project_name_from_path
from shared.utils.time_utils import now_iso
from shared.utils.value_utils import parse_bool
from protocols.vision_task_type import VISION_TASK_TYPE_SET
from protocols.task_status import TASK_STATUS_FAILED, TASK_STATUS_RUNNING, is_active_task_status

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


def build_training_args(training_config, training_context, save_dir):
    """将前端训练配置转换为 Ultralytics 训练参数。"""
    vision_task_type = training_context.get("vision_task_type")
    if vision_task_type not in VISION_TASK_TYPE_SET:
        raise ValueError("vision_task_type 不合法")
    profile = training_context.get("training_profile") or {}
    args = {
        "data": training_context.get("data_ref"),
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

    for key, type_func in profile["arg_specs"]:
        add_arg(key, parse_bool if type_func is bool else type_func)
    return args


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
