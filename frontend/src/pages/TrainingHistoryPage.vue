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

    <main class="flex-1 overflow-y-auto p-8 space-y-6">
      <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <div class="text-sm text-gray-500 mb-1">训练记录</div>
          <div class="text-2xl font-bold text-slate-800">{{ runs.length }}</div>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <div class="text-sm text-gray-500 mb-1">可继续训练</div>
          <div class="text-2xl font-bold text-emerald-600">{{ resumableCount }}</div>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <div class="text-sm text-gray-500 mb-1">最佳 mAP50</div>
          <div class="text-2xl font-bold text-sky-600">{{ bestMap50 }}</div>
        </div>
        <div class="bg-white rounded-xl shadow-sm border border-gray-100 p-5">
          <div class="text-sm text-gray-500 mb-1">当前训练状态</div>
          <div class="text-sm font-medium" :class="store.trainingStatus.is_running ? 'text-emerald-600' : 'text-slate-700'">
            {{ store.trainingStatus.is_running ? (store.trainingStatus.message || '训练中') : '空闲' }}
          </div>
        </div>
      </div>

      <div class="bg-white rounded-xl shadow-sm border border-gray-100">
        <div class="px-6 py-5 border-b border-gray-100 flex items-center justify-between gap-4">
          <div>
            <div class="text-lg font-semibold text-slate-800">运行列表</div>
            <div class="text-sm text-gray-500">继续训练、可视化、导出、批量推理都在这里</div>
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
              <tr v-for="run in runs" :key="runKey(run)" class="hover:bg-gray-50 align-top">
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
                  <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
                    <button
                      @click="resumeRun(run)"
                      :disabled="!run.can_resume || store.trainingStatus.is_running"
                      class="text-emerald-600 hover:underline disabled:text-gray-300 disabled:no-underline"
                    >
                      继续训练
                    </button>
                    <button @click="openArtifacts(run)" class="text-sky-600 hover:underline">可视化</button>
                    <button @click="openExport(run)" class="text-indigo-600 hover:underline">导出</button>
                    <button @click="openInference(run)" class="text-amber-600 hover:underline">批量推理</button>
                    <button @click="deleteRun(run)" class="text-rose-600 hover:underline">删除</button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </main>

    <div v-if="artifactsModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="closeArtifacts">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-5xl p-6 h-[85vh] flex flex-col">
        <div class="flex items-center justify-between mb-4 shrink-0">
          <h3 class="text-lg font-bold">训练产物：{{ currentRun ? runKey(currentRun) : '-' }}</h3>
          <button class="text-gray-500 hover:text-gray-700" @click="closeArtifacts">关闭</button>
        </div>

        <div v-if="artifactsLoading" class="flex-1 flex items-center justify-center text-gray-500">
          加载中...
        </div>
        <div v-else class="flex-1 overflow-y-auto space-y-6">
          <div v-if="currentArtifacts.images && currentArtifacts.images.length > 0">
            <h4 class="font-bold text-gray-700 mb-2 sticky top-0 bg-white py-2 z-10 border-b">可视化图片</h4>
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              <div v-for="img in currentArtifacts.images" :key="img.name" class="border rounded-lg p-2">
                <div class="text-xs font-mono mb-1 text-gray-600 truncate" :title="img.name">{{ img.name }}</div>
                <a :href="img.url" target="_blank" class="block bg-gray-50 rounded overflow-hidden">
                  <img :src="img.url" loading="lazy" class="w-full h-auto object-contain hover:scale-105 transition-transform" />
                </a>
              </div>
            </div>
          </div>

          <div v-if="currentArtifacts.weights && currentArtifacts.weights.length > 0">
            <h4 class="font-bold text-gray-700 mb-2 sticky top-0 bg-white py-2 z-10 border-b">权重文件</h4>
            <div class="flex flex-wrap gap-3">
              <a
                v-for="w in currentArtifacts.weights"
                :key="w.name"
                :href="w.url"
                target="_blank"
                class="px-3 py-2 bg-indigo-50 text-indigo-700 rounded border border-indigo-100 hover:bg-indigo-100 flex items-center gap-2"
              >
                <span>📦 {{ w.name }}</span>
                <span class="text-indigo-400 text-xs">⬇️</span>
              </a>
            </div>
          </div>

          <div v-if="currentArtifacts.config">
            <h4 class="font-bold text-gray-700 mb-2 sticky top-0 bg-white py-2 z-10 border-b">配置文件</h4>
            <a :href="currentArtifacts.config" target="_blank" class="text-blue-600 hover:underline">
              📄 查看 training_config.json
            </a>
          </div>

          <div
            v-if="(!currentArtifacts.images || !currentArtifacts.images.length) && (!currentArtifacts.weights || !currentArtifacts.weights.length) && !currentArtifacts.config"
            class="text-center py-10 text-gray-400"
          >
            未找到相关产物
          </div>
        </div>
      </div>
    </div>

    <div v-if="exportModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="closeExport">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-2xl p-6 max-h-[85vh] overflow-y-auto">
        <div class="flex items-center justify-between mb-4">
          <div>
            <h3 class="text-lg font-bold">导出模型</h3>
            <div class="text-sm text-gray-500">{{ exportRun ? runKey(exportRun) : '-' }}</div>
          </div>
          <button class="text-gray-500 hover:text-gray-700" @click="closeExport">✕</button>
        </div>

        <div class="space-y-4">
          <div v-if="store.exportStatus.is_running" class="text-center py-8">
            <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-500 mx-auto mb-4"></div>
            <div class="text-gray-700 font-medium">{{ store.exportStatus.message }}</div>
            <div class="text-gray-500 text-sm mt-1">{{ store.exportStatus.progress }}%</div>
          </div>

          <div v-else>
            <div class="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label class="block text-xs text-gray-600 mb-1">导出格式</label>
                <select v-model="exportConfig.format" class="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:border-indigo-500 outline-none">
                  <option value="onnx">ONNX</option>
                  <option value="openvino">OpenVINO</option>
                  <option value="engine">TensorRT</option>
                </select>
              </div>
              <div>
                <label class="block text-xs text-gray-600 mb-1">图片尺寸</label>
                <input v-model.number="exportConfig.imgsz" type="number" class="w-full border border-gray-300 rounded px-3 py-2 text-sm focus:border-indigo-500 outline-none">
              </div>
            </div>

            <div class="flex gap-4 mb-4">
              <label class="flex items-center gap-2 cursor-pointer">
                <input v-model="exportConfig.half" type="checkbox" class="form-checkbox text-indigo-500 rounded">
                <span class="text-sm text-gray-700">半精度 FP16</span>
              </label>
              <label class="flex items-center gap-2 cursor-pointer">
                <input v-model="exportConfig.int8" type="checkbox" class="form-checkbox text-indigo-500 rounded">
                <span class="text-sm text-gray-700">INT8 量化</span>
              </label>
            </div>

            <div v-if="exportConfig.int8 && exportConfig.format === 'openvino'" class="bg-indigo-50 border border-indigo-100 rounded p-3 mb-4">
              <div class="text-xs text-indigo-700 font-bold mb-2">INT8 校准设置</div>
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <label class="block text-[10px] text-indigo-600/70 mb-1">每类采样数</label>
                  <input v-model.number="exportConfig.per_class" type="number" class="w-full bg-white border border-indigo-200 rounded px-2 py-1 text-xs">
                </div>
                <div>
                  <label class="block text-[10px] text-indigo-600/70 mb-1">最大图片数</label>
                  <input v-model.number="exportConfig.max_images" type="number" class="w-full bg-white border border-indigo-200 rounded px-2 py-1 text-xs">
                </div>
              </div>
            </div>

            <div v-if="exportError" class="bg-red-50 text-red-700 text-sm p-3 rounded border border-red-100">
              {{ exportError }}
            </div>

            <div class="pt-2 mt-4 border-t border-gray-100 space-y-4">
              <div>
                <div class="text-sm font-semibold text-slate-800 mb-2">已有导出文件</div>
                <div v-if="exportsLoading" class="text-sm text-gray-500">加载中...</div>
                <div v-else-if="!currentExports.length" class="text-sm text-gray-400">暂无导出记录</div>
                <div v-else class="space-y-3">
                  <div
                    v-for="exp in currentExports"
                    :key="`${exp.training_id}-${exp.export_dir}`"
                    class="rounded-lg border border-emerald-200 bg-emerald-50 p-3"
                  >
                    <div class="flex items-start justify-between gap-3">
                      <div class="min-w-0">
                        <div class="text-sm font-medium text-emerald-800">{{ exportFormatLabel(exp) }}</div>
                        <div class="text-xs text-emerald-700 truncate">{{ exp.primary_model_path || exp.export_dir }}</div>
                      </div>
                      <div class="text-xs text-emerald-700 shrink-0">{{ formatBytes(exp.total_size_bytes) }}</div>
                    </div>

                    <div class="mt-3 flex flex-wrap gap-2">
                      <a
                        v-if="exp.zip_url"
                        :href="exp.zip_url"
                        target="_blank"
                        class="inline-flex items-center rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
                      >
                        下载量化包
                      </a>
                      <a
                        v-if="!exp.zip_url && exp.primary_model_url"
                        :href="exp.primary_model_url"
                        target="_blank"
                        class="inline-flex items-center rounded-md bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-emerald-700"
                      >
                        下载主模型
                      </a>
                    </div>

                    <div v-if="exp.files?.length" class="mt-3 border-t border-emerald-200 pt-3">
                      <div class="mb-2 text-xs font-medium text-emerald-800">文件列表</div>
                      <div class="space-y-2">
                        <div
                          v-for="file in exp.files"
                          :key="file.path"
                          class="flex items-center justify-between gap-3 rounded-md bg-white/70 px-3 py-2"
                        >
                          <div class="min-w-0">
                            <div class="truncate text-xs font-medium text-slate-700">{{ file.name }}</div>
                            <div class="truncate text-[11px] text-slate-500">{{ file.relative_path }}</div>
                          </div>
                          <div class="flex items-center gap-3 shrink-0">
                            <div class="text-[11px] text-slate-500">{{ formatBytes(file.size_bytes) }}</div>
                            <a :href="file.url" target="_blank" class="text-xs font-medium text-emerald-700 hover:underline">
                              下载
                            </a>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              <div class="flex justify-end">
                <button @click="startExport" class="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2 rounded-lg font-bold transition-colors shadow-sm">
                  开始导出
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="inferModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="closeInference">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-6xl p-6 h-[85vh] flex flex-col">
        <div class="flex items-center justify-between mb-4 shrink-0">
          <div>
            <h3 class="text-lg font-bold">批量推理</h3>
            <div class="text-sm text-gray-500">{{ inferRun ? runKey(inferRun) : '-' }}</div>
          </div>
          <button class="text-gray-500 hover:text-gray-700" @click="closeInference">关闭</button>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-5 shrink-0">
          <div class="md:col-span-2">
            <label class="block text-xs text-gray-600 mb-1">测试目录</label>
            <select v-model="inferConfig.test_subdir" class="w-full border border-gray-300 rounded px-3 py-2 text-sm">
              <option v-for="dir in store.testDirs" :key="dir.subdir" :value="dir.subdir">
                {{ dir.name }} ({{ dir.image_count }} 张)
              </option>
            </select>
          </div>
          <div>
            <label class="block text-xs text-gray-600 mb-1">conf</label>
            <input v-model.number="inferConfig.conf" type="number" min="0" max="1" step="0.01" class="w-full border border-gray-300 rounded px-3 py-2 text-sm">
          </div>
          <div>
            <label class="block text-xs text-gray-600 mb-1">max_det</label>
            <input v-model.number="inferConfig.max_det" type="number" min="1" step="1" class="w-full border border-gray-300 rounded px-3 py-2 text-sm">
          </div>
        </div>

        <div class="mb-4 shrink-0 flex items-center justify-between gap-4">
          <div class="min-w-0">
            <div class="text-sm font-medium text-slate-800">{{ store.testInferStatus.message || '尚未开始推理' }}</div>
            <div class="text-xs text-gray-500">
              {{ store.testInferStatus.done || 0 }}/{{ store.testInferStatus.total || 0 }}
              <span v-if="store.testInferStatus.output_dir_url" class="ml-2">
                <a :href="store.testInferStatus.output_dir_url" target="_blank" class="text-blue-600 hover:underline">打开输出目录</a>
              </span>
            </div>
          </div>
          <button
            @click="startInference"
            :disabled="!inferRun || !store.testDirs.length || store.testInferStatus.is_running"
            class="bg-amber-500 hover:bg-amber-600 text-white px-5 py-2 rounded-lg font-semibold disabled:opacity-50"
          >
            开始推理
          </button>
        </div>

        <div class="mb-4 shrink-0">
          <div class="w-full bg-gray-100 rounded-full h-2 overflow-hidden">
            <div class="bg-amber-500 h-full transition-all duration-300" :style="{ width: `${store.testInferStatus.progress || 0}%` }"></div>
          </div>
        </div>

        <div class="flex-1 overflow-y-auto">
          <div v-if="store.testInferStatus.error" class="mb-4 bg-red-50 border border-red-100 rounded-lg p-3 text-sm text-red-700">
            {{ store.testInferStatus.error }}
          </div>
          <div v-if="!store.testInferStatus.results?.length" class="h-full flex items-center justify-center text-gray-400">
            暂无推理结果
          </div>
          <div v-else class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            <div v-for="(item, index) in store.testInferStatus.results" :key="item.pred_image_url || item.image_url || index" class="border border-gray-200 rounded-xl p-3 bg-gray-50">
              <div class="flex items-center justify-between gap-2 mb-2">
                <div class="text-xs text-gray-500 truncate">{{ inferItemName(item) }}</div>
                <div class="text-xs text-slate-700 shrink-0">{{ item.boxes?.length || 0 }} boxes</div>
              </div>
              <div v-if="item.error" class="text-sm text-rose-600">{{ item.error }}</div>
              <div v-else class="space-y-3">
                <a v-if="item.pred_image_url" :href="item.pred_image_url" target="_blank" class="block bg-white rounded overflow-hidden border border-gray-200">
                  <img :src="item.pred_image_url" class="w-full h-auto object-contain" />
                </a>
                <a v-if="item.image_url" :href="item.image_url" target="_blank" class="text-xs text-blue-600 hover:underline">
                  查看原图
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
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

