export const VISION_TASK_TYPE = Object.freeze({
  DETECT: 'detect',
  CLASSIFY: 'classify',
  SEGMENT: 'segment',
  POSE: 'pose',
});

const VISION_TASK_TYPE_SET = new Set(Object.values(VISION_TASK_TYPE));

const VISION_TASK_TYPE_LABELS = Object.freeze({
  [VISION_TASK_TYPE.DETECT]: '检测',
  [VISION_TASK_TYPE.CLASSIFY]: '分类',
  [VISION_TASK_TYPE.SEGMENT]: '分割',
  [VISION_TASK_TYPE.POSE]: '姿态',
});

const VISION_TASK_TYPE_TAG_CLASSES = Object.freeze({
  [VISION_TASK_TYPE.DETECT]: 'vt-tag-info',
  [VISION_TASK_TYPE.CLASSIFY]: 'vt-tag-success',
  [VISION_TASK_TYPE.SEGMENT]: 'vt-tag-warn',
  [VISION_TASK_TYPE.POSE]: 'vt-tag-danger',
});

const VISION_TASK_TYPE_PROGRESS_CLASSES = Object.freeze({
  [VISION_TASK_TYPE.DETECT]: 'vt-meter__bar--info',
  [VISION_TASK_TYPE.CLASSIFY]: 'vt-meter__bar--success',
  [VISION_TASK_TYPE.SEGMENT]: 'vt-meter__bar--warn',
  [VISION_TASK_TYPE.POSE]: 'vt-meter__bar--danger',
});

export const getVisionTaskTypeValue = (valueOrRecord) => {
  const raw = typeof valueOrRecord === 'string' ? valueOrRecord : valueOrRecord?.vision_task_type;
  const visionTaskType = String(raw || '').trim().toLowerCase();
  return VISION_TASK_TYPE_SET.has(visionTaskType) ? visionTaskType : '';
};

export const getVisionTaskTypeLabel = (valueOrRecord) => {
  const type = getVisionTaskTypeValue(valueOrRecord);
  return VISION_TASK_TYPE_LABELS[type] || '';
};

export const getVisionTaskTypeTagClass = (valueOrRecord) => {
  const type = getVisionTaskTypeValue(valueOrRecord);
  return VISION_TASK_TYPE_TAG_CLASSES[type] || '';
};

export const getVisionTaskTypeProgressClass = (valueOrRecord) => {
  const type = getVisionTaskTypeValue(valueOrRecord);
  return VISION_TASK_TYPE_PROGRESS_CLASSES[type] || '';
};
