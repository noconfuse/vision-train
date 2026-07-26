<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import { useMainStore } from '../stores/main';
import api from '../api';
import { useToast } from '../composables/useToast';
import { useApiCall } from '../composables/useApiCall';
import { useAsyncAction } from '../composables/useAsyncAction';
import { useConfirm } from '../composables/useConfirm';
import { useDatasets } from '../composables/useDatasets';
import { useAutoFillGrid } from '../composables/useAutoFillGrid';
import { parseOptionalNumber } from '../utils';
import VideoUploadModal from './VideoUploadModal.vue';
import AppIcon from './ui/AppIcon.vue';
import AsyncButton from './ui/AsyncButton.vue';
import UiTooltip from './ui/Tooltip.vue';
import { TASK_STATUS, getTaskProgressBarClass, getTaskStatusLabel, getTaskStatusTagClass, isTaskActive } from '../taskStatus';

const store = useMainStore();
const router = useRouter();
const toast = useToast();
const apiCall = useApiCall();
const asyncAction = useAsyncAction();
const { confirm: showConfirm } = useConfirm();
const { allDatasets } = useDatasets();
const videos = ref([]);
const tasks = ref([]);
const loading = ref(false);
const error = ref(null);

// Upload modal
const showUploadModal = ref(false);
const openUploadModal = () => {
  if (!store.currentProject) return;
  showUploadModal.value = true;
};

const handleUpload = async ({ formData, onProgress, onDone }) => {
  try {
    await apiCall(api.uploadVideo(formData, (e) => {
      const p = e.total ? Math.round((e.loaded / e.total) * 100) : 0;
      onProgress(p);
    }), {
      // successMsg 已在弹窗内显式 toast，这里不再显示
      silent: true,
      onSuccess: (data) => {
        onDone && onDone();
        toast.success(`视频「${data.video_name}」上传成功`);
        fetchVideos();
      },
      onError: (_d, e) => { onDone && onDone(e); },
    });
  } catch (e) {
    onDone && onDone(e);
  }
};

const deleteVideo = async (video) => {
  if (!video) return;
  const ok = await showConfirm({
    message: `确定要删除视频「${video.name}」吗？\n关联的抽帧任务会一并清理。`,
    danger: true,
    confirmText: '删除',
  });
  if (!ok) return;
  await asyncAction.run(deleteVideoActionKey(video), async () => {
    await apiCall(api.deleteVideo({
      project_path: store.currentProject.path,
      video_name: video.name
    }), {
      successMsg: `视频「${video.name}」已删除`,
      onSuccess: () => {
        fetchVideos();
        fetchTasks();
      },
    });
  });
};

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

const EXTRACT_ACTION_KEY = 'extract-video';
const deleteVideoActionKey = (video) => `delete-video:${video?.name || ''}`;
const deleteTaskActionKey = (task) => `delete-video-task:${task?.id || ''}`;
const reviewTaskActionKey = (task) => `review-video-task:${task?.id || ''}`;
const isActionPending = (key) => asyncAction.isPending(key);

// Methods
const fetchVideos = async () => {
  if (!store.currentProject) return;
  
  loading.value = true;
  error.value = null;
  try {
    videos.value = await api.getVideos({ project_path: store.currentProject.path });
  } catch (err) {
    error.value = 'Failed to load videos';
    console.error(err);
  } finally {
    loading.value = false;
  }
};

const fetchTasks = async () => {
  if (!store.currentProject) {
    tasks.value = [];
    stopPolling();
    return;
  }
  try {
    const items = await api.getVideoTasks({
      project_path: store.currentProject.path,
    });
    tasks.value = Array.isArray(items) ? items : [];
    if (tasks.value.some((task) => isTaskActive(task))) {
      if (!taskPollTimer) {
        // 仅在存在活跃抽帧任务时保持轮询，避免页面空转。
        taskPollTimer = setInterval(fetchTasks, 6000);
      }
    } else {
      stopPolling();
    }
  } catch (err) {
    console.error('Failed to fetch tasks', err);
  }
};

