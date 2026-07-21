export const formatBytes = (size, digits = 1) => {
  const value = Number(size || 0);
  if (!value || value <= 0) return '-';
  if (value < 1024) return `${value} B`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(digits)} KB`;
  if (value < 1024 ** 3) return `${(value / (1024 ** 2)).toFixed(digits)} MB`;
  return `${(value / (1024 ** 3)).toFixed(Math.max(digits, 2))} GB`;
};

export const formatDateTime = (value, options = {}) => {
  if (!value) return '-';
  const { withSeconds = false, dateStyle = 'full' } = options;
  const time = new Date(value);
  if (Number.isNaN(time.getTime())) return value;
  const parts = dateStyle === 'compact'
    ? [time.getMonth() + 1, time.getDate()]
    : [
      time.getFullYear(),
      String(time.getMonth() + 1).padStart(2, '0'),
      String(time.getDate()).padStart(2, '0'),
    ];
  const hh = String(time.getHours()).padStart(2, '0');
  const mm = String(time.getMinutes()).padStart(2, '0');
  const ss = String(time.getSeconds()).padStart(2, '0');
  const clock = withSeconds ? `${hh}:${mm}:${ss}` : `${hh}:${mm}`;
  return `${parts.join('-')} ${clock}`;
};

export const parseOptionalNumber = (value, options = {}) => {
  const {
    integer = false,
    min = Number.NEGATIVE_INFINITY,
    max = Number.POSITIVE_INFINITY,
  } = options;
  if (value === null || value === undefined || value === '') return null;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return null;
  if (integer && !Number.isInteger(parsed)) return null;
  if (parsed < min || parsed > max) return null;
  return parsed;
};

export const getModelExportFormatLabel = ({ path = '', format = '' } = {}) => {
  const normalizedPath = String(path || '').toLowerCase();
  const normalizedFormat = String(format || '').toLowerCase();
  if (normalizedPath.endsWith('.onnx') || normalizedFormat === 'onnx') return 'ONNX';
  if (normalizedPath.endsWith('.xml') || normalizedFormat === 'openvino') return 'OpenVINO';
  if (normalizedPath.endsWith('.engine') || normalizedFormat === 'engine') return 'TensorRT';
  return '导出模型';
};

export const isOpenVinoExportPath = (path = '') => String(path || '').toLowerCase().endsWith('.xml');

export * from './resource';
