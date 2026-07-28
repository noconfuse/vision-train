export const WORKFLOW_TYPE = Object.freeze({
  TRAINING: 'training',
});

export const isTrainingWorkflowType = (value) => value === WORKFLOW_TYPE.TRAINING;
