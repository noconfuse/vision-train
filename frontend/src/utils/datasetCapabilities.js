import { resolveTrainingConfigProfile } from './trainingConfigProfile';
import { resolveTrainingExportProfile } from './trainingExportProfile';
import { resolveTrainingResultProfile } from './trainingResultProfile';
import { buildCapabilityGuard } from './capabilityGuards';

export const DATASET_ANNOTATION_MODE = Object.freeze({
  UNSUPPORTED: 'unsupported',
  DETECT_BOXES: 'detect_boxes',
  IMAGE_CLASS: 'image_class',
  SEGMENT_POLYGONS: 'segment_polygons',
  POSE_KEYPOINTS: 'pose_keypoints',
});

export const DATASET_TRAINING_MODE = Object.freeze({
  UNSUPPORTED: 'unsupported',
  YOLO_DETECT: 'yolo_detect',
  YOLO_CLASSIFY: 'yolo_classify',
  YOLO_SEGMENT: 'yolo_segment',
  YOLO_POSE: 'yolo_pose',
});

export const DATASET_AUTO_ANNOTATION_MODE = Object.freeze({
  UNSUPPORTED: 'unsupported',
  DETECT_BOXES: 'detect_boxes',
  IMAGE_CLASS: 'image_class',
  SEGMENT_POLYGONS: 'segment_polygons',
  POSE_KEYPOINTS: 'pose_keypoints',
});

export const DATASET_OPERATION = Object.freeze({
  UPLOAD_IMAGES: 'upload_images',
  CREATE_SUBSET: 'create_subset',
  SPLIT_DATASET: 'split_dataset',
  MANUAL_ANNOTATION: 'manual_annotation',
  TRAIN: 'train',
  AUTO_ANNOTATE: 'auto_annotate',
  REORDER_LABELS: 'reorder_labels',
  ADD_LABEL: 'add_label',
  DELETE_LABEL: 'delete_label',
  DEDUPLICATE_IMAGES: 'deduplicate_images',
  MERGE_DATASETS: 'merge_datasets',
  AUGMENT_DATASET: 'augment_dataset',
});

const BASE_OPERATIONS = Object.freeze({
  [DATASET_OPERATION.UPLOAD_IMAGES]: false,
  [DATASET_OPERATION.CREATE_SUBSET]: false,
  [DATASET_OPERATION.SPLIT_DATASET]: false,
  [DATASET_OPERATION.MANUAL_ANNOTATION]: false,
  [DATASET_OPERATION.TRAIN]: false,
  [DATASET_OPERATION.AUTO_ANNOTATE]: false,
  [DATASET_OPERATION.REORDER_LABELS]: false,
  [DATASET_OPERATION.ADD_LABEL]: false,
  [DATASET_OPERATION.DELETE_LABEL]: false,
  [DATASET_OPERATION.DEDUPLICATE_IMAGES]: false,
  [DATASET_OPERATION.MERGE_DATASETS]: false,
  [DATASET_OPERATION.AUGMENT_DATASET]: false,
});

const DATASET_OPERATION_DISABLED_REASONS = Object.freeze({
  [DATASET_OPERATION.UPLOAD_IMAGES]: '当前任务类型暂不支持上传图片',
  [DATASET_OPERATION.CREATE_SUBSET]: '当前任务类型暂不支持生成子集',
  [DATASET_OPERATION.SPLIT_DATASET]: '当前任务类型暂不支持重切分',
  [DATASET_OPERATION.MANUAL_ANNOTATION]: '当前任务类型暂不支持标注',
  [DATASET_OPERATION.TRAIN]: '当前任务类型的训练暂未接入',
  [DATASET_OPERATION.AUTO_ANNOTATE]: '当前任务类型暂不支持自动标注',
  [DATASET_OPERATION.REORDER_LABELS]: '当前任务类型暂不支持调整类别顺序',
  [DATASET_OPERATION.ADD_LABEL]: '当前任务类型暂不支持添加类别',
  [DATASET_OPERATION.DELETE_LABEL]: '当前任务类型暂不支持删除类别',
  [DATASET_OPERATION.DEDUPLICATE_IMAGES]: '当前任务类型暂不支持图片去重',
  [DATASET_OPERATION.MERGE_DATASETS]: '当前任务类型暂不支持合并数据集',
  [DATASET_OPERATION.AUGMENT_DATASET]: '当前任务类型暂不支持增强子集',
});

