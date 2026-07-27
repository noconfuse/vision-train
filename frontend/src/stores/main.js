import { defineStore } from 'pinia';
import api from '../api';
import { useToast } from '../composables/useToast';

// 供 store action 共用的错误处理：
//   - 把 error 写入 state.error（向后兼容旧逻辑 / 模板里的状态展示）
//   - 默认 toast.error；silent=true 或 canceled 时跳过 toast
//   - 不 throw：让 store action 继续走后续分支（保留原有"出错时不阻断"的语义）
export const handleStoreError = (err, state, opts = {}) => {
  const message = (err && err.message) ? err.message : String(err || '未知错误');
  if (state && 'error' in state) state.error = message;
  const skip = opts.silent === true || err?.code === 'canceled';
  if (!skip) {
    try {
      const toast = useToast();
      toast.error(opts.errorMsg || message);
    } catch (_) {
      // store 可能没在 setup 上下文里调用，useToast 失败时静默退回 state.error
    }
  }
  return null;
};

export const useMainStore = defineStore('main', {
  state: () => ({
    projects: [],
    currentProject: null,
    pretrainedModels: [],        // 默认模型列表（训练等场景）
    autoAnnotateModels: [],      // 自动标注候选模型列表
    pretrainedOptions: [],       // 全部官方预设（含未下载）
    selectedDataset: null,
    isLoading: false,
    error: null,
  }),
  
  actions: {
    mergePretrainedStatus(status) {
      if (!status?.name) return;
      const index = this.pretrainedOptions.findIndex((item) => item.name === status.name);
      if (index === -1) return;
      const current = this.pretrainedOptions[index];
      this.pretrainedOptions[index] = {
        ...current,
        is_downloaded: !!status.is_downloaded,
        local_path: status.local_path || null,
        download_state: status.state || (status.is_downloaded ? 'ready' : current.download_state || 'idle'),
        download_progress: typeof status.progress === 'number'
          ? status.progress
          : (status.is_downloaded ? 100 : current.download_progress || 0),
        download_error: status.error || null,
        download_message: status.message || '',
        download_total_bytes: typeof status.total_bytes === 'number'
          ? status.total_bytes
          : (current.download_total_bytes || 0),
        downloaded_bytes: typeof status.bytes_downloaded === 'number'
          ? status.bytes_downloaded
          : (current.downloaded_bytes || 0),
      };
    },

    /**
     * 拉取项目列表
     * @param {Object} [opts]
     * @param {boolean} [opts.silent=false] silent=true 时不切换 isLoading（用于后台局部刷新，不让 Sidebar 闪 loading）
     */
    async fetchProjects(opts = {}) {
      const silent = opts.silent === true;
      if (!silent) this.isLoading = true;
      try {
        const projects = await api.getProjects();
        this.projects = projects;
        // 同步当前项目
        if (this.currentProject) {
          const cur = this.projects.find(p => p.id === this.currentProject.id)
                      || this.projects.find(p => p.path === this.currentProject.path);
          if (cur) this.currentProject = cur;
        }
      } catch (err) {
        // silent 只控制 isLoading；错误一律提示用户。
        handleStoreError(err, this);
      } finally {
        if (!silent) this.isLoading = false;
      }
    },

    async createProject(name, description = '') {
      const res = await api.createProject({ name, description });
      await this.fetchProjects({ silent: true });
      return res;
    },

    async updateProject({ name, new_name, description }) {
      const res = await api.updateProject({ name, new_name, description });
      await this.fetchProjects({ silent: true });
      // 同步更新当前项目引用
      if (this.currentProject && (this.currentProject.name === name)) {
        this.currentProject = res;
      }
      return res;
    },

    async deleteProject(name) {
      const res = await api.deleteProject({ name, confirm: true });
      if (this.currentProject?.name === name) {
        this.currentProject = null;
        this.selectedDataset = null;
      }
      await this.fetchProjects({ silent: true });
      return res;
    },

    async importDataset(file, projectPath, targetName, visionTaskType, onProgress) {
      // Phase 1: 上传
      const fd = new FormData();
      fd.append('file', file);
      if (projectPath) fd.append('project_path', projectPath);
      if (targetName) fd.append('target_name', targetName);
      if (visionTaskType) fd.append('vision_task_type', visionTaskType);
      const upRes = await api.importDatasetUpload(fd, onProgress);
      const jobId = upRes?.job_id;
      if (!jobId) {
        throw new Error('上传失败：未返回 job_id');
      }
      // Phase 2: SSE 处理（30%~100%）
      const final = await api.importDatasetProcess(jobId, (ev) => {
        if (!ev.done && onProgress) {
          // 30% 起：保证 uploading 阶段完成后不再回退
          const p = Math.max(30, ev.progress ?? 30);
          onProgress({
            phase: ev.phase,
            progress: p,
            message: ev.message,
          });
        }
      });
      // silent 刷新：不触发 Sidebar 的 loading
      await this.fetchProjects({ silent: true });
      return final.result || final;  // 含 source_format
    },

    async validateProjectName(name) {
      const res = await api.validateProjectName({ name });
      return res;
    },
    
    async fetchModels(visionTaskType, usage = '') {
      if (!this.currentProject) return;
      try {
        const models = await api.getModels({
          project_path: this.currentProject.path,
          vision_task_type: visionTaskType || undefined,
          usage: usage || undefined,
        });
        if (usage === 'auto_annotate') {
          this.autoAnnotateModels = models || [];
          return;
        }
        this.pretrainedModels = models || [];
      } catch (err) {
        handleStoreError(err, this);
        if (usage === 'auto_annotate') {
          this.autoAnnotateModels = [];
          return;
        }
        this.pretrainedModels = [];
      }
    },

    async fetchPretrainedOptions(visionTaskType) {
      try {
        const res = await api.getPretrainedOptions({
          vision_task_type: visionTaskType || undefined,
        });
        this.pretrainedOptions = Array.isArray(res) ? res : [];
      } catch (err) {
        handleStoreError(err, this);
        this.pretrainedOptions = [];
      }
    },

    async preparePretrainedModel(name, visionTaskType, onEvent) {
      const result = await api.preparePretrainedModel(name, (event) => {
        this.mergePretrainedStatus(event);
        if (onEvent) onEvent(event);
      });
      await this.fetchPretrainedOptions(visionTaskType);
      return result;
    },

    selectProject(project) {
      this.currentProject = project;
      this.selectedDataset = null;
    },

    selectDataset(dataset) {
      this.selectedDataset = dataset;
    },
  }
});
