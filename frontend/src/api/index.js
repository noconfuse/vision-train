import axios from 'axios';

const api = axios.create({
  baseURL: '/api'
});

export default {
  // Projects
  getProjects() {
    return api.get('/projects');
  },
  
  // Datasets
  getDatasetInfo(params) {
    return api.get('/dataset/info', { params });
  },
  splitDataset(data) {
    return api.post('/dataset/split', data);
  },
  updateDatasetTags(data) {
    return api.post('/dataset/update_tags', data);
  },
  deleteDatasetFolder(data) {
    return api.post('/dataset/delete_folder', data);
  },
  createDatasetSubset(data) {
    return api.post('/dataset/create_subset', data);
  },
  createAugmentedSubset(data) {
    return api.post('/dataset/augment_subset', data);
  },
  previewAugmentedSubset(data) {
    return api.post('/dataset/augment_subset', { ...data, dry_run: true });
  },
  
  // Dataset Images & Annotation
  getDatasetImages(params) {
    return api.get('/dataset/images', { params });
  },
  getPersonReview(params) {
    return api.get('/dataset/person_review', { params });
  },
  downloadDatasetZip(params) {
    return api.get('/dataset/download', { params, responseType: 'blob' });
  },
  batchDeleteDatasetImages(data) {
    return api.post('/dataset/batch_delete', data);
  },
  reorderDatasetLabels(data) {
    return api.post('/dataset/reorder_labels', data);
  },
  deleteDatasetLabel(data) {
    return api.post('/dataset/delete_label', data);
  },
  deduplicateDatasetImages(data) {
    return api.post('/dataset/deduplicate_images', data);
  },
  mergeDatasets(data) {
    return api.post('/dataset/merge', data);
  },
  autoAnnotate(data) {
    return api.post('/auto_annotate/batch', data);
  },
  getAutoAnnotateStatus() {
    return api.get('/auto_annotate/batch/status');
  },
  getAnnotation(params) {
    return api.get('/annotation/get', { params });
  },
  saveAnnotation(data) {
    return api.post('/annotation/save', data);
  },
  
  // Models
  getModels(params) {
    return api.get('/models', { params });
  },
  exportModel(data) {
    return api.post('/model/export', data);
  },
  getExportStatus() {
    return api.get('/model/export/status');
  },
  getModelExports(params) {
    return api.get('/model/exports', { params });
  },
  
  // Training
  startTraining(data) {
    return api.post('/training/start', data);
  },
  stopTraining() {
    return api.post('/training/stop');
  },
  getTrainingStatus() {
    return api.get('/training/status');
  },
  getTrainingHistory(params) {
    return api.get('/training/history', { params });
  },
  getTrainingRuns(params) {
    return api.get('/training/runs', { params });
  },
  deleteTrainingRun(data) {
    return api.post('/training/delete', data);
  },
  getTrainingRunArtifacts(params) {
    return api.get('/training/run/artifacts', { params });
  },
  
  // Videos
  getVideos(params) {
    return api.get('/videos', { params });
  },
  extractVideo(data) {
    return api.post('/video/extract', data);
  },
  getTasks(params) {
    return api.get('/video/tasks', { params });
  },
  getTaskImages(params) {
    return api.get('/video/task/images', { params });
  },
  importTaskImages(data) {
    return api.post('/video/task/import', data);
  },
  batchDeleteTaskImages(data) {
    return api.post('/video/task/batch_delete', data);
  },
  deleteTaskImages(data) {
    return api.post('/video/task/images/delete', data);
  },
  deleteTask(data) {
    return api.post('/video/task/delete', data);
  }
};
