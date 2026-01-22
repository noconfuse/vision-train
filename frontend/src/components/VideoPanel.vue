<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue';
import { useMainStore } from '../stores/main';
import api from '../api';

const store = useMainStore();
const videos = ref([]);
const tasks = ref([]);
const loading = ref(false);
const error = ref(null);

// Polling timer
let taskPollTimer = null;

// Extraction Modal
const showModal = ref(false);
const currentVideo = ref(null);
const form = ref({
  strategy: 'interval', // interval | count
  value: 1.0
});

// Player Modal
const showPlayer = ref(false);
const playerVideo = ref(null);

// Review Modal
const showReview = ref(false);
const currentTask = ref(null);
const taskImages = ref([]);
const selectedImages = ref(new Set());
const importForm = ref({
  targetType: 'new', // new | existing
  newDatasetName: '',
  existingDataset: ''
});
const importing = ref(false);

const reviewMaximized = ref(false);
const reviewScrollEl = ref(null);
const displayCount = ref(0);
const displayBatch = 200;

const boxSelecting = ref(false);
const boxStartX = ref(0);
const boxStartY = ref(0);
const boxCurrentX = ref(0);
const boxCurrentY = ref(0);

const deletingImages = ref(false);

const showImagePreview = ref(false);
const previewIndex = ref(0);
const previewScale = ref(1);
const previewOffsetX = ref(0);
const previewOffsetY = ref(0);
const previewPanning = ref(false);
const previewPanStartX = ref(0);
const previewPanStartY = ref(0);
const previewPanOriginX = ref(0);
const previewPanOriginY = ref(0);

// Methods
const fetchVideos = async () => {
  if (!store.currentProject) return;
  
  loading.value = true;
  error.value = null;
  try {
    const res = await api.getVideos({ project_path: store.currentProject.path });
    if (res.data.success) {
      videos.value = res.data.videos;
    } else {
      error.value = res.data.error;
    }
  } catch (err) {
    error.value = 'Failed to load videos';
    console.error(err);
  } finally {
    loading.value = false;
  }
};

const fetchTasks = async () => {
  if (!store.currentProject) return;
  try {
    const res = await api.getTasks({ project_path: store.currentProject.path });
    if (res.data.success) {
      tasks.value = res.data.tasks;
    }
  } catch (err) {
    console.error("Failed to fetch tasks", err);
  }
};

const startPolling = () => {
  stopPolling();
  fetchTasks();
  taskPollTimer = setInterval(fetchTasks, 2000);
};

const stopPolling = () => {
  if (taskPollTimer) {
    clearInterval(taskPollTimer);
    taskPollTimer = null;
  }
};

const openExtractModal = (video) => {
  currentVideo.value = video;
  form.value = {
    strategy: 'interval',
    value: 1.0
  };
  showModal.value = true;
};

const openPlayer = (video) => {
  playerVideo.value = video;
  showPlayer.value = true;
};

const startExtraction = async () => {
  try {
    const res = await api.extractVideo({
      project_path: store.currentProject.path,
      video_name: currentVideo.value.name,
      strategy: form.value.strategy,
      value: Number(form.value.value)
    });
    
    if (res.data.success) {
      // alert('Task started');
      showModal.value = false;
      fetchTasks(); // Immediate update
    } else {
      alert('Start failed: ' + res.data.error);
    }
  } catch (err) {
    alert('Request failed');
    console.error(err);
  }
};

const reviewTask = async (task) => {
  currentTask.value = task;
  showReview.value = true;
  reviewMaximized.value = false;
  taskImages.value = [];
  selectedImages.value.clear();
  displayCount.value = 0;
  
  // Fetch images
  try {
    const res = await api.getTaskImages({
      project_path: store.currentProject.path,
      task_id: task.id
    });
    if (res.data.success) {
      taskImages.value = res.data.images;
      selectedImages.value.clear();
      taskImages.value.forEach(img => selectedImages.value.add(img.name));
      displayCount.value = Math.min(displayBatch, taskImages.value.length);
      await nextTick();
      if (reviewScrollEl.value) reviewScrollEl.value.scrollTop = 0;
    }
  } catch (err) {
    console.error(err);
    alert("Failed to load task images");
  }
};

