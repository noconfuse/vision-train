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
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">
            任务类型 <span class="text-rose-500">*</span>
          </label>
          <select v-model="visionTaskType" :disabled="uploading" class="vt-select">
            <option :value="VISION_TASK_TYPE.DETECT">检测</option>
            <option :value="VISION_TASK_TYPE.CLASSIFY">分类</option>
            <option :value="VISION_TASK_TYPE.SEGMENT">分割</option>
            <option :value="VISION_TASK_TYPE.POSE">姿态</option>
          </select>
          <div class="mt-2 rounded border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">
            <div class="mb-1 font-medium text-slate-700">支持规范</div>
            <div v-if="visionTaskType === VISION_TASK_TYPE.DETECT" class="flex flex-wrap gap-2">
              <UiTooltip
                v-for="spec in detectDatasetSpecs"
                :key="spec.key"
                side="bottom"
                align="start"
                :side-offset="10"
                :delay-duration="120"
                :disable-hoverable-content="false"
                :content-class="'!w-[26rem] !max-w-[26rem] !border-slate-200 !bg-white !p-0 !text-slate-900 shadow-xl'"
              >
                <template #trigger>
                  <button
                    type="button"
                    class="inline-flex items-center rounded border border-slate-200 bg-white px-2.5 py-1.5 text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-100"
                  >
                    {{ spec.label }}
                  </button>
                </template>
                <div class="p-3">
                  <div class="mb-2 text-xs font-medium text-slate-600">目录示例</div>
                  <pre class="overflow-x-auto rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-[12px] leading-6 text-slate-800">{{ spec.example }}</pre>
                </div>
              </UiTooltip>
            </div>
            <div v-else-if="visionTaskType === VISION_TASK_TYPE.CLASSIFY" class="flex flex-wrap gap-2">
              <UiTooltip
                v-for="spec in classifyDatasetSpecs"
                :key="spec.key"
                side="bottom"
                align="start"
                :side-offset="10"
                :delay-duration="120"
                :disable-hoverable-content="false"
                :content-class="'!w-[26rem] !max-w-[26rem] !border-slate-200 !bg-white !p-0 !text-slate-900 shadow-xl'"
              >
                <template #trigger>
                  <button
                    type="button"
                    class="inline-flex items-center rounded border border-slate-200 bg-white px-2.5 py-1.5 text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-100"
                  >
                    <code>{{ spec.label }}</code>
                  </button>
                </template>
                <div class="p-3">
                  <div class="mb-2 text-xs font-medium text-slate-600">目录示例</div>
                  <pre class="overflow-x-auto rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-[12px] leading-6 text-slate-800">{{ spec.example }}</pre>
                </div>
              </UiTooltip>
            </div>
            <div v-else-if="visionTaskType === VISION_TASK_TYPE.SEGMENT" class="flex flex-wrap gap-2">
              <UiTooltip
                v-for="spec in segmentDatasetSpecs"
                :key="spec.key"
                side="bottom"
                align="start"
                :side-offset="10"
                :delay-duration="120"
                :disable-hoverable-content="false"
                :content-class="'!w-[26rem] !max-w-[26rem] !border-slate-200 !bg-white !p-0 !text-slate-900 shadow-xl'"
              >
                <template #trigger>
                  <button
                    type="button"
                    class="inline-flex items-center rounded border border-slate-200 bg-white px-2.5 py-1.5 text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-100"
                  >
                    {{ spec.label }}
                  </button>
                </template>
                <div class="p-3">
                  <div class="mb-2 text-xs font-medium text-slate-600">目录示例</div>
                  <pre class="overflow-x-auto rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-[12px] leading-6 text-slate-800">{{ spec.example }}</pre>
                </div>
              </UiTooltip>
            </div>
            <div v-else class="flex flex-wrap gap-2">
              <UiTooltip
                v-for="spec in poseDatasetSpecs"
                :key="spec.key"
                side="bottom"
                align="start"
                :side-offset="10"
                :delay-duration="120"
                :disable-hoverable-content="false"
                :content-class="'!w-[26rem] !max-w-[26rem] !border-slate-200 !bg-white !p-0 !text-slate-900 shadow-xl'"
              >
                <template #trigger>
                  <button
                    type="button"
                    class="inline-flex items-center rounded border border-slate-200 bg-white px-2.5 py-1.5 text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-100"
                  >
                    {{ spec.label }}
                  </button>
                </template>
                <div class="p-3">
                  <div class="mb-2 text-xs font-medium text-slate-600">目录示例</div>
                  <pre class="overflow-x-auto rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-[12px] leading-6 text-slate-800">{{ spec.example }}</pre>
                </div>
              </UiTooltip>
            </div>
          </div>
        </div>

        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">
            数据集压缩包 <span class="text-rose-500">*</span>
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
              <div>点击选择文件 / 拖入压缩包</div>
              <div class="text-xs text-gray-400 mt-1">支持 {{ ARCHIVE_FILE_ACCEPT }}，最大 2 GB</div>
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
              <div class="text-xs text-gray-500">{{ formatBytes(file.size) }}</div>
            </div>
            <input ref="fileInput" type="file" :accept="ARCHIVE_FILE_ACCEPT" class="hidden"
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
            placeholder="留空则使用压缩包内的数据集名"
            class="vt-input"
          />
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
import { usePhaseProgress } from '../composables/usePhaseProgress';
import { formatBytes, validateResourceName } from '../utils';
import { ARCHIVE_FILE_ACCEPT, isSupportedArchiveFile } from '../utils/media';
import { VISION_TASK_TYPE } from '../domain/dataset/visionTaskType';
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
const visionTaskType = ref(VISION_TASK_TYPE.DETECT);
const progress = ref(0);
const phaseMessage = ref('');
const uploading = ref(false);
const success = ref(false);
const error = ref('');
const dragging = ref(false);

