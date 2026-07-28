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

/**
 * 校验 token 类名称（资源名/类别名等）。
 * 规则与后端 TOKEN_NAME_PATTERN（^[A-Za-z0-9_-]{1,64}$）保持一致。
 *
 * @param {string} value - 待校验名称
 * @param {object} [options]
 * @param {string} [options.fieldName='名称'] - 用于错误提示中的字段名
 * @param {string} [options.emptyMessage] - 为空时的提示；不传则用 ``${fieldName}不能为空``
 * @param {string[]} [options.reservedNames] - 保留名列表（仅 validateResourceName 需要）
 * @returns {string} 错误信息，空串表示通过
 */
const _msg = (fieldName, suffix) =>
  fieldName ? `${fieldName}${suffix}` : suffix;

export const validateTokenName = (value, { fieldName = '', emptyMessage, reservedNames = [] } = {}) => {
  const v = String(value || '').trim();
  if (!v) return emptyMessage ?? _msg(fieldName, '不能为空');
  if (v.length > 64) return _msg(fieldName, '不能超过 64 个字符');
  if (!/^[A-Za-z0-9_-]+$/.test(v)) return _msg(fieldName, '只能包含字母、数字、_、-');
  if (reservedNames.includes(v)) return `"${v}" 是保留名称，请换一个`;
  return '';
};

/**
 * 校验项目/数据集等资源名称。委托给 ``validateTokenName``。
 * @param {string} value
 * @param {object} [options]
 * @param {string} [options.emptyMessage]
 * @param {string[]} [options.reservedNames]
 * @returns {string}
 */
export const validateResourceName = (value, opts = {}) =>
  validateTokenName(value, { fieldName: '名称', ...opts });

/**
 * 数据集类别（dataset.yaml ``names``）名校验。委托给 ``validateTokenName``。
 * 提示文案不含 fieldName 前缀，方便与 `类别名「xxx」${validateCategoryName(x)}` 拼接。
 * @param {string} value
 * @returns {string}
 */
export const validateCategoryName = (value) =>
  validateTokenName(value, { fieldName: '' });

/** 类别名匹配正则，用于「是否合法」的快速判定。*/
export const CATEGORY_NAME_PATTERN = /^[A-Za-z0-9_-]{1,64}$/;

export * from './resource';
