export const DATASET_TYPE = Object.freeze({
  TRAINING: 'training',
});

const DATASET_TYPE_LABELS = {
  [DATASET_TYPE.TRAINING]: '训练数据集',
};

const DATASET_TYPE_TAG_CLASSES = {
  [DATASET_TYPE.TRAINING]: 'vt-tag-info',
};

const DATASET_TYPE_PROGRESS_CLASSES = {
  [DATASET_TYPE.TRAINING]: 'vt-meter__bar--info',
};

export const isTrainingDataset = (datasetOrType) => {
  return !!datasetOrType;
};

export const getDatasetTypeLabel = (datasetOrType) => {
  const type = typeof datasetOrType === 'string' ? datasetOrType : datasetOrType?.type;
  return DATASET_TYPE_LABELS[type] || DATASET_TYPE_LABELS[DATASET_TYPE.TRAINING];
};

export const getDatasetTypeTagClass = (datasetOrType) => {
  const type = typeof datasetOrType === 'string' ? datasetOrType : datasetOrType?.type;
  return DATASET_TYPE_TAG_CLASSES[type] || DATASET_TYPE_TAG_CLASSES[DATASET_TYPE.TRAINING];
};

export const getDatasetTypeProgressClass = (datasetOrType) => {
  const type = typeof datasetOrType === 'string' ? datasetOrType : datasetOrType?.type;
  return DATASET_TYPE_PROGRESS_CLASSES[type] || DATASET_TYPE_PROGRESS_CLASSES[DATASET_TYPE.TRAINING];
};
