export const TASK_TYPE = Object.freeze({
  TRAINING: 'training',
  BATCH_CALIBRATION: 'batch_calibration',
  FRAME_EXTRACTION: 'frame_extraction',
  AUTO_ANNOTATION: 'auto_annotation',
  EVALUATE: 'evaluate',
  EXPORT: 'export',
  TEMPLATE: 'template',
  INFERENCE: 'inference',
});

export const TASK_TYPE_FILTER_OPTIONS = [
  { value: TASK_TYPE.TRAINING, label: '训练' },
  { value: TASK_TYPE.BATCH_CALIBRATION, label: '批次校准' },
  { value: TASK_TYPE.FRAME_EXTRACTION, label: '抽帧' },
  { value: TASK_TYPE.AUTO_ANNOTATION, label: '自动标注' },
  { value: TASK_TYPE.EVALUATE, label: '评估' },
  { value: TASK_TYPE.EXPORT, label: '导出' },
  { value: TASK_TYPE.TEMPLATE, label: '部署模板' },
  { value: TASK_TYPE.INFERENCE, label: '推理' },
];

const TASK_TYPE_LABELS = {
  [TASK_TYPE.TRAINING]: '训练',
  [TASK_TYPE.BATCH_CALIBRATION]: '批次校准',
  [TASK_TYPE.FRAME_EXTRACTION]: '抽帧',
  [TASK_TYPE.AUTO_ANNOTATION]: '自动标注',
  [TASK_TYPE.EVALUATE]: '评估',
  [TASK_TYPE.EXPORT]: '导出',
  [TASK_TYPE.TEMPLATE]: '部署模板',
  [TASK_TYPE.INFERENCE]: '推理',
};

const TASK_TYPE_ICONS = {
  [TASK_TYPE.TRAINING]: '🚀',
  [TASK_TYPE.BATCH_CALIBRATION]: '🧪',
  [TASK_TYPE.FRAME_EXTRACTION]: '🎬',
  [TASK_TYPE.AUTO_ANNOTATION]: '🏷️',
  [TASK_TYPE.EVALUATE]: '📊',
  [TASK_TYPE.EXPORT]: '📦',
  [TASK_TYPE.TEMPLATE]: '🚀',
  [TASK_TYPE.INFERENCE]: '🔍',
};

const TASK_TYPES_WITH_DETAIL = new Set([
  TASK_TYPE.TRAINING,
  TASK_TYPE.BATCH_CALIBRATION,
  TASK_TYPE.EVALUATE,
  TASK_TYPE.EXPORT,
  TASK_TYPE.TEMPLATE,
  TASK_TYPE.INFERENCE,
]);

const TASK_TYPES_WITH_ARTIFACTS = new Set([
  TASK_TYPE.TRAINING,
  TASK_TYPE.EVALUATE,
  TASK_TYPE.EXPORT,
  TASK_TYPE.INFERENCE,
]);

const TASK_TYPES_WITH_DELETEABLE_ARTIFACTS = new Set([
  TASK_TYPE.TRAINING,
  TASK_TYPE.BATCH_CALIBRATION,
]);

export const getTaskTypeLabel = (type) => TASK_TYPE_LABELS[type] || type || '-';

export const getTaskTypeIcon = (type) => TASK_TYPE_ICONS[type] || '⚙️';

export const canViewTask = (taskOrType) => {
  const type = typeof taskOrType === 'string' ? taskOrType : taskOrType?.type;
  return TASK_TYPES_WITH_DETAIL.has(type);
};

export const taskHasArtifactsView = (taskOrType) => {
  const type = typeof taskOrType === 'string' ? taskOrType : taskOrType?.type;
  return TASK_TYPES_WITH_ARTIFACTS.has(type);
};

export const shouldDeleteTaskArtifacts = (taskOrType) => {
  const type = typeof taskOrType === 'string' ? taskOrType : taskOrType?.type;
  return TASK_TYPES_WITH_DELETEABLE_ARTIFACTS.has(type);
};

export const isTrainingTask = (taskOrType) => {
  const type = typeof taskOrType === 'string' ? taskOrType : taskOrType?.type;
  return type === TASK_TYPE.TRAINING;
};

export const isFrameExtractionTask = (taskOrType) => {
  const type = typeof taskOrType === 'string' ? taskOrType : taskOrType?.type;
  return type === TASK_TYPE.FRAME_EXTRACTION;
};
