"""创建训练相关任务记录并启动对应 worker 进程。"""

import os

from contexts.task.domain.task_types import (
    TASK_TYPE_EVALUATE,
    TASK_TYPE_INFERENCE,
    TASK_TYPE_TRAINING,
)
from contexts.task.domain.task_artifact_keys import (
    ARTIFACT_BEST_WEIGHT_PATH,
    ARTIFACT_DATASET_YAML,
    ARTIFACT_LAST_WEIGHT_PATH,
    ARTIFACT_MODEL_PATH,
    ARTIFACT_OUTPUT_DIR,
    ARTIFACT_RUN_ID,
)
from contexts.task.infrastructure.task_repository import (
    create_task as start_task,
    update_task as update_task_status,
)
from contexts.task.infrastructure.task_runtime import load_task
from contexts.training.domain.training_constants import (
    TRAINING_WEIGHT_BEST_FILENAME,
    TRAINING_WEIGHT_LAST_FILENAME,
    WORKFLOW_TYPE_TRAINING,
)
from contexts.task.infrastructure.worker_task_ops import build_worker_artifacts
from contexts.training.infrastructure.evaluate_runtime import resolve_evaluate_split
from contexts.training.infrastructure.execution_support import (
    BATCH_CALIBRATION_TYPE,
    find_existing_batch_calibration,
    is_active_task_status,
    make_batch_calibration_key,
    new_run_token,
    normalize_training_config,
    prepare_training_sources,
    start_worker_task,
)
from contexts.training.infrastructure.training_artifacts import (
    build_training_calibration_dir,
    build_training_inference_dir,
    build_training_output_dir,
    build_training_task_run_dir,
    build_training_weight_artifacts,
)
from contexts.training.infrastructure.workflow_repository import (
    delete_training_task_artifacts,
    ensure_training_workflow_record,
    touch_training_workflow_record,
)
from contexts.training.infrastructure.runtime_profile import get_device
from shared.utils.json_utils import save_json_file
from shared.utils.path_utils import project_name_from_path
from shared.utils.value_utils import require_present


def start_batch_calibration_task(project_path, dataset_name, model_name, imgsz=640, dataset_path=None, force=False, workflow_id=None, model_path=None):
    """创建或复用批次校准任务并启动 worker。"""
    try:
        imgsz = int(imgsz or 640)
    except (TypeError, ValueError):
        raise ValueError("imgsz 必须是整数")
    existing = find_existing_batch_calibration(project_path, dataset_name, model_name, imgsz)
    if existing and is_active_task_status(existing.get("status")):
        return {"task_id": existing["id"], "workflow_id": existing.get("workflow_id") or workflow_id, "cached": False, "reused": True}
    if existing and existing.get("status") == "completed" and not force:
        return {"task_id": existing["id"], "workflow_id": existing.get("workflow_id") or workflow_id, "cached": True, "reused": True}
    calibration_id = new_run_token()
    save_dir = build_training_calibration_dir(project_path, dataset_name, calibration_id)
    worker_artifacts = build_worker_artifacts(save_dir, "batch-calibration-worker.log", "task_worker")
    sources = prepare_training_sources(project_path, dataset_name, model_name, dataset_path, model_path=model_path)
    device_type = get_device()
    calibration_key = make_batch_calibration_key(project_path, dataset_name, model_name, imgsz, device_type)
    task = start_task(
        project_path=project_path,
        project_name=project_name_from_path(project_path),
        type_=BATCH_CALIBRATION_TYPE,
        dataset_name=dataset_name,
        dataset_path=sources["dataset_path"],
        payload={
            "model_name": model_name,
            "model_path": sources["model_path"],
            "imgsz": imgsz,
            "device": device_type,
            "calibration_key": calibration_key,
        },
        message="等待开始批次校准...",
        artifacts={ARTIFACT_OUTPUT_DIR: save_dir, ARTIFACT_DATASET_YAML: sources["data_yaml"], ARTIFACT_MODEL_PATH: sources["model_path"], **worker_artifacts},
    )
    task = update_task_status(task["id"], workflow_id=workflow_id, workflow_type=WORKFLOW_TYPE_TRAINING if workflow_id else None)
    if workflow_id:
        touch_training_workflow_record(workflow_id, dataset_path=sources["dataset_path"])
    return {
        **start_worker_task(
            task["id"],
            running_message="批次校准任务已启动，准备实测可启动上限...",
            failure_message="批次校准启动失败",
            module_name="task_worker",
        ),
        "cached": False,
        "reused": False,
        "workflow_id": workflow_id,
    }


