import { computed, unref } from 'vue';

/**
 * 图片列表的画幅：一屏分成几列，格子按占比铺满整行，图跟着格子铺满。
 *
 * 给的是列数不是像素边长：窗口大了格子跟着变大，看得清东西；窗口小了自动少列，
 * 不会出现「设了每行 8 个，屏不够宽就留一截白」。间隙要算进占比里，否则 8 列
 * 会因为放不下而掉成 7 列，一格宽出来的差异全摊到最后一列上。
 */
export function useAutoFillGrid(columnsRef, options = {}) {
  const { gapPx = 12 } = options;

  const gridClass = computed(() => 'grid content-start');
  const gridStyle = computed(() => {
    const columns = Math.max(1, Math.round(Number(unref(columnsRef)) || 1));
    const minTrack = `calc(${100 / columns}% - ${(gapPx * (columns - 1)) / columns}px)`;
    return {
      gap: `${gapPx}px`,
      gridTemplateColumns: `repeat(auto-fill, minmax(${minTrack}, 1fr))`,
    };
  });

  return { gridClass, gridStyle };
}