const startPolling = () => {
  stopPolling();
  fetchTasks();
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

const closePlayer = () => {
  showPlayer.value = false;
  playerVideo.value = null;
};

const startExtraction = async () => {
  if (!currentVideo.value?.name) return;
  await asyncAction.run(EXTRACT_ACTION_KEY, async () => {
    await apiCall(api.extractVideo({
      project_path: store.currentProject.path,
      video_name: currentVideo.value.name,
      strategy: form.value.strategy,
      value: Number(form.value.value)
    }), {
      successMsg: '抽帧任务已启动',
      onSuccess: () => {
        showModal.value = false;
        fetchTasks();
      }
    });
  });
};

const reviewTask = async (task) => {
  if (!task?.id) return;
  await asyncAction.run(reviewTaskActionKey(task), async () => {
    currentTask.value = task;
    showReview.value = true;
    reviewMaximized.value = false;
    taskImages.value = [];
    selectedImages.value.clear();
    displayCount.value = 0;
    await apiCall(api.getTaskImages({
      project_path: store.currentProject.path,
      task_id: task.id
    }), {
      errorMsg: '加载任务图片失败',
      onSuccess: (data) => {
        taskImages.value = Array.isArray(data)
          ? data
          : (Array.isArray(data?.images) ? data.images : []);
        selectedImages.value.clear();
        taskImages.value.forEach(img => selectedImages.value.add(img.name));
        displayCount.value = Math.min(displayBatch, taskImages.value.length);
        nextTick(() => {
          if (reviewScrollEl.value) reviewScrollEl.value.scrollTop = 0;
        });
      }
    });
  });
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
    toast.warn('请选择要删除的图片');
    return;
  }
  const ok = await showConfirm({
    message: `确定要删除选中的 ${selectedList.length} 张图片吗？`,
    danger: true,
    confirmText: '删除',
  });
  if (!ok) return;

  deletingImages.value = true;
  await apiCall(api.batchDeleteTaskImages({
    project_path: store.currentProject.path,
    task_id: currentTask.value.id,
    selected_images: selectedList
  }), {
    successMsg: '已删除选中的图片',
    onSuccess: (data) => {
      const deleted = new Set(data.deleted_images || selectedList);
      taskImages.value = taskImages.value.filter((img) => !deleted.has(img.name));
      for (const n of deleted) selectedImages.value.delete(n);
      displayCount.value = Math.min(displayCount.value, taskImages.value.length);
      if (showImagePreview.value && deleted.has(previewImage.value?.name)) closePreview();
      fetchTasks();
    },
    finally: () => { deletingImages.value = false; },
  });
};

const deleteTask = async (task) => {
  if (!task?.id) return;
  const ok = await showConfirm({
    message: '确定要删除这个任务及其临时文件吗？',
    danger: true,
    confirmText: '删除',
  });
  if (!ok) return;
  await asyncAction.run(deleteTaskActionKey(task), async () => {
    await apiCall(api.deleteVideoTask({
      project_path: store.currentProject.path,
      task_id: task.id
    }), {
      successMsg: '任务已删除',
      onSuccess: () => fetchTasks(),
    });
  });
};

const importImages = async () => {
  let datasetName = '';
  if (importForm.value.targetType === 'new') {
    datasetName = importForm.value.newDatasetName.trim();
    if (!datasetName) {
      toast.warn('请输入新数据集名称');
      return;
    }
  } else {
    datasetName = importForm.value.existingDataset;
    if (!datasetName) {
      toast.warn('请选择已存在的数据集');
      return;
    }
  }

  const selectedList = Array.from(selectedImages.value);
  if (selectedList.length === 0) {
    toast.warn('请选择要导入的图片');
    return;
  }

  importing.value = true;
  await apiCall(api.importTaskImages({
    project_path: store.currentProject.path,
    task_id: currentTask.value.id,
    dataset_name: datasetName,
    selected_images: selectedList
  }), {
    onSuccess: async (data) => {
      const finalDatasetName = String(data?.dataset_name || datasetName || '').trim();
      toast.success(`成功导入 ${data.imported_count} 张图片到数据集 ${finalDatasetName}`);
      showReview.value = false;
      await store.fetchProjects({ silent: true });
      const nextProject = store.projects.find(p => p.id === store.currentProject?.id)
        || store.projects.find(p => p.path === store.currentProject?.path)
        || store.currentProject;
      const nextDataset = (nextProject?.datasets || []).find(d => d.name === finalDatasetName) || null;
      if (nextProject) store.selectProject(nextProject);
      if (nextDataset) store.selectDataset(nextDataset);
      await router.push({
        name: 'dataset-detail',
        params: {
          project: encodeURIComponent(nextProject?.name || store.currentProject?.name || ''),
          name: encodeURIComponent(finalDatasetName),
        },
      });
    },
    finally: () => { importing.value = false; },
  });
};

