import { ref } from 'vue';

/**
 * 通用阶段进度计算 composable。
 *
 * 场景：上传/导入/创建等多阶段任务，前端要把状态拆成若干阶段名（如
 * ``uploading`` / ``saving`` / ``done``），并把"当前阶段"渲染成可视化步骤条：
 * 已完成阶段 = 绿色，进行中 = 强调色，未开始 = 灰色，整体完成 = 绿色加粗。
 *
 * 用法：
 *   const { phaseClass, currentPhase, markFail } = usePhaseProgress({
 *     phases: ['uploading', 'saving', 'done'],
 *   });
 *   // 模板：
 *   //   <span :class="phaseClass('uploading')">① 上传</span>
 *
 * 终态：
 *   - 全部完成（``currentPhase.value === 'done'``）：所有阶段都是绿色加粗。
 *   - 失败：通过 ``markFail(phase)`` 记录失败前正在跑的阶段；当前/之后阶段红色加粗，
 *     之前阶段保持绿色。
 */
export const usePhaseProgress = ({ phases, initial = 'idle' } = {}) => {
  const phaseList = Array.isArray(phases) ? phases.slice() : [];

  const currentPhase = ref(initial);
  const lastReached = ref('');

  const phaseIndex = (name) => phaseList.indexOf(name);

  const phaseClass = (p) => {
    if (!phaseList.includes(p)) return 'text-gray-400';
    if (currentPhase.value === 'done') {
      return 'text-emerald-600 font-semibold';
    }
    if (currentPhase.value === 'fail') {
      const idx = phaseIndex(lastReached.value);
      const pIdx = phaseIndex(p);
      if (pIdx < idx) return 'text-emerald-600 font-medium';
      if (pIdx === idx) return 'text-rose-600 font-semibold';
      return 'text-gray-400';
    }
    const idx = phaseIndex(currentPhase.value);
    const pIdx = phaseIndex(p);
    if (pIdx < idx) return 'text-emerald-600 font-medium';
    if (pIdx === idx) return 'vt-text-accent-strong';
    return 'text-gray-400';
  };

  const setPhase = (name) => {
    currentPhase.value = name;
    if (phaseList.includes(name)) lastReached.value = name;
  };

  const markFail = (name) => {
    if (name && phaseList.includes(name)) lastReached.value = name;
    currentPhase.value = 'fail';
  };

  return {
    currentPhase,
    phaseClass,
    setPhase,
    markFail,
    phaseList,
  };
};