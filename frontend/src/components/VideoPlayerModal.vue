<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import api from '../api';
import { useToast } from '../composables/useToast';
import { useApiCall } from '../composables/useApiCall';
import AppIcon from './ui/AppIcon.vue';

const props = defineProps({
  video: { type: Object, required: true },
  project: { type: Object, required: true },
});
const emit = defineEmits(['close', 'refresh', 'trimmed']);

const toast = useToast();
const apiCall = useApiCall();

const videoEl = ref(null);
const trackEl = ref(null);

const previewReady = ref(Boolean(props.video?.preview_ready));
const previewStatus = ref(props.video?.preview_status || 'none');
const previewProgress = ref(Number(props.video?.preview_progress || 0));
const previewTaskId = ref(props.video?.preview_task_id || null);
const previewError = ref('');

const duration = ref(Number(props.video?.duration || 0));
const currentTime = ref(0);
const trimStart = ref(0);
const trimEnd = ref(Number(props.video?.duration || 0));

const trimming = ref(false);
const trimProgress = ref(0);
const trimTaskId = ref(null);
const trimError = ref('');

const dragging = ref(null);

const needsPreview = computed(() => Boolean(props.video?.needs_preview) && !previewReady.value);
const playableSrc = computed(() => {
  if (previewReady.value) return props.video.preview_url || `${props.video.stream_url}&preview=1`;
  if (!props.video.needs_preview) return props.video.stream_url;
  return null;
});
const previewBusy = computed(() => previewStatus.value === 'processing' || previewStatus.value === 'pending' || previewStatus.value === 'stopping');

const startPct = computed(() => (duration.value > 0 ? (trimStart.value / duration.value) * 100 : 0));
const endPct = computed(() => (duration.value > 0 ? (trimEnd.value / duration.value) * 100 : 0));
const playheadPct = computed(() => (duration.value > 0 ? (currentTime.value / duration.value) * 100 : 0));
const regionStyle = computed(() => ({ left: `${startPct.value}%`, width: `${Math.max(0, endPct.value - startPct.value)}%` }));
const canTrim = computed(() => duration.value > 0 && trimEnd.value > trimStart.value && !trimming.value);

const formatTime = (sec) => {
  const total = Math.max(0, Math.floor(Number(sec) || 0));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = String(m).padStart(2, '0');
  const ss = String(s).padStart(2, '0');
  return h > 0 ? `${String(h).padStart(2, '0')}:${mm}:${ss}` : `${mm}:${ss}`;
};

// ---- 任务轮询 ----
const timers = new Set();
let disposed = false;
const schedule = (fn, ms) => {
  const id = setTimeout(() => { timers.delete(id); if (!disposed) fn(); }, ms);
  timers.add(id);
};
const pollTask = (taskId, handlers) => {
  const tick = async () => {
    if (disposed) return;
    let task = null;
    try { task = await api.getTask(taskId); } catch (_) { task = null; }
    if (disposed) return;
    if (!task) { schedule(tick, 2000); return; }
    handlers.onProgress?.(task);
    const status = task.status;
    if (status === 'completed') { handlers.onCompleted?.(task); return; }
    if (status === 'failed' || status === 'interrupted') { handlers.onFailed?.(task); return; }
    if (status === 'stopped') { handlers.onStopped?.(task); return; }
    schedule(tick, 1500);
  };
  tick();
};

// ---- 预览转码 ----
const pollPreview = (taskId) => {
  pollTask(taskId, {
    onProgress: (task) => {
      previewProgress.value = Number(task.progress || 0);
      previewStatus.value = task.status;
    },
    onCompleted: () => {
      previewReady.value = true;
      previewStatus.value = 'ready';
      previewProgress.value = 100;
      previewError.value = '';
      emit('refresh');
    },
    onFailed: (task) => {
      previewStatus.value = 'failed';
      previewError.value = task.error || '预览生成失败';
    },
    onStopped: () => { previewStatus.value = 'stopped'; },
  });
};

const startPreview = async () => {
  previewError.value = '';
  const data = await apiCall(api.transcodeVideo({
    project_path: props.project.path,
    video_name: props.video.name,
    mode: 'preview',
  }), {
    silent: true,
    onError: (_d, e) => { previewError.value = e?.message || '预览生成失败'; previewStatus.value = 'failed'; },
  });
  if (!data) return;
  if (data.already_ready) {
    previewReady.value = true;
    previewStatus.value = 'ready';
    emit('refresh');
    return;
  }
  previewTaskId.value = data.task_id;
  previewStatus.value = 'processing';
  previewProgress.value = 0;
  pollPreview(data.task_id);
};

const cancelPreview = async () => {
  if (!previewTaskId.value) return;
  await apiCall(api.stopTask(previewTaskId.value), { silent: true });
};

