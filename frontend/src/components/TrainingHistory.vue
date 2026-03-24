<template>
  <div class="mt-8">
    <h2 class="text-xl font-bold text-white mb-4">训练历史 (History)</h2>
    
    <div v-if="runs.length === 0" class="text-white/60 text-center py-8 bg-black/20 rounded-xl">
      暂无训练记录
    </div>

    <div v-else class="space-y-4">
      <div v-for="run in runs" :key="run.id" class="bg-white/10 rounded-xl p-4 border border-white/10 hover:bg-white/15 transition-colors">
        <div class="flex justify-between items-start mb-3">
          <div>
            <div class="font-mono text-lg font-bold text-white">{{ run.name || run.id }}</div>
            <div class="text-xs text-white/60">{{ formatDate(run.date) }}</div>
          </div>
          <div class="flex gap-2">
            <span class="px-2 py-1 rounded text-xs font-bold" 
                  :class="run.status === 'completed' ? 'bg-green-500/20 text-green-300' : 'bg-yellow-500/20 text-yellow-300'">
              {{ run.status }}
            </span>
          </div>
        </div>

        <!-- Metrics -->
        <div class="grid grid-cols-4 gap-2 mb-4">
          <div class="bg-black/20 rounded p-2 text-center">
            <div class="text-[10px] text-white/50 uppercase">mAP50</div>
            <div class="text-sm font-mono font-bold text-white">{{ formatMetric(run.metrics?.map50) }}</div>
          </div>
          <div class="bg-black/20 rounded p-2 text-center">
            <div class="text-[10px] text-white/50 uppercase">mAP50-95</div>
            <div class="text-sm font-mono font-bold text-white">{{ formatMetric(run.metrics?.map) }}</div>
          </div>
          <div class="bg-black/20 rounded p-2 text-center">
            <div class="text-[10px] text-white/50 uppercase">Precision</div>
            <div class="text-sm font-mono font-bold text-white">{{ formatMetric(run.metrics?.precision) }}</div>
          </div>
          <div class="bg-black/20 rounded p-2 text-center">
            <div class="text-[10px] text-white/50 uppercase">Recall</div>
            <div class="text-sm font-mono font-bold text-white">{{ formatMetric(run.metrics?.recall) }}</div>
          </div>
        </div>

        <!-- Actions -->
        <div class="flex justify-between items-center border-t border-white/10 pt-3">
           <div class="flex flex-wrap gap-2">
             <!-- Existing Exports -->
             <div v-for="exp in (runExports[run.id] || [])" :key="exp.filename" class="group relative">
                <a :href="exp.download_url" target="_blank" class="flex items-center gap-1 bg-indigo-500/20 hover:bg-indigo-500/40 text-indigo-200 px-2 py-1 rounded text-xs transition-colors">
                  <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
                    <path fill-rule="evenodd" d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm3.293-7.707a1 1 0 011.414 0L9 10.586V3a1 1 0 112 0v7.586l1.293-1.293a1 1 0 111.414 1.414l-3 3a1 1 0 01-1.414 0l-3-3a1 1 0 010-1.414z" clip-rule="evenodd" />
                  </svg>
                  {{ exp.format }} {{ exp.int8 ? '(INT8)' : (exp.half ? '(FP16)' : '') }}
                </a>
             </div>
             <!-- Test Inference -->
             <button @click="openInferModal(run)" class="bg-yellow-500/20 hover:bg-yellow-500/40 text-yellow-200 px-2 py-1 rounded text-xs transition-colors flex items-center gap-1">
               <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" viewBox="0 0 20 20" fill="currentColor">
                 <path d="M2 10a8 8 0 1116 0A8 8 0 012 10zm8-5a1 1 0 011 1v3a1 1 0 11-2 0V6a1 1 0 011-1zm-1 8a1 1 0 102 0 1 1 0 00-2 0z"/>
               </svg>
               批量推理测试集
             </button>
           </div>

           <button @click="openExportModal(run)" class="bg-white/10 hover:bg-white/20 text-white px-3 py-1.5 rounded text-xs font-semibold transition-colors flex items-center gap-1">
             <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
               <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
             </svg>
             导出模型 (Export)
           </button>
        </div>
      </div>
    </div>

    <!-- Export Modal -->
    <div v-if="showModal" class="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4" @click.self="closeModal">
      <div class="bg-slate-800 rounded-xl shadow-2xl max-w-lg w-full overflow-hidden border border-white/10">
        <div class="p-4 border-b border-white/10 flex justify-between items-center bg-slate-900/50">
          <h3 class="text-lg font-bold text-white">导出模型 (Export Model)</h3>
          <button @click="closeModal" class="text-white/50 hover:text-white transition-colors">✕</button>
        </div>
        
        <div class="p-6 space-y-4">
          <div v-if="store.exportStatus.is_running" class="text-center py-8">
             <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-500 mx-auto mb-4"></div>
             <div class="text-white font-medium">{{ store.exportStatus.message }}</div>
             <div class="text-white/60 text-sm mt-1">{{ store.exportStatus.progress }}%</div>
          </div>
          
          <div v-else>
            <div class="grid grid-cols-2 gap-4 mb-4">
              <div>
                <label class="block text-xs text-white/60 mb-1">导出格式</label>
                <select v-model="exportConfig.format" class="w-full bg-black/20 border border-white/10 rounded px-3 py-2 text-white text-sm focus:border-indigo-500 outline-none">
                  <option value="onnx">ONNX</option>
                  <option value="openvino">OpenVINO</option>
                  <option value="engine">TensorRT</option>
                </select>
              </div>
              <div>
                <label class="block text-xs text-white/60 mb-1">图片尺寸 (imgsz)</label>
                <input type="number" v-model="exportConfig.imgsz" class="w-full bg-black/20 border border-white/10 rounded px-3 py-2 text-white text-sm focus:border-indigo-500 outline-none">
              </div>
            </div>

  <!-- Inference Modal -->
  <div v-if="showInferModal" class="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4" @click.self="closeInferModal">
    <div class="bg-slate-800 rounded-xl shadow-2xl max-w-5xl w-full overflow-hidden border border-white/10">
      <div class="p-4 border-b border-white/10 flex justify-between items-center bg-slate-900/50">
        <h3 class="text-lg font-bold text-white">批量推理测试集 (Infer Test Images)</h3>
        <button @click="closeInferModal" class="text-white/50 hover:text-white transition-colors">✕</button>
      </div>
      <div class="p-6 space-y-4">
        <div class="grid grid-cols-3 gap-4">
          <div>
            <label class="block text-xs text-white/60 mb-1">测试子目录 (位于项目 test/ 下)</label>
            <input v-model="inferConfig.test_subdir" placeholder="例如：test_01（留空则使用 test 根目录）" class="w-full bg-black/20 border border-white/10 rounded px-3 py-2 text-white text-sm focus:border-yellow-500 outline-none">
          </div>
          <div>
            <label class="block text-xs text-white/60 mb-1">置信度阈值 (conf)</label>
            <input type="number" step="0.01" v-model="inferConfig.conf" class="w-full bg-black/20 border border-white/10 rounded px-3 py-2 text-white text-sm focus:border-yellow-500 outline-none">
          </div>
          <div>
            <label class="block text-xs text-white/60 mb-1">最大检测数 (max_det)</label>
            <input type="number" v-model="inferConfig.max_det" class="w-full bg-black/20 border border-white/10 rounded px-3 py-2 text-white text-sm focus:border-yellow-500 outline-none">
          </div>
        </div>
        <div v-if="inferError" class="bg-red-500/20 border border-red-500/50 text-red-200 text-sm p-3 rounded">
          {{ inferError }}
        </div>
        <div class="flex justify-end pt-2" v-if="!store.testInferStatus.is_running">
          <button @click="startInfer" class="bg-yellow-600 hover:bg-yellow-700 text-white px-6 py-2 rounded-lg font-bold transition-colors shadow-lg">
            🚀 开始批量推理
          </button>
        </div>

        <!-- Status / Results -->
        <div v-if="store.testInferStatus.is_running" class="text-center py-8">
          <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-yellow-500 mx-auto mb-4"></div>
          <div class="text-white font-medium">{{ store.testInferStatus.message }}</div>
          <div class="text-white/60 text-sm mt-1">{{ store.testInferStatus.progress }}%</div>
        </div>
        <div v-else-if="store.testInferStatus.results && store.testInferStatus.results.length > 0" class="mt-4">
          <div class="text-white/80 mb-2 text-sm">推理完成，结果预览：</div>
          <div class="grid grid-cols-3 gap-3">
            <div v-for="(item, idx) in store.testInferStatus.results" :key="idx" class="bg-black/20 border border-white/10 rounded p-2">
              <div class="text-white/60 text-xs mb-1 truncate">{{ item.image?.split('/').pop() }}</div>
              <img :src="item.pred_image_url || item.image_url" class="w-full rounded">
              <div class="text-white/60 text-xs mt-1">预测框: {{ (item.boxes || []).length }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
            <div class="flex gap-4 mb-4">
               <label class="flex items-center gap-2 cursor-pointer">
                 <input type="checkbox" v-model="exportConfig.half" class="form-checkbox bg-transparent border-white/40 rounded text-indigo-500">
                 <span class="text-sm text-white">半精度 (FP16)</span>
               </label>
               <label class="flex items-center gap-2 cursor-pointer">
                 <input type="checkbox" v-model="exportConfig.int8" class="form-checkbox bg-transparent border-white/40 rounded text-indigo-500">
                 <span class="text-sm text-white">INT8 量化</span>
               </label>
            </div>

            <div v-if="exportConfig.int8 && exportConfig.format === 'openvino'" class="bg-indigo-500/10 border border-indigo-500/20 rounded p-3 mb-4">
               <div class="text-xs text-indigo-300 font-bold mb-2">INT8 量化校准设置</div>
               <div class="grid grid-cols-2 gap-3">
                 <div>
                    <label class="block text-[10px] text-indigo-200/70 mb-1">每类采样数</label>
                    <input type="number" v-model="exportConfig.per_class" class="w-full bg-black/20 border border-indigo-500/30 rounded px-2 py-1 text-white text-xs">
                 </div>
                 <div>
                    <label class="block text-[10px] text-indigo-200/70 mb-1">最大图片数</label>
                    <input type="number" v-model="exportConfig.max_images" class="w-full bg-black/20 border border-indigo-500/30 rounded px-2 py-1 text-white text-xs">
                 </div>
               </div>
            </div>
            
            <div v-if="error" class="bg-red-500/20 border border-red-500/50 text-red-200 text-sm p-3 rounded mb-4">
              {{ error }}
            </div>

            <div class="flex justify-end pt-2">
              <button @click="startExport" class="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2 rounded-lg font-bold transition-colors shadow-lg">
                🚀 开始导出
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useMainStore } from '../stores/main';
import { ref, reactive, onMounted, computed, watch } from 'vue';

