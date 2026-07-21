import axios from 'axios';

// ============================================================================
// 单一 axios instance（不再 default export 一个对象）
// ============================================================================
// 后端统一响应结构（@json_endpoint 装饰器强制）：
//   成功: {success: true,  data: <业务数据>, error: null}
//   失败: {success: false, data: null,         error: "<msg>"}
//
// interceptor 自动 unwrap：
//   - 成功：response.data 直接是业务数据
//   - 失败：throw Error(message)，调用方 try/catch
// ============================================================================

const TOKEN_KEY = 'vt.auth.token';
const USER_KEY = 'vt.auth.user';

export function getAuthToken() {
  return localStorage.getItem(TOKEN_KEY) || '';
}
export function setAuthToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}
export function getStoredUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch (e) {
    return null;
  }
}
export function setStoredUser(user) {
  if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
  else localStorage.removeItem(USER_KEY);
}
export function clearAuth() {
  setAuthToken('');
  setStoredUser(null);
}

function appendAuthTokenToAssetUrl(url) {
  if (typeof url !== 'string') return url;
  if (
    !url.startsWith('/api/file?')
    && !url.startsWith('/api/video/thumbnail?')
    && !url.startsWith('/api/video/stream?')
    && !url.startsWith('/api/video/task/image_file?')
    && !url.startsWith('/api/training/model_export_bundle?')
  ) {
    return url;
  }

  const token = getAuthToken();
  if (!token) return url;

  try {
    const parsed = new URL(url, window.location.origin);
    if (!parsed.searchParams.get('token')) {
      parsed.searchParams.set('token', token);
    }
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch (_) {
    return url;
  }
}

function decorateAssetUrls(value) {
  if (typeof value === 'string') {
    return appendAuthTokenToAssetUrl(value);
  }
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i += 1) {
      value[i] = decorateAssetUrls(value[i]);
    }
    return value;
  }
  if (value && typeof value === 'object') {
    Object.keys(value).forEach((key) => {
      value[key] = decorateAssetUrls(value[key]);
    });
  }
  return value;
}

const http = axios.create({
  baseURL: '/api',
});

// 自动加 Authorization 头
http.interceptors.request.use(cfg => {
  const token = getAuthToken();
  if (token) {
    cfg.headers = cfg.headers || {};
    cfg.headers.Authorization = `Bearer ${token}`;
  }
  return cfg;
});

// 自动 unwrap
http.interceptors.response.use(
  resp => {
    const body = resp.data;
    if (body && typeof body === 'object' && 'success' in body) {
      if (body.success === false) {
        const err = new Error(body.error || '请求失败');
        err.status = resp.status;
        err.code = 'api_error';
        err.data = body;
        return Promise.reject(err);
      }
      resp.data = decorateAssetUrls(body.data);
    }
    return resp;
  },
  err => {
    if (err.response?.status === 401 && !err.config?.url?.includes('/auth/login')) {
      clearAuth();
      window.dispatchEvent(new CustomEvent('vt:auth-expired', {
        detail: { url: err.config?.url },
      }));
    }
    const body = err.response?.data;
    if (body && typeof body === 'object' && 'success' in body && body.success === false) {
      const e = new Error(body.error || '请求失败');
      e.status = err.response.status;
      e.code = 'api_error';
      e.data = body;
      return Promise.reject(e);
    }
    return Promise.reject(err);
  }
);

// 命名导出（axio 风格）
export const get = (url, cfg) => http.get(url, cfg).then(r => r.data);
export const post = (url, data, cfg) => http.post(url, data, cfg).then(r => r.data);
export const put = (url, data, cfg) => http.put(url, data, cfg).then(r => r.data);
export const del = (url, cfg) => http.delete(url, cfg).then(r => r.data);