const cloneCapabilities = (capabilities) => ({
  annotation_mode: capabilities?.annotation_mode || DATASET_ANNOTATION_MODE.UNSUPPORTED,
  training_mode: capabilities?.training_mode || DATASET_TRAINING_MODE.UNSUPPORTED,
  auto_annotation_mode: capabilities?.auto_annotation_mode || DATASET_AUTO_ANNOTATION_MODE.UNSUPPORTED,
  operation_disabled_reasons: {
    ...(capabilities?.operation_disabled_reasons || {}),
  },
  training_profile: resolveTrainingConfigProfile({
    capabilities_snapshot: capabilities,
  }),
  result_profile: resolveTrainingResultProfile({
    capabilities_snapshot: capabilities,
  }),
  export_profile: resolveTrainingExportProfile({
    capabilities_snapshot: capabilities,
  }),
  operations: {
    ...BASE_OPERATIONS,
    ...(capabilities?.operations || {}),
  },
});

const resolveDatasetVersioningBlockReason = (dataset) => {
  if (!dataset || dataset.current_version_id) return '';
  if (dataset.versioning_status === 'pending') return '首个版本入库中，请等待快照完成';
  if (dataset.versioning_status === 'failed') return '首个版本入库失败，请先到任务中心处理';
  return '';
};

const applyVersioningConstraints = (capabilities, dataset) => {
  const reason = resolveDatasetVersioningBlockReason(dataset);
  if (!reason) return capabilities;
  const operations = { ...(capabilities?.operations || {}) };
  const operationDisabledReasons = {
    ...(capabilities?.operation_disabled_reasons || {}),
  };
  Object.keys(operations).forEach((operation) => {
    if (!operations[operation]) return;
    operations[operation] = false;
    operationDisabledReasons[operation] = reason;
  });
  return {
    ...capabilities,
    operations,
    operation_disabled_reasons: operationDisabledReasons,
  };
};

export const resolveDatasetCapabilities = (dataset) => {
  const raw = dataset?.capabilities;
  if (raw && typeof raw === 'object') {
    return applyVersioningConstraints(cloneCapabilities(raw), dataset);
  }
  return applyVersioningConstraints(cloneCapabilities(null), dataset);
};

export const isDatasetOperationSupported = (dataset, operation) => {
  return !!resolveDatasetCapabilities(dataset).operations?.[operation];
};

export const getDatasetOperationDisabledReason = (operation, dataset = null) => {
  const snapshotReason = resolveDatasetCapabilities(dataset).operation_disabled_reasons?.[operation];
  return snapshotReason || DATASET_OPERATION_DISABLED_REASONS[operation] || '当前任务类型暂不支持该操作';
};

export const resolveDatasetOperationGuard = (dataset, operation, options = {}) => {
  const {
    visibleWhenUnsupported = false,
    extraEnabled = true,
    disabledReason = '',
  } = options || {};
  const supported = isDatasetOperationSupported(dataset, operation);
  if (!supported) {
    return buildCapabilityGuard({
      visible: visibleWhenUnsupported,
      enabled: false,
      reason: disabledReason || getDatasetOperationDisabledReason(operation, dataset),
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

export const getDatasetAnnotationMode = (dataset) => {
  return resolveDatasetCapabilities(dataset).annotation_mode;
};

export const getDatasetTrainingMode = (dataset) => {
  return resolveDatasetCapabilities(dataset).training_mode;
};
