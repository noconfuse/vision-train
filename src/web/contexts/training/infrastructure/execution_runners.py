"""执行训练、校准、评估与推理任务的实际运行逻辑。"""

import os

from contexts.dataset.infrastructure.dataset_schema import load_dataset_names
from contexts.model.domain.capabilities import model_training_mode_for_task
from contexts.task.domain.task_types import (
    TASK_TYPE_EVALUATE,
    TASK_TYPE_INFERENCE,
)
from contexts.task.domain.task_artifact_keys import (
    ARTIFACT_OUTPUT_DIR,
    ARTIFACT_STOP_SIGNAL_PATH,
    ARTIFACT_TASK_DIR,
)
from contexts.task.infrastructure.task_repository import (
    append_task_history as write_task_history,
    update_task as update_task_status,
)
from contexts.task.infrastructure.task_runtime import load_task
from contexts.task.infrastructure.worker_task_ops import (
    finish_worker_task,
    is_stop_requested,
    mark_worker_exited,
    mark_worker_started,
    update_worker_task_progress,
)
from contexts.training.infrastructure.calibration_runtime import clear_accelerator_cache, run_batch_probe, search_calibration_limit
from contexts.training.infrastructure.evaluate_runtime import build_evaluate_recommendations, resolve_evaluate_split
from contexts.training.infrastructure.execution_context import (
    require_existing_dir_path,
    require_existing_file_path,
    resolve_task_evaluate_runtime_context,
    resolve_task_training_runtime_context,
    resolve_task_vision_task_type,
)
from contexts.training.infrastructure.training_runtime_adapter import resolve_training_runtime_adapter
from contexts.training.infrastructure.execution_support import (
    BATCH_CALIBRATION_FRACTION,
    BATCH_CALIBRATION_MAX_ATTEMPTS,
    BATCH_CALIBRATION_MAX_BATCH,
    BATCH_CALIBRATION_TIME_HOURS,
    BATCH_CALIBRATION_TYPE,
    BATCH_CALIBRATION_WORKERS,
    build_training_args,
    get_device,
)
from contexts.training.infrastructure.training_artifacts import build_training_weight_artifacts
from constants.media import IMAGE_FILE_EXTENSIONS
from shared.utils.path_utils import file_api_url, resolve_storage_path
from shared.utils.time_utils import now_iso
from protocols.task_status import TASK_STATUS_COMPLETED, TASK_STATUS_FAILED, TASK_STATUS_RUNNING, TASK_STATUS_STOPPED


def _save_prediction_preview(output, preview_path):
    """保存预测预览图，优先使用 OpenCV，失败时回退 Pillow。"""
    preview = output.plot()
    os.makedirs(os.path.dirname(preview_path), exist_ok=True)
    try:
        import cv2

        return cv2.imwrite(preview_path, preview)
    except Exception:
        try:
            from PIL import Image

            image = Image.fromarray(preview[:, :, ::-1] if getattr(preview, "ndim", 0) == 3 else preview)
            image.save(preview_path)
            return True
        except Exception:
            return False


def _build_preview_path(task_dir, image_path, relative_path=None):
    """为一张图片生成稳定的推理预览图路径。"""
    image_name = os.path.splitext(str(relative_path or os.path.basename(image_path)))[0]
    safe_name = image_name.replace("\\", "__").replace("/", "__")
    return os.path.join(task_dir, "preview", f"{safe_name}.jpg")

