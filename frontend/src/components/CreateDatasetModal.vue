<template>
  <div class="vt-modal-backdrop" @click.self="onCancel">
    <div class="vt-modal-panel vt-modal-panel--md flex flex-col">
      <div class="vt-modal-header">
        <h3 class="text-base font-semibold text-slate-800 inline-flex items-center gap-2">
          <AppIcon name="plus" class="h-4 w-4 text-slate-600" />
          <span>新建数据集</span>
        </h3>
        <button class="vt-modal-close" :disabled="busy && !success && !error" @click="onCancel">
          <AppIcon name="close" class="h-4 w-4" />
        </button>
      </div>

      <div class="vt-modal-body space-y-3">
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">
            数据集名称 <span class="text-rose-500">*</span>
          </label>
          <input
            v-model="datasetName"
            type="text"
            :disabled="busy"
            placeholder="例如：warehouse_pallet_2026"
            class="vt-input"
          />
          <div v-if="nameError" class="mt-1 text-xs text-rose-600">{{ nameError }}</div>
        </div>

        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">
            任务类型 <span class="text-rose-500">*</span>
          </label>
          <select v-model="visionTaskType" :disabled="busy" class="vt-select">
            <option :value="VISION_TASK_TYPE.DETECT">检测</option>
            <option :value="VISION_TASK_TYPE.CLASSIFY">分类</option>
            <option :value="VISION_TASK_TYPE.SEGMENT">分割</option>
            <option :value="VISION_TASK_TYPE.POSE">姿态</option>
          </select>
        </div>

        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">
            初始类别 <span class="text-gray-400 font-normal">（Enter / 逗号添加）</span>
          </label>
          <div class="flex flex-wrap items-center gap-1.5 rounded border border-slate-200 p-2 focus-within:border-[color:var(--vt-color-primary-border)]"
               @click="focusClassInput">
            <span v-for="(c, idx) in initialClasses" :key="c + idx"
                  class="vt-chip vt-chip--selected inline-flex items-center gap-1">
              <span class="font-medium">{{ c }}</span>
              <button type="button" class="text-slate-500 hover:text-rose-600"
                      :disabled="busy"
                      :aria-label="`移除类别 ${c}`"
                      @click.stop="removeInitialClass(idx)">
                <AppIcon name="close" class="h-3 w-3" />
              </button>
            </span>
            <input
              ref="classInput"
              v-model="newClassName"
              type="text"
              class="flex-1 min-w-[8rem] border-0 bg-transparent text-sm focus:outline-none disabled:bg-transparent"
              :disabled="busy"
              placeholder="例如 cat"
              @keydown.enter.prevent="commitClassInput"
              @keydown="onClassInputKeydown"
              @blur="commitClassInput"
            />
          </div>
        </div>

        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">
            上传图片 
          </label>
          <div
            class="vt-dropzone"
            :class="[
              dragging ? 'vt-dropzone--active' : 'hover:border-[color:var(--vt-color-primary-border)]',
              busy ? 'pointer-events-none opacity-60' : 'cursor-pointer'
            ]"
            @click="!busy && fileInput && fileInput.click()"
            @dragover.prevent="dragging = true"
            @dragleave.prevent="dragging = false"
            @drop.prevent="onDrop"
          >
            <div v-if="!files.length" class="text-gray-500 text-sm">
              <div class="mb-2 flex justify-center">
                <AppIcon name="upload" class="h-7 w-7 text-slate-500" />
              </div>
              <div>点击选择或拖入图片 / 压缩包</div>
              <div class="text-xs text-gray-400 mt-1">
                支持单张图片、批量图片、.zip / .tar / .tar.gz / .tgz 压缩包
              </div>
            </div>
            <div v-else class="text-left text-sm space-y-1">
              <div
                v-for="(f, idx) in files"
                :key="idx"
                class="flex items-center justify-between gap-2"
              >
                <div class="truncate text-slate-700">
                  <AppIcon
                    :name="isSupportedArchiveFile(f.name) ? 'download' : 'image'"
                    class="h-4 w-4 text-slate-500 mr-1"
                  />
                  {{ f.name }}
                </div>
                <div class="text-xs text-gray-500 shrink-0">{{ formatSize(f.size) }}</div>
              </div>
              <div class="text-xs text-gray-500 pt-1 border-t border-slate-100">
                共 {{ files.length }} 个文件
              </div>
            </div>
            <input ref="fileInput" type="file" multiple class="hidden"
                   :accept="UPLOAD_FILE_ACCEPT"
                   @change="onPick" />
          </div>
        </div>

        <div v-if="busy || success || error" class="space-y-2">
          <div class="flex items-center justify-between text-xs">
            <div class="flex items-center gap-2">
              <span :class="phaseClass('creating')">① 建目录</span>
              <span class="text-gray-300">→</span>
              <span :class="phaseClass('uploading')">② 上传图片</span>
              <span class="text-gray-300">→</span>
              <span :class="phaseClass('snapshot')">③ 入库</span>
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
        </div>

        <div v-if="error" class="border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">
          {{ error }}
        </div>
      </div>

      <div class="vt-modal-footer flex justify-end gap-2">
        <button type="button"
                class="vt-btn-secondary vt-btn-size-md"
                :disabled="busy && !success && !error"
                @click="onCancel">
          {{ success ? '完成' : (error ? '关闭' : '取消') }}
        </button>
        <button v-if="!busy && !success && !error"
                type="button"
                :disabled="!canSubmit"
                class="vt-btn-solid-primary vt-btn-size-md"
                @click="onSubmit">
          <AppIcon name="plus" class="h-4 w-4" />
          创建数据集
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue';
import { useAsyncEmit } from '../composables/useAsyncEmit';
import { usePhaseProgress } from '../composables/usePhaseProgress';
import {
  CATEGORY_NAME_PATTERN,
  formatBytes,
  validateCategoryName,
  validateResourceName,
} from '../utils';
import { isSupportedArchiveFile, isSupportedUploadFile, UPLOAD_FILE_ACCEPT } from '../utils/media';
import { VISION_TASK_TYPE } from '../domain/dataset/visionTaskType';
import AppIcon from './ui/AppIcon.vue';

