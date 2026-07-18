<template>
  <router-link
    v-if="!isTasksCenter"
    :to="tasksCenterLink"
    class="vt-btn-secondary vt-btn-size-md font-mono"
  >
    <AppIcon name="tasks" class="h-4 w-4" />
    <span>任务中心</span>
  </router-link>
</template>

<script setup>
import { computed } from 'vue';
import { useRoute } from 'vue-router';
import AppIcon from './ui/AppIcon.vue';

// 入口按钮：跳到全局任务中心。
// 不再做轮询；轮询只在打开任务中心时由 TasksCenterPage 单独负责。
const route = useRoute();
const isTasksCenter = computed(() => route.name === 'tasks-center');
const tasksCenterLink = computed(() => ({
  name: 'tasks-center',
  query: route.fullPath ? { return_to: route.fullPath } : {},
}));
</script>
