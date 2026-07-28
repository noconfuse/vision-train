import { defineStore } from 'pinia';
import api from '../api';
import { isTaskTerminal } from '../domain/task/taskStatus';

const POLL_INTERVAL_MS = 2000;

export const useDatasetSnapshotStore = defineStore('datasetSnapshot', {
  state: () => ({
    taskByDatasetId: {},
    pollTimers: {},
  }),
  actions: {
    activeTaskFor(datasetId) {
      if (!datasetId) return null;
      return this.taskByDatasetId[datasetId] || null;
    },

    async fetchActiveTask(datasetId, { projectPath, taskId } = {}) {
      if (!datasetId) return null;
      try {
        if (taskId) {
          const task = await api.getTask(taskId);
          this.taskByDatasetId = { ...this.taskByDatasetId, [datasetId]: task || null };
          return task || null;
        }
        const params = {
          type_: 'dataset_snapshot',
          dataset_id: datasetId,
          limit: 1,
        };
        if (projectPath) params.project_path = projectPath;
        const result = await api.listTasks(params);
        const tasks = Array.isArray(result?.tasks) ? result.tasks : [];
        const latest = tasks[0] || null;
        this.taskByDatasetId = { ...this.taskByDatasetId, [datasetId]: latest };
        return latest;
      } catch (_err) {
        return null;
      }
    },

    startPolling(datasetId, opts = {}) {
      if (!datasetId) return;
      // 把种子任务立即塞进 store，避免首屏等待
      if (opts.seed) {
        this.taskByDatasetId = { ...this.taskByDatasetId, [datasetId]: opts.seed };
      }
      // 同一 dataset 上的轮询只能有一份；如果已有，先停掉再用新 opts 重建，
      // 否则后续传入的 taskId / onTerminal 不会生效（典型场景：打开弹窗时
      // 启动轮询，然后点“发布当前版本”传入 onTerminal 触发列表刷新）。
      const hadTimer = Boolean(this.pollTimers[datasetId]);
      if (hadTimer) {
        this.stopPolling(datasetId);
      }
      const tick = async () => {
        const task = await this.fetchActiveTask(datasetId, opts);
        // 任务已是终态（completed/failed/stopped/interrupted） -> 停轮询
        if (isTaskTerminal(task)) {
          this.stopPolling(datasetId);
          if (typeof opts.onTerminal === 'function') {
            await opts.onTerminal(task);
          }
          return;
        }
        // 后端查不到匹配任务（dataset_id 写错 / 任务已被清理 / 还没入库）
        // 且之前已经显示过 seed -> 视为已结束，避免轮询一直跑。
        if (!task && opts.seed) {
          this.stopPolling(datasetId);
        }
      };
      tick();
      this.pollTimers[datasetId] = setInterval(tick, POLL_INTERVAL_MS);
    },

    stopPolling(datasetId) {
      if (!datasetId) return;
      const timer = this.pollTimers[datasetId];
      if (timer) {
        clearInterval(timer);
        const next = { ...this.pollTimers };
        delete next[datasetId];
        this.pollTimers = next;
      }
    },

    clear(datasetId) {
      this.stopPolling(datasetId);
      if (!datasetId) return;
      const next = { ...this.taskByDatasetId };
      delete next[datasetId];
      this.taskByDatasetId = next;
    },
  },
});