const toggleImage = (imgName) => {
  if (selectedImages.value.has(imgName)) {
    selectedImages.value.delete(imgName);
  } else {
    selectedImages.value.add(imgName);
  }
};

const loadMoreImages = () => {
  if (displayCount.value >= taskImages.value.length) return;
  displayCount.value = Math.min(taskImages.value.length, displayCount.value + displayBatch);
};

const onReviewScroll = (e) => {
  const el = e?.target;
  if (!el) return;
  const remaining = el.scrollHeight - el.scrollTop - el.clientHeight;
  if (remaining < 900) loadMoreImages();
};

const openPreview = (imgName) => {
  const idx = taskImages.value.findIndex(x => x?.name === imgName);
  previewIndex.value = idx >= 0 ? idx : 0;
  previewScale.value = 1;
  previewOffsetX.value = 0;
  previewOffsetY.value = 0;
  showImagePreview.value = true;
};

const closePreview = () => {
  showImagePreview.value = false;
  previewPanning.value = false;
};

const navPreview = (dir) => {
  const total = taskImages.value.length;
  if (!total) return;
  const next = previewIndex.value + dir;
  if (next < 0 || next >= total) return;
  previewIndex.value = next;
  previewScale.value = 1;
  previewOffsetX.value = 0;
  previewOffsetY.value = 0;
};

const setPreviewScale = (next) => {
  previewScale.value = Math.max(0.2, Math.min(6, next));
};

const onPreviewWheel = (e) => {
  e.preventDefault();
  const delta = e.deltaY || 0;
  const factor = delta > 0 ? 0.9 : 1.1;
  setPreviewScale(previewScale.value * factor);
};

const onPreviewMouseDown = (e) => {
  if (e.button !== 0) return;
  previewPanning.value = true;
  previewPanStartX.value = e.clientX;
  previewPanStartY.value = e.clientY;
  previewPanOriginX.value = previewOffsetX.value;
  previewPanOriginY.value = previewOffsetY.value;
};

const onPreviewMouseMove = (e) => {
  if (!previewPanning.value) return;
  previewOffsetX.value = previewPanOriginX.value + (e.clientX - previewPanStartX.value);
  previewOffsetY.value = previewPanOriginY.value + (e.clientY - previewPanStartY.value);
};

const onPreviewMouseUp = () => {
  previewPanning.value = false;
};

const selectAll = () => {
  if (selectedImages.value.size === taskImages.value.length) {
    selectedImages.value.clear();
  } else {
    taskImages.value.forEach(img => selectedImages.value.add(img.name));
  }
};

const getReviewContentPoint = (e) => {
  const el = reviewScrollEl.value;
  if (!el) return null;
  const rect = el.getBoundingClientRect();
  return {
    x: e.clientX - rect.left + el.scrollLeft,
    y: e.clientY - rect.top + el.scrollTop
  };
};

const onBoxSelectMove = (e) => {
  if (!boxSelecting.value) return;
  const pt = getReviewContentPoint(e);
  if (!pt) return;
  boxCurrentX.value = pt.x;
  boxCurrentY.value = pt.y;
};

const onBoxSelectEnd = () => {
  if (!boxSelecting.value) return;
  boxSelecting.value = false;
  window.removeEventListener('mousemove', onBoxSelectMove);
  window.removeEventListener('mouseup', onBoxSelectEnd);

  const left = Math.min(boxStartX.value, boxCurrentX.value);
  const right = Math.max(boxStartX.value, boxCurrentX.value);
  const top = Math.min(boxStartY.value, boxCurrentY.value);
  const bottom = Math.max(boxStartY.value, boxCurrentY.value);

  if ((right - left) < 6 && (bottom - top) < 6) return;

  const el = reviewScrollEl.value;
  if (!el) return;
  const containerRect = el.getBoundingClientRect();
  const tiles = el.querySelectorAll('[data-img-tile="1"]');

  const nextSelected = new Set();
  for (const tile of tiles) {
    const name = tile?.getAttribute?.('data-img-name');
    if (!name) continue;
    const r = tile.getBoundingClientRect();
    const tileLeft = r.left - containerRect.left + el.scrollLeft;
    const tileRight = tileLeft + r.width;
    const tileTop = r.top - containerRect.top + el.scrollTop;
    const tileBottom = tileTop + r.height;
    const intersects = !(tileRight < left || tileLeft > right || tileBottom < top || tileTop > bottom);
    if (intersects) nextSelected.add(name);
  }

  if (nextSelected.size > 0) {
    selectedImages.value.clear();
    nextSelected.forEach((n) => selectedImages.value.add(n));
  }
};