def execute_training_task(task_id):
    """执行一个训练任务并持续回写进度与产物。"""
    task = load_task(task_id)
    if not task:
        raise ValueError(f"任务不存在: {task_id}")
    payload = task.get("payload") or {}
    artifacts = task.get("artifacts") or {}
    model_name = payload.get("model_name") or ""
    training_config = payload.get("training_config") or {}
    training_context = resolve_task_training_runtime_context(task)
    runtime_adapter = resolve_training_runtime_adapter(training_context["training_mode"])
    model_path = training_context["model_path"]
    save_dir = resolve_storage_path(artifacts.get(ARTIFACT_OUTPUT_DIR)) if artifacts.get(ARTIFACT_OUTPUT_DIR) else artifacts.get(ARTIFACT_OUTPUT_DIR)
    stop_signal_path = resolve_storage_path(artifacts.get(ARTIFACT_STOP_SIGNAL_PATH)) if artifacts.get(ARTIFACT_STOP_SIGNAL_PATH) else artifacts.get(ARTIFACT_STOP_SIGNAL_PATH)
    if not model_path or not save_dir:
        raise ValueError(f"训练任务缺少必要产物信息: {task_id}")
    mark_worker_started(task_id, os.getpid())
    try:
        update_task_status(task_id, status=TASK_STATUS_RUNNING, started_at=task.get("started_at") or now_iso(), progress=max(task.get("progress") or 0, 0), message=f"开始训练 {model_name}...")
        from ultralytics import YOLO

        model = YOLO(model_path)
        update_task_status(task_id, status=TASK_STATUS_RUNNING, progress=max(task.get("progress") or 0, 1), message="训练环境已准备，正在进入首轮 epoch...")

        _last_batch_progress = -1

        def on_train_batch_end(trainer):
            """每批训练后更新平滑进度（epoch 级回调负责写指标，本回调只刷新进度条）。"""
            nonlocal _last_batch_progress
            try:
                batches_per_epoch = len(trainer.train_loader)
                total_batches = batches_per_epoch * max(trainer.epochs, 1)
                if total_batches <= 0:
                    return
                # trainer.ni 是所有 epoch 累计的全局 batch 计数器
                pct = min(int(trainer.ni / total_batches * 99), 99)
                if pct == _last_batch_progress:
                    return
                _last_batch_progress = pct
                update_worker_task_progress(
                    task_id,
                    progress=pct,
                    message=f"训练中（{trainer.ni}/{total_batches} 批）...",
                )
            except Exception:
                pass  # 进度上报异常不打断训练

        def on_train_epoch_end(trainer):
            """在每轮训练结束后回写指标并响应停止请求。"""
            if is_stop_requested(stop_signal_path):
                trainer.stop = True
                raise InterruptedError("用户终止训练")
            epoch = trainer.epoch + 1
            epochs = trainer.epochs
            progress = int(epoch / epochs * 100)
            epoch_update = runtime_adapter.build_epoch_update(trainer, epoch, epochs)
            update_task_status(task_id, status=TASK_STATUS_RUNNING, progress=progress, message=epoch_update["message"])
            write_task_history(task_id, **epoch_update["history"])

        model.add_callback("on_train_batch_end", on_train_batch_end)
        model.add_callback("on_train_epoch_end", on_train_epoch_end)
        args = build_training_args(training_config, training_context, save_dir)
        update_task_status(task_id, status=TASK_STATUS_RUNNING, progress=max(task.get("progress") or 0, 1), message="训练已开始，等待首轮 epoch 完成...")
        model.train(**args)
        finish_worker_task(
            task_id,
            TASK_STATUS_COMPLETED,
            "训练完成",
            progress=100,
            artifacts_patch=build_training_weight_artifacts(save_dir),
            stop_signal_path=stop_signal_path,
        )
    except InterruptedError:
        finish_worker_task(
            task_id,
            TASK_STATUS_STOPPED,
            "训练已终止",
            artifacts_patch=build_training_weight_artifacts(save_dir),
            stop_signal_path=stop_signal_path,
        )
    except Exception as exc:
        finish_worker_task(
            task_id,
            TASK_STATUS_FAILED,
            "训练出错",
            error=str(exc),
            artifacts_patch=build_training_weight_artifacts(save_dir),
            stop_signal_path=stop_signal_path,
        )
    finally:
        mark_worker_exited(task_id)