const { currentPhase, phaseClass, setPhase, markFail } = usePhaseProgress({
  phases: ['uploading', 'parsing', 'converting', 'saving'],
});

const detectDatasetSpecs = [
  {
    key: 'yolo',
    label: 'YOLO',
    example: `dataset/
  images/
    train/
    val/
  labels/
    train/
    val/
  dataset.yaml`,
  },
  {
    key: 'coco',
    label: 'COCO',
    example: `dataset/
  train2017/
  val2017/
  annotations/
    instances_train2017.json
    instances_val2017.json`,
  },
  {
    key: 'voc',
    label: 'Pascal VOC',
    example: `dataset/
  JPEGImages/
  Annotations/
  ImageSets/
    Main/`,
  },
  {
    key: 'roboflow',
    label: 'Roboflow',
    example: `dataset/
  train/
    images/
    labels/
  valid/
    images/
    labels/
  data.yaml`,
  },
];

const classifyDatasetSpecs = [
  {
    key: 'imagefolder',
    label: 'class/*',
    example: `dataset/
  cat/
    0001.jpg
    0002.jpg
  dog/
    0001.jpg
    0002.jpg`,
  },
  {
    key: 'split-imagefolder',
    label: 'train|val|test/class/*',
    example: `dataset/
  train/
    cat/
      0001.jpg
    dog/
      0001.jpg
  val/
    cat/
      0002.jpg
    dog/
      0002.jpg
  test/
    cat/
      0003.jpg
    dog/
      0003.jpg`,
  },
];

const segmentDatasetSpecs = [
  {
    key: 'yolo-segment',
    label: 'YOLO Segment',
    example: `dataset/
  images/
    train/
    val/
    test/
  labels/
    train/
    val/
    test/
  dataset.yaml

label line:
  <class> <x1> <y1> <x2> <y2> ... <xn> <yn>`,
  },
];

const poseDatasetSpecs = [
  {
    key: 'yolo-pose',
    label: 'YOLO Pose',
    example: `dataset/
  images/
    train/
    val/
    test/
  labels/
    train/
    val/
    test/
  dataset.yaml  

label line:
  <class> <cx> <cy> <w> <h> <px1> <py1> <v1> ... <pxn> <pyn> <vn>`,
  },
];



const onPick = (e) => {
  const f = e.target.files?.[0];
  if (f) {
    if (!isSupportedArchiveFile(f.name)) {
      error.value = '仅支持 .zip / .tar / .tar.gz / .tgz 文件';
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
    if (!isSupportedArchiveFile(f.name)) {
      error.value = '仅支持 .zip / .tar / .tar.gz / .tgz 文件';
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

  try {
    await asyncEmit('submit', {
      file: file.value,
      projectPath: props.project.path || props.project.name,
      targetName: targetName.value.trim() || undefined,
      visionTaskType: visionTaskType.value,
      onProgress: (ev) => {
        if (typeof ev === 'number') {
          progress.value = ev;
        } else {
          progress.value = ev.progress ?? progress.value;
          phaseMessage.value = ev.message || phaseMessage.value;
          if (ev.phase) setPhase(ev.phase);
        }
      },
    });
    success.value = true;
    setPhase('done');
    progress.value = 100;
    phaseMessage.value = '导入完成';
    setTimeout(() => {
      if (success.value) emit('close');
    }, 800);
  } catch (e) {
    error.value = e?.message || '导入失败';
    markFail(currentPhase.value);
  } finally {
    uploading.value = false;
  }
};
</script>
