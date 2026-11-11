<template>
  <div class="vt-shell">
    <AppHeader v-if="!store.listFocus" :crumbs="[
      { label: projectName, to: { name: 'home-with-project', params: { project: encodeURIComponent(projectName) } } },
      { label: datasetName || '数据集' }
    ]" :back-href="{ name: 'home-with-project', params: { project: encodeURIComponent(projectName) } }">
      <template #meta>
        <span v-if="dataset" class="vt-tag" :class="getDatasetTypeTagClass(dataset)">
          {{ getDatasetTypeLabel(dataset) }}
        </span>
      </template>
    </AppHeader>

    <main class="vt-body">
      <PageState
        v-if="loading || (!loading && (!dataset || loadError))"
        :loading="loading"
        :error="!loading ? loadError : ''"
        :empty="!loading && !dataset && !loadError"
        empty-icon="📦"
        empty-text="数据集不存在"
        :loading-text="loadingText"
        @back="goBack"
      />
      <div v-else class="flex-1 min-h-0 flex flex-col">
        <DatasetPreview :key="dataset.dataset_id" class="flex-1 min-h-0" />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useMainStore } from '../stores/main';
import DatasetPreview from '../components/DatasetPreview.vue';
import PageState from '../components/PageState.vue';
import AppHeader from '../components/AppHeader.vue';
import { getDatasetTypeLabel, getDatasetTypeTagClass } from '../domain/dataset/datasetType';

const route = useRoute();
const router = useRouter();
const store = useMainStore();

// URL 中的 dataset_id 是稳定定位键，name 只用于可读展示。
const projectName = computed(() => decodeURIComponent(route.params.project || ''));
const routeDatasetName = computed(() => decodeURIComponent(route.params.name || ''));
const routeDatasetId = computed(() => String(route.query.dataset_id || '').trim());

const project = computed(() => store.projects.find(p => p.name === projectName.value) || null);
const dataset = computed(() => {
  const p = project.value;
  if (!p || !routeDatasetId.value) return null;
  return (p.datasets || []).find((item) => item.dataset_id === routeDatasetId.value) || null;
});
const datasetName = computed(() => dataset.value?.name || routeDatasetName.value);

const loadError = ref('');
const loading = ref(true);
const scanning = ref(false);
const loadingText = computed(() => (scanning.value ? '正在扫描项目数据集...' : '加载中...'));

// 定位键：项目 + dataset_id。同一个键只自动重扫一次，避免刷不中时反复拉全量列表。
const locatorKey = () => `${projectName.value}::${routeDatasetId.value}`;
let settledKey = '';

// 页面打开的数据集以 URL 里的 dataset_id 为准；store 只负责跟上它。
const syncStore = () => {
  if (project.value && store.currentProject?.path !== project.value.path) {
    store.selectProject(project.value);
  }
  if (dataset.value && store.selectedDatasetId !== dataset.value.dataset_id) {
    store.selectDataset(dataset.value);
  }
};

const goBack = () => {
  router.push({
    name: 'home-with-project',
    params: { project: encodeURIComponent(projectName.value) },
  });
};

const missText = (rescanned) => {
  const target = datasetName.value || routeDatasetId.value || '未知数据集';
  const prefix = rescanned ? '重新扫描后仍' : '';
  if (!project.value) {
    return `${prefix}没有项目「${projectName.value}」`;
  }
  return `${prefix}在项目「${projectName.value}」下找不到数据集「${target}」`;
};

// store 里还没有这个数据集时（刚导入、刚新建、直接粘链接进来），由本页重新拉一次项目列表再判。
const syncPageState = async () => {
  loading.value = true;
  loadError.value = '';
  if (dataset.value) {
    syncStore();
    loading.value = false;
    return;
  }
  const key = locatorKey();
  let refreshed = null;
  if (settledKey !== key) {
    settledKey = key;
    scanning.value = true;
    refreshed = await store.fetchProjects({ silent: true });
    scanning.value = false;
  }
  // 等待期间定位键变了：这一轮的判定已过时，交给新一轮，不覆盖当前界面。
  if (key !== locatorKey()) return;
  if (dataset.value) {
    syncStore();
  } else if (refreshed === false) {
    loadError.value = '项目列表刷新失败，本页暂时读不到数据集';
  } else {
    loadError.value = missText(refreshed === true);
  }
  loading.value = false;
};

watch([projectName, routeDatasetId], syncPageState, { immediate: true });

// 后台刷新换了 dataset 对象（不是身份）时，让 store 重新跟上页面正在看的这个数据集。
watch([project, dataset], syncStore);

// 后台刷新把数据集带回来时（例如刚导入的那次重扫晚于本页判定），撤掉旧错误重新判定。
watch(dataset, (now, prev) => {
  if (now && !prev && locatorKey() === settledKey) syncPageState();
});
</script>