def execute_batch_calibration_task(task_id):
    """执行一个批次校准任务并记录试跑结果。"""
    task = load_task(task_id)
    if not task or task.get("type") != BATCH_CALIBRATION_TYPE:
        raise ValueError(f"批次校准任务不存在: {task_id}")
    payload = task.get("payload") or {}
    artifacts = task.get("artifacts") or {}
    training_context = resolve_task_training_runtime_context(task)
    stop_signal_path = resolve_storage_path(artifacts.get(ARTIFACT_STOP_SIGNAL_PATH)) if artifacts.get(ARTIFACT_STOP_SIGNAL_PATH) else artifacts.get(ARTIFACT_STOP_SIGNAL_PATH)
    model_path = training_context["model_path"]
    save_dir = resolve_storage_path(artifacts.get(ARTIFACT_OUTPUT_DIR)) if artifacts.get(ARTIFACT_OUTPUT_DIR) else artifacts.get(ARTIFACT_OUTPUT_DIR)
    imgsz = int(payload.get("imgsz") or 640)
    device_type = payload.get("device") or get_device()
    if not model_path or not os.path.isfile(model_path):
        raise ValueError("校准模型不存在")
    if not save_dir:
        raise ValueError("校准输出目录不存在")
    mark_worker_started(task_id, os.getpid())
    attempts = []
    try:
        update_task_status(task_id, status=TASK_STATUS_RUNNING, progress=1, message="开始实测 batch 可启动上限...")
        probe_script = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "batch_probe.py"))
        calibration = search_calibration_limit(
            task_id=task_id,
            stop_signal_path=stop_signal_path,
            max_attempts=BATCH_CALIBRATION_MAX_ATTEMPTS,
            max_batch=BATCH_CALIBRATION_MAX_BATCH,
            run_probe=lambda batch: run_batch_probe(
                task_id=task_id,
                batch=batch,
                model_path=model_path,
                data_yaml=training_context["data_ref"],
                probe_dir=save_dir,
                imgsz=imgsz,
                device_type=device_type,
                fraction=BATCH_CALIBRATION_FRACTION,
                time_hours=BATCH_CALIBRATION_TIME_HOURS,
                workers=BATCH_CALIBRATION_WORKERS,
                probe_script_path=probe_script,
            ),
            is_stop_requested=is_stop_requested,
            update_progress=update_worker_task_progress,
            clear_cache=clear_accelerator_cache,
        )
        attempts = calibration["attempts"]
        result = {
            "max_batch": calibration["max_batch"],
            "imgsz": imgsz,
            "device": device_type,
            "attempt_count": calibration["attempt_count"],
            "attempts": attempts,
            "measured_at": now_iso(),
        }
        finish_worker_task(
            task_id,
            TASK_STATUS_COMPLETED,
            f'批次校准完成，实测可启动上限为 {calibration["max_batch"]}',
            progress=100,
            artifacts_patch={"calibration_result": result},
            stop_signal_path=stop_signal_path,
        )
    except InterruptedError:
        finish_worker_task(
            task_id,
            TASK_STATUS_STOPPED,
            "批次校准已终止",
            artifacts_patch={"calibration_result": {"attempts": attempts}},
            stop_signal_path=stop_signal_path,
        )
    except Exception as exc:
        finish_worker_task(
            task_id,
            TASK_STATUS_FAILED,
            "批次校准失败",
            error=str(exc),
            artifacts_patch={"calibration_result": {"attempts": attempts}},
            stop_signal_path=stop_signal_path,
        )
    finally:
        mark_worker_exited(task_id)
        clear_accelerator_cache()


def execute_evaluate_task(task_id):
    """执行一个测试集评估任务并回填指标结果。"""
    task = load_task(task_id)
    if not task or task.get("type") != TASK_TYPE_EVALUATE:
        raise ValueError(f"评估任务不存在: {task_id}")
    artifacts = task.get("artifacts") or {}
    stop_signal_path = artifacts.get(ARTIFACT_STOP_SIGNAL_PATH)
    evaluate_context = resolve_task_evaluate_runtime_context(task)
    runtime_adapter = resolve_training_runtime_adapter(evaluate_context["training_mode"])
    weight_path = evaluate_context["weight_path"]
    data_yaml = evaluate_context["data_yaml"]
    vision_task_type = evaluate_context["vision_task_type"]
    evaluate_split = evaluate_context["split"] or resolve_evaluate_split(data_yaml)
    if evaluate_split != "test":
        raise ValueError("当前数据集没有测试集，无法执行测试评估")
    mark_worker_started(task_id, os.getpid())
    try:
        from ultralytics import YOLO

        update_task_status(task_id, status=TASK_STATUS_RUNNING, progress=max(task.get("progress") or 0, 5), message="正在加载评估模型...")
        if is_stop_requested(stop_signal_path):
            raise InterruptedError("用户终止评估")
        model = YOLO(weight_path)

        def on_val_start(validator):
            """在评估开始时初始化批次总数和首条进度。"""
            try:
                total_batches = len(validator.dataloader or [])
            except Exception:
                total_batches = 0
            validator._vt_total_batches = total_batches
            if total_batches > 0:
                update_worker_task_progress(task_id, 10, f"正在测试集上执行评估，共 {total_batches} 批...")
            else:
                update_worker_task_progress(task_id, 10, "正在测试集上执行评估...")

        def on_val_batch_end(validator):
            """在每个评估批次结束后刷新进度。"""
            total_batches = int(getattr(validator, "_vt_total_batches", 0) or 0)
            current_batch = int(getattr(validator, "batch_i", -1) or -1) + 1
            if total_batches > 0:
                progress = 10 + int(current_batch / total_batches * 85)
                message = f"正在测试集上执行评估 {current_batch}/{total_batches} 批..."
            else:
                progress = min(95, 10 + max(current_batch, 0))
                message = f"正在测试集上执行评估，第 {max(current_batch, 0)} 批..."
            update_worker_task_progress(task_id, progress, message)

        def on_val_end(_validator):
            """在评估计算结束后切换到结果整理阶段。"""
            update_worker_task_progress(task_id, 95, "评估计算完成，正在整理结果...")

        model.add_callback("on_val_start", on_val_start)
        model.add_callback("on_val_batch_end", on_val_batch_end)
        model.add_callback("on_val_end", on_val_end)
        metrics = model.val(
            data=evaluate_context["data_ref"],
            device=get_device(),
            split=evaluate_split,
        )
        results = runtime_adapter.build_evaluate_results(metrics, evaluate_split)
        results["recommendations"] = build_evaluate_recommendations(results, vision_task_type)
        finish_worker_task(task_id, TASK_STATUS_COMPLETED, "测试评估完成", progress=100, artifacts_patch={"results": results}, stop_signal_path=stop_signal_path)
    except InterruptedError:
        finish_worker_task(task_id, TASK_STATUS_STOPPED, "测试评估已终止", stop_signal_path=stop_signal_path)
    except Exception as exc:
        finish_worker_task(task_id, TASK_STATUS_FAILED, "测试评估失败", error=str(exc), stop_signal_path=stop_signal_path)
    finally:
        mark_worker_exited(task_id)