// ---- 裁剪 ----
const pollTrim = (taskId, targetName) => {
  pollTask(taskId, {
    onProgress: (task) => { trimProgress.value = Number(task.progress || 0); },
    onCompleted: (task) => {
      trimming.value = false;
      trimProgress.value = 100;
      const name = task?.artifacts?.output_video_name || targetName || '新片段';
      toast.success(`已生成片段「${name}」，可在视频列表中抽帧`);
      emit('trimmed', name);
      emit('refresh');
    },
    onFailed: (task) => {
      trimming.value = false;
      trimError.value = task.error || '裁剪失败';
    },
    onStopped: () => { trimming.value = false; },
  });
};

const doTrim = async () => {
  if (!canTrim.value) return;
  trimError.value = '';
  trimming.value = true;
  trimProgress.value = 0;
  const data = await apiCall(api.transcodeVideo({
    project_path: props.project.path,
    video_name: props.video.name,
    mode: 'trim',
    start: Number(trimStart.value.toFixed(3)),
    end: Number(trimEnd.value.toFixed(3)),
  }), {
    silent: true,
    onError: (_d, e) => { trimError.value = e?.message || '裁剪失败'; trimming.value = false; },
  });
  if (!data) { trimming.value = false; return; }
  trimTaskId.value = data.task_id;
  pollTrim(data.task_id, data.target_name);
};

const cancelTrim = async () => {
  if (!trimTaskId.value) return;
  await apiCall(api.stopTask(trimTaskId.value), { silent: true });
};

// ---- 播放与时间轴 ----
const onMeta = () => {
  if (!videoEl.value) return;
  const d = Number(videoEl.value.duration || 0);
  if (d > 0) {
    duration.value = d;
    if (trimEnd.value <= 0 || trimEnd.value > d) trimEnd.value = d;
  }
};
const onTime = () => { if (videoEl.value) currentTime.value = Number(videoEl.value.currentTime || 0); };

const clampStart = (v) => { trimStart.value = Math.min(Math.max(0, Number(v) || 0), Math.max(0, trimEnd.value - 0.1)); };
const clampEnd = (v) => { trimEnd.value = Math.max(Math.min(duration.value, Number(v) || 0), trimStart.value + 0.1); };

const ratioFromEvent = (e) => {
  if (!trackEl.value) return 0;
  const rect = trackEl.value.getBoundingClientRect();
  if (rect.width <= 0) return 0;
  return Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
};
const onDragMove = (e) => {
  if (!dragging.value) return;
  const t = ratioFromEvent(e) * duration.value;
  if (dragging.value === 'start') clampStart(t);
  else clampEnd(t);
};
let lastDragEnd = 0;
const onDragUp = () => {
  if (!dragging.value) return;
  dragging.value = null;
  lastDragEnd = Date.now();
  window.removeEventListener('pointermove', onDragMove);
  window.removeEventListener('pointerup', onDragUp);
};
const onHandleDown = (which, e) => {
  e.preventDefault();
  dragging.value = which;
  window.addEventListener('pointermove', onDragMove);
  window.addEventListener('pointerup', onDragUp);
};
const onTrackClick = (e) => {
  if (dragging.value || Date.now() - lastDragEnd < 300) return;
  if (!videoEl.value || duration.value <= 0) return;
  videoEl.value.currentTime = ratioFromEvent(e) * duration.value;
};

onMounted(() => {
  if (needsPreview.value) {
    if (previewBusy.value && previewTaskId.value) pollPreview(previewTaskId.value);
    else startPreview();
  }
});

onUnmounted(() => {
  disposed = true;
  timers.forEach((id) => clearTimeout(id));
  timers.clear();
  window.removeEventListener('pointermove', onDragMove);
  window.removeEventListener('pointerup', onDragUp);
});
</script>