def start_training_task(
    project_path,
    dataset_name,
    model_name,
    training_config,
    dataset_path=None,
    resume_from_task_id=None,
    resume_weight=None,
    workflow_id=None,
    model_path=None,
):
    """创建训练任务、准备输入源并启动 worker。"""
    if not workflow_id and not resume_from_task_id:
        raise ValueError("缺少 workflow_id，请先创建工作流")
    require_present(project_path=project_path, dataset_name=dataset_name, model_name=model_name)
    training_config = normalize_training_config(training_config)
    train_id = new_run_token()
    save_dir = build_training_output_dir(project_path, dataset_name, train_id)
    worker_artifacts = build_worker_artifacts(save_dir, "training-worker.log", "task_worker")
    sources = prepare_training_sources(project_path, dataset_name, model_name, dataset_path, model_path=model_path)
    config_save = {
        "dataset_name": dataset_name,
        "model_name": model_name,
        "config": training_config,
        "dataset_path": sources["dataset_path"],
        "start_time": train_id,
        "dataset_yaml": sources["data_yaml"],
    }
    save_json_file(os.path.join(save_dir, "training_config.json"), config_save)
    if not workflow_id and resume_from_task_id:
        resume_task = load_task(resume_from_task_id)
        workflow_id = (resume_task or {}).get("workflow_id") or resume_from_task_id
    workflow = ensure_training_workflow_record(
        workflow_id=workflow_id,
        project_path=project_path,
        dataset_name=dataset_name,
        dataset_path=sources["dataset_path"],
    )
    task = start_task(
        project_path=project_path,
        project_name=project_name_from_path(project_path),
        type_=TASK_TYPE_TRAINING,
        dataset_name=dataset_name,
        dataset_path=sources["dataset_path"],
        payload={
            "model_name": model_name,
            "model_path": sources["model_path"],
            "training_config": training_config,
            "resume_from_task_id": resume_from_task_id,
            "resume_weight": resume_weight,
        },
        message="初始化训练...",
        artifacts={
            ARTIFACT_RUN_ID: train_id,
            ARTIFACT_OUTPUT_DIR: save_dir,
            ARTIFACT_DATASET_YAML: sources["data_yaml"],
            ARTIFACT_MODEL_PATH: sources["model_path"],
            **build_training_weight_artifacts(save_dir),
            **worker_artifacts,
        },
    )
    task = update_task_status(task["id"], workflow_id=workflow["id"], workflow_type=WORKFLOW_TYPE_TRAINING)
    touch_training_workflow_record(workflow["id"], dataset_path=sources["dataset_path"])
    return start_worker_task(
        task["id"],
        running_message=f"训练进程已启动，准备训练 {model_name}...",
        failure_message="训练进程启动失败",
        module_name="task_worker",
        progress=0,
    )


def start_evaluate_task(project_path, dataset_name, src_task_id, use_best=True):
    """基于训练产物创建测试评估任务。"""
    src_task = load_task(src_task_id)
    if not src_task or not src_task.get("artifacts", {}).get(ARTIFACT_OUTPUT_DIR):
        raise ValueError("任务不存在或产物不可用")
    workflow_id = src_task.get("workflow_id") or src_task_id
    ensure_training_workflow_record(
        workflow_id=workflow_id,
        project_path=project_path,
        dataset_name=dataset_name,
        dataset_path=src_task.get("dataset_path"),
    )
    artifacts = src_task.get("artifacts") or {}
    weights_dir = artifacts[ARTIFACT_OUTPUT_DIR]
    weight = TRAINING_WEIGHT_BEST_FILENAME if use_best else TRAINING_WEIGHT_LAST_FILENAME
    weight_path = artifacts.get(ARTIFACT_BEST_WEIGHT_PATH) if use_best else artifacts.get(ARTIFACT_LAST_WEIGHT_PATH)
    if not weight_path or not os.path.isfile(weight_path):
        raise ValueError(f"{weight} 不存在")
    data_yaml = artifacts.get(ARTIFACT_DATASET_YAML) or ((src_task.get("payload") or {}).get("training_config") or {}).get("data_yaml")
    if not data_yaml or not os.path.isfile(data_yaml):
        raise ValueError("dataset.yaml 不可用")
    evaluate_split = resolve_evaluate_split(data_yaml)
    if evaluate_split != "test":
        raise ValueError("当前数据集没有测试集，无法执行测试评估")
    eval_task = start_task(
        project_path=project_path,
        project_name=project_name_from_path(project_path),
        type_=TASK_TYPE_EVALUATE,
        dataset_name=dataset_name,
        dataset_path=src_task.get("dataset_path"),
        payload={"src_task_id": src_task_id, "weight": weight, "weight_path": weight_path, "data_yaml": data_yaml, "split": evaluate_split},
        message="开始测试评估...",
        artifacts={},
    )
    eval_task = update_task_status(eval_task["id"], workflow_id=workflow_id, workflow_type=WORKFLOW_TYPE_TRAINING)
    task_dir = build_training_task_run_dir(weights_dir, TASK_TYPE_EVALUATE, eval_task["id"])
    update_task_status(eval_task["id"], artifacts=build_worker_artifacts(task_dir, "evaluate-worker.log", "task_worker"))
    touch_training_workflow_record(workflow_id, dataset_path=src_task.get("dataset_path"))
    return start_worker_task(eval_task["id"], "评估进程已启动...", "评估进程启动失败", "task_worker")