const onReviewMouseDown = (e) => {
  if (e.button !== 0) return;
  if (e.target?.closest?.('[data-img-tile="1"]')) return;
  if (e.target?.closest?.('button, input, select, textarea, a')) return;
  const pt = getReviewContentPoint(e);
  if (!pt) return;
  e.preventDefault();
  boxSelecting.value = true;
  boxStartX.value = pt.x;
  boxStartY.value = pt.y;
  boxCurrentX.value = pt.x;
  boxCurrentY.value = pt.y;
  window.addEventListener('mousemove', onBoxSelectMove);
  window.addEventListener('mouseup', onBoxSelectEnd);
};

const batchDeleteSelected = async () => {
  if (deletingImages.value) return;
  const selectedList = Array.from(selectedImages.value);
  if (selectedList.length === 0) {
    alert('请选择要删除的图片');
    return;
  }
  if (!confirm(`确定要删除选中的 ${selectedList.length} 张图片吗？`)) return;

  deletingImages.value = true;
  try {
    const res = await api.batchDeleteTaskImages({
      project_path: store.currentProject.path,
      task_id: currentTask.value.id,
      selected_images: selectedList
    });
    if (!res.data?.success) {
      alert('删除失败: ' + (res.data?.error || 'unknown error'));
      return;
    }

    const deleted = new Set(res.data.deleted_images || selectedList);
    taskImages.value = taskImages.value.filter((img) => !deleted.has(img.name));
    for (const n of deleted) selectedImages.value.delete(n);
    displayCount.value = Math.min(displayCount.value, taskImages.value.length);
    if (showImagePreview.value && deleted.has(previewImage.value?.name)) closePreview();
    fetchTasks();
  } catch (err) {
    console.error(err);
    alert('删除请求失败');
  } finally {
    deletingImages.value = false;
  }
};

const deleteTask = async (task) => {
  if (!confirm('确定要删除这个任务及其临时文件吗？')) return;
  try {
    await api.deleteTask({
      project_path: store.currentProject.path,
      task_id: task.id
    });
    fetchTasks();
  } catch (err) {
    alert("Delete failed");
  }
};

const importImages = async () => {
  let datasetName = '';
  if (importForm.value.targetType === 'new') {
    datasetName = importForm.value.newDatasetName.trim();
    if (!datasetName) {
      alert("请输入新数据集名称");
      return;
    }
  } else {
    datasetName = importForm.value.existingDataset;
    if (!datasetName) {
      alert("请选择已存在的数据集");
      return;
    }
  }
  
  const selectedList = Array.from(selectedImages.value);
  if (selectedList.length === 0) {
    alert('请选择要导入的图片');
    return;
  }

  importing.value = true;
  try {
    const res = await api.importTaskImages({
      project_path: store.currentProject.path,
      task_id: currentTask.value.id,
      dataset_name: datasetName,
      selected_images: selectedList
    });
    
    if (res.data.success) {
      alert(`成功导入 ${res.data.imported_count} 张图片到数据集 ${datasetName}`);
      showReview.value = false;
      // Refresh project to update dataset list if needed
      store.fetchProjects(); 
    } else {
      alert("Import failed: " + res.data.error);
    }
  } catch (err) {
    console.error(err);
    alert("Import request failed");
  } finally {
    importing.value = false;
  }
};

// Computed
const existingDatasets = computed(() => {
  const ds = store.currentProject?.datasets || {};
  const merged = [...(ds.trainable || []), ...(ds.annotatable || [])].filter(Boolean);
  const byName = new Map();
  for (const d of merged) {
    if (d?.name && !byName.has(d.name)) byName.set(d.name, d);
  }
  return Array.from(byName.values()).sort((a, b) => String(a.name).localeCompare(String(b.name)));
});

const visibleTaskImages = computed(() => taskImages.value.slice(0, displayCount.value));

