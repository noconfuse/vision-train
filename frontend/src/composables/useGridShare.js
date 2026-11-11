import { computed, ref } from 'vue';

/**
 * 走查列表的画幅三档：一屏排几列。
 *
 * 「大图」看的是一帧里的细节，「小图」看的是一批图的分布，中间那档平时用。
 * 存的是浏览器偏好（这台屏幕多大由我自己定），不是数据集的状态，所以不进后端。
 */
export const GRID_SHARE_OPTIONS = [
  { key: 'lg', label: '大图', columns: 5, hint: '一屏 5 列，看得清单个目标' },
  { key: 'md', label: '中图', columns: 8, hint: '一屏 8 列，细节和总量都能顾上' },
  { key: 'sm', label: '小图', columns: 13, hint: '一屏 13 列，一屏扫过的图最多' },
];

const STORAGE_KEY = 'vt-grid-share';

export function useGridShare(defaultKey = 'md') {
  const stored = (() => {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (_) {
      return null;
    }
  })();
  const shareKey = ref(GRID_SHARE_OPTIONS.some((option) => option.key === stored) ? stored : defaultKey);
  const columns = computed(() => GRID_SHARE_OPTIONS.find((option) => option.key === shareKey.value).columns);

  const setShare = (key) => {
    const option = GRID_SHARE_OPTIONS.find((item) => item.key === key);
    if (!option) return;
    shareKey.value = option.key;
    try {
      localStorage.setItem(STORAGE_KEY, option.key);
    } catch (_) {
      // 隐私模式下存不下就用当前这次，不弹错
    }
  };

  return { shareKey, columns, setShare };
}
