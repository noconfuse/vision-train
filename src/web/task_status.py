"""集中声明任务状态常量与状态判定函数。"""

TASK_STATUS_PENDING = 'pending'
TASK_STATUS_RUNNING = 'running'
TASK_STATUS_STOPPING = 'stopping'
TASK_STATUS_COMPLETED = 'completed'
TASK_STATUS_FAILED = 'failed'
TASK_STATUS_STOPPED = 'stopped'
TASK_STATUS_INTERRUPTED = 'interrupted'

TASK_STATUSES = (
    TASK_STATUS_PENDING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_STOPPING,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_STOPPED,
    TASK_STATUS_INTERRUPTED,
)

TASK_STATUS_ACTIVE = 'active'
ACTIVE_TASK_STATUSES = (
    TASK_STATUS_PENDING,
    TASK_STATUS_RUNNING,
    TASK_STATUS_STOPPING,
)
TERMINAL_TASK_STATUSES = (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_FAILED,
    TASK_STATUS_STOPPED,
    TASK_STATUS_INTERRUPTED,
)
RESUMABLE_TASK_STATUSES = (
    TASK_STATUS_COMPLETED,
    TASK_STATUS_STOPPED,
    TASK_STATUS_INTERRUPTED,
)


def is_active_task_status(status):
    """判断任务是否处于待执行或执行中状态。"""
    return status in ACTIVE_TASK_STATUSES


def is_terminal_task_status(status):
    """判断任务是否已进入终态。"""
    return status in TERMINAL_TASK_STATUSES


def is_resumable_task_status(status):
    """判断任务是否允许从历史状态恢复。"""
    return status in RESUMABLE_TASK_STATUSES