const props = defineProps({
  project: { type: Object, default: null },
});
const emit = defineEmits(['close', 'submit']);
const asyncEmit = useAsyncEmit(emit);

const fileInput = ref(null);
const classInput = ref(null);
const files = ref([]);
const datasetName = ref('');
const visionTaskType = ref(VISION_TASK_TYPE.DETECT);
const initialClasses = ref([]);
const newClassName = ref('');
const dragging = ref(false);
const progress = ref(0);
const phaseMessage = ref('');
const busy = ref(false);
const success = ref(false);
const error = ref('');
const nameError = ref('');

const isAcceptedFile = isSupportedUploadFile;

// 创建数据集的三段进度：建目录 → 上传图片 → 入库快照。
const { currentPhase, phaseClass, setPhase, markFail } = usePhaseProgress({
  phases: ['creating', 'uploading', 'snapshot'],
});

const formatSize = formatBytes;

const onPick = (e) => {
  const list = Array.from(e.target.files || []);
  addFiles(list);
  if (fileInput.value) fileInput.value.value = '';
};
const onDrop = (e) => {
  dragging.value = false;
  const list = Array.from(e.dataTransfer?.files || []);
  addFiles(list);
};
const addFiles = (list) => {
  error.value = '';
  const accepted = list.filter(isAcceptedFile);
  if (accepted.length === 0) {
    error.value = '未识别任何受支持的图片或压缩包文件';
    return;
  }
  files.value = [...files.value, ...accepted];
};

const focusClassInput = () => {
  classInput.value && classInput.value.focus();
};

const commitClassInput = () => {
  const raw = String(newClassName.value || '').trim();
  if (!raw) return;
  // 支持逗号 / 空格批量粘贴："cat, dog person"
  const tokens = raw.split(/[,\s]+/).map(t => t.trim()).filter(Boolean);
  for (const t of tokens) {
    if (!CATEGORY_NAME_PATTERN.test(t)) {
      error.value = `类别名「${t}」${validateCategoryName(t)}`;
      newClassName.value = raw.startsWith(t) ? raw.slice(t.length).replace(/^[,\s]+/, '') : '';
      return;
    }
    if (initialClasses.value.includes(t)) continue;
    initialClasses.value = [...initialClasses.value, t];
  }
  newClassName.value = '';
  error.value = '';
};

const removeInitialClass = (idx) => {
  initialClasses.value = initialClasses.value.filter((_, i) => i !== idx);
};

const onClassInputKeydown = (e) => {
  if (e.key === ',' || e.key === '，') {
    e.preventDefault();
    commitClassInput();
  } else if (e.key === 'Backspace' && !newClassName.value && initialClasses.value.length) {
    initialClasses.value = initialClasses.value.slice(0, -1);
  }
};

const canSubmit = computed(() => !validateResourceName(datasetName.value) && !!props.project);


const onCancel = () => {
  if (busy.value && !success.value && !error.value) return;
  emit('close');
};

const onSubmit = async () => {
  const err = validateResourceName(datasetName.value);
  nameError.value = err;
  if (err || !props.project) return;
  busy.value = true;
  success.value = false;
  error.value = '';
  progress.value = 0;
  phaseMessage.value = '准备创建…';
  setPhase('creating');

  try {
    await asyncEmit('submit', {
      datasetName: datasetName.value.trim(),
      visionTaskType: visionTaskType.value,
      initialClasses: initialClasses.value,
      files: files.value,
      projectPath: props.project.path || props.project.name,
      onProgress: (ev) => {
        if (typeof ev === 'number') {
          progress.value = ev;
        } else {
          if (typeof ev.progress === 'number') progress.value = ev.progress;
          if (ev.message) phaseMessage.value = ev.message;
          if (ev.phase) setPhase(ev.phase);
        }
      },
    });
    success.value = true;
    setPhase('done');
    progress.value = 100;
    phaseMessage.value = '创建完成';
    setTimeout(() => {
      if (success.value) emit('close');
    }, 800);
  } catch (e) {
    error.value = e?.message || '创建失败';
    markFail(currentPhase.value);
  } finally {
    busy.value = false;
  }
};
</script>