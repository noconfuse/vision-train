<template>
  <div class="flex flex-col h-full min-w-0">
    <header class="h-16 bg-white border-b border-gray-200 px-8 flex items-center justify-between shadow-sm shrink-0">
      <div class="flex items-center gap-4 min-w-0">
        <button @click="goBack" class="px-4 py-2 rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-50">返回</button>
        <div class="min-w-0">
          <h1 class="text-xl font-bold text-slate-800 truncate">训练历史：{{ datasetName || '-' }}</h1>
          <div class="text-sm text-gray-500 truncate">{{ store.currentProject?.name || projectPath || '未选择项目' }}</div>
        </div>
      </div>
      <button @click="loadHistory" class="px-4 py-2 rounded-lg bg-slate-800 text-white hover:bg-slate-900">刷新</button>
    </header>

    <main class="flex-1 overflow-y-auto p-8">
      <div class="bg-white rounded-xl shadow-sm border border-gray-100">
        <div class="px-6 py-5 border-b border-gray-100 flex items-center justify-between gap-4">
          <div>
            <div class="text-lg font-semibold text-slate-800">运行列表</div>
            <div class="text-sm text-gray-500">支持按具体 run 继续训练</div>
          </div>
          <div class="text-sm text-gray-500">共 {{ runs.length }} 条</div>
        </div>

        <div v-if="loading" class="py-16 text-center text-gray-500">加载中...</div>
        <div v-else-if="loadError" class="py-16 text-center text-rose-600">{{ loadError }}</div>
        <div v-else-if="runs.length === 0" class="py-16 text-center text-gray-500">暂无训练记录</div>
        <div v-else class="overflow-auto">
          <table class="min-w-full text-sm">
            <thead class="bg-gray-50 text-gray-600">
              <tr>
                <th class="text-left px-4 py-3 font-medium">训练ID</th>
                <th class="text-left px-4 py-3 font-medium">模型</th>
                <th class="text-left px-4 py-3 font-medium">epochs</th>
                <th class="text-left px-4 py-3 font-medium">imgsz</th>
                <th class="text-left px-4 py-3 font-medium">mAP50</th>
                <th class="text-left px-4 py-3 font-medium">mAP50-95</th>
                <th class="text-left px-4 py-3 font-medium">状态</th>
                <th class="text-left px-4 py-3 font-medium">时间</th>
                <th class="text-left px-4 py-3 font-medium">操作</th>
              </tr>
            </thead>
            <tbody class="divide-y divide-gray-100">
              <tr v-for="run in runs" :key="runKey(run)" class="hover:bg-gray-50">
                <td class="px-4 py-3 font-mono text-xs text-gray-700">{{ runKey(run) }}</td>
                <td class="px-4 py-3 text-gray-700">{{ run.model_name || run.config?.model_name || '-' }}</td>
                <td class="px-4 py-3 text-gray-700">{{ run.config?.epochs ?? '-' }}</td>
                <td class="px-4 py-3 text-gray-700">{{ run.config?.imgsz ?? '-' }}</td>
                <td class="px-4 py-3 text-gray-700">{{ displayMetric(run, 'mAP50', 'map50') }}</td>
                <td class="px-4 py-3 text-gray-700">{{ displayMetric(run, 'mAP50-95', 'map') }}</td>
                <td class="px-4 py-3">
                  <span class="px-2 py-1 rounded-full text-xs font-medium" :class="run.can_resume ? 'bg-emerald-50 text-emerald-700' : 'bg-sky-50 text-sky-700'">
                    {{ run.can_resume ? '可继续' : '已完成' }}
                  </span>
                </td>
                <td class="px-4 py-3 text-gray-500 text-xs">{{ run.created_at || '-' }}</td>
                <td class="px-4 py-3 text-xs">
                  <div class="flex items-center gap-3">
                    <button
                      @click="resumeRun(run)"
                      :disabled="!run.can_resume || store.trainingStatus.is_running"
                      class="text-emerald-600 hover:underline disabled:text-gray-300 disabled:no-underline"
                    >
                      继续训练
                    </button>
                    <button @click="deleteRun(run)" class="text-rose-600 hover:underline">删除</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </main>
  </div>
</template>
<script setup>
import { computed, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useMainStore } from '../stores/main';
import api from '../api';

