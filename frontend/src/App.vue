<template>
  <div class="flex h-screen w-screen overflow-hidden bg-gray-50">
    <Sidebar />
    <div class="flex-1 flex flex-col min-w-0">
      <RouterView />
    </div>
  </div>
</template>

<script setup>
import { RouterView } from 'vue-router';
import Sidebar from './components/Sidebar.vue';
</script>
