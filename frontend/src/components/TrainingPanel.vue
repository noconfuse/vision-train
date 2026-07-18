<template>
  <div v-if="store.selectedDataset" class="bg-white border border-gray-200 p-4 text-slate-800 h-full overflow-y-auto">
    <div class="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_320px] gap-4 items-start">
      <div class="min-w-0">
        <div class="mb-5">
          <div class="flex justify-between items-center mb-2">
            <label class="text-sm font-medium text-gray-700">预训练模型</label>
            <div class="flex items-center gap-3 text-xs text-gray-500">
              <span class="flex items-center gap-1">
                <span class="vt-status-dot vt-status-dot--info"></span>
                官方预设 <span class="font-mono text-slate-600">{{ downloadedOptions.length }}/{{ presetOptions.length }}</span>
              </span>
              <span class="flex items-center gap-1">
                <span class="vt-status-dot vt-status-dot--warn"></span>
                训练历史 <span class="font-mono text-slate-600">{{ historyModels.length }}</span>
              </span>
            </div>
          </div>

          <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2.5 max-h-80 overflow-y-auto pr-1">
            <div
              v-if="allOptions.length === 0 && historyModels.length === 0"
              class="col-span-full text-center py-8 text-gray-400 text-sm border border-dashed border-gray-200"
            >
              暂无可用模型
            </div>

            <div
              v-for="opt in allOptions"
              :key="`opt-${opt.name}`"
              class="vt-choice-card relative p-2.5"
              :class="opt.is_downloaded
                ? (selectedModel === opt.name ? 'vt-choice-card--selected' : 'vt-choice-card--interactive')
                : (selectedModel === opt.name ? 'vt-choice-card--selected border-dashed' : 'vt-choice-card--interactive border-dashed border-gray-300')"
              @click="selectedModel = opt.name"
            >
              <span
                v-if="opt.is_downloaded"
                class="vt-tag vt-tag-info vt-tag--sm absolute top-1.5 right-1.5 gap-1"
              >
                <span class="vt-status-dot vt-status-dot--info h-1.5 w-1.5"></span>{{ opt.family }}
              </span>
              <UiTooltip
                v-else
                side="top"
                align="end"
                content-class="max-w-[20rem] break-words text-left"
              >
                <template #trigger>
                  <span class="absolute top-1.5 right-1.5 inline-flex items-center gap-1 border border-gray-300 bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-600">
                    <span>未下载</span>
                  </span>
                </template>
                首次训练时会自动从官方下载
              </UiTooltip>

              <UiTooltip
                side="bottom"
                align="start"
                content-class="max-w-[24rem] break-all text-left"
              >
                <template #trigger>
                  <div class="font-semibold text-sm truncate pr-16">{{ opt.name }}</div>
                </template>
                {{ opt.name }}
              </UiTooltip>
              <div v-if="getPretrainedMeta(opt)" class="text-[11px] text-gray-500 mt-1">{{ getPretrainedMeta(opt) }}</div>
            </div>

            <div
              v-for="model in historyModels"
              :key="`h-${model.path}`"
              class="vt-choice-card vt-choice-card--interactive relative p-2.5"
              :class="selectedModel === model.name ? 'vt-choice-card--selected' : ''"
              @click="selectedModel = model.name"
            >
              <span class="vt-tag vt-tag--sm absolute top-1.5 right-1.5 gap-1">
                <span class="vt-status-dot vt-status-dot--warn h-1.5 w-1.5"></span>历史
              </span>
              <div v-if="model.metrics && model.metrics.map50" class="text-[10px] font-mono text-emerald-700 mb-1">
                mAP50: {{ (model.metrics.map50 * 100).toFixed(1) }}%
              </div>
              <UiTooltip
                side="bottom"
                align="start"
                content-class="max-w-[24rem] break-all text-left"
              >
                <template #trigger>
                  <div class="font-semibold text-sm truncate pr-12">{{ model.name }}</div>
                </template>
                {{ model.name }}
              </UiTooltip>
              <div class="flex items-center gap-1.5 text-[11px] text-gray-500 mt-1">
                <span v-if="model.dataset" class="border border-gray-200 bg-slate-100 px-1">{{ model.dataset }}</span>
                <span>{{ (model.size / 1024 / 1024).toFixed(1) }} MB</span>
              </div>
            </div>
          </div>
        </div>

        <div class="mb-5">
          <div class="flex justify-between items-end mb-2">
            <h3 class="text-sm font-medium text-gray-700">基础参数</h3>
          </div>
          <div class="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 mb-3">
            <div v-for="field in basicFields" :key="field.key" :class="field.type === 'checkbox' ? 'flex items-end' : ''">
              <template v-if="field.type === 'checkbox'">
                <label class="vt-check-card vt-check-card--interactive w-full h-[34px] mt-auto items-center px-2 py-1.5">
                  <input type="checkbox" v-model="config[field.key]" class="vt-checkbox">
                  <span class="text-xs font-medium text-gray-700 select-none">{{ field.label }}</span>
                </label>
              </template>
              <template v-else>
                <label class="block text-xs font-medium text-gray-600 mb-1">{{ field.label }}</label>
                <input
                  type="number"
                  v-model="config[field.key]"
                  class="vt-input vt-control-md"
                  :placeholder="field.placeholder"
                >
              </template>
            </div>
          </div>

          <div class="vt-surface-info mb-3 p-3 transition-colors">
            <label class="flex items-center space-x-3 cursor-pointer">
              <input type="checkbox" v-model="config.imbalance_optimization" @change="onImbalanceChange" class="vt-checkbox h-5 w-5">
              <div class="flex-1">
                <div class="flex items-center gap-2">
                  <span class="font-semibold text-sm text-slate-800">针对不平衡数据集优化 (Class Imbalance Optimization)</span>
                  <span class="vt-badge-recommend">Recommended</span>
                </div>
                <p class="text-xs text-gray-600 mt-0.5">自动启用 Cosine LR，并调整 Mosaic, Mixup, Flip 等增强参数，提升小样本类别检测效果。</p>
              </div>
            </label>
          </div>

          <div class="border border-gray-200 overflow-hidden">
            <button @click="showAdvanced = !showAdvanced" class="w-full flex justify-between items-center p-2.5 hover:bg-gray-50 transition-colors text-sm font-medium text-gray-700">
              <span class="flex items-center gap-2">
                <AppIcon name="settings" class="h-4 w-4 text-gray-500" />
                高级增强参数 (Advanced Augmentation)
              </span>
              <AppIcon name="chevronDown" class="h-4 w-4 text-gray-400 transition-transform duration-200" :class="showAdvanced ? 'rotate-180' : ''" />
            </button>

            <div v-show="showAdvanced" class="p-3 border-t border-gray-200 grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-3 bg-gray-50">
              <div v-for="field in advancedFields" :key="field.key" :class="field.type === 'checkbox' ? 'flex items-end' : ''">
                <template v-if="field.type === 'checkbox'">
                  <label class="vt-check-card vt-check-card--interactive w-full h-[34px] mt-auto items-center px-2 py-1.5">
                    <input type="checkbox" v-model="config[field.key]" class="vt-checkbox">
                    <span class="text-xs font-medium text-gray-700 select-none">{{ field.label }}</span>
                  </label>
                </template>
                <template v-else>
                  <label class="block text-[10px] uppercase tracking-wider font-medium text-gray-500 mb-1">{{ field.label }}</label>
                  <input
                    type="number"
                    v-model="config[field.key]"
                    step="0.1"
                    class="vt-input vt-control-md"
                    :placeholder="field.placeholder"
                  >
                </template>
              </div>
            </div>
          </div>
        </div>

      </div>

      <aside class="space-y-4 xl:sticky xl:top-3">
        <div class="border border-gray-200 p-4 bg-slate-50/60">
          <div class="vt-step-section-title">环境与校准</div>
          <div class="text-xs text-gray-500 mb-4">训练环境会自动更新。批次校准只是辅助工具，不属于工作流主步骤。</div>

          <div class="mb-4">
            <div class="text-xs font-semibold text-slate-700 mb-3">当前训练环境</div>
            <div v-if="runtimeProfile" class="grid grid-cols-2 gap-3 text-sm">
              <div>
                <div class="text-xs text-gray-500">运行设备</div>
                <div class="font-semibold text-slate-800">{{ runtimeProfile.device?.label || '-' }}</div>
              </div>
              <div>
                <div class="text-xs text-gray-500">系统平台</div>
                <div class="font-semibold text-slate-800">
                  {{ runtimeProfile.platform?.system || '-' }}
                </div>
              </div>
              <div class="col-span-2">
                <div class="text-xs text-gray-500">CPU</div>
                <div class="text-slate-800 break-words">{{ runtimeProfile.cpu?.model || '-' }}</div>
              </div>
              <div>
                <div class="text-xs text-gray-500">逻辑核心</div>
                <div class="font-mono text-slate-800">{{ runtimeProfile.cpu?.logical_cores || '-' }}</div>
              </div>
              <div>
                <div class="text-xs text-gray-500">可用内存</div>
                <div class="font-mono text-slate-800">{{ formatBytes(runtimeProfile.memory?.available_bytes) }}</div>
              </div>
              <div>
                <div class="text-xs text-gray-500">总内存</div>
                <div class="font-mono text-slate-800">{{ formatBytes(runtimeProfile.memory?.total_bytes) }}</div>
              </div>
              <template v-if="runtimeProfile.gpu">
                <div class="col-span-2">
                  <div class="text-xs text-gray-500">GPU</div>
                  <div class="text-slate-800 break-words">{{ runtimeProfile.gpu?.name || '-' }}</div>
                </div>
                <div>
                  <div class="text-xs text-gray-500">可用显存</div>
                  <div class="font-mono text-slate-800">{{ formatBytes(runtimeProfile.gpu?.free_memory_bytes) }}</div>
                </div>
              </template>
            </div>
            <div v-else class="text-sm text-gray-400">正在加载训练运行环境...</div>
          </div>

          <div class="border-t border-gray-200 pt-4">
            <div class="flex items-center justify-between gap-3 mb-3">
              <div>
                <div class="text-xs font-semibold text-slate-700">批次校准</div>
                <div class="text-[11px] text-gray-500 mt-1">用当前模型、图像尺寸和设备做一次短时试跑，确认可启动批次范围。</div>
              </div>
              <button
                class="vt-btn-secondary text-xs"
                :disabled="!canCalibrate"
                @click="startBatchCalibration(shouldForceCalibration)"
              >
                {{ calibrationButtonLabel }}
              </button>
            </div>
            <div class="space-y-2 text-sm">
              <div class="grid grid-cols-2 gap-3">
                <div>
                  <div class="text-xs text-gray-500">当前模型</div>
                  <div class="font-mono text-slate-800 break-all">{{ displayedCalibrationModel }}</div>
                </div>
                <div>
                  <div class="text-xs text-gray-500">当前图像尺寸</div>
                  <div class="font-mono text-slate-800">{{ displayedCalibrationImgsz }}</div>
                </div>
                <div>
                  <div class="text-xs text-gray-500">运行设备</div>
                  <div class="font-mono text-slate-800">{{ runtimeProfile?.device?.label || '-' }}</div>
                </div>
                <div>
                  <div class="text-xs text-gray-500">校准状态</div>
                  <span
                    v-if="batchCalibration"
                    class="vt-tag"
                    :class="getTaskStatusTagClass(batchCalibration.status)"
                  >
                    {{ getTaskStatusLabel(batchCalibration.status) }}
                  </span>
                  <div v-else class="font-mono text-slate-800">未校准</div>
                </div>
              </div>
              <div v-if="batchCalibration" class="text-xs text-slate-600 whitespace-pre-wrap break-all">
                {{ batchCalibration.message || '批次校准任务已创建。' }}
              </div>
              <div
                v-if="isTaskActive(batchCalibration) && batchCalibrationMatchesSelection === false"
                class="text-xs text-slate-500"
              >
                当前显示的是这个数据集正在进行的校准任务。
              </div>
              <div v-if="batchCalibrationResult?.max_batch" class="grid grid-cols-2 gap-3">
                <div>
                  <div class="text-xs text-gray-500">实测可启动上限</div>
                  <div class="font-mono text-slate-800">{{ batchCalibrationResult.max_batch }}</div>
                </div>
                <div>
                  <div class="text-xs text-gray-500">尝试次数</div>
                  <div class="font-mono text-slate-800">{{ batchCalibrationResult.attempt_count || '-' }}</div>
                </div>
                <div class="col-span-2">
                  <div class="text-xs text-gray-500">最近校准时间</div>
                  <div class="font-mono text-slate-800 break-all">{{ batchCalibrationResult.measured_at || '-' }}</div>
                </div>
              </div>
              <div
                v-if="batchCalibrationResult?.attempts?.length"
                class="vt-surface-info p-2 text-xs text-slate-700 space-y-1"
              >
                <div class="font-medium text-slate-800">最近试跑记录</div>
                <div
                  v-for="attempt in batchCalibrationResult.attempts.slice().reverse().slice(0, 4)"
                  :key="`${attempt.batch}-${attempt.duration_ms}-${attempt.exit_code}`"
                  class="font-mono"
                >
                  batch={{ attempt.batch }} · {{ attempt.ok ? '通过' : '失败' }} · {{ attempt.duration_ms }}ms
                </div>
              </div>
              <div v-if="!batchCalibration" class="text-sm text-gray-500">
                选择模型后可开始校准。
              </div>
              <div v-else-if="batchCalibrationResult?.max_batch" class="text-xs text-slate-600">
                该结果表示当前环境下的实测可启动上限。
              </div>
              <div v-else-if="!isTaskActive(batchCalibration)" class="text-xs text-slate-600">
                本次校准未得到可用结果，请检查错误信息后重试。
              </div>
              <div v-if="isTaskActive(batchCalibration)" class="space-y-2">
                <div class="flex items-center gap-2">
                  <div class="vt-meter flex-1" :style="{ background: 'var(--vt-color-primary-soft)' }">
                    <div
                      class="vt-meter__bar vt-meter__bar--info"
                      :style="{ width: `${batchCalibration.progress || 0}%` }"
                    ></div>
                  </div>
                  <span class="text-[10px] font-mono text-slate-500 w-9 text-right">
                    {{ batchCalibration.progress || 0 }}%
                  </span>
                </div>
                <div class="text-xs text-slate-500">可在任务中心查看详情。</div>
              </div>
            </div>
          </div>
        </div>
      </aside>
    </div>
    <div class="mt-4 flex flex-wrap justify-end gap-2">
      <button
        v-if="isRunning"
        @click="emit('show-task-detail')"
        class="vt-btn-secondary vt-btn-size-lg"
      >
        <AppIcon name="detail" class="h-4 w-4" />
        去任务详情
      </button>
      <button
        @click="startTraining"
        class="vt-btn-solid-primary vt-btn-size-lg"
        :disabled="!isValid || trainingSubmitting"
      >
        <span v-if="trainingSubmitting" class="inline-block w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin mr-1 align-[-2px]"></span>
        <AppIcon v-else name="train" class="h-4 w-4" />
        {{ trainingSubmitting ? '启动中...' : '开始训练' }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { useMainStore } from '../stores/main';
import { useTrainingStore } from '../stores/training';
import { useTrainingWorkflowStore } from '../stores/trainingWorkflow';
import { useApiCall } from '../composables/useApiCall';
import AppIcon from './ui/AppIcon.vue';
import UiTooltip from './ui/Tooltip.vue';
import { getTaskStatusLabel, getTaskStatusTagClass, isTaskActive, isTaskCompleted } from '../taskStatus';
import { formatBytes } from '../utils';

const props = defineProps({
  workflowId: { type: String, default: '' },
});

const emit = defineEmits(['training-started', 'show-task-detail', 'workflow-bound']);

const store = useMainStore();
const trainingStore = useTrainingStore();
const workflowStore = useTrainingWorkflowStore();
const apiCall = useApiCall();

const currentTask = computed(() => trainingStore.currentTask);
const isRunning = computed(() => isTaskActive(currentTask.value));
const runtimeProfile = computed(() => trainingStore.runtimeProfile);
const batchCalibration = computed(() => trainingStore.batchCalibration);
const batchCalibrationResult = computed(() => batchCalibration.value?.artifacts?.calibration_result || null);
const calibrationPayload = computed(() => batchCalibration.value?.payload || {});
const selectedModelEntry = computed(() => allModels.value.find((item) => item.name === selectedModel.value) || null);

const selectedModel = ref('');
const showAdvanced = ref(false);
const trainingSubmitting = ref(false);
let calibrationTimer = null;

const presetOptions = computed(() => store.pretrainedOptions || []);
const downloadedOptions = computed(() => presetOptions.value.filter((o) => o.is_downloaded));
const allOptions = computed(() => presetOptions.value);
const historyModels = computed(() => (
  store.pretrainedModels
    .filter((m) => m.type === 'trained')
    .sort((a, b) => {
      if (a.created_at && b.created_at) {
        return new Date(b.created_at) - new Date(a.created_at);
      }
      return 0;
    })
));
const allModels = computed(() => [
  ...downloadedOptions.value.map((o) => ({ name: o.name, type: 'pretrained', path: o.local_path, size: o.size_bytes })),
  ...historyModels.value,
]);

const TRAINING_DEFAULTS = {
  epochs: 100,
  batch: 16,
  imgsz: 640,
  freeze: 0,
  lr0: 0.01,
};

const config = reactive({
  epochs: TRAINING_DEFAULTS.epochs,
  batch: TRAINING_DEFAULTS.batch,
  imgsz: TRAINING_DEFAULTS.imgsz,
  freeze: TRAINING_DEFAULTS.freeze,
  lr0: TRAINING_DEFAULTS.lr0,
  rect: false,
  imbalance_optimization: false,
  mosaic: '',
  mixup: '',
  copy_paste: '',
  degrees: '',
  translate: '',
  scale: '',
  shear: '',
  perspective: '',
  flipud: '',
  fliplr: '',
  hsv_h: '',
  hsv_s: '',
  hsv_v: '',
  close_mosaic: '',
  cos_lr: false,
});

const basicFields = [
  { key: 'epochs', label: '轮数(Epochs)', placeholder: String(TRAINING_DEFAULTS.epochs) },
  { key: 'batch', label: '批次(Batch)', placeholder: String(TRAINING_DEFAULTS.batch) },
  { key: 'imgsz', label: '图像尺寸', placeholder: String(TRAINING_DEFAULTS.imgsz) },
  { key: 'freeze', label: '冻结层数', placeholder: String(TRAINING_DEFAULTS.freeze) },
  { key: 'lr0', label: '初始学习率', placeholder: String(TRAINING_DEFAULTS.lr0) },
  { key: 'rect', label: '矩形训练', type: 'checkbox' },
];

const advancedFields = [
  { key: 'mosaic', label: 'Mosaic (马赛克)', placeholder: '1.0' },
  { key: 'mixup', label: 'Mixup (混合)', placeholder: '0.15' },
  { key: 'copy_paste', label: 'CopyPaste', placeholder: '0.0' },
  { key: 'degrees', label: '旋转角度 (°)', placeholder: '0.0' },
  { key: 'translate', label: '平移 (Translate)', placeholder: '0.1' },
  { key: 'scale', label: '缩放 (Scale)', placeholder: '0.5' },
  { key: 'shear', label: '剪切 (Shear)', placeholder: '0.0' },
  { key: 'flipud', label: '上下翻转', placeholder: '0.0' },
  { key: 'fliplr', label: '左右翻转', placeholder: '0.5' },
  { key: 'hsv_h', label: 'HSV-Hue', placeholder: '0.015' },
  { key: 'hsv_s', label: 'HSV-Saturation', placeholder: '0.7' },
  { key: 'hsv_v', label: 'HSV-Value', placeholder: '0.4' },
  { key: 'close_mosaic', label: '关闭 Mosaic (最后N轮)', placeholder: '10' },
  { key: 'cos_lr', label: 'Cosine LR', type: 'checkbox' },
];

const isValid = computed(() => Boolean(store.selectedDataset && selectedModel.value));
const parsedImgsz = computed(() => parseInt(config.imgsz, 10) || TRAINING_DEFAULTS.imgsz);
const displayedCalibrationModel = computed(() => calibrationPayload.value.model_name || selectedModel.value || '-');
const displayedCalibrationImgsz = computed(() => calibrationPayload.value.imgsz || parsedImgsz.value || '-');
const batchCalibrationMatchesSelection = computed(() => (
  Boolean(selectedModel.value) &&
  calibrationPayload.value.model_name === selectedModel.value &&
  Number(calibrationPayload.value.imgsz || TRAINING_DEFAULTS.imgsz) === Number(parsedImgsz.value || TRAINING_DEFAULTS.imgsz)
));
const canCalibrate = computed(() => Boolean(
  store.currentProject?.path &&
  store.selectedDataset?.name &&
  selectedModel.value
));
const shouldForceCalibration = computed(() => isTaskCompleted(batchCalibration.value));
const calibrationButtonLabel = computed(() => {
  if (!canCalibrate.value) return '开始校准';
  if (isTaskActive(batchCalibration.value)) return '校准中...';
  return shouldForceCalibration.value ? '重新校准' : '开始校准';
});

const getPretrainedMeta = (opt) => {
  const parts = [];
  if (typeof opt?.size === 'string' && opt.size.trim()) {
    parts.push(opt.size.trim());
  }
  const bytesText = formatBytes(opt?.size_bytes);
  if (opt?.is_downloaded && bytesText !== '-') {
    parts.push(bytesText);
  }
  return parts.join(' · ');
};

const onImbalanceChange = () => {
  if (config.imbalance_optimization) {
    config.cos_lr = true;
    if (!config.mosaic) config.mosaic = 1.0;
    if (!config.mixup) config.mixup = 0.15;
    if (!config.fliplr) config.fliplr = 0.5;
    if (!config.degrees) config.degrees = 10.0;
  }
};

const buildTrainingConfig = () => ({
  epochs: parseInt(config.epochs, 10) || null,
  batch: parseInt(config.batch, 10) || null,
  imgsz: parseInt(config.imgsz, 10) || null,
  freeze: config.freeze,
  lr0: parseFloat(config.lr0) || null,
  rect: config.rect || false,
  imbalance_optimization: config.imbalance_optimization || false,
  mosaic: parseFloat(config.mosaic) || null,
  mixup: parseFloat(config.mixup) || null,
  copy_paste: parseFloat(config.copy_paste) || null,
  degrees: parseFloat(config.degrees) || null,
  translate: parseFloat(config.translate) || null,
  scale: parseFloat(config.scale) || null,
  shear: parseFloat(config.shear) || null,
  perspective: parseFloat(config.perspective) || null,
  flipud: parseFloat(config.flipud) || null,
  fliplr: parseFloat(config.fliplr) || null,
  hsv_h: parseFloat(config.hsv_h) || null,
  hsv_s: parseFloat(config.hsv_s) || null,
  hsv_v: parseFloat(config.hsv_v) || null,
  close_mosaic: parseInt(config.close_mosaic, 10) || null,
  cos_lr: config.cos_lr || false,
});

const clearCalibrationTimer = () => {
  if (calibrationTimer) {
    clearTimeout(calibrationTimer);
    calibrationTimer = null;
  }
};

const refreshBatchCalibration = async () => {
  if (!canCalibrate.value) {
    trainingStore.batchCalibration = null;
    return;
  }
  const task = await trainingStore.fetchTrainingBatchCalibration({
    project_path: store.currentProject.path,
    dataset_name: store.selectedDataset.name,
    model_name: selectedModel.value,
    imgsz: parsedImgsz.value,
  });
  if (isTaskActive(task)) {
    clearCalibrationTimer();
    calibrationTimer = setTimeout(() => {
      refreshBatchCalibration().catch(() => {});
    }, 1500);
  } else {
    clearCalibrationTimer();
  }
};

const startBatchCalibration = async (force = false) => {
  if (!canCalibrate.value || isTaskActive(batchCalibration.value)) return;
  const selectedHistoryModelPath = selectedModelEntry.value?.type === 'trained' ? selectedModelEntry.value?.path : undefined;
  const data = await apiCall(trainingStore.startTrainingBatchCalibration({
    project_path: store.currentProject.path,
    dataset_name: store.selectedDataset.name,
    dataset_path: store.selectedDataset.path,
    model_name: selectedModel.value,
    model_path: selectedHistoryModelPath,
    imgsz: parsedImgsz.value,
    force,
    workflow_id: props.workflowId || undefined,
  }), {
    errorMsg: '启动批次校准失败',
  });
  if (data?.workflow_id) emit('workflow-bound', data.workflow_id);
  if (data?.task_id) {
    await refreshBatchCalibration();
  }
};

const startTraining = async () => {
  if (!isValid.value || trainingSubmitting.value) return;
  trainingSubmitting.value = true;
  let workflowId = props.workflowId || '';
  try {
    if (!workflowId) {
      const workflow = await apiCall(workflowStore.createWorkflow({
        project_path: store.currentProject.path,
        dataset_name: store.selectedDataset.name,
        dataset_path: store.selectedDataset.path,
      }), {
        errorMsg: '创建工作流失败',
      });
      workflowId = workflow?.id || '';
      if (!workflowId) return;
      emit('workflow-bound', workflowId);
    }

    const payload = {
      project_path: store.currentProject.path,
      dataset_name: store.selectedDataset.name,
      dataset_path: store.selectedDataset.path,
      model_name: selectedModel.value,
      model_path: selectedModelEntry.value?.type === 'trained' ? selectedModelEntry.value?.path : undefined,
      training_config: buildTrainingConfig(),
      workflow_id: workflowId,
    };

    await apiCall(trainingStore.startTraining(payload), {
      errorMsg: '启动训练失败',
      onSuccess: (data) => {
        if (data?.workflow_id) emit('workflow-bound', data.workflow_id);
        if (data?.task_id) emit('training-started', data);
      },
    });
  } finally {
    trainingSubmitting.value = false;
  }
};

onMounted(() => {
  if (!store.pretrainedModels.length) {
    store.fetchModels().catch(() => {});
  }
  if (!store.pretrainedOptions.length) {
    store.fetchPretrainedOptions().catch(() => {});
  }
  if (!trainingStore.runtimeProfile) {
    trainingStore.fetchTrainingRuntimeProfile().catch(() => {});
  }
  refreshBatchCalibration().catch(() => {});
});

watch(() => store.selectedDataset?.path, () => {
  if (selectedModel.value && !allModels.value.find((m) => m.name === selectedModel.value)) {
    selectedModel.value = '';
  }
  refreshBatchCalibration().catch(() => {});
});

watch([() => store.selectedDataset?.path, allModels], () => {
  if (!selectedModel.value && allModels.value.length > 0) {
    selectedModel.value = allModels.value[0].name;
  }
}, { immediate: true });

watch(batchCalibration, (task) => {
  const taskModelName = task?.payload?.model_name;
  if (!taskModelName || selectedModel.value) return;
  selectedModel.value = taskModelName;
});

watch([selectedModel, () => config.imgsz], () => {
  refreshBatchCalibration().catch(() => {});
}, { immediate: true });

onBeforeUnmount(() => {
  clearCalibrationTimer();
});
</script>
