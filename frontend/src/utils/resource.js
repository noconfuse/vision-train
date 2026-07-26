const INVALID_FILENAME_RE = /[<>:"/\\|?*\u0000-\u001f]/g;

const sanitizeFilenameStem = (value = '', fallback = 'download') => {
  const candidate = String(value || fallback).trim().replace(INVALID_FILENAME_RE, '_');
  return candidate || fallback;
};

const extractPathLikeValue = (value = '') => {
  const raw = String(value || '').trim();
  if (!raw) return '';
  try {
    const url = new URL(raw, window.location.origin);
    const queryPath = url.searchParams.get('path') || url.searchParams.get('export_dir');
    if (queryPath) return decodeURIComponent(queryPath);
    return decodeURIComponent(url.pathname || raw);
  } catch (_) {
    return decodeURIComponent(raw.split('#')[0].split('?')[0]);
  }
};

export const parseDownloadFilename = (value = '', fallback = 'download') => {
  const normalized = extractPathLikeValue(value).replace(/\/+$/, '');
  const filename = normalized.split('/').pop() || '';
  return sanitizeFilenameStem(filename, fallback);
};

export const getPathBasename = (value = '', fallback = '-') => (
  parseDownloadFilename(value, fallback)
);

export const getPathDisplayName = (value = '', fallback = '-') => {
  if (!value) return fallback;
  return getPathBasename(value, fallback);
};

const ensureFileExtension = (filename = '', extension = '') => {
  const normalizedExtension = String(extension || '').replace(/^\.+/, '');
  if (!normalizedExtension) return filename;
  return filename.toLowerCase().endsWith(`.${normalizedExtension.toLowerCase()}`)
    ? filename
    : `${filename}.${normalizedExtension}`;
};

export const buildDatasetZipFilename = (datasetName = '') => {
  const stem = sanitizeFilenameStem(datasetName || 'dataset', 'dataset');
  return ensureFileExtension(stem, 'zip');
};

const EXPORT_FORMAT_EXTENSION = Object.freeze({
  engine: 'engine',
  onnx: 'onnx',
  openvino: 'xml',
});

export const getModelExportDownloadFilename = (exp = {}, target = 'primary') => {
  if (target === 'bundle') {
    const dirName = parseDownloadFilename(exp?.export_path || exp?.export_dir || '', 'model_export');
    return ensureFileExtension(dirName, 'zip');
  }
  const primaryPath = String(exp?.primary_model_path || '').trim();
  if (primaryPath) return parseDownloadFilename(primaryPath, 'model_export');
  const format = String(exp?.payload?.format || '').toLowerCase();
  const extension = EXPORT_FORMAT_EXTENSION[format] || 'bin';
  const stem = sanitizeFilenameStem(`${format || 'model'}_export`, 'model_export');
  return ensureFileExtension(stem, extension);
};

export const getTemplateBundleDownloadFilename = (record = {}) => {
  const taskId = String(record?.task_id || '').trim();
  const templateType = sanitizeFilenameStem(record?.template_type || 'template', 'template');
  const stem = sanitizeFilenameStem(taskId || 'template', 'template');
  return ensureFileExtension(`${stem}_deployment_template_${templateType}`, 'zip');
};

export const triggerBlobDownload = (blob, filename = 'download') => {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = parseDownloadFilename(filename, 'download');
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
};
