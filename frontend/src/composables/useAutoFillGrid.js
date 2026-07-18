import { computed, unref } from 'vue';

export function useAutoFillGrid(expandedRef, options = {}) {
  const {
    compactTile = 112,
    regularTile = 132,
    gapClass = 'gap-3',
  } = options;

  const gridClass = computed(() => `grid content-start ${gapClass}`);
  const gridStyle = computed(() => {
    const tileSize = unref(expandedRef) ? compactTile : regularTile;
    return {
      gridTemplateColumns: `repeat(auto-fill, minmax(${tileSize}px, ${tileSize}px))`,
    };
  });

  return {
    gridClass,
    gridStyle,
  };
}
