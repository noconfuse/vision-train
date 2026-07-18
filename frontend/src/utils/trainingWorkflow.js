import { TASK_TYPE } from '../taskType';

export const WORKFLOW_STEP = Object.freeze({
  CONFIG: 'config',
  DETAIL: 'detail',
  EVALUATE: 'evaluate',
  EXPORT_CONFIG: 'export_config',
});

const WORKFLOW_STEP_VALUES = new Set(Object.values(WORKFLOW_STEP));

export const normalizeWorkflowStep = (step) => (
  WORKFLOW_STEP_VALUES.has(step) ? step : WORKFLOW_STEP.CONFIG
);

export const getWorkflowPreferredStepFromTask = (task, preferredStep = '') => {
  if (preferredStep) return preferredStep;
  if (task?.type === TASK_TYPE.EVALUATE) return WORKFLOW_STEP.EVALUATE;
  if (task?.type === TASK_TYPE.EXPORT) return WORKFLOW_STEP.EXPORT_CONFIG;
  return WORKFLOW_STEP.DETAIL;
};