function consumeSse(url, onEvent) {
  return new Promise((resolve, reject) => {
    const token = getAuthToken();
    const headers = { Accept: 'text/event-stream' };
    if (token) headers.Authorization = `Bearer ${token}`;
    fetch(url, { method: 'GET', headers })
      .then(resp => {
        if (!resp.ok) {
          resp.text().then(t => {
            let msg = `HTTP ${resp.status}`;
            try {
              const j = JSON.parse(t);
              if (j?.error) msg = j.error;
              else if (j?.data?.error) msg = j.data.error;
            } catch (e) {
              if (t) msg = `${msg}: ${t.slice(0, 100)}`;
            }
            reject(new Error(msg));
          }).catch(() => reject(new Error(`HTTP ${resp.status}`)));
          return;
        }
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        let resolved = false;
        const handleSseChunk = (rawChunk) => {
          const chunk = String(rawChunk || '').trim();
          if (!chunk.startsWith('data:')) return false;
          const data = chunk
            .split(/\r?\n/)
            .filter((line) => line.startsWith('data:'))
            .map((line) => line.slice(5).trim())
            .join('\n')
            .trim();
          if (!data) return false;
          let ev;
          try { ev = JSON.parse(data); } catch (e) { return false; }
          if (onEvent) onEvent(ev);
          if (ev.done && ev.success !== undefined) {
            if (resolved) return true;
            resolved = true;
            if (ev.success) resolve(ev); else reject(new Error(ev.error || '处理失败'));
            return true;
          }
          if (ev.done && ev.result?.success) {
            if (resolved) return true;
            resolved = true;
            resolve(ev);
            return true;
          }
          if (ev.done || ev.state === 'ready') {
            if (resolved) return true;
            resolved = true;
            resolve(ev);
            return true;
          }
          if (ev.error || ev.state === 'failed') {
            if (resolved) return true;
            resolved = true;
            reject(new Error(ev.error || '处理失败'));
            return true;
          }
          return false;
        };
        const flushBufferedEvents = () => {
          const blocks = buffer.split(/\r?\n\r?\n/);
          buffer = blocks.pop() || '';
          for (const block of blocks) {
            if (handleSseChunk(block) && resolved) return;
          }
        };
        const flushTrailingBuffer = () => {
          const tail = buffer.trim();
          buffer = '';
          if (tail) handleSseChunk(tail);
        };
        function read() {
          reader.read().then(({ done, value }) => {
            if (done) {
              buffer += decoder.decode();
              flushBufferedEvents();
              if (!resolved) flushTrailingBuffer();
              if (!resolved) reject(new Error('SSE 连接中断'));
              return;
            }
            buffer += decoder.decode(value, { stream: true });
            flushBufferedEvents();
            if (resolved) return;
            read();
          }).catch(err => {
            if (!resolved) reject(err);
          });
        }
        read();
      })
      .catch((err) => {
        reject(err);
      });
  });
}

