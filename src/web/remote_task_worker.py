"""远端 GPU worker 入口：把训练任务交给本地监督进程去驱动远端服务器。

与 task_worker 的区别只有一句：真正的计算不在本机发生。本机的职责是同步数据、
启动远端训练、把远端事件写回本地任务，以及把产物收回来。
"""

import os
import sys
import traceback

from protocols.task_status import TASK_STATUS_FAILED
from protocols.task_type import TASK_TYPE_TRAINING
from contexts.task.application.task_service import finish_worker_task, load_task
from contexts.training.infrastructure.remote_execution import execute_remote_training_task


def _stderr(message):
    """向标准错误输出单行 worker 日志。"""
    try:
        os.write(2, f'{message}\n'.encode('utf-8', errors='replace'))
    except Exception:
        pass


def main():
    """加载任务并进入远端训练监督流程。"""
    if len(sys.argv) < 2:
        _stderr('remote_task_worker: missing task_id')
        return 2

    task_id = sys.argv[1]
    task = load_task(task_id)
    if not task:
        _stderr(f'remote_task_worker: task not found task_id={task_id}')
        return 2
    if task.get('type') != TASK_TYPE_TRAINING:
        error = f'远端 GPU worker 目前只承接训练任务，收到的是 {task.get("type")}'
        _stderr(f'remote_task_worker: {error} task_id={task_id}')
        finish_worker_task(task_id, TASK_STATUS_FAILED, '远端任务启动失败', error=error)
        return 1

    _stderr(f'remote_task_worker: boot task_id={task_id} pid={os.getpid()}')
    try:
        execute_remote_training_task(task_id)
        _stderr(f'remote_task_worker: done task_id={task_id}')
        return 0
    except Exception:
        detail = traceback.format_exc()
        _stderr(f'remote_task_worker: fatal task_id={task_id}\n{detail}')
        # 走到这里说明连失败收口都没做成（任务还没进监督流程就炸了），
        # 必须把原因落到任务上，否则界面上只剩一个永远不动的进度条。
        finish_worker_task(task_id, TASK_STATUS_FAILED, '远端训练启动失败', error=detail[-2000:])
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
