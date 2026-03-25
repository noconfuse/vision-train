<script setup>
import { ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useMainStore } from '../stores/main';
import DatasetList from '../components/DatasetList.vue';
import TrainingPanel from '../components/TrainingPanel.vue';
import DatasetPreview from '../components/DatasetPreview.vue';
import VideoPanel from '../components/VideoPanel.vue';

const store = useMainStore();
const route = useRoute();
const router = useRouter();

const activeTab = ref(route.query.tab === 'train' ? 'train' : 'preview');
const activeView = ref(route.query.view === 'videos' ? 'videos' : 'datasets');

const updateRouteQuery = (next = {}) => {
  router.replace({
    path: '/',
    query: {
      ...route.query,
      ...next
    }
  });
};

const setActiveView = (view) => {
  activeView.value = view;
  updateRouteQuery({ view });
};

const setActiveTab = (tab) => {
  activeTab.value = tab;
  updateRouteQuery({ tab });
};

const syncDatasetFromRoute = () => {
  if (!store.currentProject) return;
  const datasetPath = route.query.datasetPath;
  const datasetName = route.query.datasetName;
  if (!datasetPath && !datasetName) return;
  const allDatasets = [
    ...(store.currentProject.datasets?.trainable || []),
    ...(store.currentProject.datasets?.annotatable || [])
  ];
  const matched = allDatasets.find((ds) => ds.path === datasetPath || ds.name === datasetName);
  if (matched && store.selectedDataset?.path !== matched.path) {
    store.selectDataset(matched);
  }
};

watch(() => route.query.tab, (tab) => {
  activeTab.value = tab === 'train' ? 'train' : 'preview';
});

watch(() => route.query.view, (view) => {
  activeView.value = view === 'videos' ? 'videos' : 'datasets';
});

watch(
  () => [store.currentProject?.path, route.query.datasetPath, route.query.datasetName],
  () => {
    syncDatasetFromRoute();
  },
  { immediate: true }
);
</script>

<template>
  <div class="flex flex-col min-w-0 h-full">
    <header class="h-16 bg-white border-b border-gray-200 px-8 flex justify-between items-center shadow-sm z-10 shrink-0">
      <h1 class="text-xl font-bold text-slate-800">
        {{ store.currentProject ? store.currentProject.name : 'Select a Project' }}
      </h1>

      <div v-if="store.currentProject" class="flex bg-gray-100 p-1 rounded-lg">
        <button
          @click="setActiveView('datasets')"
          class="px-4 py-1.5 text-sm font-medium rounded-md transition-all"
          :class="activeView === 'datasets' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
        >
          Datasets
        </button>
        <button
          @click="setActiveView('videos')"
          class="px-4 py-1.5 text-sm font-medium rounded-md transition-all"
          :class="activeView === 'videos' ? 'bg-white text-blue-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'"
        >
          Videos
        </button>
      </div>

      <div class="flex items-center gap-4">
        <div class="text-sm text-gray-500">
          Version 2.0 (Vue+Vite)
        </div>
      </div>
    </header>

    <main class="flex-1 overflow-y-auto p-8">
      <div v-if="store.currentProject">
        <div v-if="activeView === 'videos'" class="h-full">
          <VideoPanel />
        </div>

        <div v-else>
          <DatasetList />

          <div v-if="store.selectedDataset" class="mt-8">
            <div class="flex gap-2 mb-4 border-b border-gray-200">
              <button
                @click="setActiveTab('preview')"
                class="px-6 py-3 font-medium text-sm rounded-t-lg transition-colors relative top-[1px]"
                :class="activeTab === 'preview' ? 'bg-white text-blue-600 border-x border-t border-gray-200 border-b-white' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'"
              >
                📊 数据预览 & 标注
              </button>
              <button
                @click="setActiveTab('train')"
                class="px-6 py-3 font-medium text-sm rounded-t-lg transition-colors relative top-[1px]"
                :class="activeTab === 'train' ? 'bg-white text-blue-600 border-x border-t border-gray-200 border-b-white' : 'text-gray-500 hover:text-gray-700 hover:bg-gray-50'"
              >
                🚀 训练配置
              </button>
            </div>

            <transition name="fade" mode="out-in">
              <div v-if="activeTab === 'preview'">
                <DatasetPreview />
              </div>
              <div v-else-if="activeTab === 'train'">
                <TrainingPanel />
              </div>
            </transition>
          </div>
        </div>
      </div>

      <div v-else class="flex flex-col items-center justify-center h-full text-gray-400">
        <svg xmlns="http://www.w3.org/2000/svg" class="h-16 w-16 mb-4 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
        </svg>
        <p class="text-lg">请从左侧选择一个项目开始</p>
      </div>
    </main>
  </div>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
