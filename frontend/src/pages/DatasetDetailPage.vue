<template>
  <div class="vt-shell">
    <AppHeader :crumbs="[
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
        loading-text="加载中..."
        @back="goBack"
      />
      <div v-else class="flex-1 min-h-0 flex flex-col">
        <DatasetPreview :key="dataset.path" class="flex-1 min-h-0" />
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
import { getDatasetTypeLabel, getDatasetTypeTagClass } from '../datasetType';

const route = useRoute();
const router = useRouter();
const store = useMainStore();

// URL 是上下文的唯一来源：path 同时携带 project + name
const projectName = computed(() => decodeURIComponent(route.params.project || ''));
const datasetName = computed(() => decodeURIComponent(route.params.name || ''));

const project = computed(() => store.projects.find(p => p.name === projectName.value) || null);
const dataset = computed(() => {
  const p = project.value;
  if (!p) return null;
  return (p.datasets || []).find(d => d.name === datasetName.value) || null;
});

const loadError = ref('');
const loading = ref(true);

const syncStore = () => {
  if (project.value && store.currentProject?.path !== project.value.path) {
    store.selectProject(project.value);
  }
  if (dataset.value && store.selectedDataset?.path !== dataset.value.path) {
    store.selectDataset(dataset.value);
  }
};

const goBack = () => {
  router.push({
    name: 'home-with-project',
    params: { project: encodeURIComponent(projectName.value) },
  });
};

const ensureProjectsLoaded = async () => {
  if (store.projects.length === 0) {
    try { await store.fetchProjects({ silent: true }); } catch (_) { /* silent */ }
  }
};

const syncPageState = async () => {
  loading.value = true;
  loadError.value = '';
  await ensureProjectsLoaded();
  if (dataset.value) {
    syncStore();
  } else if (project.value) {
    loadError.value = `项目「${projectName.value}」下找不到数据集「${datasetName.value}」`;
  } else {
    loadError.value = `项目「${projectName.value}」不存在`;
  }
  loading.value = false;
};

watch([projectName, datasetName], syncPageState, { immediate: true });
</script>