const artifactsModal = ref(false);
const artifactsLoading = ref(false);
const currentRun = ref(null);
const currentArtifacts = ref({ images: [], weights: [], config: null });

const exportModal = ref(false);
const exportRun = ref(null);
const exportError = ref('');
const exportsLoading = ref(false);
const runExports = ref({});
const exportConfig = ref({
  format: 'onnx',
  imgsz: 640,
  half: false,
  int8: false,
  per_class: 20,
  max_images: 200
});

const inferModal = ref(false);
const inferRun = ref(null);
const inferConfig = ref({
  test_subdir: '',
  conf: 0.25,
  max_det: 200
});

const datasetName = computed(() => datasetContext.value?.name || route.query.datasetName || '');
const datasetPath = computed(() => datasetContext.value?.path || route.query.datasetPath || '');
const projectPath = computed(() => store.currentProject?.path || route.query.projectPath || '');
const resumableCount = computed(() => runs.value.filter(run => run.can_resume).length);
const bestMap50 = computed(() => {
  const values = runs.value
    .map(run => metric(run, 'mAP50', 'map50'))
    .filter(value => typeof value === 'number');
  if (!values.length) return '-';
  return Math.max(...values).toFixed(4);
});
const currentExports = computed(() => {
  if (!exportRun.value) return [];
  return runExports.value[runKey(exportRun.value)] || [];
});

