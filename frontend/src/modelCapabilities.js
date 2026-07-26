import { buildCapabilityGuard } from './capabilityGuards';

export const MODEL_TRAINING_MODE = Object.freeze({
  UNSUPPORTED: 'unsupported',
  YOLO_DETECT: 'yolo_detect',
  YOLO_CLASSIFY: 'yolo_classify',
  YOLO_SEGMENT: 'yolo_segment',
  YOLO_POSE: 'yolo_pose',
});

export const MODEL_OPERATION = Object.freeze({
  TRAIN: 'train',
  EVALUATE: 'evaluate',
  EXPORT: 'export',
});

const BASE_OPERATIONS = Object.freeze({
  [MODEL_OPERATION.TRAIN]: false,
  [MODEL_OPERATION.EVALUATE]: true,
  [MODEL_OPERATION.EXPORT]: true,
});

const MODEL_OPERATION_DISABLED_REASONS = Object.freeze({
  [MODEL_OPERATION.TRAIN]: '当前模型暂不支持训练',
  [MODEL_OPERATION.EVALUATE]: '当前模型暂不支持测试评估',
  [MODEL_OPERATION.EXPORT]: '当前模型暂不支持导出',
});

export const resolveModelCapabilities = (model) => {
  const raw = model?.capabilities;
  return {
    training_mode: raw?.training_mode || MODEL_TRAINING_MODE.UNSUPPORTED,
    operations: {
      ...BASE_OPERATIONS,
      ...(raw?.operations || {}),
    },
  };
};

export const isModelOperationSupported = (model, operation) => {
  return !!resolveModelCapabilities(model).operations?.[operation];
};

export const getModelTrainingMode = (model) => {
  return resolveModelCapabilities(model).training_mode;
};

export const getModelOperationDisabledReason = (operation) => {
  return MODEL_OPERATION_DISABLED_REASONS[operation] || '当前模型暂不支持该操作';
};

export const resolveModelOperationGuard = (model, operation, options = {}) => {
  const {
    visibleWhenUnsupported = false,
    extraEnabled = true,
    disabledReason = '',
  } = options || {};
  const supported = isModelOperationSupported(model, operation);
  if (!supported) {
    return buildCapabilityGuard({
      visible: visibleWhenUnsupported,
      enabled: false,
      reason: disabledReason || getModelOperationDisabledReason(operation),
    });
  }
  if (!extraEnabled) {
    return buildCapabilityGuard({
      visible: true,
      enabled: false,
      reason: disabledReason,
    });
  }
  return buildCapabilityGuard({
    visible: true,
    enabled: true,
  });
};
