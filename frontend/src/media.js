export const IMAGE_FILE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.bmp', '.webp', '.avif'];

export const IMAGE_FILE_ACCEPT = IMAGE_FILE_EXTENSIONS.join(',');

export const isSupportedImageFile = (file) => {
  if (!file) return false;
  const name = String(file.name || '').trim().toLowerCase();
  return IMAGE_FILE_EXTENSIONS.some((ext) => name.endsWith(ext));
};