<template>
  <div class="vt-media-backdrop" @click.self="emit('close')">
    <div class="vt-media-panel max-h-[94vh] overflow-y-auto" style="width: min(96vw, 960px);">
      <div class="flex justify-between items-center mb-2 text-white">
        <h3 class="font-medium truncate">{{ video.name }}</h3>
        <button @click="emit('close')" class="vt-media-close" aria-label="关闭视频播放器">
          <AppIcon name="close" class="h-4 w-4" />
        </button>
      </div>

      <!-- 可播放：预览副本或原生可解码视频 -->
      <video
        v-if="playableSrc"
        ref="videoEl"
        :src="playableSrc"
        controls
        autoplay
        playsinline
        preload="metadata"
        class="w-full max-h-[46vh] bg-black"
        @loadedmetadata="onMeta"
        @timeupdate="onTime"
      ></video>

      <!-- 需要预览但尚未就绪 -->
      <div v-else class="flex flex-col items-center justify-center gap-3 bg-black text-white py-14 px-6">
        <AppIcon name="video" class="h-8 w-8 text-white/60" />
        <div class="text-sm text-white/80 text-center">
          该视频编码（{{ video.codec || '未知' }}）浏览器无法直接播放，需先生成 H.264 预览副本。
        </div>
        <template v-if="previewBusy">
          <div class="w-full max-w-sm">
            <div class="flex justify-between text-xs text-white/70 mb-1">
              <span class="flex items-center gap-1.5"><span class="vt-inline-spinner h-3 w-3"></span>正在生成可播放预览…</span>
              <span>{{ previewProgress }}%</span>
            </div>
            <div class="vt-meter h-1.5"><div class="vt-meter__bar vt-meter__bar--info transition-all duration-300" :style="{ width: previewProgress + '%' }"></div></div>
          </div>
          <button class="vt-btn-inverse" @click="cancelPreview">取消</button>
        </template>
        <template v-else>
          <div v-if="previewError" class="text-xs text-rose-300 text-center max-w-md break-words">{{ previewError }}</div>
          <button class="vt-btn-inverse" @click="startPreview">
            <AppIcon name="restore" class="h-4 w-4" />
            {{ previewStatus === 'failed' || previewStatus === 'stopped' ? '重新生成预览' : '生成预览' }}
          </button>
        </template>
      </div>

      <!-- 裁剪控制 -->
      <div class="mt-3 bg-white border border-gray-200 p-4">
        <div class="flex items-center justify-between mb-3">
          <h4 class="text-sm font-semibold text-slate-800 flex items-center gap-1.5">
            <AppIcon name="split" class="h-4 w-4 text-slate-500" />
            裁剪片段
          </h4>
          <span class="text-xs text-gray-400">拖动滑块选择保留区间，生成可直接抽帧的新片段</span>
        </div>

        <!-- 时间轴 -->
        <div
          ref="trackEl"
          class="relative h-10 select-none touch-none bg-slate-200 cursor-pointer"
          @click="onTrackClick"
        >
          <div class="absolute top-0 bottom-0 bg-[color:var(--vt-color-primary-soft)] border-y-2 border-[color:var(--vt-color-primary)]" :style="regionStyle"></div>
          <div class="absolute top-0 bottom-0 w-0.5 bg-slate-800 pointer-events-none" :style="{ left: playheadPct + '%' }"></div>
          <div
            class="absolute top-0 bottom-0 w-5 -ml-2.5 cursor-ew-resize touch-none flex items-center justify-center"
            :style="{ left: startPct + '%' }"
            title="起点"
            @pointerdown.stop="onHandleDown('start', $event)"
            @click.stop
          ><div class="w-1.5 h-full bg-[color:var(--vt-color-primary)] rounded-sm flex items-center justify-center"><div class="w-0.5 h-4 bg-white/80"></div></div></div>
          <div
            class="absolute top-0 bottom-0 w-5 -ml-2.5 cursor-ew-resize touch-none flex items-center justify-center"
            :style="{ left: endPct + '%' }"
            title="终点"
            @pointerdown.stop="onHandleDown('end', $event)"
            @click.stop
          ><div class="w-1.5 h-full bg-[color:var(--vt-color-primary)] rounded-sm flex items-center justify-center"><div class="w-0.5 h-4 bg-white/80"></div></div></div>
        </div>

        <div class="flex justify-between text-xs text-gray-500 mt-1.5">
          <span>起点 <span class="font-mono text-slate-700">{{ formatTime(trimStart) }}</span></span>
          <span>当前 <span class="font-mono text-slate-700">{{ formatTime(currentTime) }}</span> / {{ formatTime(duration) }}</span>
          <span>终点 <span class="font-mono text-slate-700">{{ formatTime(trimEnd) }}</span></span>
        </div>

        <!-- 控制行 -->
        <div class="flex flex-wrap items-center gap-2 mt-3">
          <span class="text-xs text-gray-500">保留 <span class="font-mono text-slate-700">{{ formatTime(Math.max(0, trimEnd - trimStart)) }}</span></span>
          <div class="flex-1"></div>
          <button class="vt-btn-solid-primary vt-btn-size-md" :disabled="!canTrim" @click="doTrim">
            <AppIcon name="split" class="h-4 w-4" />
            {{ trimming ? '裁剪中…' : '裁剪为新片段' }}
          </button>
        </div>

        <!-- 裁剪进度 / 错误 -->
        <div v-if="trimming" class="mt-3">
          <div class="flex justify-between text-xs text-gray-500 mb-1">
            <span class="flex items-center gap-1.5"><span class="vt-inline-spinner h-3 w-3"></span>正在裁剪并重编码为 H.264…</span>
            <span>{{ trimProgress }}%</span>
          </div>
          <div class="vt-meter h-1.5"><div class="vt-meter__bar vt-meter__bar--info transition-all duration-300" :style="{ width: trimProgress + '%' }"></div></div>
          <div class="mt-2 flex justify-end">
            <button class="vt-btn-secondary vt-btn-size-sm" @click="cancelTrim">取消裁剪</button>
          </div>
        </div>
        <div v-if="trimError" class="mt-2 text-xs text-rose-500 break-words">{{ trimError }}</div>
      </div>
    </div>
  </div>
</template>