const route = useRoute();
const router = useRouter();
const store = useMainStore();

const loading = ref(false);
const loadError = ref('');
const runs = ref([]);
const datasetContext = ref(null);

const datasetName = computed(() => datasetContext.value?.name || route.query.datasetName || '');
const datasetPath = computed(() => datasetContext.value?.path || route.query.datasetPath || '');
const projectPath = computed(() => store.currentProject?.path || route.query.projectPath || '');

const runKey = (run) => run?.training_id || run?.id;

const metric = (run, ...keys) => {
  const values = run?.metrics;
  if (!values || typeof values !== 'object') return undefined;
  for (const key of keys) {
    if (values[key] !== undefined && values[key] !== null && values[key] !== '') return values[key];
  }
  return undefined;
};

const displayMetric = (run, ...keys) => {
  const value = metric(run, ...keys);
  return typeof value === 'number' ? value.toFixed(4) : '-';
};

const resolveContext = async () => {
  const requestedProjectPath = route.query.projectPath;
  if (!store.projects.length) await store.fetchProjects();
  let project = store.currentProject;
  if (requestedProjectPath && project?.path !== requestedProjectPath) {
    project = store.projects.find((item) => item.path === requestedProjectPath) || null;
  }
  if (!project && store.projects.length === 1) {
    project = store.projects[0];
  }
  if (project && store.currentProject?.path !== project.path) {
    store.selectProject(project);
  }
  const allDatasets = [
    ...(store.currentProject?.datasets?.trainable || []),
    ...(store.currentProject?.datasets?.annotatable || [])
  ];
  const matchedDataset = allDatasets.find((ds) => ds.path === route.query.datasetPath || ds.name === route.query.datasetName) || null;
  if (matchedDataset) {
    store.selectDataset(matchedDataset);
  }
  datasetContext.value = matchedDataset || (route.query.datasetName ? { name: route.query.datasetName, path: route.query.datasetPath || '' } : null);
};

const loadHistory = async () => {
  loading.value = true;
  loadError.value = '';
  runs.value = [];
  try {
    await resolveContext();
    if (!projectPath.value || !datasetName.value) {
      loadError.value = '缺少项目路径或数据集名称';
      return;
    }
    const res = await api.getTrainingHistory({
      project_path: projectPath.value,
      dataset_name: datasetName.value
    });
    if (!res.data.success) {
      loadError.value = res.data.error || '加载失败';
      return;
    }
    runs.value = res.data.history || [];
  } catch (e) {
    console.error(e);
    loadError.value = '请求失败';
  } finally {
    loading.value = false;
  }
};

const goBack = () => {
  router.push({
    path: '/',
    query: { view: 'datasets', datasetName: datasetName.value, datasetPath: datasetPath.value }
  });
};

const resumeRun = async (run) => {
  if (!run.can_resume || store.trainingStatus.is_running) return;
  try {
    const res = await api.resumeTraining({
      project_path: projectPath.value,
      dataset_name: datasetName.value,
      training_id: runKey(run)
    });
    if (!res.data.success) {
      alert(res.data.error || '继续训练失败');
      return;
    }
    store.trainingStatus.is_running = true;
    store.trainingStatus.message = `恢复训练中: ${runKey(run)}`;
    store.pollTrainingStatus();
    router.push({
      path: '/',
      query: { view: 'datasets', tab: 'train', datasetName: datasetName.value, datasetPath: datasetPath.value }
    });
  } catch (e) {
    console.error(e);
    alert('请求失败');
  }
};

const deleteRun = async (run) => {
  if (!confirm(`确定要删除训练记录 ${runKey(run)} 吗？`)) return;
  try {
    const res = await api.deleteTrainingRun({
      project_path: projectPath.value,
      dataset_name: datasetName.value,
      training_id: runKey(run)
    });
    if (res.data.success) {
      await loadHistory();
    } else {
      alert(res.data.error || '删除失败');
    }
  } catch (e) {
    console.error(e);
    alert('请求失败');
  }
};

watch(
  () => [route.query.projectPath, route.query.datasetName, route.query.datasetPath],
  () => {
    loadHistory();
  }
);

onMounted(() => {
  loadHistory();
});
</script>
