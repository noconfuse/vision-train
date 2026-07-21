import { computed, unref } from 'vue';
import {
  getDatasetAnnotationMode,
  getDatasetTrainingMode,
  resolveDatasetCapabilities,
  resolveDatasetOperationGuard,
} from '../datasetCapabilities';

export const useDatasetCapabilities = (datasetSource) => {
  const dataset = computed(() => unref(datasetSource) || null);
  const capabilities = computed(() => resolveDatasetCapabilities(dataset.value));
  const operations = computed(() => capabilities.value.operations || {});

  const hasDatasetOperation = (operation) => !!operations.value?.[operation];
  const getDatasetOperationGuard = (operation, options = {}) => (
    resolveDatasetOperationGuard(dataset.value, operation, options)
  );

  return {
    dataset,
    datasetCapabilities: capabilities,
    datasetOperations: operations,
    annotationMode: computed(() => getDatasetAnnotationMode(dataset.value)),
    trainingMode: computed(() => getDatasetTrainingMode(dataset.value)),
    hasDatasetOperation,
    getDatasetOperationGuard,
  };
};
