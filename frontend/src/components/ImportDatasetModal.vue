<template>
  <div class="vt-modal-backdrop" @click.self="onCancel">
    <div class="vt-modal-panel vt-modal-panel--md flex flex-col">
      <div class="vt-modal-header">
        <h3 class="text-base font-semibold text-slate-800 inline-flex items-center gap-2">
          <AppIcon name="download" class="h-4 w-4 text-slate-600" />
          <span>导入数据集</span>
        </h3>
        <button class="vt-modal-close" @click="onCancel" :disabled="uploading && !success && !error">
          <AppIcon name="close" class="h-4 w-4" />
        </button>
      </div>

      <div class="vt-modal-body space-y-3">
        <div class="text-xs text-gray-500">
          将上传到项目 <span class="font-mono text-slate-700">projects/{{ project?.name }}/training/&lt;name&gt;/</span>
        </div>

        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">
            数据集 zip 包 <span class="text-rose-500">*</span>
          </label>
          <div
            class="vt-dropzone"
            :class="[
              dragging ? 'vt-dropzone--active' : 'hover:border-[color:var(--vt-color-primary-border)]',
              uploading ? 'pointer-events-none opacity-60' : 'cursor-pointer'
            ]"
            @click="!uploading && fileInput && fileInput.click()"
            @dragover.prevent="dragging = true"
            @dragleave.prevent="dragging = false"
            @drop.prevent="onDrop"
          >
            <div v-if="!file" class="text-gray-500 text-sm">
              <div class="mb-2 flex justify-center">
                <AppIcon name="download" class="h-7 w-7 text-slate-500" />
              </div>
              <div>点击选择文件 / 拖入 zip 包</div>
              <div class="text-xs text-gray-400 mt-1">最大 2 GB</div>
            </div>
            <div v-else class="text-left text-sm">
              <UiTooltip side="bottom" align="start" content-class="max-w-[24rem] break-all text-left">
                <template #trigger>
                  <div class="font-medium text-slate-800 truncate inline-flex items-center gap-2">
                    <AppIcon name="download" class="h-4 w-4 text-slate-500" />
                    <span>{{ file.name }}</span>
                  </div>
                </template>
                {{ file.name }}
              </UiTooltip>
              <div class="text-xs text-gray-500">{{ formatSize(file.size) }}</div>
            </div>
            <input ref="fileInput" type="file" accept=".zip" class="hidden"
                   @change="onPick" />
          </div>
        </div>

        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">
            重命名为（可选）
          </label>
          <input
            v-model="targetName"
            type="text"
            :disabled="uploading"
            placeholder="留空则使用 zip 内的数据集名"
            class="vt-input"
          />
          <div class="mt-1 text-xs text-gray-400">
            若 zip 内数据集名与你已有数据集冲突，可在此改名。
          </div>
        </div>

        <div v-if="uploading || success || error" class="space-y-2">
          <!-- 阶段指示器 -->
          <div class="flex items-center justify-between text-xs">
            <div class="flex items-center gap-2">
              <span :class="phaseClass('uploading')">① 上传</span>
              <span class="text-gray-300">→</span>
              <span :class="phaseClass('parsing')">② 解析</span>
              <span class="text-gray-300">→</span>
              <span :class="phaseClass('converting')">③ 转换</span>
              <span class="text-gray-300">→</span>
              <span :class="phaseClass('saving')">④ 落盘</span>
            </div>
            <span class="text-gray-500 font-mono">{{ progress }}%</span>
          </div>
          <!-- 进度条 -->
          <div class="vt-meter h-2">
            <div class="vt-meter__bar transition-all duration-300"
                 :class="success ? 'vt-meter__bar--success' : (error ? 'vt-meter__bar--danger' : 'vt-meter__bar--info')"
                 :style="{ width: progress + '%' }"></div>
          </div>
          <!-- 当前阶段消息 -->
          <div v-if="phaseMessage" class="text-xs text-gray-600 flex items-center gap-1.5">
            <span v-if="!success && !error" class="vt-inline-spinner h-3 w-3"></span>
            <span v-if="success" class="text-emerald-600">✓</span>
            <span v-if="error" class="text-rose-600">✕</span>
            <span>{{ phaseMessage }}</span>
          </div>
        </div>

        <div v-if="error" class="border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">
          {{ error }}
        </div>

        <div class="vt-section-muted text-xs text-gray-600 leading-relaxed">
          <div class="mb-1 inline-flex items-center gap-2 font-medium">
            <AppIcon name="detail" class="h-3.5 w-3.5 text-slate-500" />
            <span>支持的数据集格式（任一即可，自动识别）</span>
          </div>
          <ul class="list-disc pl-5 space-y-0.5">
            <li><b>YOLO</b> · 含 <code>dataset.yaml</code> + <code>train/{images,labels}</code></li>
            <li><b>COCO</b> · 含 <code>annotations/instances_*.json</code> + 图片目录</li>
            <li><b>Pascal VOC</b> · 含 <code>Annotations/*.xml</code> + <code>ImageSets/Main/</code></li>
          </ul>
          <div class="mt-1.5 text-gray-500">COCO / VOC 上传后将自动转换为 YOLO 规范后落盘。</div>
        </div>

        <div class="flex justify-end gap-2 pt-1">
          <button type="button"
                  class="vt-btn-secondary vt-btn-size-md"
                  :disabled="uploading && !success && !error"
                  @click="onCancel">
            {{ success ? '完成' : (error ? '关闭' : '取消') }}
          </button>
          <button v-if="!uploading && !success && !error"
                  type="button"
                  :disabled="!file"
                  class="vt-btn-solid-primary vt-btn-size-md"
                  @click="onSubmit">
            <AppIcon name="download" class="h-4 w-4" />
            开始导入
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useAsyncEmit } from '../composables/useAsyncEmit';
import AppIcon from './ui/AppIcon.vue';
import UiTooltip from './ui/Tooltip.vue';

const props = defineProps({
  project: { type: Object, default: null }
});
const emit = defineEmits(['close', 'submit']);
const asyncEmit = useAsyncEmit(emit);

const fileInput = ref(null);
const file = ref(null);
const targetName = ref('');
const progress = ref(0);
const phaseMessage = ref('');
const currentPhase = ref('idle'); // 'idle' | 'uploading' | 'parsing' | 'converting' | 'saving' | 'done'
const uploading = ref(false);
const success = ref(false);
const error = ref('');
const dragging = ref(false);

// 阶段顺序：判断阶段先后
const phaseOrder = ['uploading', 'parsing', 'converting', 'saving'];

const phaseClass = (p) => {
  const idx = phaseOrder.indexOf(currentPhase.value);
  const pIdx = phaseOrder.indexOf(p);
  if (currentPhase.value === 'done') return 'text-emerald-600 font-semibold';
  if (currentPhase.value === 'fail') {
    if (pIdx < idx) return 'text-emerald-600';
    if (pIdx === idx) return 'text-rose-600 font-semibold';
    return 'text-gray-400';
  }
  if (pIdx < idx) return 'text-emerald-600 font-medium';
  if (pIdx === idx) return 'vt-text-accent-strong';
  return 'text-gray-400';
};

const formatSize = (b) => {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / 1024 / 1024).toFixed(1)} MB`;
  return `${(b / 1024 / 1024 / 1024).toFixed(2)} GB`;
};

const onPick = (e) => {
  const f = e.target.files?.[0];
  if (f) {
    if (!f.name.toLowerCase().endsWith('.zip')) {
      error.value = '仅支持 .zip 文件';
      return;
    }
    file.value = f;
    error.value = '';
  }
};
const onDrop = (e) => {
  dragging.value = false;
  const f = e.dataTransfer?.files?.[0];
  if (f) {
    if (!f.name.toLowerCase().endsWith('.zip')) {
      error.value = '仅支持 .zip 文件';
      return;
    }
    file.value = f;
    error.value = '';
  }
};

const onCancel = () => {
  if (uploading.value && !success.value && !error.value) return;
  emit('close');
};

const onSubmit = async () => {
  if (!file.value || !props.project) return;
  uploading.value = true;
  success.value = false;
  error.value = '';
  progress.value = 0;
  phaseMessage.value = '准备上传…';
  currentPhase.value = 'uploading';

  try {
    await asyncEmit('submit', {
      file: file.value,
      projectPath: props.project.path || props.project.name,
      targetName: targetName.value.trim() || undefined,
      onProgress: (ev) => {
        if (typeof ev === 'number') {
          progress.value = ev;
        } else {
          progress.value = ev.progress ?? progress.value;
          phaseMessage.value = ev.message || phaseMessage.value;
          if (ev.phase) currentPhase.value = ev.phase;
        }
      },
    });
    success.value = true;
    currentPhase.value = 'done';
    progress.value = 100;
    phaseMessage.value = '导入完成';
    setTimeout(() => {
      if (success.value) emit('close');
    }, 800);
  } catch (e) {
    error.value = e?.message || '导入失败';
    currentPhase.value = 'fail';
  } finally {
    uploading.value = false;
  }
};
</script>