const getTaskVideoName = (task) => {
  const rawName = task?.video_name ?? task?.payload?.video_name ?? '';
  const normalized = String(rawName || '').trim();
  return normalized || '未命名视频';
};

const getTaskExtractedCount = (task) => {
  const rawCount = task?.extracted_count ?? task?.artifacts?.extracted_count;
  return parseOptionalNumber(rawCount, { integer: true, min: 0 });
};

// Computed
const existingDatasets = computed(() => {
  const byName = new Map();
  for (const d of allDatasets.value) {
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

const { gridClass: reviewGridClass, gridStyle: reviewGridStyle } = useAutoFillGrid(reviewMaximized, {
  compactTile: 112,
  regularTile: 132,
  gapClass: 'gap-3',
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
  <div class="vt-view vt-view--cols">
    <!-- Main Content: Video List -->
    <div class="vt-view__main p-4">
      <!-- Toolbar -->
      <div class="flex justify-between items-center shrink-0">
        <h2 class="text-sm font-semibold text-slate-800">视频列表 <span class="text-xs text-gray-400 font-normal">({{ videos.length }})</span></h2>
        <div class="flex items-center gap-3">
          <button @click="openUploadModal"
                  class="vt-btn-solid-primary vt-btn-size-md">
            <AppIcon name="video" class="h-4 w-4" />
            <span>上传视频</span>
          </button>
        </div>
      </div>

      <div class="flex-1 min-h-0 flex flex-col">
        <!-- Loading / Error -->
        <div v-if="loading" class="vt-empty text-sm text-gray-500">加载中...</div>
        <div v-else-if="error" class="vt-empty text-sm text-red-500">{{ error }}</div>
        <div v-else-if="videos.length === 0" class="vt-empty text-sm text-gray-500">
          <div class="mb-2 flex justify-center">
            <AppIcon name="video" class="h-8 w-8 text-slate-400" />
          </div>
          <div class="mb-3">当前项目下还没有视频</div>
          <button @click="openUploadModal"
                  class="vt-btn-solid-primary vt-btn-size-md">
            <AppIcon name="video" class="h-4 w-4" />
            上传第一个视频
          </button>
        </div>

        <!-- Video Grid -->
        <div v-else class="flex-1 min-h-0 overflow-y-auto">
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
            <div v-for="video in videos" :key="video.name" class="bg-white border border-gray-200 overflow-hidden flex flex-col group hover:border-[color:var(--vt-color-primary-border)] transition-colors">
          <!-- Thumbnail -->
            <div class="relative h-32 bg-black flex items-center justify-center cursor-pointer group-hover:opacity-95 transition-opacity" @click="openPlayer(video)">
              <img
                :src="video.thumbnail_url"
                class="w-full h-full object-cover"
                loading="lazy"
                @error="$event.target.style.display='none'"
              />
              <!-- Play Icon Overlay -->
              <div class="absolute inset-0 flex items-center justify-center bg-black/20 group-hover:bg-black/30 transition-colors">
                <div class="vt-media-play-trigger">
                  <AppIcon name="train" class="h-5 w-5" />
                </div>
              </div>
            </div>

            <div class="p-3 flex-1 flex flex-col">
              <div class="flex items-start justify-between mb-1">
                <UiTooltip side="bottom" align="start" content-class="max-w-[24rem] break-words text-left">
                  <template #trigger>
                    <h3 class="font-medium text-gray-900 text-sm truncate flex-1">{{ video.name }}</h3>
                  </template>
                  {{ video.name }}
                </UiTooltip>
                <UiTooltip side="top" align="center" content-class="max-w-[24rem] break-words text-left">
                  <template #trigger>
                    <AsyncButton
                      @click="deleteVideo(video)"
                      :pending="isActionPending(deleteVideoActionKey(video))"
                      class="vt-icon-btn ml-1 -mt-0.5 h-7 w-7 border-transparent bg-transparent text-gray-300 hover:bg-rose-50 hover:text-rose-500 disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <AppIcon name="delete" class="h-4 w-4" />
                    </AsyncButton>
                  </template>
                  {{ isActionPending(deleteVideoActionKey(video)) ? '删除中...' : `删除 ${video.name}` }}
                </UiTooltip>
              </div>
              <div class="text-xs text-gray-500 mb-3">
                {{ video.size_mb }} MB • {{ video.modified }}
              </div>

              <div class="mt-auto">
                <button @click="openExtractModal(video)" class="vt-btn-solid-primary vt-btn-size-md w-full justify-center" :disabled="isActionPending(EXTRACT_ACTION_KEY)">
                  <AppIcon name="split" class="h-4 w-4" />
                  抽帧构建数据集
                </button>
              </div>
            </div>
          </div>
        </div>
        </div>
      </div>
    </div>

    <!-- Right Sidebar: Task List -->
    <div class="w-80 bg-white border-l border-gray-200 flex flex-col z-10 h-full min-h-0">
      <div class="px-3 pt-4 pb-2 border-b border-gray-200 bg-gray-50 shrink-0">
        <div class="h-8 flex justify-between items-center">
        <h3 class="text-sm font-semibold text-gray-800">当前项目任务</h3>
        <span class="text-xs text-gray-500" v-if="tasks.length">{{ tasks.length }} 个任务</span>
        </div>
      </div>

      <div class="flex-1 overflow-y-auto px-3 py-3 space-y-2">
        <div v-if="tasks.length === 0" class="text-center text-gray-400 text-xs py-8">
          当前项目下暂无抽帧任务
        </div>

        <article
          v-for="task in tasks"
          :key="task.id"
          class="vt-record-card"
          :class="isTaskActive(task) ? 'vt-record-card--active' : ''"
        >
          <div class="vt-record-header mb-2">
            <UiTooltip side="bottom" align="start" content-class="max-w-[24rem] break-words text-left">
              <template #trigger>
                <div class="vt-record-main">
                  <div class="vt-record-title truncate pr-2">{{ getTaskVideoName(task) }}</div>
                  <div class="vt-record-meta">{{ task.created_at }}</div>
                </div>
              </template>
              {{ getTaskVideoName(task) }}
            </UiTooltip>
            <div class="vt-record-side">
              <div class="vt-record-badges">
                <span class="vt-tag vt-tag--sm" :class="getTaskStatusTagClass(task.status)">
                  {{ getTaskStatusLabel(task.status) }}
                </span>
              </div>
              <AsyncButton
                @click="deleteTask(task)"
                class="vt-icon-btn vt-icon-btn--sm border-transparent bg-transparent text-slate-300 hover:bg-rose-50 hover:text-rose-500"
                :pending="isActionPending(deleteTaskActionKey(task))"
                aria-label="删除任务"
              >
                <AppIcon name="delete" class="h-3.5 w-3.5" />
              </AsyncButton>
            </div>
          </div>

          <!-- Status & Progress -->
          <div v-if="task.status === TASK_STATUS.RUNNING || task.status === TASK_STATUS.PENDING || task.status === TASK_STATUS.STOPPING" class="space-y-1.5">
            <div class="flex justify-between text-xs">
              <span class="text-slate-500">{{ task.status === TASK_STATUS.PENDING ? '等待处理' : task.status === TASK_STATUS.STOPPING ? '停止中' : '进行中' }}</span>
              <span>{{ task.progress }}%</span>
            </div>
            <div class="vt-meter h-1">
              <div class="vt-meter__bar transition-all duration-300" :class="getTaskProgressBarClass(task.status)" :style="{ width: task.progress + '%' }"></div>
            </div>
          </div>

          <div v-else-if="task.status === TASK_STATUS.COMPLETED" class="space-y-2">
            <div class="flex items-center justify-between gap-2 text-xs">
              <span class="text-slate-500">可进入审查并导入</span>
              <span v-if="getTaskExtractedCount(task) !== null" class="vt-count-badge">
                {{ getTaskExtractedCount(task) }} 张
              </span>
            </div>
            <AsyncButton
              @click="reviewTask(task)"
              class="vt-btn-solid-primary vt-btn-size-md w-full justify-center"
              :pending="isActionPending(reviewTaskActionKey(task))"
              loading-text="加载中..."
            >
              <AppIcon name="detail" class="h-4 w-4" />
              审查并导入
            </AsyncButton>
          </div>

          <div v-else class="text-xs text-rose-500">
            {{ task.error || '任务执行失败' }}
          </div>
        </article>
      </div>
    </div>

    <!-- Modals -->

    <!-- Extraction Config Modal -->
    <div v-if="showModal" class="vt-modal-backdrop">
      <div class="vt-modal-panel vt-modal-panel--md p-5">
        <h3 class="text-base font-semibold text-slate-800 mb-4">抽帧配置</h3>
        <p class="text-sm text-gray-600 mb-4">
          源视频: <span class="font-medium">{{ currentVideo?.name }}</span>
        </p>

        <div class="space-y-4">
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">抽帧策略</label>
            <select v-model="form.strategy" class="vt-select">
              <option value="interval">按时间间隔 (秒)</option>
              <option value="count">按总帧数 (均匀抽取)</option>
            </select>
          </div>

          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">
              {{ form.strategy === 'interval' ? '间隔时间 (秒)' : '抽取总张数' }}
            </label>
            <input v-model="form.value" type="number" :step="form.strategy === 'interval' ? 0.1 : 1" class="vt-input">
          </div>
        </div>

        <div class="mt-6 flex justify-end gap-3">
          <button @click="showModal = false" class="vt-btn-secondary vt-btn-size-md" :disabled="isActionPending(EXTRACT_ACTION_KEY)">取消</button>
          <AsyncButton
            @click="startExtraction"
            class="vt-btn-solid-primary vt-btn-size-md"
            :pending="isActionPending(EXTRACT_ACTION_KEY)"
            loading-text="启动中..."
          >
            <AppIcon name="split" class="h-4 w-4" />
            开始抽帧
          </AsyncButton>
        </div>
      </div>
    </div>

    <!-- Video Player Modal -->
    <div v-if="showPlayer" class="vt-media-backdrop" @click.self="closePlayer">
      <div class="vt-media-panel">
        <div class="flex justify-between items-center mb-2 text-white">
          <h3 class="font-medium truncate">{{ playerVideo?.name }}</h3>
          <button @click="closePlayer" class="vt-media-close" aria-label="关闭视频播放器">
            <AppIcon name="close" class="h-4 w-4" />
          </button>
        </div>
        <video
          v-if="playerVideo"
          :src="playerVideo.stream_url"
          controls
          autoplay
          playsinline
          preload="metadata"
          class="w-full max-h-[80vh] bg-black"
        ></video>
      </div>
    </div>

    <!-- Review Modal -->
    <div
      v-if="showReview"
      class="vt-workspace-backdrop"
      :class="reviewMaximized ? 'vt-workspace-backdrop--full' : ''"
    >
      <div
        class="vt-workspace-panel"
        :class="reviewMaximized ? 'vt-workspace-panel--full' : 'vt-workspace-panel--lg'"
      >
        <!-- Header -->
        <div class="p-4 border-b border-gray-200 flex justify-between items-center">
          <div>
            <h3 class="text-base font-semibold text-slate-800">抽帧结果审查</h3>
            <p class="text-sm text-gray-500">任务 ID: {{ currentTask?.id.slice(0, 8) }}...</p>
          </div>
          <div class="flex items-center gap-2">
            <button
              @click="reviewMaximized = !reviewMaximized"
              class="vt-icon-btn"
              :aria-label="reviewMaximized ? '退出全屏审查弹窗' : '全屏审查弹窗'"
            >
              <AppIcon :name="reviewMaximized ? 'minimize' : 'maximize'" class="h-4 w-4" />
            </button>
            <button @click="showReview = false" class="vt-modal-close">
              <AppIcon name="close" class="h-4 w-4" />
            </button>
          </div>
        </div>

        <!-- Main Content -->
        <div class="flex-1 flex min-h-0">
          <!-- Image Grid -->
          <div ref="reviewScrollEl" class="flex-1 p-4 overflow-y-auto bg-gray-50 relative" @scroll="onReviewScroll" @mousedown="onReviewMouseDown">
            <div class="flex justify-between items-center mb-4 gap-3">
              <span class="text-sm text-gray-600">
                共 {{ taskImages.length }} 张，已显示 {{ visibleTaskImages.length }} 张，已选 <span class="font-bold text-[color:var(--vt-color-primary)]">{{ selectedImages.size }}</span> 张
              </span>
              <div class="flex items-center gap-3">
                <button @click="batchDeleteSelected" class="vt-btn-danger vt-btn-size-sm" :disabled="deletingImages || selectedImages.size === 0">
                  <AppIcon name="delete" class="h-3.5 w-3.5" />
                  {{ deletingImages ? '删除中...' : '批量删除' }}
                </button>
                <button @click="selectAll" class="vt-btn-secondary vt-btn-size-sm">
                  {{ selectedImages.size === taskImages.length ? '取消全选' : '全选' }}
                </button>
              </div>
            </div>

            <div
              v-if="boxSelecting"
              class="absolute z-20 border-2 pointer-events-none"
              :style="{
                ...boxStyle,
                borderColor: 'var(--vt-color-primary)',
                background: 'color-mix(in srgb, var(--vt-color-primary-soft) 72%, transparent)',
              }"
            ></div>

            <div :class="reviewGridClass" :style="reviewGridStyle">
              <div
                v-for="img in visibleTaskImages"
                :key="img.name"
                data-img-tile="1"
                :data-img-name="img.name"
                class="aspect-square relative group cursor-pointer border-2 overflow-hidden"
                :class="selectedImages.has(img.name) ? 'vt-selectable--selected' : 'vt-selectable'"
                @click="toggleImage(img.name)"
              >
                <img :src="img.url" class="w-full h-full object-cover" loading="lazy" />
                <button
                  class="vt-overlay-icon-btn absolute bottom-1 left-1"
                  @click.stop="openPreview(img.name)"
                  aria-label="放大预览图片"
                >
                  <AppIcon name="eye" class="h-3.5 w-3.5" />
                </button>
                <!-- Selection Overlay -->
                <div class="absolute top-1 right-1">
                  <div class="h-5 w-5 border border-white flex items-center justify-center transition-colors"
                    :class="selectedImages.has(img.name) ? 'bg-[var(--vt-color-primary)]' : 'bg-black/30 group-hover:bg-black/50'"
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
                class="vt-btn-secondary vt-btn-size-md"
                @click="loadMoreImages"
              >
                加载更多
              </button>
            </div>
          </div>

          <!-- Sidebar: Import Settings -->
          <div class="w-80 border-l border-gray-200 bg-white p-5 flex flex-col">
            <h4 class="text-sm font-semibold text-slate-800 mb-5">导入设置</h4>

            <div class="space-y-5 flex-1">
              <div>
                <label class="flex items-center gap-2 mb-2 cursor-pointer">
                  <input type="radio" v-model="importForm.targetType" value="new" class="vt-radio">
                  <span class="text-sm font-medium">创建新数据集</span>
                </label>
                <input
                  v-if="importForm.targetType === 'new'"
                  v-model="importForm.newDatasetName"
                  type="text"
                  placeholder="输入数据集名称"
                  class="vt-input"
                >
              </div>

              <div>
                <label class="flex items-center gap-2 mb-2 cursor-pointer">
                  <input type="radio" v-model="importForm.targetType" value="existing" class="vt-radio">
                  <span class="text-sm font-medium">添加到现有数据集</span>
                </label>
                <select
                  v-if="importForm.targetType === 'existing'"
                  v-model="importForm.existingDataset"
                  class="vt-select"
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
                class="w-full vt-btn-solid-primary vt-btn-size-md justify-center"
                :disabled="importing || taskImages.length === 0 || selectedImages.size === 0 || (importForm.targetType === 'new' && !importForm.newDatasetName.trim()) || (importForm.targetType === 'existing' && !importForm.existingDataset)"
              >
                <AppIcon name="download" class="h-4 w-4" />
                {{ importing ? '导入中...' : '确认导入' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showImagePreview" class="vt-media-backdrop z-[60]" @click.self="closePreview">
      <div class="vt-media-viewer">
        <div class="vt-media-header">
          <div class="vt-media-meta">
            <div class="vt-media-title">{{ previewImage?.name }}</div>
            <div class="vt-media-subtitle">{{ previewIndex + 1 }} / {{ taskImages.length }}</div>
          </div>
          <div class="vt-media-actions">
            <button class="vt-btn-inverse" @click="setPreviewScale(previewScale * 0.9)">-</button>
            <button class="vt-btn-inverse" @click="previewScale = 1; previewOffsetX = 0; previewOffsetY = 0">100%</button>
            <button class="vt-btn-inverse" @click="setPreviewScale(previewScale * 1.1)">+</button>
            <button class="vt-btn-inverse" :disabled="previewIndex <= 0" @click="navPreview(-1)">上一张</button>
            <button class="vt-btn-inverse" :disabled="previewIndex >= taskImages.length - 1" @click="navPreview(1)">下一张</button>
            <button class="vt-btn-inverse" @click="closePreview">关闭</button>
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

    <!-- Upload Modal -->
    <VideoUploadModal
      :visible="showUploadModal"
      :project="store.currentProject"
      @close="showUploadModal = false"
      @submit="handleUpload"
    />
  </div>
</template>
