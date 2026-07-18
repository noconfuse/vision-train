<template>
  <div class="flex h-screen w-screen overflow-hidden bg-gray-50">
    <!-- 登录 / LandingPage 等全屏路由不显示 Sidebar -->
    <template v-if="$route.meta?.public">
      <RouterView />
    </template>
    <template v-else>
      <Sidebar />
      <div class="flex-1 flex flex-col min-w-0">
        <RouterView />
      </div>
    </template>
    <ToastHost />
    <ConfirmDialog />
  </div>
</template>

<script setup>
import { RouterView } from 'vue-router';
import Sidebar from './components/Sidebar.vue';
import ToastHost from './components/ToastHost.vue';
import ConfirmDialog from './components/ConfirmDialog.vue';
</script>
