import { defineStore } from 'pinia';
import api from '../api';
import { handleStoreError } from './main';

const toKey = (...parts) => parts.map((value) => String(value || '')).join('::');
const WORKFLOW_LATEST_TASK_FIELD = Object.freeze({
  evaluate: 'latest_evaluate_task',
  training: 'latest_training_task',
});

export const useTrainingWorkflowStore = defineStore('trainingWorkflow', {
  state: () => ({
    workflowLists: {},
    workflowLoading: {},
    workflowDetails: {},
  }),

  actions: {
    getDatasetCacheKey({ project_path = '', dataset_id = '', archived_only = false } = {}) {
      return toKey(project_path, dataset_id, archived_only ? 'archived' : 'current');
    },

    getDetailCacheKey({ project_path = '', dataset_id = '', workflow_id = '', include_archived = false } = {}) {
      return toKey(project_path, dataset_id, workflow_id, include_archived ? 'all' : 'current');
    },

    getWorkflowFromState({ project_path = '', dataset_id = '', workflow_id = '', include_archived = true } = {}) {
      if (!project_path || !dataset_id || !workflow_id) return null;
      const detailKeys = include_archived
        ? [
            this.getDetailCacheKey({ project_path, dataset_id, workflow_id, include_archived: true }),
            this.getDetailCacheKey({ project_path, dataset_id, workflow_id, include_archived: false }),
          ]
        : [this.getDetailCacheKey({ project_path, dataset_id, workflow_id, include_archived: false })];
      for (const key of detailKeys) {
        const detail = this.workflowDetails[key];
        if (detail?.id === workflow_id) return detail;
      }

      const listKeys = include_archived
        ? [
            this.getDatasetCacheKey({ project_path, dataset_id, archived_only: false }),
            this.getDatasetCacheKey({ project_path, dataset_id, archived_only: true }),
          ]
        : [this.getDatasetCacheKey({ project_path, dataset_id, archived_only: false })];
      for (const key of listKeys) {
        const list = this.workflowLists[key] || [];
        const workflow = list.find((item) => item?.id === workflow_id);
        if (workflow?.id) return workflow;
      }
      return null;
    },

    async fetchWorkflows({ project_path = '', dataset_id = '', archived_only = false } = {}) {
      if (!project_path || !dataset_id) return [];
      const key = this.getDatasetCacheKey({ project_path, dataset_id, archived_only });
      this.workflowLoading[key] = true;
      try {
        const workflows = await api.getTrainingWorkflows({ project_path, dataset_id, archived_only });
        const normalized = Array.isArray(workflows) ? workflows : [];
        this.workflowLists[key] = normalized;
        normalized.forEach((workflow) => {
          if (!workflow?.id) return;
          const detailKey = this.getDetailCacheKey({
            project_path,
            dataset_id: workflow.dataset_id || dataset_id,
            workflow_id: workflow.id,
            include_archived: true,
          });
          this.workflowDetails[detailKey] = workflow;
        });
        return normalized;
      } catch (err) {
        handleStoreError(err, this);
        this.workflowLists[key] = [];
        return [];
      } finally {
        this.workflowLoading[key] = false;
      }
    },

    async fetchWorkflowDetail({ project_path = '', dataset_id = '', workflow_id = '', include_archived = false } = {}) {
      if (!project_path || !dataset_id || !workflow_id) return null;
      const key = this.getDetailCacheKey({ project_path, dataset_id, workflow_id, include_archived });
      try {
        const workflow = await api.getTrainingWorkflow({ project_path, dataset_id, workflow_id, include_archived });
        const normalized = workflow?.id ? workflow : null;
        if (normalized) {
          this.workflowDetails[key] = normalized;
          this.workflowDetails[this.getDetailCacheKey({
            project_path,
            dataset_id: normalized.dataset_id || dataset_id,
            workflow_id,
            include_archived: true,
          })] = normalized;
        }
        return normalized;
      } catch (err) {
        handleStoreError(err, this);
        return this.workflowDetails[key] || null;
      }
    },

    async fetchLatestWorkflowTask({
      project_path = '',
      dataset_id = '',
      workflow_id = '',
      task_type = 'training',
      include_archived = true,
    } = {}) {
      const workflow = this.getWorkflowFromState({
        project_path,
        dataset_id,
        workflow_id,
        include_archived,
      }) || await this.fetchWorkflowDetail({
        project_path,
        dataset_id,
        workflow_id,
        include_archived,
      });
      const field = WORKFLOW_LATEST_TASK_FIELD[task_type] || WORKFLOW_LATEST_TASK_FIELD.training;
      return workflow?.[field] || null;
    },

    invalidateDataset({ project_path = '', dataset_id = '' } = {}) {
      if (!project_path || !dataset_id) return;
      const datasetPrefix = toKey(project_path, dataset_id);
      Object.keys(this.workflowLists).forEach((key) => {
        if (key.startsWith(datasetPrefix)) {
          delete this.workflowLists[key];
          delete this.workflowLoading[key];
        }
      });
      Object.keys(this.workflowDetails).forEach((key) => {
        if (key.startsWith(datasetPrefix)) {
          delete this.workflowDetails[key];
        }
      });
    },

    async createWorkflow(data) {
      const workflow = await api.createTrainingWorkflow(data);
      this.invalidateDataset({
        project_path: data?.project_path,
        dataset_id: workflow?.dataset_id || data?.dataset_id,
      });
      return workflow;
    },

    async archiveWorkflow(data, context = {}) {
      const workflow = await api.archiveTrainingWorkflow(data);
      this.invalidateDataset({
        project_path: data?.project_path,
        dataset_id: context?.dataset_id || workflow?.dataset_id || data?.dataset_id,
      });
      return workflow;
    },

    async deleteWorkflow(data, context = {}) {
      const res = await api.deleteTrainingWorkflow(data);
      this.invalidateDataset({
        project_path: data?.project_path,
        dataset_id: context?.dataset_id || data?.dataset_id,
      });
      return res;
    },
  },
});
