import {
  VISION_TASK_TYPE,
  getVisionTaskTypeValue,
  getVisionTaskTypeLabel,
  getVisionTaskTypeProgressClass,
  getVisionTaskTypeTagClass,
} from './visionTaskType';

export const DATASET_TYPE = Object.freeze({
  TRAINING: 'training',
});

export const isTrainingDataset = (datasetOrType) => {
  const datasetType = typeof datasetOrType === 'string' ? datasetOrType : datasetOrType?.type;
  return datasetType === DATASET_TYPE.TRAINING;
};

export const getDatasetTypeLabel = (datasetOrType) => {
  return getVisionTaskTypeLabel(datasetOrType);
};

export const getDatasetTypeTagClass = (datasetOrType) => {
  return getVisionTaskTypeTagClass(datasetOrType);
};

export const getDatasetTypeProgressClass = (datasetOrType) => {
  return getVisionTaskTypeProgressClass(datasetOrType);
};

export const isDetectDataset = (datasetOrType) => getVisionTaskTypeValue(datasetOrType) === VISION_TASK_TYPE.DETECT;