def start_inference_task(project_path, dataset_name, src_task_id, test_subdir="val", conf=0.25, max_det=200):
    """基于训练产物创建测试集推理任务。"""
    src_task = load_task(src_task_id)
    if not src_task or not src_task.get("artifacts", {}).get(ARTIFACT_OUTPUT_DIR):
        raise ValueError("任务或产物不可用")
    workflow_id = src_task.get("workflow_id") or src_task_id
    ensure_training_workflow_record(
        workflow_id=workflow_id,
        project_path=project_path,
        dataset_name=dataset_name,
        dataset_path=src_task.get("dataset_path"),
    )
    artifacts = src_task.get("artifacts") or {}
    weight = artifacts.get(ARTIFACT_BEST_WEIGHT_PATH)
    if not weight or not os.path.isfile(weight):
        raise ValueError("best.pt 不存在")
    from contexts.training.infrastructure.execution_support import resolve_and_validate_dataset

    dataset_root = resolve_and_validate_dataset(project_path, dataset_name, src_task.get("dataset_path"))
    img_dir = os.path.join(dataset_root, test_subdir, "images")
    if not os.path.isdir(img_dir):
        raise ValueError(f"测试目录不存在: {img_dir}")
    inf_task = start_task(
        project_path=project_path,
        project_name=project_name_from_path(project_path),
        type_=TASK_TYPE_INFERENCE,
        dataset_name=dataset_name,
        dataset_path=src_task.get("dataset_path"),
        payload={"src_task_id": src_task_id, "weight_path": weight, "img_dir": img_dir, "test_subdir": test_subdir, "conf": conf, "max_det": max_det},
        message="开始批量推理...",
        artifacts={},
    )
    inf_task = update_task_status(inf_task["id"], workflow_id=workflow_id, workflow_type=WORKFLOW_TYPE_TRAINING)
    task_dir = build_training_inference_dir(artifacts[ARTIFACT_OUTPUT_DIR], inf_task["id"])
    update_task_status(inf_task["id"], artifacts=build_worker_artifacts(task_dir, "inference-worker.log", "task_worker"))
    touch_training_workflow_record(workflow_id, dataset_path=src_task.get("dataset_path"))
    return start_worker_task(inf_task["id"], "推理进程已启动...", "推理进程启动失败", "task_worker")


def start_retry_training_task(project_path, dataset_name, task_id):
    """复用历史训练任务参数重新启动训练。"""
    require_present(project_path=project_path, dataset_name=dataset_name, task_id=task_id)
    task = load_task(task_id)
    if not task:
        raise ValueError("任务不存在")
    if task.get("project_path") != project_path or task.get("dataset_name") != dataset_name:
        raise ValueError("任务与当前数据集不匹配")
    if task.get("type") != TASK_TYPE_TRAINING:
        raise ValueError("仅训练任务支持重新训练")
    if task.get("status") in ("pending", "running"):
        raise ValueError("任务进行中，无法重新训练")
    payload = task.get("payload") or {}
    model_name = payload.get("model_name")
    if not model_name:
        raise ValueError("原训练任务缺少模型信息")
    delete_training_task_artifacts(task)
    return start_training_task(
        project_path=project_path,
        dataset_name=dataset_name,
        model_name=model_name,
        training_config=payload.get("training_config") or {},
        dataset_path=task.get("dataset_path"),
        workflow_id=task.get("workflow_id") or task.get("id"),
    )


__all__ = [
    "get_batch_calibration",
    "start_batch_calibration_task",
    "start_evaluate_task",
    "start_inference_task",
    "start_retry_training_task",
    "start_training_task",
]
