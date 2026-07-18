<script setup>
import { ref, watch, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useMainStore } from '../stores/main';
import DatasetList from '../components/DatasetList.vue';
import VideoPanel from '../components/VideoPanel.vue';
import AppHeader from '../components/AppHeader.vue';
import AppIcon from '../components/ui/AppIcon.vue';

const store = useMainStore();
const route = useRoute();
const router = useRouter();

// URL 是项目上下文的唯一来源
const routeProjectName = computed(() => decodeURIComponent(route.params.project || ''));

const activeView = ref(route.query.view === 'videos' ? 'videos' : 'datasets');

const project = computed(() => {
  if (!routeProjectName.value) return null;
  return store.projects.find(p => p.name === routeProjectName.value) || null;
});

// 当 store.currentProject 与 URL 不一致时同步（避免点击其他组件时残留）
const syncStoreProject = () => {
  if (project.value && store.currentProject?.path !== project.value.path) {
    store.selectProject(project.value);
  }
};

// 切 view：只换 query，不换项目
const setActiveView = (view) => {
  activeView.value = view;
  router.replace({
    name: route.name,
    params: route.params,
    query: { ...route.query, view },
  });
};

// 路由变化 → 同步项目上下文
watch(
  [() => route.params.project, () => store.projects.length],
  () => {
    // / 路径上且没有 currentProject → 跳到第一个项目
    if (!routeProjectName.value) {
      const first = store.projects[0];
      if (first) {
        router.replace({
          name: 'home-with-project',
          params: { project: encodeURIComponent(first.name) },
        });
      }
      return;
    }
    syncStoreProject();
  },
  { immediate: true }
);

watch(() => route.query.view, (view) => {
  activeView.value = view === 'videos' ? 'videos' : 'datasets';
});
</script>

<template>
  <div class="vt-shell">
    <AppHeader :crumbs="[
      { label: project ? project.name : '请选择项目' },
      { label: '/ 数据集与视频' }
    ]">
      <template v-if="project" #tabs>
        <button
          @click="setActiveView('datasets')"
          class="vt-segmented-tab"
          :class="{ 'vt-segmented-tab--active': activeView === 'datasets' }"
        >
          <AppIcon name="dataset" class="h-4 w-4" />
          <span>数据集</span>
        </button>
        <button
          @click="setActiveView('videos')"
          class="vt-segmented-tab"
          :class="{ 'vt-segmented-tab--active': activeView === 'videos' }"
        >
          <AppIcon name="video" class="h-4 w-4" />
          <span>视频</span>
        </button>
      </template>
    </AppHeader>

    <main class="vt-body" :class="activeView === 'videos' ? 'overflow-hidden' : 'overflow-y-auto'">
      <div v-if="project" class="flex-1 min-h-0 flex flex-col">
        <div v-if="activeView === 'videos'" class="flex-1 min-h-0 flex flex-col">
          <VideoPanel />
        </div>
        <div v-else>
          <DatasetList />
        </div>
      </div>

      <div v-else class="vt-empty">
        <div class="text-3xl text-gray-300">📁</div>
        <div class="text-sm text-gray-500">请从左侧选择一个项目开始</div>
      </div>
    </main>
  </div>
</template>
