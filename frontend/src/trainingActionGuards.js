import { buildCapabilityGuard } from './capabilityGuards';
import { DATASET_OPERATION, resolveDatasetOperationGuard } from './datasetCapabilities';
import { MODEL_OPERATION, resolveModelOperationGuard } from './modelCapabilities';

export const resolveTrainingDatasetGuard = (dataset, options = {}) => (
  resolveDatasetOperationGuard(dataset, DATASET_OPERATION.TRAIN, {
    visibleWhenUnsupported: true,
    ...(options || {}),
  })
);

export const resolveTrainingModelGuard = (dataset, model) => {
  const datasetGuard = resolveTrainingDatasetGuard(dataset);
  if (!datasetGuard.enabled) {
    return buildCapabilityGuard({
      visible: true,
      enabled: false,
      reason: datasetGuard.reason,
    });
  }
  return resolveModelOperationGuard(model, MODEL_OPERATION.TRAIN, {
    visibleWhenUnsupported: true,
  });
};

export const resolveTrainingStartGuard = ({ dataset, model, requiresDownload = false } = {}) => {
  const modelGuard = resolveTrainingModelGuard(dataset, model);
  if (!modelGuard.enabled) {
    return modelGuard;
  }
  if (requiresDownload) {
    return buildCapabilityGuard({
      visible: true,
      enabled: false,
      reason: '请先下载所选模型',
    });
  }
  if (!model) {
    return buildCapabilityGuard({
      visible: true,
      enabled: false,
      reason: '请选择训练模型',
    });
  }
  return buildCapabilityGuard({
    visible: true,
    enabled: true,
  });
};

export const resolveBatchCalibrationGuard = ({
  dataset,
  model,
  supportsBatchCalibration = false,
  requiresDownload = false,
  isRunning = false,
  hasContext = true,
} = {}) => {
  if (!supportsBatchCalibration) {
    return buildCapabilityGuard({
      visible: false,
      enabled: false,
    });
  }
  if (!hasContext) {
    return buildCapabilityGuard({
      visible: true,
      enabled: false,
      reason: '当前数据集上下文不完整',
    });
  }
  if (isRunning) {
    return buildCapabilityGuard({
      visible: true,
      enabled: false,
      reason: '批次校准进行中',
    });
  }
  return resolveTrainingStartGuard({
    dataset,
    model,
    requiresDownload,
  });
};

export const resolveEvaluateStartGuard = ({
  trainingTaskId = '',
  hasTestSplit = false,
  isRunning = false,
} = {}) => {
  if (isRunning) {
    return buildCapabilityGuard({
      visible: true,
      enabled: false,
      reason: '测试评估进行中',
    });
  }
  if (!trainingTaskId) {
    return buildCapabilityGuard({
      visible: true,
      enabled: false,
      reason: '缺少训练任务上下文',
    });
  }
  if (!hasTestSplit) {
    return buildCapabilityGuard({
      visible: true,
      enabled: false,
      reason: '当前数据集没有 test 划分，无法执行测试集评估',
    });
  }
  return buildCapabilityGuard({
    visible: true,
    enabled: true,
  });
};

export const resolveExportStartGuard = ({
  trainingTaskId = '',
  isRunning = false,
  validationError = '',
} = {}) => {
  if (isRunning) {
    return buildCapabilityGuard({
      visible: true,
      enabled: false,
      reason: '导出进行中',
    });
  }
  if (!trainingTaskId) {
    return buildCapabilityGuard({
      visible: true,
      enabled: false,
      reason: '缺少训练任务上下文',
    });
  }
  if (String(validationError || '').trim()) {
    return buildCapabilityGuard({
      visible: true,
      enabled: false,
      reason: String(validationError || '').trim(),
    });
  }
  return buildCapabilityGuard({
    visible: true,
    enabled: true,
  });
};

export const resolveExportDeleteGuard = ({ isRunning = false } = {}) => {
  if (isRunning) {
    return buildCapabilityGuard({
      visible: true,
      enabled: false,
      reason: '导出进行中，无法删除',
    });
  }
  return buildCapabilityGuard({
    visible: true,
    enabled: true,
  });
};
