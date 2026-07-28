<template>
  <div v-if="visible" class="vt-modal-backdrop" @click.self="onClose">
    <div class="vt-modal-panel vt-modal-panel--md p-6">
      <div class="mb-4 flex items-center justify-between">
        <h3 class="text-lg font-semibold text-slate-800 inline-flex items-center gap-2">
          <AppIcon name="video" class="h-5 w-5 text-slate-600" />
          <span>上传视频到 <span class="vt-text-accent">{{ project?.name }}</span></span>
        </h3>
        <button class="vt-modal-close"
                :disabled="uploading"
                @click="onClose">
          <AppIcon name="close" class="h-4 w-4" />
        </button>
      </div>

      <div v-if="!uploading && !success && !error">
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">
            视频文件 <span class="text-rose-500">*</span>
          </label>
          <div
            class="vt-dropzone"
            :class="dragging ? 'vt-dropzone--active' : 'hover:border-[color:var(--vt-color-primary-border)]'"
            @click="fileInput && fileInput.click()"
            @dragover.prevent="dragging = true"
            @dragleave.prevent="dragging = false"
            @drop.prevent="onDrop"
          >
            <div v-if="!file" class="text-gray-500 text-sm">
              <div class="mb-2 flex justify-center">
                <AppIcon name="video" class="h-7 w-7 text-slate-500" />
              </div>
              <div>点击选择 / 拖入视频文件</div>
              <div class="text-xs text-gray-400 mt-1">支持 {{ VIDEO_FILE_EXTENSIONS.join(' / ') }} · 最大 2 GB</div>
            </div>
            <div v-else class="text-left text-sm">
              <UiTooltip side="bottom" align="start" content-class="max-w-[24rem] break-all text-left">
                <template #trigger>
                  <div class="inline-flex items-center gap-2 truncate font-medium text-slate-800">
                    <AppIcon name="video" class="h-4 w-4 text-slate-500" />
                    <span>{{ file.name }}</span>
                  </div>
                </template>
                {{ file.name }}
              </UiTooltip>
              <div class="text-xs text-gray-500">{{ formatBytes(file.size) }}</div>
            </div>
            <input ref="fileInput" type="file" class="hidden" :accept="VIDEO_FILE_ACCEPT" @change="onPick" />
          </div>
        </div>

        <div class="mt-3">
          <label class="block text-xs font-medium text-gray-700 mb-1">
            重命名为（可选）
          </label>
          <input
            v-model="targetName"
            type="text"
            placeholder="留空则使用原文件名（去掉扩展名）"
            class="vt-input"
          />
          <div class="mt-1 text-xs text-gray-400">
            仅支持字母/数字/下划线/短横线/点
          </div>
        </div>

        <div class="mt-5 flex justify-end gap-2">
          <button @click="onClose"
                  class="vt-btn-secondary vt-btn-size-md">
            取消
          </button>
          <button :disabled="!file"
                  class="vt-btn-solid-primary vt-btn-size-md"
                  @click="onSubmit">
            <AppIcon name="video" class="h-4 w-4" />
            开始上传
          </button>
        </div>
      </div>

      <!-- 上传中 / 成功 / 失败 -->
      <div v-else class="space-y-2">
        <div class="flex items-center justify-between text-xs">
          <div class="flex items-center gap-2">
            <span :class="phaseClass('uploading')">① 上传</span>
            <span class="text-gray-300">→</span>
            <span :class="phaseClass('saving')">② 落盘</span>
            <span class="text-gray-300">→</span>
            <span :class="phaseClass('done')">③ 完成</span>
          </div>
          <span class="text-gray-500 font-mono">{{ progress }}%</span>
        </div>
        <div class="vt-meter h-2">
          <div class="vt-meter__bar transition-all duration-300"
               :class="success ? 'vt-meter__bar--success' : (error ? 'vt-meter__bar--danger' : 'vt-meter__bar--info')"
               :style="{ width: progress + '%' }"></div>
        </div>
        <div v-if="phaseMessage" class="text-xs text-gray-600 flex items-center gap-1.5">
          <span v-if="!success && !error" class="vt-inline-spinner h-3 w-3"></span>
          <span v-if="success" class="text-emerald-600">✓</span>
          <span v-if="error" class="text-rose-600">✕</span>
          <span>{{ phaseMessage }}</span>
        </div>

        <div class="mt-4 flex justify-end">
          <button v-if="!uploading" @click="onClose"
                  class="vt-btn-secondary vt-btn-size-md">
            {{ success ? '完成' : '关闭' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';
import { useAsyncEmit } from '../composables/useAsyncEmit';
import { usePhaseProgress } from '../composables/usePhaseProgress';
import { formatBytes, validateResourceName } from '../utils';
import {
  UPLOAD_SIZE_LIMIT_BYTES,
  VIDEO_FILE_ACCEPT,
  VIDEO_FILE_EXTENSIONS,
  isSupportedVideoFile,
} from '../utils/media';
import AppIcon from './ui/AppIcon.vue';
import UiTooltip from './ui/Tooltip.vue';

const props = defineProps({
  visible: { type: Boolean, default: false },
  project: { type: Object, required: true },
});
const emit = defineEmits(['close', 'uploaded', 'onDone']);
const asyncEmit = useAsyncEmit(emit);

const fileInput = ref(null);
const file = ref(null);
const targetName = ref('');
const progress = ref(0);
const phaseMessage = ref('');
const uploading = ref(false);
const success = ref(false);
const error = ref('');

const dragging = ref(false);

// 视频上传的三段进度：上传 → 落盘 → 完成。
const { currentPhase, phaseClass, setPhase, markFail } = usePhaseProgress({
  phases: ['uploading', 'saving', 'done'],
});


const onPick = (e) => {
  const f = e.target.files?.[0];
  if (f) setFile(f);
};
const onDrop = (e) => {
  dragging.value = false;
  const f = e.dataTransfer?.files?.[0];
  if (f) setFile(f);
};
const setFile = (f) => {
  if (!isSupportedVideoFile(f)) {
    error.value = `仅支持 ${VIDEO_FILE_EXTENSIONS.join(' / ')} 格式`;
    return;
  }
  if (f.size > UPLOAD_SIZE_LIMIT_BYTES) {
    error.value = '视频不能超过 2 GB';
    return;
  }
  file.value = f;
  error.value = '';
};

const reset = () => {
  file.value = null;
  targetName.value = '';
  progress.value = 0;
  phaseMessage.value = '';
  setPhase('idle');
  uploading.value = false;
  success.value = false;
  error.value = '';
  if (fileInput.value) fileInput.value.value = '';
};

watch(() => props.visible, (v) => {
  if (v) reset();
});

const onClose = () => {
  if (uploading.value && !success.value && !error.value) return;
  emit('close');
};

const onSubmit = async () => {
  if (!file.value || !props.project) return;
  if (targetName.value.trim()) {
    const nameErr = validateResourceName(targetName.value.trim(), { emptyMessage: '' });
    if (nameErr) { error.value = nameErr; return; }
  }
  uploading.value = true;
  success.value = false;
  error.value = '';
  progress.value = 0;
  phaseMessage.value = '准备上传…';
  setPhase('uploading');

  const fd = new FormData();
  fd.append('file', file.value);
  fd.append('project_path', props.project.path || props.project.name);
  if (targetName.value.trim()) fd.append('target_name', targetName.value.trim());

  try {
    await asyncEmit('submit', {
      formData: fd,
      onProgress: (p) => {
        progress.value = p;
        phaseMessage.value = `上传中… ${p}%`;
      },
    });
    setPhase('saving');
    progress.value = 95;
    phaseMessage.value = '保存到项目…';
    // 模拟小延迟，让用户看到落盘阶段
    await new Promise(r => setTimeout(r, 200));
    success.value = true;
    setPhase('done');
    progress.value = 100;
    phaseMessage.value = `上传完成：${file.value.name}`;
    setTimeout(() => { if (success.value) emit('close'); }, 800);
  } catch (e) {
    error.value = e?.message || '上传失败';
    markFail(currentPhase.value);
  } finally {
    uploading.value = false;
  }
};
</script>
