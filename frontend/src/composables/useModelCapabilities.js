import { computed, unref } from 'vue';
import {
  getModelTrainingMode,
  resolveModelCapabilities,
  resolveModelOperationGuard,
} from '../modelCapabilities';

export const useModelCapabilities = (modelSource) => {
  const model = computed(() => unref(modelSource) || null);
  const capabilities = computed(() => resolveModelCapabilities(model.value));
  const modelOperations = computed(() => capabilities.value.operations || {});

  const hasModelOperation = (operation) => !!modelOperations.value?.[operation];
  const getModelOperationGuard = (operation, options = {}) => (
    resolveModelOperationGuard(model.value, operation, options)
  );

  return {
    model,
    modelCapabilities: capabilities,
    modelOperations,
    trainingMode: computed(() => getModelTrainingMode(model.value)),
    hasModelOperation,
    getModelOperationGuard,
  };
};
