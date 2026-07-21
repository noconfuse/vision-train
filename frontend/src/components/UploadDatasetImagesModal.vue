<template>
  <div v-if="visible" class="vt-modal-backdrop" @click.self="onClose">
    <div class="vt-modal-panel vt-modal-panel--md p-6">
      <div class="mb-4 flex items-center justify-between">
        <h3 class="text-lg font-semibold text-slate-800 inline-flex items-center gap-2">
          <AppIcon name="upload" class="h-5 w-5 text-slate-600" />
          <span>上传图片到 <span class="vt-text-accent">{{ datasetName }}</span></span>
        </h3>
        <button class="vt-modal-close" :disabled="uploading" @click="onClose">
          <AppIcon name="close" class="h-4 w-4" />
        </button>
      </div>

      <div v-if="!uploading && !success && !error">
        <div class="mb-3">
          <label class="block text-xs font-medium text-gray-700 mb-1">目标 split</label>
          <select v-model="localSplit" class="vt-select">
            <option value="train">train</option>
            <option value="val">val</option>
            <option value="test">test</option>
          </select>
        </div>

        <div
          class="vt-dropzone"
          :class="dragging ? 'vt-dropzone--active' : 'hover:border-[color:var(--vt-color-primary-border)]'"
          @click="fileInput && fileInput.click()"
          @dragover.prevent="dragging = true"
          @dragleave.prevent="dragging = false"
          @drop.prevent="onDrop"
        >
          <div v-if="files.length === 0" class="text-gray-500 text-sm">
            <div class="mb-2 flex justify-center">
              <AppIcon name="upload" class="h-7 w-7 text-slate-500" />
            </div>
            <div>点击选择 / 拖入图片文件</div>
            <div class="text-xs text-gray-400 mt-1">支持多选，仅上传图片到当前数据集（{{ IMAGE_FILE_ACCEPT }}）</div>
          </div>
          <div v-else class="text-left text-sm">
            <div class="font-medium text-slate-800">{{ files.length }} 张图片待上传</div>
            <div class="mt-1 max-h-32 overflow-auto text-xs text-gray-500 space-y-1">
              <div v-for="file in files.slice(0, 8)" :key="`${file.name}-${file.size}`" class="truncate">
                {{ file.name }}
              </div>
              <div v-if="files.length > 8" class="text-gray-400">还有 {{ files.length - 8 }} 张</div>
            </div>
          </div>
          <input
            ref="fileInput"
            type="file"
            class="hidden"
            :accept="IMAGE_FILE_ACCEPT"
            multiple
            @change="onPick"
          />
        </div>

        <div class="mt-5 flex justify-end gap-2">
          <button @click="onClose" class="vt-btn-secondary vt-btn-size-md">取消</button>
          <button :disabled="files.length === 0" class="vt-btn-solid-primary vt-btn-size-md" @click="onSubmit">
            <AppIcon name="upload" class="h-4 w-4" />
            开始上传
          </button>
        </div>
      </div>

      <div v-else class="space-y-2">
        <div class="flex items-center justify-between text-xs">
          <div class="flex items-center gap-2">
            <span :class="uploading ? 'vt-text-accent-strong' : 'text-emerald-600 font-medium'">① 上传</span>
            <span class="text-gray-300">→</span>
            <span :class="success ? 'text-emerald-600 font-semibold' : (error ? 'text-rose-600 font-semibold' : 'text-gray-400')">② 完成</span>
          </div>
          <span class="text-gray-500 font-mono">{{ progress }}%</span>
        </div>
        <div class="vt-meter h-2">
          <div
            class="vt-meter__bar transition-all duration-300"
            :class="success ? 'vt-meter__bar--success' : (error ? 'vt-meter__bar--danger' : 'vt-meter__bar--info')"
            :style="{ width: `${progress}%` }"
          ></div>
        </div>
        <div class="text-xs text-gray-600 flex items-center gap-1.5">
          <span v-if="!success && !error" class="vt-inline-spinner h-3 w-3"></span>
          <span v-if="success" class="text-emerald-600">✓</span>
          <span v-if="error" class="text-rose-600">✕</span>
          <span>{{ phaseMessage }}</span>
        </div>
        <div class="mt-4 flex justify-end">
          <button v-if="!uploading" @click="onClose" class="vt-btn-secondary vt-btn-size-md">
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
import { IMAGE_FILE_ACCEPT, isSupportedImageFile } from '../media';
import AppIcon from './ui/AppIcon.vue';

const props = defineProps({
  visible: { type: Boolean, default: false },
  datasetName: { type: String, required: true },
  split: { type: String, default: 'train' },
});

const emit = defineEmits(['close', 'submit']);
const asyncEmit = useAsyncEmit(emit);

const fileInput = ref(null);
const files = ref([]);
const localSplit = ref('train');
const progress = ref(0);
const phaseMessage = ref('');
const uploading = ref(false);
const success = ref(false);
const error = ref('');
const dragging = ref(false);

const allowedImage = (file) => isSupportedImageFile(file);

const reset = () => {
  files.value = [];
  localSplit.value = props.split || 'train';
  progress.value = 0;
  phaseMessage.value = '';
  uploading.value = false;
  success.value = false;
  error.value = '';
  dragging.value = false;
  if (fileInput.value) fileInput.value.value = '';
};

watch(() => props.visible, (visible) => {
  if (visible) reset();
});

const setFiles = (items) => {
  const next = Array.from(items || []).filter(allowedImage);
  if (next.length === 0) {
    error.value = `仅支持以下图片格式：${IMAGE_FILE_ACCEPT}`;
    return;
  }
  files.value = next;
  error.value = '';
};

const onPick = (event) => setFiles(event.target.files);
const onDrop = (event) => {
  dragging.value = false;
  setFiles(event.dataTransfer?.files);
};

const onClose = () => {
  if (uploading.value && !success.value && !error.value) return;
  emit('close');
};

const onSubmit = async () => {
  if (files.value.length === 0) return;
  uploading.value = true;
  success.value = false;
  error.value = '';
  progress.value = 0;
  phaseMessage.value = '准备上传…';
  try {
    await asyncEmit('submit', {
      split: localSplit.value,
      files: files.value,
      onProgress: (value) => {
        progress.value = Number(value || 0);
        phaseMessage.value = `已上传 ${progress.value}%`;
      },
    });
    success.value = true;
    progress.value = 100;
    phaseMessage.value = '图片已上传';
  } catch (err) {
    error.value = err?.message || '上传失败';
    phaseMessage.value = error.value;
  } finally {
    uploading.value = false;
  }
};
</script>