const runKey = (run) => run?.training_id || run?.id;
const runDataset = (run) => run?.dataset || datasetName.value;

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

const formatBytes = (size) => {
  if (!size || size <= 0) return '-';
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  if (size < 1024 * 1024 * 1024) return `${(size / 1024 / 1024).toFixed(1)} MB`;
  return `${(size / 1024 / 1024 / 1024).toFixed(2)} GB`;
};

const exportFormatLabel = (exp) => {
  const p = (exp?.primary_model_path || '').toLowerCase();
  if (p.endsWith('.onnx')) return 'ONNX';
  if (p.endsWith('.xml')) return 'OpenVINO';
  if (p.endsWith('.engine')) return 'TensorRT';
  return '导出文件';
};

const inferItemName = (item) => {
  const src = item?.image_url || item?.image || item?.pred_image_url || '';
  if (!src) return '未命名结果';
  return src.split('/').pop();
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
      dataset_name: runDataset(run),
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

const openArtifacts = async (run) => {
  currentRun.value = run;
  currentArtifacts.value = { images: [], weights: [], config: null };
  artifactsModal.value = true;
  artifactsLoading.value = true;
  try {
    const res = await api.getTrainingRunArtifacts({
      project_path: projectPath.value,
      dataset_name: runDataset(run),
      training_id: runKey(run)
    });
    if (res.data.success) {
      currentArtifacts.value = res.data.artifacts || { images: [], weights: [], config: null };
    } else {
      alert(res.data.error || '加载训练产物失败');
    }
  } catch (e) {
    console.error(e);
    alert('请求失败');
  } finally {
    artifactsLoading.value = false;
  }
};

const closeArtifacts = () => {
  artifactsModal.value = false;
};

const loadRunExports = async (run) => {
  exportsLoading.value = true;
  try {
    const items = await store.getModelExports(runKey(run));
    runExports.value = {
      ...runExports.value,
      [runKey(run)]: items
    };
  } finally {
    exportsLoading.value = false;
  }
};

const openExport = async (run) => {
  exportRun.value = run;
  exportError.value = '';
  exportModal.value = true;
  await loadRunExports(run);
};

const closeExport = () => {
  exportModal.value = false;
};

const startExport = async () => {
  if (!exportRun.value) return;
  exportError.value = '';
  const result = await store.startExport({
    project_path: projectPath.value,
    training_id: runKey(exportRun.value),
    format: exportConfig.value.format,
    imgsz: exportConfig.value.imgsz,
    half_precision: exportConfig.value.half,
    int8_quant: exportConfig.value.int8,
    per_class: exportConfig.value.per_class,
    max_images: exportConfig.value.max_images
  });
  if (!result.success) {
    exportError.value = result.error || '导出失败';
  }
};

const openInference = async (run) => {
  inferRun.value = run;
  inferModal.value = true;
  await store.fetchTestDirs();
  if (!store.testDirs.length) return;
  if (!store.testDirs.find(item => item.subdir === inferConfig.value.test_subdir)) {
    inferConfig.value.test_subdir = store.testDirs[0].subdir;
  }
};

const closeInference = () => {
  inferModal.value = false;
};

const startInference = async () => {
  if (!inferRun.value) return;
  const result = await store.startTestInference({
    project_path: projectPath.value,
    dataset_name: runDataset(inferRun.value),
    training_id: runKey(inferRun.value),
    test_subdir: inferConfig.value.test_subdir,
    conf: inferConfig.value.conf,
    max_det: inferConfig.value.max_det
  });
  if (!result.success) {
    alert(result.error || '启动推理失败');
  }
};

const deleteRun = async (run) => {
  if (!confirm(`确定要删除训练记录 ${runKey(run)} 吗？`)) return;
  try {
    const res = await api.deleteTrainingRun({
      project_path: projectPath.value,
      dataset_name: runDataset(run),
      training_id: runKey(run)
    });
    if (res.data.success) {
      if (currentRun.value && runKey(currentRun.value) === runKey(run)) {
        closeArtifacts();
      }
      if (exportRun.value && runKey(exportRun.value) === runKey(run)) {
        closeExport();
      }
      if (inferRun.value && runKey(inferRun.value) === runKey(run)) {
        closeInference();
      }
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

watch(
  () => store.exportStatus.is_running,
  async (isRunning, wasRunning) => {
    if (wasRunning && !isRunning && exportRun.value) {
      await loadRunExports(exportRun.value);
    }
  }
);

onMounted(() => {
  loadHistory();
});
</script>
