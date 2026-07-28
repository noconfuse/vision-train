export const IMAGE_FILE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.webp', '.avif'];

export const IMAGE_FILE_ACCEPT = IMAGE_FILE_EXTENSIONS.join(',');

export const ARCHIVE_FILE_EXTENSIONS = ['.zip', '.tar', '.tar.gz', '.tgz'];

export const ARCHIVE_FILE_ACCEPT = ARCHIVE_FILE_EXTENSIONS.join(',');

export const UPLOAD_FILE_ACCEPT = `${IMAGE_FILE_ACCEPT},${ARCHIVE_FILE_ACCEPT}`;

export const VIDEO_FILE_EXTENSIONS = ['.mp4', '.avi', '.mov', '.mkv', '.webm'];

export const VIDEO_FILE_ACCEPT = `video/*,${VIDEO_FILE_EXTENSIONS.join(',')}`;

export const VIDEO_FILE_PATTERN = new RegExp(
  `\\.(?:${VIDEO_FILE_EXTENSIONS.map((ext) => ext.slice(1)).join('|')})$`,
  'i',
);

/** 通用上传体积上限（2 GB），按字节计算。 */
export const UPLOAD_SIZE_LIMIT_BYTES = 2 * 1024 * 1024 * 1024;

/** 判断文件是否为受支持的图片（按后缀大小写不敏感比对）。 */
export const isSupportedImageFile = (file) => {
  if (!file) return false;
  const name = String(file.name || '').trim().toLowerCase();
  return IMAGE_FILE_EXTENSIONS.some((ext) => name.endsWith(ext));
};

/** 判断文件名是否为受支持的压缩包（zip/tar/tar.gz/tgz）。 */
export const isSupportedArchiveFile = (name) => {
  const lowered = String(name || '').trim().toLowerCase();
  return ARCHIVE_FILE_EXTENSIONS.some((ext) => lowered.endsWith(ext));
};

/** 判断文件是否为图片或压缩包中的一种。 */
export const isSupportedUploadFile = (file) =>
  isSupportedImageFile(file) || isSupportedArchiveFile(file?.name);

/** 判断文件是否为受支持的视频（按后缀大小写不敏感比对）。 */
export const isSupportedVideoFile = (file) => {
  if (!file) return false;
  const name = String(file.name || '').trim().toLowerCase();
  return VIDEO_FILE_PATTERN.test(name);
};
