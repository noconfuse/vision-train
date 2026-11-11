import { defineStore } from 'pinia';
import api from '../api';
import { handleStoreError } from './main';

export const LOCAL_COMPUTE_TARGET_ID = '';

// 「运行位置」的唯一事实源：本机 + 数据库里配的 GPU 服务器。
// 预检结果按服务器 id 存，改了配置就要重新预检才允许开始训练。
export const useComputeStore = defineStore('compute', {
  state: () => ({
    targets: [],
    loaded: false,
    selectedTargetId: LOCAL_COMPUTE_TARGET_ID,
    preflightReports: {},
  }),

  getters: {
    selectedTarget(state) {
      return state.targets.find((item) => item.id === state.selectedTargetId) || null;
    },
    selectedPreflight(state) {
      return state.preflightReports[state.selectedTargetId] || null;
    },
  },

  actions: {
    async fetchComputeTargets() {
      try {
        this.targets = (await api.getComputeTargets()) || [];
        this.loaded = true;
        if (this.selectedTargetId && !this.targets.some((item) => item.id === this.selectedTargetId)) {
          this.selectedTargetId = LOCAL_COMPUTE_TARGET_ID;
        }
        return this.targets;
      } catch (err) {
        handleStoreError(err, this, { errorMsg: '读取 GPU 服务器列表失败' });
        this.targets = [];
        return [];
      }
    },

    selectTarget(targetId) {
      const next = targetId || LOCAL_COMPUTE_TARGET_ID;
      if (next !== LOCAL_COMPUTE_TARGET_ID && !this.targets.some((item) => item.id === next)) {
        return;
      }
      this.selectedTargetId = next;
    },

    async createComputeTarget(payload) {
      try {
        const target = await api.createComputeTarget(payload);
        await this.fetchComputeTargets();
        return target;
      } catch (err) {
        handleStoreError(err, this, { errorMsg: '新增 GPU 服务器失败' });
        return null;
      }
    },

    async updateComputeTarget(payload) {
      try {
        const target = await api.updateComputeTarget(payload);
        // 配置一变，之前那次预检就代表不了现在这台机器了
        this.dropPreflight(payload.target_id);
        await this.fetchComputeTargets();
        return target;
      } catch (err) {
        handleStoreError(err, this, { errorMsg: '修改 GPU 服务器失败' });
        return null;
      }
    },

    async deleteComputeTarget(targetId) {
      try {
        await api.deleteComputeTarget({ target_id: targetId });
        this.dropPreflight(targetId);
        if (this.selectedTargetId === targetId) {
          this.selectedTargetId = LOCAL_COMPUTE_TARGET_ID;
        }
        await this.fetchComputeTargets();
        return true;
      } catch (err) {
        handleStoreError(err, this, { errorMsg: '删除 GPU 服务器失败' });
        return false;
      }
    },

    async runPreflight(targetId) {
      try {
        const report = await api.preflightComputeTarget({ target_id: targetId });
        this.preflightReports = { ...this.preflightReports, [targetId]: report };
        return report;
      } catch (err) {
        handleStoreError(err, this, { errorMsg: '预检失败' });
        this.dropPreflight(targetId);
        return null;
      }
    },

    dropPreflight(targetId) {
      if (!(targetId in this.preflightReports)) return;
      const next = { ...this.preflightReports };
      delete next[targetId];
      this.preflightReports = next;
    },
  },
});
