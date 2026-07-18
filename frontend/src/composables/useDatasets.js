// 数据集统一访问 composable
// 业务里常见的 "把所有数据集拼起来" 模式统一收口
import { computed } from 'vue';
import { useMainStore } from '../stores/main';

/**
 * 统一访问数据集集合
 * - allDatasets:         当前项目优先的数据集列表
 * - allDatasetsGlobal:   所有项目下的数据集聚合
 * - hasAnyDataset:       任一数据集非空
 *
 * 说明：
 * - 详情页/训练页的路由恢复必须使用 project + dataset name 精确匹配；
 * - 这里的全局聚合仅用于训练历史、创建后回填等辅助查找，不应用于详情页路由判定。
 */
export const useDatasets = () => {
  const store = useMainStore();

  const projectDatasets = computed(() => (
    Array.isArray(store.currentProject?.datasets) ? store.currentProject.datasets : []
  ));

  // 全局数据集：所有项目下的 datasets 单列表
  // 仅作为辅助查找能力，不用于详情页/训练页的路由恢复
  const allDatasetsGlobal = computed(() => {
    const out = [];
    for (const p of store.projects || []) {
      if (Array.isArray(p?.datasets)) out.push(...p.datasets);
    }
    return out;
  });

  // 当前项目优先；未选中项目时退回到全局
  const allDatasets = computed(() => {
    if (store.currentProject) {
      return projectDatasets.value;
    }
    return allDatasetsGlobal.value;
  });

  const hasAnyDataset = computed(() => allDatasets.value.length > 0);

  /**
   * 查找数据集（按 name / path / function predicate）
   * 优先当前项目，找不到就退到全局
   */
  const findDataset = (predicate) => {
    const fn = typeof predicate === 'function'
      ? predicate
      : (d) => d?.name === predicate || d?.path === predicate;
    return allDatasets.value.find(fn) || allDatasetsGlobal.value.find(fn) || null;
  };

  return {
    allDatasets,
    projectDatasets,
    allDatasetsGlobal,
    hasAnyDataset,
    findDataset,
  };
};
