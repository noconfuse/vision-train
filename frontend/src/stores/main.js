import { defineStore } from 'pinia';
import api from '../api';

export const useMainStore = defineStore('main', {
  state: () => ({
    projects: [],
    currentProject: null,
    pretrainedModels: [],
    selectedDataset: null,
    trainingStatus: {
      is_running: false,
      progress: 0,
      message: '',
      results: {}
    },
    trainingRuns: [],
    exportStatus: {
      is_running: false,
      progress: 0,
      message: '',
      download_url: null
    },
    testInferStatus: {
      is_running: false,
      progress: 0,
      message: '',
      results: []
    },
    testDirs: [],
    isLoading: false,
    error: null
  }),
  
  actions: {
    async fetchProjects() {
      this.isLoading = true;
      try {
        const res = await api.getProjects();
        if (res.data.success) {
          this.projects = res.data.projects;
        }
      } catch (err) {
        this.error = err.message;
      } finally {
        this.isLoading = false;
      }
    },
    
    async fetchModels() {
      if (!this.currentProject) return;
      try {
        const res = await api.getModels({ project_path: this.currentProject.path });
        if (res.data?.success) {
          this.pretrainedModels = res.data.models || [];
        } else {
          this.pretrainedModels = [];
        }
      } catch (err) {
        console.error(err);
      }
    },

    selectProject(project) {
      this.currentProject = project;
      this.selectedDataset = null;
    },

    selectDataset(dataset) {
      this.selectedDataset = dataset;
    },
    
    async pollTrainingStatus() {
      if (!this.trainingStatus.is_running) return;
      try {
        const res = await api.getTrainingStatus();
        if (res.data.success) {
          this.trainingStatus = res.data.status;
          if (this.trainingStatus.is_running) {
            setTimeout(() => this.pollTrainingStatus(), 1000);
          }
        }
      } catch (e) {
        console.error(e);
      }
    },
    
    async startTraining(config) {
      try {
        const res = await api.startTraining(config);
        if (res.data.success) {
          this.trainingStatus.is_running = true;
          this.pollTrainingStatus();
        } else {
          throw new Error(res.data.error);
        }
        return res.data;
      } catch (err) {
        throw err;
      }
    },
    
    async stopTraining() {
      try {
        await api.stopTraining();
        this.trainingStatus.is_running = false;
      } catch (err) {
        console.error(err);
      }
    },

    async fetchTrainingRuns() {
      if (!this.currentProject) return;
      try {
        const res = await api.getTrainingRuns({ project_path: this.currentProject.path });
        if (res.data.success) {
          this.trainingRuns = res.data.runs;
        }
      } catch (err) {
        console.error(err);
      }
    },

    async startExport(payload) {
      try {
        const res = await api.exportModel(payload);
        if (res.data.success) {
          this.exportStatus.is_running = true;
          this.exportStatus.message = 'Starting export...';
          this.pollExportStatus();
          return { success: true };
        } else {
          return { success: false, error: res.data.error };
        }
      } catch (err) {
        return { success: false, error: err.message };
      }
    },

    async pollExportStatus() {
      if (!this.exportStatus.is_running) return;
      try {
        const res = await api.getExportStatus();
        if (res.data.success) {
          const status = res.data.status;
          this.exportStatus = { ...this.exportStatus, ...status };
          
          if (status.is_running) {
            setTimeout(() => this.pollExportStatus(), 1000);
          } else {
             // Refresh runs or exports if needed?
             // Maybe fetch exports for the specific run?
          }
        }
      } catch (e) {
        console.error(e);
        this.exportStatus.is_running = false;
      }
    },

    async getModelExports(trainingId) {
        if (!this.currentProject) return [];
        try {
            const res = await api.getModelExports({ 
                project_path: this.currentProject.path,
                training_id: trainingId 
            });
            if (res.data.success) {
                return res.data.exports;
            }
            return [];
        } catch (e) {
            console.error(e);
            return [];
        }
    },

    async startTestInference(payload) {
      try {
        const res = await api.startTestInference(payload);
        if (res.data.success) {
          this.testInferStatus.is_running = true;
          this.testInferStatus.progress = 0;
          this.testInferStatus.message = '启动推理...';
          this.testInferStatus.results = [];
          this.pollTestInferenceStatus();
          return { success: true };
        } else {
          return { success: false, error: res.data.error };
        }
      } catch (err) {
        return { success: false, error: err.message };
      }
    },

    async pollTestInferenceStatus() {
      if (!this.testInferStatus.is_running) return;
      try {
        const res = await api.getTestInferenceStatus();
        if (res.data.success) {
          const st = res.data.status;
          this.testInferStatus = {
            ...this.testInferStatus,
            is_running: !!st.is_running,
            progress: st.progress || 0,
            message: st.message || '',
            results: st.results || [],
            output_dir_url: st.output_dir_url || null
          };
          if (st.is_running) {
            setTimeout(() => this.pollTestInferenceStatus(), 1000);
          }
        }
      } catch (e) {
        console.error(e);
        this.testInferStatus.is_running = false;
      }
    },

    async fetchTestDirs() {
      if (!this.currentProject) return;
      try {
        const res = await api.getTestDirs({ project_path: this.currentProject.path });
        if (res.data.success) {
          this.testDirs = res.data.dirs || [];
        } else {
          this.testDirs = [];
        }
      } catch (e) {
        console.error(e);
        this.testDirs = [];
      }
    }
  }
});
