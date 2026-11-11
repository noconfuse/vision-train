<template>
  <div class="flex h-screen w-screen overflow-hidden bg-gray-50">
    <!-- 登录 / LandingPage 等全屏路由不显示 Sidebar -->
    <template v-if="$route.meta?.public">
      <RouterView />
    </template>
    <template v-else>
      <!-- 走查聚焦时侧边栏让给图片列表；退出聚焦的入口在列表自己的工具条里，不会没有出口 -->
      <Sidebar v-if="!store.listFocus" />
      <div class="flex-1 flex flex-col min-w-0">
        <div v-if="initialLoading" class="flex-1 flex items-center justify-center text-sm text-gray-500 gap-2">
          <span class="vt-inline-spinner h-4 w-4"></span>
          <span>正在加载项目…</span>
        </div>
        <RouterView v-else />
      </div>
    </template>
    <ToastHost />
    <ConfirmDialog />
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { RouterView } from 'vue-router';
import { useMainStore } from './stores/main';
import Sidebar from './components/Sidebar.vue';
import ToastHost from './components/ToastHost.vue';
import ConfirmDialog from './components/ConfirmDialog.vue';

const store = useMainStore();
const initialLoading = computed(() => store.isLoading && store.projects.length === 0);
</script>