const boxStyle = computed(() => {
  if (!boxSelecting.value) return null;
  const left = Math.min(boxStartX.value, boxCurrentX.value);
  const top = Math.min(boxStartY.value, boxCurrentY.value);
  const width = Math.abs(boxCurrentX.value - boxStartX.value);
  const height = Math.abs(boxCurrentY.value - boxStartY.value);
  return {
    left: `${left}px`,
    top: `${top}px`,
    width: `${width}px`,
    height: `${height}px`
  };
});

const reviewGridClass = computed(() => {
  return reviewMaximized.value
    ? 'grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-6 gap-3'
    : 'grid grid-cols-4 md:grid-cols-5 lg:grid-cols-6 xl:grid-cols-8 gap-3';
});

const previewImage = computed(() => taskImages.value[previewIndex.value] || null);

const handleGlobalKeydown = (e) => {
  if (!showImagePreview.value) return;
  if (e.key === 'Escape') {
    e.preventDefault();
    closePreview();
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault();
    navPreview(-1);
  } else if (e.key === 'ArrowRight') {
    e.preventDefault();
    navPreview(1);
  } else if (e.key === '+' || e.key === '=') {
    e.preventDefault();
    setPreviewScale(previewScale.value * 1.1);
  } else if (e.key === '-' || e.key === '_') {
    e.preventDefault();
    setPreviewScale(previewScale.value * 0.9);
  } else if (e.key === '0') {
    e.preventDefault();
    previewScale.value = 1;
    previewOffsetX.value = 0;
    previewOffsetY.value = 0;
  }
};

watch(() => store.currentProject, (val) => {
  if (val) {
    fetchVideos();
    startPolling();
  } else {
    stopPolling();
  }
});

onMounted(() => {
  if (store.currentProject) {
    fetchVideos();
    startPolling();
  }
  window.addEventListener('keydown', handleGlobalKeydown);
});

onUnmounted(() => {
  stopPolling();
  window.removeEventListener('keydown', handleGlobalKeydown);
  window.removeEventListener('mousemove', onBoxSelectMove);
  window.removeEventListener('mouseup', onBoxSelectEnd);
});
</script>