// ============================================================================
// default export: 业务方法对象
// 所有方法都已 unwrap：直接返回业务数据
// ============================================================================
const api = {
  // Projects
  getProjects() { return get('/projects'); },
  createProject(data) { return post('/project/create', data); },
  updateProject(data) { return post('/project/update', data); },
  deleteProject(data) { return post('/project/delete', data); },
  validateProjectName(data) { return post('/project/validate_name', data); },

  // Dataset upload（带进度）
  importDatasetUpload(formData, onProgress) {
    return post('/dataset/import/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: e => {
        if (onProgress && e.total) {
          onProgress({
            phase: 'uploading',
            progress: Math.round((e.loaded * 30) / e.total),
            message: '上传中...',
          });
        }
      },
    });
  },
  // SSE 流式 import process
  importDatasetProcess(jobId, onEvent) {
    const url = `/api/dataset/import/process?job_id=${encodeURIComponent(jobId)}`;
    // #region debug-point D:sse-start
    __dbgReportDatasetImportSseDrop('D', 'sse_fetch_start', {
      jobId,
      hasToken: !!getAuthToken(),
      url,
    });
    // #endregion
    return consumeSse(url, onEvent);
  },

  // Datasets
  getDatasetInfo(params) { return get('/dataset/info', { params }); },
  splitDataset(data) { return post('/dataset/split', data); },
  updateDatasetTags(data) { return post('/dataset/update_tags', data); },
  clearDatasetAutoLabels(data) { return post('/dataset/clear_auto_labels', data); },
  deleteDatasetFolder(data) { return post('/dataset/delete_folder', data); },
  createDatasetSubset(data) { return post('/dataset/create_subset', data); },
  createAugmentedSubset(data) { return post('/dataset/augment_subset', data); },
  previewAugmentedSubset(data) { return post('/dataset/augment_subset', { ...data, dry_run: true }); },

  // Dataset Images & Annotation
  getDatasetImages(params, cfg = {}) { return get('/dataset/images', { ...(cfg || {}), params }); },
  uploadDatasetImages(formData, onProgress) {
    return post('/dataset/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: e => {
        if (onProgress && e.total) {
          onProgress(Math.round((e.loaded * 100) / e.total));
        }
      },
    });
  },
  downloadDatasetZip(params) {
    return http.get('/dataset/download', { params, responseType: 'blob' }).then(r => r.data);
  },
  batchDeleteDatasetImages(data) { return post('/dataset/batch_delete', data); },
  reorderDatasetLabels(data) { return post('/dataset/reorder_labels', data); },
  deleteDatasetLabel(data) { return post('/dataset/delete_label', data); },
  deduplicateDatasetImages(data) { return post('/dataset/deduplicate_images', data); },
  mergeDatasets(data) { return post('/dataset/merge', data); },
  autoAnnotate(data) { return post('/auto_annotate/batch', data); },
  getAutoAnnotateStatus(params) { return get('/auto_annotate/batch/status', { params }); },
  getAnnotation(params) { return get('/annotation/get', { params }); },
  saveAnnotation(data) { return post('/annotation/save', data); },

  // Models
  getModels(params) { return get('/models', { params }); },
  getPretrainedOptions(params) { return get('/pretrained/options', { params }); },
  preparePretrainedModel(name, onEvent) {
    return consumeSse(`/api/pretrained/prepare?name=${encodeURIComponent(name)}`, onEvent);
  },

  // Training
  createTrainingWorkflow(data) { return post('/training/workflow/create', data); },
  startTraining(data) { return post('/training/start', data); },
  getTrainingRuntimeProfile() { return get('/training/runtime_profile'); },
  getTrainingBatchCalibration(params) { return get('/training/batch_calibration', { params }); },
  startTrainingBatchCalibration(data) { return post('/training/batch_calibration/start', data); },
  getTrainingWorkflows(params) { return get('/training/workflows', { params }); },
  getTrainingWorkflow(params) { return get('/training/workflow', { params }); },
  archiveTrainingWorkflow(data) { return post('/training/workflow/archive', data); },
  restoreTrainingWorkflow(data) { return post('/training/workflow/restore', data); },
  deleteTrainingWorkflow(data) { return post('/training/workflow/delete', data); },
  resumeTraining(data) { return post('/training/resume', data); },
  retryTraining(data) { return post('/training/retry', data); },
  getTrainingRunArtifacts(params) { return get('/training/run/artifacts', { params }); },

  // Tasks
  listTasks(params) { return get('/tasks', { params }); },
  getTask(taskId) { return get(`/tasks/${taskId}`); },
  stopTask(taskId) { return post(`/tasks/${taskId}/stop`, {}); },
  getTrainingMetricsHistory(taskId) { return get('/training/metrics_history', { params: { task_id: taskId } }); },

  // Training model_exports
  getTrainingModelExports(params) { return get('/training/model_exports', { params }); },
  deleteTrainingModelExport(data) { return post('/training/model_export/delete', data); },

  // 评估 / 导出
  startEvaluate(data) { return post('/training/start_evaluate', data); },
  trainingExport(data) { return post('/training/export', data); },

  // Videos
  getVideos(params) { return get('/videos', { params }); },
  uploadVideo(formData, onUploadProgress) {
    return post('/video/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress,
    });
  },
  deleteVideo(data) { return post('/video/delete', data); },
  extractVideo(data) { return post('/video/extract', data); },
  getVideoTasks(params) { return get('/video/tasks', { params }); },
  getTaskImages(params) { return get('/video/task/images', { params }); },
  importTaskImages(data) { return post('/video/task/import', data); },
  batchDeleteTaskImages(data) { return post('/video/task/batch_delete', data); },
  deleteTaskImages(data) { return post('/video/task/images/delete', data); },
  deleteVideoTask(data) { return post('/video/task/delete', data); },
};

export default api;
