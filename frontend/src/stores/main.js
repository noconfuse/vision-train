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
    }
  }
});