const store = useMainStore();
const showModal = ref(false);
const showInferModal = ref(false);
const selectedRun = ref(null);
const error = ref(null);
const inferError = ref(null);
const runExports = reactive({}); // map run_id -> list of exports

const exportConfig = reactive({
  format: 'onnx',
  imgsz: 640,
  half: false,
  int8: false,
  per_class: 20,
  max_images: 200
});

const inferConfig = reactive({
  test_subdir: '',
  conf: 0.25,
  max_det: 200
});

const runs = computed(() => {
    // Filter runs for current dataset if needed, or show all for project
    // Assuming backend returns all runs for project
    if (!store.trainingRuns) return [];
    // Sort by date desc
    return [...store.trainingRuns].sort((a, b) => new Date(b.date) - new Date(a.date));
});

const formatDate = (dateStr) => {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleString();
};

const formatMetric = (val) => {
  if (val === undefined || val === null) return '-';
  return (val * 100).toFixed(1) + '%';
};

const openExportModal = (run) => {
  selectedRun.value = run;
  exportConfig.format = 'onnx';
  exportConfig.half = false;
  exportConfig.int8 = false;
  error.value = null;
  showModal.value = true;
};

const closeModal = () => {
  if (!store.exportStatus.is_running) {
    showModal.value = false;
    selectedRun.value = null;
  }
};

