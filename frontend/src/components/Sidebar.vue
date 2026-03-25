<template>
  <div class="w-80 bg-white border-r border-gray-200 flex flex-col h-full">
    <div class="h-16 shrink-0 px-5 bg-slate-800 text-white flex items-center shadow-sm z-20">
      <h2 class="text-lg font-semibold tracking-wide">视觉项目列表</h2>
    </div>
    
    <div class="flex-1 overflow-y-auto p-3">
      <div v-if="store.isLoading" class="p-4 text-center text-gray-500">
        加载中...
      </div>
      <div v-else-if="store.projects.length === 0" class="p-4 text-center text-gray-500">
        暂无项目
      </div>
      
      <div v-for="p in store.projects" 
           :key="p.id"
           class="p-4 mb-2 rounded-lg cursor-pointer transition-colors duration-200"
           :class="store.currentProject?.id === p.id ? 'bg-blue-500 text-white' : 'bg-gray-50 hover:bg-gray-100'"
           @click="selectProject(p)">
        <div class="font-semibold mb-1">{{ p.name }}</div>
        <div class="text-xs opacity-80">
          Trainable: {{ p.datasets?.trainable?.length || 0 }} | 
          Annotatable: {{ p.datasets?.annotatable?.length || 0 }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useMainStore } from '../stores/main';
import { onMounted } from 'vue';
import { useRouter } from 'vue-router';

const store = useMainStore();
const router = useRouter();

const selectProject = (project) => {
  store.selectProject(project);
  router.push({ path: '/', query: { view: 'datasets' } });
};

onMounted(() => {
  store.fetchProjects();
});
</script>