<template>
  <div class="h-full flex">
    <!-- Main Content: Video List -->
    <div class="flex-1 flex flex-col min-w-0 p-6 overflow-y-auto">
      <!-- Toolbar -->
      <div class="mb-6 flex justify-between items-center">
        <h2 class="text-lg font-medium text-gray-800">视频列表</h2>
        <button @click="fetchVideos" class="text-blue-600 hover:text-blue-800 text-sm">
          刷新列表
        </button>
      </div>

      <!-- Loading / Error -->
      <div v-if="loading" class="text-center py-8 text-gray-500">加载中...</div>
      <div v-else-if="error" class="text-center py-8 text-red-500">{{ error }}</div>
      <div v-else-if="videos.length === 0" class="text-center py-8 text-gray-500">
        当前项目下没有视频文件 (请将视频放入 projects/{{ store.currentProject?.name }}/videos 目录)
      </div>

      <!-- Video Grid -->
      <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        <div v-for="video in videos" :key="video.name" class="bg-white border border-gray-200 rounded-lg shadow-sm hover:shadow-md transition-shadow overflow-hidden flex flex-col group">
          <!-- Thumbnail -->
          <div class="relative h-36 bg-black flex items-center justify-center cursor-pointer group-hover:opacity-95 transition-opacity" @click="openPlayer(video)">
            <img 
              :src="video.thumbnail_url" 
              class="w-full h-full object-cover" 
              loading="lazy"
              @error="$event.target.style.display='none'"
            />
            <!-- Play Icon Overlay -->
            <div class="absolute inset-0 flex items-center justify-center bg-black/20 group-hover:bg-black/30 transition-colors">
              <div class="w-12 h-12 rounded-full bg-white/80 flex items-center justify-center pl-1 shadow-lg">
                <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6 text-gray-900" viewBox="0 0 20 20" fill="currentColor">
                  <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z" clip-rule="evenodd" />
                </svg>
              </div>
            </div>
          </div>
          
          <div class="p-4 flex-1 flex flex-col">
            <h3 class="font-medium text-gray-900 truncate mb-1" :title="video.name">{{ video.name }}</h3>
            <div class="text-xs text-gray-500 mb-4">
              {{ video.size_mb }} MB • {{ video.modified }}
            </div>
            
            <div class="mt-auto">
              <button @click="openExtractModal(video)" class="w-full bg-blue-50 text-blue-600 hover:bg-blue-100 py-2 rounded-md text-sm font-medium transition-colors">
                抽帧构建数据集
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Right Sidebar: Task List -->
    <div class="w-80 bg-white border-l border-gray-200 flex flex-col shadow-lg z-10">
      <div class="p-4 border-b border-gray-200 bg-gray-50 flex justify-between items-center">
        <h3 class="font-medium text-gray-800">任务列表</h3>
        <span class="text-xs text-gray-500" v-if="tasks.length">{{ tasks.length }} 个任务</span>
      </div>
      
      <div class="flex-1 overflow-y-auto p-4 space-y-4">
        <div v-if="tasks.length === 0" class="text-center text-gray-400 text-sm py-8">
          暂无抽帧任务
        </div>
        
        <div v-for="task in tasks" :key="task.id" class="bg-white border border-gray-200 rounded-lg p-3 shadow-sm">
          <div class="flex justify-between items-start mb-2">
            <div class="text-sm font-medium truncate w-40" :title="task.video_name">{{ task.video_name }}</div>
            <button @click="deleteTask(task)" class="text-gray-400 hover:text-red-500">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          
          <div class="text-xs text-gray-500 mb-2">
            {{ task.created_at }}
          </div>
          
          <!-- Status & Progress -->
          <div v-if="task.status === 'running'" class="space-y-1">
            <div class="flex justify-between text-xs">
              <span class="text-blue-600">进行中...</span>
              <span>{{ task.progress }}%</span>
            </div>
            <div class="w-full bg-gray-100 rounded-full h-1.5">
              <div class="bg-blue-600 h-1.5 rounded-full transition-all duration-300" :style="{ width: task.progress + '%' }"></div>
            </div>
          </div>
          
          <div v-else-if="task.status === 'completed'" class="space-y-2">
            <div class="flex justify-between text-xs">
              <span class="text-green-600">已完成</span>
              <span>{{ task.extracted_count }} 张</span>
            </div>
            <button @click="reviewTask(task)" class="w-full bg-green-50 text-green-600 hover:bg-green-100 py-1.5 rounded text-xs font-medium">
              审查并导入
            </button>
          </div>
          
          <div v-else class="text-xs text-red-500">
            失败: {{ task.error }}
          </div>
        </div>
      </div>
    </div>

    <!-- Modals -->
    
    <!-- Extraction Config Modal -->
    <div v-if="showModal" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div class="bg-white rounded-lg shadow-xl w-full max-w-md p-6">
        <h3 class="text-lg font-bold mb-4">抽帧配置</h3>
        <p class="text-sm text-gray-600 mb-4">
          源视频: <span class="font-medium">{{ currentVideo?.name }}</span>
        </p>
        
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">抽帧策略</label>
            <select v-model="form.strategy" class="w-full border border-gray-300 rounded-md px-3 py-2 focus:ring-blue-500 focus:border-blue-500">
              <option value="interval">按时间间隔 (秒)</option>
              <option value="count">按总帧数 (均匀抽取)</option>
            </select>
          </div>
          
          <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">
              {{ form.strategy === 'interval' ? '间隔时间 (秒)' : '抽取总张数' }}
            </label>
            <input v-model="form.value" type="number" :step="form.strategy === 'interval' ? 0.1 : 1" class="w-full border border-gray-300 rounded-md px-3 py-2 focus:ring-blue-500 focus:border-blue-500">
          </div>
        </div>
        
        <div class="mt-6 flex justify-end gap-3">
          <button @click="showModal = false" class="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-md">取消</button>
          <button @click="startExtraction" class="px-4 py-2 bg-blue-600 text-white hover:bg-blue-700 rounded-md">开始抽帧</button>
        </div>
      </div>
    </div>

    <!-- Video Player Modal -->
    <div v-if="showPlayer" class="fixed inset-0 bg-black/90 flex items-center justify-center z-50" @click.self="showPlayer = false">
      <div class="w-full max-w-4xl p-4">
        <div class="flex justify-between items-center mb-2 text-white">
          <h3 class="font-medium truncate">{{ playerVideo?.name }}</h3>
          <button @click="showPlayer = false" class="hover:text-gray-300">
            <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        <video 
          v-if="playerVideo"
          :src="playerVideo.stream_url" 
          controls 
          autoplay
          class="w-full max-h-[80vh] bg-black rounded-lg shadow-2xl"
        ></video>
      </div>
    </div>
    
    <!-- Review Modal -->
    <div v-if="showReview" class="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div
        class="bg-white rounded-lg shadow-xl flex flex-col"
        :class="reviewMaximized ? 'w-[98vw] max-w-none h-[95vh]' : 'w-full max-w-6xl h-[90vh]'"
      >
        <!-- Header -->
        <div class="p-4 border-b border-gray-200 flex justify-between items-center">
          <div>
            <h3 class="text-lg font-bold">抽帧结果审查</h3>
            <p class="text-sm text-gray-500">任务 ID: {{ currentTask?.id.slice(0, 8) }}...</p>
          </div>
          <div class="flex items-center gap-2">
            <button
              @click="reviewMaximized = !reviewMaximized"
              class="px-3 py-1.5 text-sm rounded-md border border-gray-200 hover:bg-gray-50"
            >
              {{ reviewMaximized ? '还原' : '放大' }}
            </button>
            <button @click="showReview = false" class="text-gray-400 hover:text-gray-600">
              <svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
        
        <!-- Main Content -->
        <div class="flex-1 flex min-h-0">
          <!-- Image Grid -->
          <div ref="reviewScrollEl" class="flex-1 p-4 overflow-y-auto bg-gray-50 relative" @scroll="onReviewScroll" @mousedown="onReviewMouseDown">
            <div class="flex justify-between items-center mb-4 gap-3">
              <span class="text-sm text-gray-600">
                共 {{ taskImages.length }} 张，已显示 {{ visibleTaskImages.length }} 张，已选 <span class="font-bold text-blue-600">{{ selectedImages.size }}</span> 张
              </span>
              <div class="flex items-center gap-3">
                <button @click="batchDeleteSelected" class="text-red-600 text-sm hover:underline disabled:opacity-50" :disabled="deletingImages || selectedImages.size === 0">
                  {{ deletingImages ? '删除中...' : '批量删除' }}
                </button>
                <button @click="selectAll" class="text-blue-600 text-sm hover:underline">
                  {{ selectedImages.size === taskImages.length ? '取消全选' : '全选' }}
                </button>
              </div>
            </div>

            <div v-if="boxSelecting" class="absolute border-2 border-blue-500 bg-blue-200/20 pointer-events-none z-20" :style="boxStyle"></div>
            
            <div :class="reviewGridClass">
              <div 
                v-for="img in visibleTaskImages" 
                :key="img.name" 
                data-img-tile="1"
                :data-img-name="img.name"
                class="aspect-square relative group cursor-pointer border-2 rounded-lg overflow-hidden"
                :class="selectedImages.has(img.name) ? 'border-blue-500 ring-2 ring-blue-200' : 'border-gray-200 hover:border-gray-300'"
                @click="toggleImage(img.name)"
              >
                <img :src="img.url" class="w-full h-full object-cover" loading="lazy" />
                <button
                  class="absolute bottom-1 left-1 px-2 py-1 rounded-md bg-black/40 text-white text-xs opacity-0 group-hover:opacity-100 transition-opacity"
                  @click.stop="openPreview(img.name)"
                >
                  放大
                </button>
                <!-- Selection Overlay -->
                <div class="absolute top-1 right-1">
                  <div class="w-5 h-5 rounded-full border border-white shadow-sm flex items-center justify-center transition-colors"
                    :class="selectedImages.has(img.name) ? 'bg-blue-500' : 'bg-black/30 group-hover:bg-black/50'"
                  >
                    <svg v-if="selectedImages.has(img.name)" xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 text-white" viewBox="0 0 20 20" fill="currentColor">
                      <path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" />
                    </svg>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="displayCount < taskImages.length" class="flex justify-center py-6">
              <button
                class="px-4 py-2 text-sm rounded-md border border-gray-200 bg-white hover:bg-gray-50"
                @click="loadMoreImages"
              >
                加载更多
              </button>
            </div>
          </div>
          
          <!-- Sidebar: Import Settings -->
          <div class="w-80 border-l border-gray-200 bg-white p-6 flex flex-col">
            <h4 class="font-bold text-gray-800 mb-6">导入设置</h4>
            
            <div class="space-y-6 flex-1">
              <div>
                <label class="flex items-center gap-2 mb-2 cursor-pointer">
                  <input type="radio" v-model="importForm.targetType" value="new" class="text-blue-600 focus:ring-blue-500">
                  <span class="text-sm font-medium">创建新数据集</span>
                </label>
                <input 
                  v-if="importForm.targetType === 'new'"
                  v-model="importForm.newDatasetName"
                  type="text" 
                  placeholder="输入数据集名称"
                  class="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
                >
              </div>
              
              <div>
                <label class="flex items-center gap-2 mb-2 cursor-pointer">
                  <input type="radio" v-model="importForm.targetType" value="existing" class="text-blue-600 focus:ring-blue-500">
                  <span class="text-sm font-medium">添加到现有数据集</span>
                </label>
                <select 
                  v-if="importForm.targetType === 'existing'"
                  v-model="importForm.existingDataset"
                  class="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="" disabled>选择数据集...</option>
                  <option v-for="d in existingDatasets" :key="d.name" :value="d.name">
                    {{ d.name }}
                  </option>
                </select>
                <p v-if="existingDatasets.length === 0" class="text-xs text-red-500 mt-1">没有可用的数据集</p>
              </div>
            </div>
            
            <div class="pt-4 border-t border-gray-200">
              <button 
                @click="importImages" 
                class="w-full bg-blue-600 text-white py-2 rounded-lg font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                :disabled="importing || taskImages.length === 0 || selectedImages.size === 0 || (importForm.targetType === 'new' && !importForm.newDatasetName.trim()) || (importForm.targetType === 'existing' && !importForm.existingDataset)"
              >
                {{ importing ? '导入中...' : '确认导入' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showImagePreview" class="fixed inset-0 bg-black/90 z-[60]" @click.self="closePreview">
      <div class="h-full w-full flex flex-col">
        <div class="px-4 py-3 flex items-center justify-between text-white">
          <div class="min-w-0">
            <div class="font-medium truncate">{{ previewImage?.name }}</div>
            <div class="text-xs text-white/70">{{ previewIndex + 1 }} / {{ taskImages.length }}</div>
          </div>
          <div class="flex items-center gap-2">
            <button class="px-3 py-1.5 text-sm rounded-md bg-white/10 hover:bg-white/20" @click="setPreviewScale(previewScale * 0.9)">-</button>
            <button class="px-3 py-1.5 text-sm rounded-md bg-white/10 hover:bg-white/20" @click="previewScale = 1; previewOffsetX = 0; previewOffsetY = 0">100%</button>
            <button class="px-3 py-1.5 text-sm rounded-md bg-white/10 hover:bg-white/20" @click="setPreviewScale(previewScale * 1.1)">+</button>
            <button class="px-3 py-1.5 text-sm rounded-md bg-white/10 hover:bg-white/20" :disabled="previewIndex <= 0" @click="navPreview(-1)">上一张</button>
            <button class="px-3 py-1.5 text-sm rounded-md bg-white/10 hover:bg-white/20" :disabled="previewIndex >= taskImages.length - 1" @click="navPreview(1)">下一张</button>
            <button class="px-3 py-1.5 text-sm rounded-md bg-white/10 hover:bg-white/20" @click="closePreview">关闭</button>
          </div>
        </div>

        <div
          class="flex-1 overflow-hidden select-none cursor-grab active:cursor-grabbing"
          @wheel="onPreviewWheel"
          @mousedown="onPreviewMouseDown"
          @mousemove="onPreviewMouseMove"
          @mouseup="onPreviewMouseUp"
          @mouseleave="onPreviewMouseUp"
        >
          <div class="h-full w-full flex items-center justify-center">
            <img
              v-if="previewImage"
              :src="previewImage.url"
              class="max-w-none max-h-none"
              :style="{
                transform: `translate(${previewOffsetX}px, ${previewOffsetY}px) scale(${previewScale})`,
                transformOrigin: 'center center'
              }"
              draggable="false"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