const openInferModal = (run) => {
  selectedRun.value = run;
  inferError.value = null;
  showInferModal.value = true;
};

const closeInferModal = () => {
  if (!store.testInferStatus.is_running) {
    showInferModal.value = false;
    selectedRun.value = null;
  }
};

const startExport = async () => {
  if (!selectedRun.value) return;
  
  error.value = null;
  const payload = {
    project_path: store.currentProject.path,
    training_id: selectedRun.value.id,
    format: exportConfig.format,
    half_precision: exportConfig.half,
    int8_quant: exportConfig.int8,
    imgsz: parseInt(exportConfig.imgsz) || 640,
    per_class: parseInt(exportConfig.per_class) || 20,
    max_images: parseInt(exportConfig.max_images) || 200
  };

  const res = await store.startExport(payload);
  if (!res.success) {
    error.value = res.error;
  }
};

const startInfer = async () => {
  if (!selectedRun.value) return;
  inferError.value = null;
  const payload = {
    project_path: store.currentProject.path,
    dataset_name: selectedRun.value.dataset,
    training_id: selectedRun.value.id,
    test_subdir: inferConfig.test_subdir || '',
    conf: parseFloat(inferConfig.conf) || 0.25,
    max_det: parseInt(inferConfig.max_det) || 200
  };
  const res = await store.startTestInference(payload);
  if (!res.success) {
    inferError.value = res.error;
  }
};

// Load exports for runs
const loadExports = async () => {
    for (const run of runs.value) {
        const exports = await store.getModelExports(run.id);
        runExports[run.id] = exports;
    }
};

// Watch for export completion to reload exports
watch(() => store.exportStatus.is_running, async (newVal, oldVal) => {
    if (oldVal && !newVal) { // Finished
        if (store.exportStatus.error) {
            error.value = store.exportStatus.error;
        } else if (store.exportStatus.message && store.exportStatus.message.includes('失败')) {
             error.value = store.exportStatus.message;
        } else if (showModal.value) { // Success
             await loadExports();
             closeModal();
        }
    }
});

// Watch for inference completion (no special action needed here)
watch(() => store.testInferStatus.is_running, (newVal, oldVal) => {
  if (oldVal && !newVal) {
    // inference finished; keep modal open to show results
  }
});

onMounted(() => {
  store.fetchTrainingRuns().then(() => {
      loadExports();
  });
});

// Watch for project change to reload runs
watch(() => store.currentProject, () => {
  store.fetchTrainingRuns().then(() => {
      loadExports();
  });
});
</script>
