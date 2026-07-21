"""处理 Web 服务启动初始化、停机回收与请求级认证钩子。"""

import logging

from app.config import AUTH
from app.http import auth_error_response
from contexts.auth.infrastructure.auth_gateway import ensure_bootstrap_admin, get_current_user, populate_current_user
from contexts.task.domain.task_artifact_keys import (
    ARTIFACT_STOP_SIGNAL_PATH,
    ARTIFACT_WORKER_EXITED_AT,
    ARTIFACT_WORKER_PID,
)
from contexts.task.infrastructure.task_repository import (
    list_task_records,
    mark_orphan_tasks_interrupted as reconcile_orphan_tasks,
    update_task,
)
from contexts.task.infrastructure.worker_task_ops import request_stop
from db import init_db
from shared.infra.worker_process import terminate_process_group
from shared.utils.time_utils import now_iso
from protocols.task_status import TASK_STATUS_ACTIVE, TASK_STATUS_INTERRUPTED

logger = logging.getLogger(__name__)
_runtime_shutdown_done = False

AUTH_WHITELIST = (
    "/api/auth/login",
    "/api/auth/status",
    "/api/health",
)


def initialize_runtime():
    """初始化数据库、修复孤儿任务并尝试补建管理员。"""
    init_db()
    try:
        changed, _ = reconcile_orphan_tasks()
        if changed:
            logger.warning("启动时标记 %s 个孤儿任务为 interrupted", changed)
    except Exception as exc:
        logger.warning("孤儿任务扫描失败: %s", exc)
    try:
        ensure_bootstrap_admin()
    except Exception as exc:
        logger.warning("bootstrap admin 失败: %s", exc)


def shutdown_runtime():
    """停机时终止活动 worker 并把任务标记为中断。"""
    global _runtime_shutdown_done
    if _runtime_shutdown_done:
        return
    _runtime_shutdown_done = True

    now = now_iso()
    try:
        tasks = list_task_records(status=TASK_STATUS_ACTIVE, include_archived=True, limit=1000)
    except Exception as exc:
        logger.warning("停机扫描活动任务失败: %s", exc)
        return

    interrupted = 0
    terminated = 0
    for task in tasks:
        task_id = task.get("id")
        artifacts = dict(task.get("artifacts") or {})
        stop_signal_path = artifacts.get(ARTIFACT_STOP_SIGNAL_PATH)
        worker_pid = artifacts.get(ARTIFACT_WORKER_PID)
        if stop_signal_path:
            try:
                request_stop(stop_signal_path)
            except Exception as exc:
                logger.warning("停机写入 stop signal 失败 task=%s: %s", task_id, exc)
        if worker_pid:
            try:
                if terminate_process_group(worker_pid):
                    terminated += 1
            except Exception as exc:
                logger.warning("停机终止 worker 失败 task=%s pid=%s: %s", task_id, worker_pid, exc)
        artifacts[ARTIFACT_WORKER_PID] = None
        artifacts[ARTIFACT_WORKER_EXITED_AT] = now
        try:
            update_task(
                task_id,
                status=TASK_STATUS_INTERRUPTED,
                message="服务关闭中断",
                finished_at=now,
                artifacts=artifacts,
            )
            interrupted += 1
        except Exception as exc:
            logger.warning("停机回写任务中断失败 task=%s: %s", task_id, exc)
    if interrupted:
        logger.warning("停机回收 %s 个活动任务，终止 %s 个 worker", interrupted, terminated)


def attach_request_hooks(app):
    """注册当前用户注入与统一鉴权前置钩子。"""
    app.before_request(populate_current_user)

    @app.before_request
    def _enforce_auth():
        """拦截未登录请求并放行鉴权白名单路径。"""
        if not AUTH.get("enabled", False):
            return None
        path = getattr(app, "request_class", None)
        del path
        from flask import request

        current_path = request.path
        for prefix in AUTH_WHITELIST:
            if current_path == prefix or current_path.startswith(prefix):
                return None
        if get_current_user() is None:
            return auth_error_response("未登录或登录已过期", code="auth_required", status_code=401)
        return None

    _ = _enforce_auth
