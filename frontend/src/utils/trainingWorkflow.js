import { TASK_TYPE } from '../domain/task/taskType';
import { isTaskTerminal } from '../domain/task/taskStatus';

export const WORKFLOW_STEP = Object.freeze({
  CONFIG: 'config',
  DETAIL: 'detail',
  EVALUATE: 'evaluate',
  EXPORT_CONFIG: 'export_config',
  DEPLOYMENT_TEMPLATE: 'deployment_template',
});

const WORKFLOW_STEP_VALUES = new Set(Object.values(WORKFLOW_STEP));

// 训练任务已经结束、且已经写出 best.pt，评估/导出/部署这三步就有东西可用；
// 被停止或中断但留有产物的训练同样放行，不必等它跑满轮数计划。
export const hasUsableTrainingWeight = (task) => (
  isTaskTerminal(task) && task?.best_weight_ready === true
);

// 这三步的输入都是训练产出的权重，入口统一按权重可用性放行。
export const WEIGHT_BASED_WORKFLOW_STEPS = Object.freeze([
  WORKFLOW_STEP.EVALUATE,
  WORKFLOW_STEP.EXPORT_CONFIG,
  WORKFLOW_STEP.DEPLOYMENT_TEMPLATE,
]);

export const normalizeWorkflowStep = (step) => (
  WORKFLOW_STEP_VALUES.has(step) ? step : WORKFLOW_STEP.CONFIG
);

export const getWorkflowPreferredStepFromTask = (task, preferredStep = '') => {
  if (preferredStep) return preferredStep;
  if (task?.type === TASK_TYPE.EVALUATE) return WORKFLOW_STEP.EVALUATE;
  if (task?.type === TASK_TYPE.EXPORT) return WORKFLOW_STEP.EXPORT_CONFIG;
  if (task?.type === TASK_TYPE.TEMPLATE) return WORKFLOW_STEP.DEPLOYMENT_TEMPLATE;
  return WORKFLOW_STEP.DETAIL;
};
