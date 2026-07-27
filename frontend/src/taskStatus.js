export const TASK_STATUS = Object.freeze({
  PENDING: 'pending',
  RUNNING: 'running',
  STOPPING: 'stopping',
  COMPLETED: 'completed',
  FAILED: 'failed',
  STOPPED: 'stopped',
  INTERRUPTED: 'interrupted',
});

export const TASK_STATUS_ORDER = [
  TASK_STATUS.PENDING,
  TASK_STATUS.RUNNING,
  TASK_STATUS.STOPPING,
  TASK_STATUS.COMPLETED,
  TASK_STATUS.FAILED,
  TASK_STATUS.STOPPED,
  TASK_STATUS.INTERRUPTED,
];

export const TASK_STATUS_FILTER_OPTIONS = [
  { value: TASK_STATUS.RUNNING, label: '进行中' },
  { value: TASK_STATUS.STOPPING, label: '停止中' },
  { value: TASK_STATUS.PENDING, label: '等待中' },
  { value: TASK_STATUS.COMPLETED, label: '已完成' },
  { value: TASK_STATUS.FAILED, label: '失败' },
  { value: TASK_STATUS.STOPPED, label: '已停止' },
  { value: TASK_STATUS.INTERRUPTED, label: '已中断' },
];

const ACTIVE_TASK_STATUSES = new Set([
  TASK_STATUS.PENDING,
  TASK_STATUS.RUNNING,
  TASK_STATUS.STOPPING,
]);

const TERMINAL_TASK_STATUSES = new Set([
  TASK_STATUS.COMPLETED,
  TASK_STATUS.FAILED,
  TASK_STATUS.STOPPED,
  TASK_STATUS.INTERRUPTED,
]);

const RESUMABLE_TASK_STATUSES = new Set([
  TASK_STATUS.FAILED,
  TASK_STATUS.STOPPED,
  TASK_STATUS.INTERRUPTED,
]);

const RETRYABLE_TASK_STATUSES = new Set([
  TASK_STATUS.FAILED,
  TASK_STATUS.STOPPED,
  TASK_STATUS.INTERRUPTED,
]);

const STATUS_LABELS = {
  [TASK_STATUS.PENDING]: '等待中',
  [TASK_STATUS.RUNNING]: '进行中',
  [TASK_STATUS.STOPPING]: '停止中',
  [TASK_STATUS.COMPLETED]: '已完成',
  [TASK_STATUS.FAILED]: '失败',
  [TASK_STATUS.STOPPED]: '已停止',
  [TASK_STATUS.INTERRUPTED]: '已中断',
};

const STATUS_TAG_CLASSES = {
  [TASK_STATUS.PENDING]: 'vt-tag-info',
  [TASK_STATUS.RUNNING]: 'vt-tag-info',
  [TASK_STATUS.STOPPING]: 'vt-tag-warn',
  [TASK_STATUS.COMPLETED]: 'vt-tag-success',
  [TASK_STATUS.FAILED]: 'vt-tag-danger',
  [TASK_STATUS.STOPPED]: 'vt-tag-warn',
  [TASK_STATUS.INTERRUPTED]: 'vt-tag-warn',
};

const STATUS_PROGRESS_CLASSES = {
  [TASK_STATUS.FAILED]: 'vt-meter__bar--danger',
  [TASK_STATUS.COMPLETED]: 'vt-meter__bar--success',
  [TASK_STATUS.STOPPED]: 'vt-meter__bar--warn',
  [TASK_STATUS.INTERRUPTED]: 'vt-meter__bar--warn',
  [TASK_STATUS.STOPPING]: 'vt-meter__bar--warn',
};

const getTaskStatusValue = (taskOrStatus) => {
  if (!taskOrStatus) return '';
  return typeof taskOrStatus === 'string' ? taskOrStatus : (taskOrStatus.status || '');
};

export const getTaskStatusLabel = (taskOrStatus) => {
  const status = getTaskStatusValue(taskOrStatus);
  return STATUS_LABELS[status] || status || '-';
};

export const getTaskStatusTagClass = (taskOrStatus) => {
  const status = getTaskStatusValue(taskOrStatus);
  return STATUS_TAG_CLASSES[status] || 'vt-tag';
};

export const getTaskProgressBarClass = (taskOrStatus) => {
  const status = getTaskStatusValue(taskOrStatus);
  return STATUS_PROGRESS_CLASSES[status] || 'vt-meter__bar--info';
};

export const isTaskActive = (taskOrStatus) => {
  const status = getTaskStatusValue(taskOrStatus);
  return ACTIVE_TASK_STATUSES.has(status);
};

export const isTaskTerminal = (taskOrStatus) => {
  const status = getTaskStatusValue(taskOrStatus);
  return TERMINAL_TASK_STATUSES.has(status);
};

export const isTaskResumable = (taskOrStatus) => {
  const status = getTaskStatusValue(taskOrStatus);
  return RESUMABLE_TASK_STATUSES.has(status);
};

export const isTaskRetryable = (taskOrStatus) => {
  const status = getTaskStatusValue(taskOrStatus);
  return RETRYABLE_TASK_STATUSES.has(status);
};

export const isTaskCompleted = (taskOrStatus) => {
  const status = getTaskStatusValue(taskOrStatus);
  return status === TASK_STATUS.COMPLETED;
};

export const getTaskTerminalSummary = (task, fallback = '', opts = {}) => {
  const actionLabel = opts.actionLabel || '训练';
  const message = task?.message || '';
  const status = getTaskStatusValue(task);
  if (status === TASK_STATUS.PENDING) return message || `${actionLabel}等待中`;
  if (status === TASK_STATUS.RUNNING) return message || `${actionLabel}进行中`;
  if (status === TASK_STATUS.STOPPING) return message || `${actionLabel}停止中`;
  if (status === TASK_STATUS.FAILED) return message || `${actionLabel}失败`;
  if (status === TASK_STATUS.STOPPED) return message || `${actionLabel}已停止`;
  if (status === TASK_STATUS.INTERRUPTED) return message || `${actionLabel}已中断`;
  if (status === TASK_STATUS.COMPLETED) return message || `${actionLabel}已完成`;
  return fallback;
};

export const getTaskTerminalSummaryClass = (taskOrStatus) => {
  const status = getTaskStatusValue(taskOrStatus);
  if (status === TASK_STATUS.FAILED) return 'text-rose-700';
  if (status === TASK_STATUS.STOPPING || status === TASK_STATUS.STOPPED || status === TASK_STATUS.INTERRUPTED) return 'text-amber-700';
  if (status === TASK_STATUS.COMPLETED) return 'text-emerald-700';
  return 'text-gray-500';
};

export const canArchiveTask = (task) => !isTaskActive(task);

export const canHardDeleteTask = (task) => !!task?.is_archived && !isTaskActive(task);