def execute_inference_task(task_id):
    """执行一个测试目录的批量推理任务。"""
    task = load_task(task_id)
    if not task or task.get("type") != TASK_TYPE_INFERENCE:
        raise ValueError(f"推理任务不存在: {task_id}")
    payload = task.get("payload") or {}
    artifacts = task.get("artifacts") or {}
    stop_signal_path = artifacts.get(ARTIFACT_STOP_SIGNAL_PATH)
    task_dir = resolve_storage_path(artifacts.get(ARTIFACT_TASK_DIR)) if artifacts.get(ARTIFACT_TASK_DIR) else artifacts.get(ARTIFACT_TASK_DIR)
    weight = require_existing_file_path(payload.get("weight_path"), "推理权重不存在: {path}")
    img_dir = require_existing_dir_path(payload.get("img_dir"), "测试目录不存在: {path}")
    project_path = task.get("project_path")
    dataset_root = resolve_storage_path(task.get("dataset_path")) if task.get("dataset_path") else task.get("dataset_path")
    vision_task_type = resolve_task_vision_task_type(task)
    runtime_adapter = resolve_training_runtime_adapter(model_training_mode_for_task(vision_task_type))
    mark_worker_started(task_id, os.getpid())
    try:
        from ultralytics import YOLO

        update_task_status(task_id, status=TASK_STATUS_RUNNING, message="开始批量推理...")
        model = YOLO(weight)
        class_names = load_dataset_names(dataset_root) if dataset_root else []
        images = [os.path.join(img_dir, name) for name in os.listdir(img_dir) if name.lower().endswith(IMAGE_FILE_EXTENSIONS)]
        total = len(images)
        results = []
        for index, image_path in enumerate(images, 1):
            if is_stop_requested(stop_signal_path):
                raise InterruptedError("用户终止推理")
            relative_image_path = os.path.relpath(image_path, project_path)
            pred = model.predict(
                image_path,
                conf=float(payload.get("conf", 0.25)),
                max_det=int(payload.get("max_det", 200)),
                device=get_device(),
                save=False,
                verbose=False,
            )
            output = pred[0]
            preview_path = _build_preview_path(task_dir, image_path, relative_image_path) if task_dir else ""
            saved_preview = bool(preview_path) and _save_prediction_preview(output, preview_path)
            result_item = {
                "image": relative_image_path,
                "image_url": file_api_url(image_path),
                "pred_image_url": file_api_url(preview_path) if saved_preview else file_api_url(image_path),
            }
            result_item.update(runtime_adapter.build_inference_result(output, image_path, img_dir, class_names))
            results.append(result_item)
            if total:
                update_task_status(task_id, status=TASK_STATUS_RUNNING, progress=int(index / total * 100), message=f"已推理 {index}/{total} 张")
        finish_worker_task(task_id, TASK_STATUS_COMPLETED, f"推理完成 {total} 张", progress=100, artifacts_patch={"results": results, "total": total}, stop_signal_path=stop_signal_path)
    except InterruptedError:
        finish_worker_task(task_id, TASK_STATUS_STOPPED, "推理已终止", stop_signal_path=stop_signal_path)
    except Exception as exc:
        finish_worker_task(task_id, TASK_STATUS_FAILED, "推理失败", error=str(exc), stop_signal_path=stop_signal_path)
    finally:
        mark_worker_exited(task_id)


__all__ = [
    "execute_batch_calibration_task",
    "execute_evaluate_task",
    "execute_inference_task",
    "execute_training_task",
]
