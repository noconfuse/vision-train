export const getResumeFromTaskId = (task, fallback = '') => task?.payload?.resume_from_task_id || fallback;

export const getResumeWeight = (task, fallback = '') => task?.payload?.resume_weight || fallback;

export const getResumeSourceText = (task) => {
  const fromTaskId = getResumeFromTaskId(task);
  if (!fromTaskId) return '';
  const weight = getResumeWeight(task);
  return weight ? `继续自 ${fromTaskId} · ${weight}` : `继续自 ${fromTaskId}`;
};
