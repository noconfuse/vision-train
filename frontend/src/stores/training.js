import { defineStore } from 'pinia';
import api from '../api';
import { isTaskActive } from '../domain/task/taskStatus';
import { handleStoreError } from './main';

let currentTaskPollingTimer = null;

export const useTrainingStore = defineStore('training', {
  state: () => ({
    currentTaskId: null,
    currentTask: null,
    runtimeProfile: null,
    batchCalibration: null,
  }),

  actions: {
    async fetchCurrentTask() {
      if (!this.currentTaskId) {
        return this.currentTask;
      }
      try {
        const res = await api.getTask(this.currentTaskId);
        if (res?.id) {
          this.currentTask = res;
          return this.currentTask;
        }
      } catch (_) {
        // 网络抖动时保留旧快照
      }
      return this.currentTask;
    },

    async pollCurrentTask() {
      if (currentTaskPollingTimer) return;
      const tick = async () => {
        const task = await this.fetchCurrentTask();
        if (isTaskActive(task)) {
          currentTaskPollingTimer = setTimeout(tick, 1000);
        } else {
          currentTaskPollingTimer = null;
        }
      };
      await tick();
    },

    stopCurrentTaskPolling() {
      if (currentTaskPollingTimer) {
        clearTimeout(currentTaskPollingTimer);
        currentTaskPollingTimer = null;
      }
    },

    async startTraining(config) {
      const res = await api.startTraining(config);
      const taskId = res.task_id;
      if (!taskId) {
        throw new Error('启动成功但未返回 task_id');
      }
      this.currentTaskId = taskId;
      this.fetchCurrentTask().catch(() => {});
      this.pollCurrentTask().catch(() => {});
      return res;
    },

    async fetchTrainingRuntimeProfile() {
      try {
        const res = await api.getTrainingRuntimeProfile();
        this.runtimeProfile = res || null;
        return this.runtimeProfile;
      } catch (err) {
        handleStoreError(err, this);
        this.runtimeProfile = null;
        return null;
      }
    },

    async fetchTrainingBatchCalibration({ project_path, dataset_name, model_name, imgsz } = {}) {
      if (!project_path || !dataset_name || !model_name) {
        this.batchCalibration = null;
        return null;
      }
      try {
        const task = await api.getTrainingBatchCalibration({
          project_path,
          dataset_name,
          model_name,
          imgsz,
        });
        this.batchCalibration = task || null;
        return this.batchCalibration;
      } catch (err) {
        handleStoreError(err, this);
        this.batchCalibration = null;
        return null;
      }
    },

    async startTrainingBatchCalibration(payload) {
      return api.startTrainingBatchCalibration(payload);
    },
  },
});
