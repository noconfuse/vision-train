<template>
  <div 
    class="bg-white shadow-sm flex flex-col transition-all duration-300"
    :class="isFullScreen ? 'fixed inset-0 z-40 rounded-none h-screen mb-0 p-6' : 'rounded-xl p-6 mb-6 h-[800px]'"
  >
    <div class="mb-4">
      <div class="flex items-center justify-between gap-4">
        <h2 class="text-xl font-semibold text-slate-800">数据集预览：{{ store.selectedDataset.name }}</h2>
        <div class="flex items-center gap-2">
          <button
            class="px-3 py-2 rounded-lg text-sm border border-gray-200 bg-white hover:bg-gray-50"
            @click="isFullScreen = !isFullScreen"
          >
            {{ isFullScreen ? '退出全屏' : '全屏' }}
          </button>
          <button
            class="px-3 py-2 rounded-lg text-sm border border-gray-200 bg-white hover:bg-gray-50"
            @click="toggleSelectionMode"
          >
            {{ selectionMode ? '退出选择模式' : '进入选择模式' }}
          </button>
          <button
            v-if="selectionMode"
            class="px-3 py-2 rounded-lg text-sm border border-gray-200 bg-white hover:bg-gray-50"
            @click="selectAllCurrentPage"
          >
            全选本页
          </button>
          <button
            v-if="selectionMode"
            class="px-3 py-2 rounded-lg text-sm bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"
            :disabled="selectedCount === 0"
            @click="openCreateSubset"
          >
            生成数据集（{{ selectedCount }}）
          </button>
          <button
            v-if="selectionMode"
            class="px-3 py-2 rounded-lg text-sm bg-red-600 hover:bg-red-700 text-white disabled:opacity-50"
            :disabled="selectedCount === 0 || deleting"
            @click="batchDelete"
          >
            {{ deleting ? '删除中...' : `删除选中（${selectedCount}）` }}
          </button>
        </div>
      </div>

      <div v-if="datasetInfo" class="mt-4">
        <div class="text-sm text-gray-700 mb-2 flex items-center gap-2">
          <span>分类统计（总目标数：<span class="font-mono">{{ datasetInfo.total_objects || 0 }}</span>）</span>
          <button
            class="px-2 py-1 rounded-lg text-xs border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-50"
            :disabled="reorderingLabels || !canReorderLabels"
            @click="openReorderLabels"
          >
            {{ reorderingLabels ? '处理中...' : '调整标签顺序' }}
          </button>
          <button
            class="px-2 py-1 rounded-lg text-xs border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-50"
            :disabled="deletingLabel || !canReorderLabels"
            @click="openDeleteLabel"
          >
            {{ deletingLabel ? '处理中...' : '删除标签' }}
          </button>
        </div>
        <div class="flex flex-wrap gap-2">
          <button
            v-for="s in datasetInfo.class_stats || []"
            :key="s.id"
            class="px-3 py-1.5 rounded-full text-xs border transition-colors"
            :class="selectedClassIds.includes(s.id) ? 'bg-blue-50 border-blue-400 text-blue-700' : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50'"
            @click="toggleClass(s.id)"
          >
            {{ s.name }} | {{ s.count }}（{{ s.percentage }}%）
          </button>
        </div>
      </div>

      <div class="mt-4 flex flex-wrap items-center gap-3">
        <div class="flex items-center gap-2">
          <span class="text-sm text-gray-600">分割</span>
          <select v-model="filters.split" class="border border-gray-300 rounded-lg px-3 py-1.5 text-sm">
            <option value="train">train</option>
            <option value="val">val</option>
            <option value="test">test</option>
          </select>
        </div>

        <div class="flex items-center gap-2">
          <span class="text-sm text-gray-600">类别筛选</span>
          <span class="text-sm text-gray-700">
            选择了 <span class="font-mono">{{ selectedClassIds.length }}</span> 项
          </span>
          <button
            class="px-2 py-1 rounded-lg text-sm border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-50"
            :disabled="selectedClassIds.length === 0"
            @click="clearClasses"
          >
            清空
          </button>
        </div>

        <div class="flex items-center gap-2">
          <select v-model="filters.mode" class="border border-gray-300 rounded-lg px-3 py-1.5 text-sm">
            <option value="include">包含所选类别</option>
            <option value="exclude">不包含所选类别</option>
          </select>
        </div>

        <label class="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" v-model="filters.unannotated" class="rounded border-gray-300">
          仅看未标注
        </label>

        <label class="flex items-center gap-2 text-sm text-gray-700">
          <input type="checkbox" v-model="filters.has_auto_label" class="rounded border-gray-300">
          仅看待复核
        </label>

        <button
          class="px-3 py-2 rounded-lg text-sm bg-slate-700 hover:bg-slate-800 text-white"
          @click="applyFilters"
        >
          应用筛选
        </button>

        <div class="flex-1"></div>

        <div class="flex items-center gap-2">
          <button
            class="px-2 py-1.5 rounded-lg text-sm border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-50"
            :disabled="currentPage <= 1"
            @click="goPrevPage"
          >
            上一页
          </button>
          <button
            class="px-2 py-1.5 rounded-lg text-sm border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-50"
            :disabled="currentPage >= totalPages"
            @click="goNextPage"
          >
            下一页
          </button>
          <span class="text-sm text-gray-600">页码</span>
          <input
            v-model.number="pageInput"
            type="number"
            min="1"
            :max="totalPages"
            class="w-20 border border-gray-300 rounded-lg px-3 py-1.5 text-sm"
            @keydown.enter.prevent="jumpPage"
          />
          <span class="text-sm text-gray-600">/ {{ totalPages }}</span>
          <button class="px-2 py-1.5 rounded-lg text-sm border border-gray-200 bg-white hover:bg-gray-50" @click="jumpPage">跳转</button>
        </div>
      </div>
    </div>

    <!-- Image Grid -->
    <div class="flex-1 overflow-y-auto min-h-0 bg-gray-50 rounded-lg p-4 border border-gray-100">
      <div v-if="loading" class="flex justify-center items-center h-full">
        <div class="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-500"></div>
      </div>
      
      <div v-else-if="images.length === 0" class="flex flex-col items-center justify-center h-full text-gray-400">
        <span class="text-4xl mb-2">📷</span>
        <p>暂无图片</p>
      </div>

      <div v-else class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 2xl:grid-cols-10 gap-4">
        <div 
          v-for="img in images" 
          :key="img.path" 
          class="group relative aspect-square bg-gray-200 rounded-lg overflow-hidden cursor-pointer hover:ring-2 ring-blue-500 transition-all"
          @click="onImageClick(img)"
        >
          <img :src="img.url" class="w-full h-full object-cover" loading="lazy" />
          
          <div class="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
             <span class="text-white text-xs font-mono truncate px-2">{{ img.path.split('/').pop() }}</span>
          </div>

          <!-- Status Indicators -->
          <div class="absolute top-2 right-2 flex gap-1">
            <span v-if="!img.pending" class="w-2 h-2 rounded-full bg-green-500 shadow-sm" title="Annotated"></span>
            <span v-else class="w-2 h-2 rounded-full bg-yellow-500 shadow-sm" title="Pending"></span>
          </div>

          <div v-if="selectionMode" class="absolute top-2 left-2">
            <div
              class="w-5 h-5 rounded border flex items-center justify-center text-xs font-bold shadow-sm"
              :class="isSelected(img.path) ? 'bg-blue-600 border-blue-600 text-white' : 'bg-white/90 border-gray-300 text-transparent'"
            >
              ✓
            </div>
          </div>
        </div>
      </div>
    </div>
    
    <!-- Footer Actions -->
    <div class="mt-4 pt-4 border-t border-gray-100 flex justify-between items-center">
       <span class="text-sm text-gray-500">共 {{ total }} 张图片</span>
       <div class="flex gap-2 relative">
         <button @click="showAutoAnnotateModal = true" class="bg-indigo-500 hover:bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm transition-colors">
           自动标注 (整张表)...
         </button>
       </div>
    </div>
    
    <!-- Auto Annotate Progress Modal -->
    <div v-if="autoAnnotating" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-md p-6 text-center">
        <h3 class="text-lg font-bold mb-4">自动标注中...</h3>
        
        <div class="mb-4">
          <div class="flex justify-between text-sm mb-1 text-gray-600">
            <span>{{ autoAnnotateStatus.message }}</span>
            <span>{{ autoAnnotateStatus.progress }}%</span>
          </div>
          <div class="w-full bg-gray-200 rounded-full h-2.5">
            <div class="bg-indigo-600 h-2.5 rounded-full transition-all duration-300" :style="{ width: `${autoAnnotateStatus.progress}%` }"></div>
          </div>
        </div>
        
        <div class="grid grid-cols-2 gap-4 text-sm">
          <div class="bg-gray-50 p-3 rounded-lg">
            <div class="text-gray-500 mb-1">新增标注</div>
            <div class="font-mono font-bold text-lg text-green-600">{{ autoAnnotateStatus.added }}</div>
          </div>
          <div class="bg-gray-50 p-3 rounded-lg">
            <div class="text-gray-500 mb-1">待复核</div>
            <div class="font-mono font-bold text-lg text-orange-500">{{ autoAnnotateStatus.pending }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- Auto Annotate Modal -->
    <div v-if="showAutoAnnotateModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <h3 class="text-lg font-bold mb-4">自动标注配置</h3>
        
        <div class="mb-4">
          <label class="block text-sm font-medium text-gray-700 mb-2">选择模型</label>
          <div class="flex gap-2 mb-2">
            <button 
              @click="autoAnnotateType = 'pretrained'" 
              class="flex-1 py-2 text-sm border rounded-lg"
              :class="autoAnnotateType === 'pretrained' ? 'bg-indigo-50 border-indigo-500 text-indigo-700' : 'border-gray-300 text-gray-600'"
            >预训练模型</button>
            <button 
              @click="autoAnnotateType = 'trained'" 
              class="flex-1 py-2 text-sm border rounded-lg"
              :class="autoAnnotateType === 'trained' ? 'bg-indigo-50 border-indigo-500 text-indigo-700' : 'border-gray-300 text-gray-600'"
            >已训练模型</button>
          </div>
          
          <select v-if="autoAnnotateType === 'pretrained'" v-model="selectedModelPath" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">
             <option v-for="m in pretrainedModelOptions" :key="m.path" :value="m.path">{{ m.name }}</option>
          </select>
          
          <select v-else v-model="selectedModelPath" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">
             <option v-if="trainingRuns.length === 0" disabled>无可用训练记录</option>
             <option v-for="opt in trainedModelOptions" :key="opt.key" :value="opt.value">{{ opt.label }}</option>
          </select>
        </div>
        
        <div class="flex justify-end gap-2">
          <button @click="showAutoAnnotateModal = false" class="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg text-sm">取消</button>
          <button @click="runAutoAnnotate" class="px-4 py-2 bg-indigo-500 hover:bg-indigo-600 text-white rounded-lg text-sm" :disabled="!selectedModelPath">
            开始标注
          </button>
        </div>
      </div>
    </div>

    <!-- Annotator Modal -->
    <ImageAnnotator 
      v-if="currentImage"
      :image="currentImage"
      :class-list="classList"
      :dataset-name="store.selectedDataset.name"
      :split="filters.split"
      @close="currentImage = null"
      @prev="navImage(-1)"
      @next="navImage(1)"
      @update="onImageUpdate"
    />

    <div v-if="showCreateSubsetModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="closeCreateSubset">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
        <h3 class="text-lg font-bold mb-4">生成独立数据集</h3>
        <div class="mb-4 text-sm text-gray-600">已选择 <span class="font-mono">{{ selectedCount }}</span> 张图片</div>
        <div class="mb-6">
          <label class="block text-sm font-medium text-gray-700 mb-2">新数据集名称</label>
          <input v-model.trim="subsetName" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" placeholder="例如：datasets_04_subset" />
        </div>
        <div class="flex justify-end gap-2">
          <button class="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg text-sm" @click="closeCreateSubset">取消</button>
          <button class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm disabled:opacity-50" :disabled="creatingSubset || !subsetName" @click="createSubset">
            {{ creatingSubset ? '创建中...' : '创建' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="showReorderLabelsModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="closeReorderLabels">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-lg p-6">
        <h3 class="text-lg font-bold mb-4">调整标签顺序</h3>
        <div class="mb-3 text-sm text-gray-600">该操作会批量重写当前数据集的标注文件（train/val/test 及 auto_labels）。</div>

        <div class="max-h-[420px] overflow-auto border border-gray-200 rounded-lg">
          <div
            v-for="(it, idx) in reorderItems"
            :key="it.oldIndex"
            class="flex items-center gap-2 px-3 py-2 border-b border-gray-100 last:border-b-0"
          >
            <div class="w-10 text-right font-mono text-sm text-gray-500">{{ idx }}</div>
            <div class="flex-1 text-sm text-gray-800 truncate">{{ it.name }}</div>
            <div class="flex gap-1">
              <button
                class="px-2 py-1 rounded border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-50 text-xs"
                :disabled="idx === 0 || reorderingLabels"
                @click="moveReorderItem(idx, -1)"
              >
                上移
              </button>
              <button
                class="px-2 py-1 rounded border border-gray-200 bg-white hover:bg-gray-50 disabled:opacity-50 text-xs"
                :disabled="idx === reorderItems.length - 1 || reorderingLabels"
                @click="moveReorderItem(idx, 1)"
              >
                下移
              </button>
            </div>
          </div>
        </div>

        <div class="flex justify-end gap-2 mt-4">
          <button class="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg text-sm" :disabled="reorderingLabels" @click="closeReorderLabels">取消</button>
          <button class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm disabled:opacity-50" :disabled="reorderingLabels || reorderItems.length === 0" @click="applyReorderLabels">
            {{ reorderingLabels ? '处理中...' : '应用' }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="showDeleteLabelModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="closeDeleteLabel">
      <div class="bg-white rounded-xl shadow-xl w-full max-w-lg p-6">
        <h3 class="text-lg font-bold mb-4">删除标签</h3>
        <div class="mb-3 text-sm text-gray-600">将从 dataset.yaml/data.yaml 删除该标签，并批量重写标注文件（不删除图片）。</div>

        <div class="max-h-[420px] overflow-auto border border-gray-200 rounded-lg">
          <div
            v-for="it in deleteLabelItems"
            :key="it.id"
            class="flex items-center gap-2 px-3 py-2 border-b border-gray-100 last:border-b-0"
          >
            <div class="w-10 text-right font-mono text-sm text-gray-500">{{ it.id }}</div>
            <div class="flex-1 text-sm text-gray-800 truncate">{{ it.name }}</div>
            <div class="text-xs text-gray-500 w-20 text-right font-mono">{{ it.count }}</div>
            <button
              class="px-2 py-1 rounded border border-rose-200 bg-rose-50 text-rose-700 hover:bg-rose-100 disabled:opacity-50 text-xs"
              :disabled="deletingLabel"
              @click="confirmDeleteLabel(it)"
            >
              删除
            </button>
          </div>
        </div>

        <div class="flex justify-end gap-2 mt-4">
          <button class="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg text-sm" :disabled="deletingLabel" @click="closeDeleteLabel">关闭</button>
        </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted, onUnmounted, computed } from 'vue';
import { useMainStore } from '../stores/main';
import api from '../api';
import ImageAnnotator from './ImageAnnotator.vue';

const store = useMainStore();
const images = ref([]);
const loading = ref(false);
const total = ref(0);
const classList = ref([]);
const datasetInfo = ref(null);
const currentImage = ref(null);
const showAutoAnnotateModal = ref(false);
const autoAnnotateType = ref('pretrained');
const selectedModelPath = ref('');
const trainingRuns = ref([]);
const selectionMode = ref(false);
const selectedClassIds = ref([]);
const selectedMap = ref({});
const showCreateSubsetModal = ref(false);
const subsetName = ref('');
const creatingSubset = ref(false);
const deleting = ref(false);
const showReorderLabelsModal = ref(false);
const reorderItems = ref([]);
const reorderingLabels = ref(false);
const showDeleteLabelModal = ref(false);
const deleteLabelItems = ref([]);
const deletingLabel = ref(false);
const pageInput = ref(1);
const isFullScreen = ref(false);

const autoAnnotating = ref(false);
const autoAnnotateStatus = ref({ progress: 0, message: '', added: 0, pending: 0 });

const filters = reactive({
  split: 'train',
  mode: 'include',
  unannotated: false,
  has_auto_label: false,
  offset: 0,
  limit: 60
});

const openAnnotator = (img) => {
  currentImage.value = img;
};

const selectedCount = computed(() => Object.keys(selectedMap.value).length);
const canReorderLabels = computed(() => {
  const v = classList.value;
  if (Array.isArray(v)) return v.length > 0;
  if (v && typeof v === 'object') return Object.keys(v).length > 0;
  return false;
});
const totalPages = computed(() => Math.max(1, Math.ceil((total.value || 0) / (filters.limit || 1))));
const currentPage = computed(() => Math.min(totalPages.value, Math.floor((filters.offset || 0) / (filters.limit || 1)) + 1));

const pretrainedModelOptions = computed(() => {
  return (store.pretrainedModels || []).filter(m => m.type === 'pretrained');
});

const trainedModelOptions = computed(() => {
  return (trainingRuns.value || [])
    .map(r => {
      const runDir = r?.path;
      if (!runDir) return null;
      const weightsDir = `${runDir}/weights`;
      // Check if weights exist (backend checks this but we can trust the entry somewhat or check status)
      // Actually backend returns all runs, status indicates completion.
      // But we construct paths blindly here.
      
      const hasBest = true; // Simplified assumption or check r.status === 'completed'
      const value = `${weightsDir}/best.pt`; // Default to best.pt
      
      const dataset = r.dataset || r.config?.dataset_name || 'Unknown Dataset';
      const modelPath = r.config?.model_name || '';
      const modelName = modelPath.split('/').pop(); // Get basename
      const map50 = r.metrics?.mAP50 ? ` mAP50:${(r.metrics.mAP50 * 100).toFixed(1)}%` : '';
      
      const label = `[${dataset}] ${r.id} (Base: ${modelName})${map50}`;
      return { key: `${r.id}:${value}`, value, label };
    })
    .filter(Boolean);
});

watch(() => showAutoAnnotateModal.value, (val) => {
  if (val) {
    store.fetchModels();
    fetchTrainingRuns();
  }
});

const isSelected = (path) => !!selectedMap.value[path];

const toggleSelectionMode = () => {
  selectionMode.value = !selectionMode.value;
  selectedMap.value = {};
};

const selectAllCurrentPage = () => {
  const next = { ...selectedMap.value };
  images.value.forEach(img => {
    next[img.path] = true;
  });
  selectedMap.value = next;
};

const toggleClass = (id) => {
  if (selectedClassIds.value.includes(id)) {
    selectedClassIds.value = selectedClassIds.value.filter(x => x !== id);
  } else {
    selectedClassIds.value = [...selectedClassIds.value, id];
  }
};

const clearClasses = () => {
  selectedClassIds.value = [];
};

const onImageClick = (img) => {
  if (!selectionMode.value) {
    openAnnotator(img);
    return;
  }
  if (isSelected(img.path)) {
    const next = { ...selectedMap.value };
    delete next[img.path];
    selectedMap.value = next;
  } else {
    selectedMap.value = { ...selectedMap.value, [img.path]: true };
  }
};

const navImage = (dir) => {
  if (!currentImage.value) return;
  const idx = images.value.findIndex(i => i.path === currentImage.value.path);
  if (idx === -1) return;
  
  const newIdx = idx + dir;
  if (newIdx >= 0 && newIdx < images.value.length) {
    currentImage.value = images.value[newIdx];
  } else if (newIdx >= images.value.length) {
    if (currentPage.value < totalPages.value) {
      alert('已到达当前页末尾，请切换到下一页');
    }
  }
};

const onImageUpdate = (img) => {
  // Update the pending status locally
  const target = images.value.find(i => i.path === img.path);
  if (target) {
    target.pending = false; // Assuming save means it's done
  }
};

const fetchDatasetInfo = async () => {
  try {
    const infoRes = await api.getDatasetInfo({
      project_path: store.currentProject.path,
      dataset_name: store.selectedDataset.name
    });
    if (infoRes.data.success) {
      datasetInfo.value = infoRes.data.info || null;
      classList.value = infoRes.data.info?.names || [];
    }
  } catch (e) { console.error('Failed to load classes', e); }
};

const fetchTrainingRuns = async () => {
  try {
    const res = await api.getTrainingRuns({
      project_path: store.currentProject.path,
      dataset_name: store.selectedDataset.name
    });
    if (res.data.success) {
      trainingRuns.value = res.data.runs;
    }
  } catch (e) { console.error(e) }
};

const fetchImages = async (reset = false) => {
  if (!store.currentProject || !store.selectedDataset) return;
  
  if (reset) {
    images.value = [];
    filters.offset = 0;
    pageInput.value = 1;
  }
  
  loading.value = true;
  try {
    const res = await api.getDatasetImages({
      project_path: store.currentProject.path,
      dataset_name: store.selectedDataset.name,
      split: filters.split,
      offset: filters.offset,
      limit: filters.limit,
      classes: selectedClassIds.value.length > 0 ? selectedClassIds.value.join(',') : undefined,
      mode: filters.mode,
      unannotated: filters.unannotated,
      has_auto_label: filters.has_auto_label
    });
    
    if (res.data.success) {
      images.value = res.data.images;
      total.value = res.data.total;
    }
  } catch (err) {
    console.error('Failed to fetch images:', err);
  } finally {
    loading.value = false;
  }
};

const applyFilters = () => {
  selectedMap.value = {};
  filters.offset = 0;
  pageInput.value = 1;
  fetchImages(true);
};

const goPrevPage = () => {
  if (currentPage.value <= 1) return;
  pageInput.value = currentPage.value - 1;
  jumpPage();
};

const goNextPage = () => {
  if (currentPage.value >= totalPages.value) return;
  pageInput.value = currentPage.value + 1;
  jumpPage();
};

const jumpPage = () => {
  const p = Math.max(1, Math.min(totalPages.value, Number(pageInput.value || 1)));
  pageInput.value = p;
  if (!selectionMode.value) {
    selectedMap.value = {};
  }
  filters.offset = (p - 1) * filters.limit;
  fetchImages(false);
};

const openCreateSubset = () => {
  const base = store.selectedDataset?.name || 'dataset';
  subsetName.value = `${base}_subset_${new Date().toISOString().slice(0, 10).replaceAll('-', '')}`;
  showCreateSubsetModal.value = true;
};

const closeCreateSubset = () => {
  showCreateSubsetModal.value = false;
  subsetName.value = '';
};

const openReorderLabels = () => {
  const v = classList.value;
  let names = [];
  if (Array.isArray(v)) {
    names = v;
  } else if (v && typeof v === 'object') {
    names = Object.keys(v)
      .map(k => ({ k: Number(k), name: v[k] }))
      .sort((a, b) => a.k - b.k)
      .map(x => x.name);
  }
  reorderItems.value = (names || []).map((name, idx) => ({ oldIndex: idx, name }));
  showReorderLabelsModal.value = true;
};

const closeReorderLabels = () => {
  showReorderLabelsModal.value = false;
  reorderItems.value = [];
};

const openDeleteLabel = () => {
  const stats = datasetInfo.value?.class_stats || [];
  deleteLabelItems.value = (stats || [])
    .map(s => ({ id: Number(s.id), name: String(s.name ?? ''), count: Number(s.count ?? 0) }))
    .filter(it => Number.isFinite(it.id) && it.name);
  showDeleteLabelModal.value = true;
};

const closeDeleteLabel = () => {
  showDeleteLabelModal.value = false;
  deleteLabelItems.value = [];
};

const confirmDeleteLabel = async (it) => {
  if (!it) return;
  if (!confirm(`确定要删除标签「${it.name}」吗？\n该操作会批量修改标注文件，且不可撤销。`)) return;
  deletingLabel.value = true;
  try {
    const res = await api.deleteDatasetLabel({
      project_path: store.currentProject.path,
      dataset_name: store.selectedDataset.name,
      class_id: it.id
    });
    if (res.data.success) {
      const delId = Number(res.data.deleted_label_id);
      selectedClassIds.value = (selectedClassIds.value || [])
        .filter(x => x !== delId)
        .map(x => (x > delId ? x - 1 : x));

      closeDeleteLabel();
      await fetchDatasetInfo();
      applyFilters();
      alert(`已删除「${res.data.deleted_label_name}」：重写文件 ${res.data.updated_files || 0} 个，移除行 ${res.data.removed_lines || 0} 行，重编号行 ${res.data.shifted_lines || 0} 行`);
    } else {
      alert(res.data.error || '处理失败');
    }
  } catch (e) {
    console.error(e);
    alert('请求失败');
  } finally {
    deletingLabel.value = false;
  }
};

const moveReorderItem = (idx, dir) => {
  const nextIdx = idx + dir;
  if (nextIdx < 0 || nextIdx >= reorderItems.value.length) return;
  const arr = [...reorderItems.value];
  const tmp = arr[idx];
  arr[idx] = arr[nextIdx];
  arr[nextIdx] = tmp;
  reorderItems.value = arr;
};

const applyReorderLabels = async () => {
  const order = reorderItems.value.map(it => it.oldIndex);
  if (order.length === 0) return;
  if (!confirm('确定要应用当前标签顺序吗？这会批量修改标注文件。')) return;
  reorderingLabels.value = true;
  try {
    const res = await api.reorderDatasetLabels({
      project_path: store.currentProject.path,
      dataset_name: store.selectedDataset.name,
      order
    });
    if (res.data.success) {
      const map = {};
      order.forEach((oldIdx, newIdx) => { map[oldIdx] = newIdx; });
      selectedClassIds.value = (selectedClassIds.value || [])
        .map(oldIdx => map[oldIdx])
        .filter(v => v !== undefined && v !== null);
      closeReorderLabels();
      await fetchDatasetInfo();
      applyFilters();
      alert(`已更新：文件 ${res.data.updated_files || 0} 个，行 ${res.data.updated_lines || 0} 行`);
    } else {
      alert(res.data.error || '处理失败');
    }
  } catch (e) {
    console.error(e);
    alert('请求失败');
  } finally {
    reorderingLabels.value = false;
  }
};

const createSubset = async () => {
  if (!subsetName.value) return;
  const imagePaths = Object.keys(selectedMap.value);
  if (imagePaths.length === 0) return;
  creatingSubset.value = true;
  try {
    const res = await api.createDatasetSubset({
      project_path: store.currentProject.path,
      source_dataset: store.selectedDataset.name,
      new_dataset_name: subsetName.value,
      image_paths: imagePaths
    });
    if (res.data.success) {
      await store.fetchProjects();
      const proj = store.projects.find(p => p.id === store.currentProject.id) || store.projects.find(p => p.path === store.currentProject.path);
      if (proj) {
        store.currentProject = proj;
        const all = [
          ...(proj.datasets?.trainable || []),
          ...(proj.datasets?.annotatable || [])
        ];
        const created = all.find(d => d.name === subsetName.value) || all.find(d => d.path?.endsWith(`/training/${subsetName.value}`));
        store.selectedDataset = created || store.selectedDataset;
      }
      closeCreateSubset();
      selectionMode.value = false;
      selectedMap.value = {};
      fetchDatasetInfo();
      fetchImages(true);
      alert(res.data.message || '创建成功');
    } else {
      alert(res.data.error || '创建失败');
    }
  } catch (e) {
    console.error(e);
    alert('请求失败');
  } finally {
    creatingSubset.value = false;
  }
};

const batchDelete = async () => {
  const imagePaths = Object.keys(selectedMap.value);
  if (imagePaths.length === 0) return;
  if (!confirm(`确定要删除选中的 ${imagePaths.length} 张图片及其标注文件吗？`)) return;
  deleting.value = true;
  try {
    const res = await api.batchDeleteDatasetImages({
      project_path: store.currentProject.path,
      dataset_name: store.selectedDataset.name,
      split: filters.split,
      image_paths: imagePaths
    });
    if (res.data.success) {
      selectedMap.value = {};
      await fetchImages(false);
      if (images.value.length === 0 && (filters.offset || 0) > 0) {
        filters.offset = Math.max(0, (filters.offset || 0) - (filters.limit || 0));
        pageInput.value = Math.floor((filters.offset || 0) / (filters.limit || 1)) + 1;
        await fetchImages(false);
      }
      alert(`成功删除 ${res.data.deleted_count || 0} 张图片`);
    } else {
      alert(res.data.error || '删除失败');
    }
  } catch (e) {
    console.error(e);
    alert('请求失败');
  } finally {
    deleting.value = false;
  }
};

const runAutoAnnotate = async () => {
  showAutoAnnotateModal.value = false;
  
  try {
    const res = await api.autoAnnotate({
      project_path: store.currentProject.path,
      dataset_name: store.selectedDataset.name,
      split: filters.split,
      model_path: selectedModelPath.value,
      conf: 0.25,
      iou: 0.7
    });
    
    if (res.data.success) {
      autoAnnotating.value = true;
      autoAnnotateStatus.value = { progress: 0, message: '初始化...', added: 0, pending: 0 };
      pollAutoAnnotateStatus();
    } else {
      alert('自动标注启动失败: ' + res.data.error);
    }
  } catch (err) {
    console.error(err);
    alert('请求失败');
  }
};

const pollAutoAnnotateStatus = () => {
  const timer = setInterval(async () => {
    try {
      const res = await api.getAutoAnnotateStatus();
      if (res.data.success) {
        const s = res.data.status;
        autoAnnotateStatus.value = s;
        if (!s.is_running) {
          clearInterval(timer);
          autoAnnotating.value = false;
          setTimeout(() => {
             alert(`自动标注完成！\n新增标注: ${s.added || 0}\n待复核: ${s.pending || 0}`);
             fetchImages(true);
          }, 300);
        }
      }
    } catch (e) {
      console.error(e);
    }
  }, 1000);
};

watch(() => store.selectedDataset, () => {
  if (store.selectedDataset) {
    fetchImages(true);
    fetchDatasetInfo();
    fetchTrainingRuns();
    selectionMode.value = false;
    selectedMap.value = {};
    selectedClassIds.value = [];
  }
});

watch(() => filters.split, () => applyFilters());

const handleGlobalKeydown = (e) => {
  if (e.defaultPrevented) return;
  if (e.ctrlKey || e.metaKey || e.altKey) return;
  if (!store.selectedDataset) return;
  if (currentImage.value || showAutoAnnotateModal.value || showCreateSubsetModal.value) return;

  const el = e.target;
  const tag = el?.tagName?.toLowerCase?.();
  if (tag === 'input' || tag === 'textarea' || tag === 'select' || el?.isContentEditable) return;

  if (e.key === 'ArrowLeft') {
    if (currentPage.value > 1) {
      e.preventDefault();
      goPrevPage();
    }
  } else if (e.key === 'ArrowRight') {
    if (currentPage.value < totalPages.value) {
      e.preventDefault();
      goNextPage();
    }
  }
};

onMounted(() => {
  if (store.selectedDataset) {
    fetchImages(true);
    fetchDatasetInfo();
    fetchTrainingRuns();
  }
  window.addEventListener('keydown', handleGlobalKeydown);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleGlobalKeydown);
});
</script>
