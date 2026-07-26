"""按任务类型分发后台 worker 执行入口。"""

import os
import sys
import traceback

from contexts.task.domain.task_types import (
    TASK_TYPE_BATCH_CALIBRATION,
    TASK_TYPE_EVALUATE,
    TASK_TYPE_EXPORT,
    TASK_TYPE_FRAME_EXTRACTION,
    TASK_TYPE_INFERENCE,
    TASK_TYPE_TEMPLATE,
    TASK_TYPE_TRAINING,
)
from contexts.task.infrastructure.task_runtime import load_task
from contexts.training.infrastructure.export_gateway import execute_export_task
from contexts.training.infrastructure.execution_runners import (
    execute_batch_calibration_task,
    execute_evaluate_task,
    execute_inference_task,
    execute_training_task,
)
from contexts.training.infrastructure.template_task_gateway import execute_template_task
from contexts.video.infrastructure.video_execution_gateway import execute_extraction_task


def _stderr(message):
    """向标准错误输出单行 worker 日志。"""
    try:
        os.write(2, f'{message}\n'.encode('utf-8', errors='replace'))
    except Exception:
        pass


def main():
    """加载任务并按类型分发到对应执行器。"""
    if len(sys.argv) < 2:
        _stderr('task_worker: missing task_id')
        return 2

    task_id = sys.argv[1]
    task = load_task(task_id)
    if not task:
        _stderr(f'task_worker: task not found task_id={task_id}')
        return 2

    task_type = task.get('type')
    _stderr(f'task_worker: boot task_id={task_id} type={task_type} pid={os.getpid()}')

    dispatch = {
        TASK_TYPE_TRAINING: execute_training_task,
        TASK_TYPE_BATCH_CALIBRATION: execute_batch_calibration_task,
        TASK_TYPE_EVALUATE: execute_evaluate_task,
        TASK_TYPE_EXPORT: execute_export_task,
        TASK_TYPE_INFERENCE: execute_inference_task,
        TASK_TYPE_FRAME_EXTRACTION: execute_extraction_task,
        TASK_TYPE_TEMPLATE: execute_template_task,
    }
    handler = dispatch.get(task_type)
    if not handler:
        _stderr(f'task_worker: unsupported type={task_type} task_id={task_id}')
        return 2

    try:
        handler(task_id)
        _stderr(f'task_worker: done task_id={task_id} type={task_type}')
        return 0
    except Exception:
        _stderr(f'task_worker: fatal task_id={task_id} type={task_type}\n{traceback.format_exc()}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
