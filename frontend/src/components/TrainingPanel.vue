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
              :class="[
                opt.is_downloaded
                  ? (selectedModel === opt.name ? 'vt-choice-card--selected' : 'vt-choice-card--interactive')
                  : (selectedModel === opt.name ? 'vt-choice-card--selected border-dashed' : 'vt-choice-card--interactive border-dashed border-gray-300'),
                isModelSelectionLocked ? 'pointer-events-none opacity-60' : '',
              ]"
              @click="selectModel(opt.name)"
            >
              <span
                v-if="opt.is_downloaded"
                class="vt-tag vt-tag-info vt-tag--sm absolute top-1.5 right-1.5 gap-1"
              >
                <span class="vt-status-dot vt-status-dot--info h-1.5 w-1.5"></span>{{ opt.family }}
              </span>
              <button
                v-else
                type="button"
                class="absolute top-1.5 right-1.5 inline-flex h-9 w-9 items-center justify-center transition-colors"
                :class="[
                  isPretrainedDownloading(opt)
                    ? 'cursor-wait'
                    : (isPretrainedFailed(opt)
                      ? 'text-rose-600 hover:text-rose-700'
                      : 'text-slate-500 hover:text-slate-700'),
                ]"
                :disabled="!canStartPretrainedDownload(opt)"
                @click.stop="startPretrainedDownload(opt)"
              >
                <span
                  v-if="isPretrainedDownloading(opt)"
                  class="relative inline-flex h-8 w-8 items-center justify-center rounded-full"
                  :style="getPretrainedProgressRingStyle(opt)"
                >
                  <span class="absolute inset-[3px] rounded-full bg-white"></span>
                  <span class="relative z-10 text-[9px] font-semibold leading-none text-sky-700">
                    {{ getPretrainedProgressLabel(opt) }}
                  </span>
                </span>
                <AppIcon v-else name="download" class="h-4 w-4" />
              </button>

              <UiTooltip
                side="bottom"
                align="start"
                content-class="max-w-[24rem] break-all text-left"
              >
                <template #trigger>
                  <div class="font-semibold text-sm truncate pr-12">{{ opt.name }}</div>
                </template>
                {{ opt.name }}
              </UiTooltip>
              <div v-if="getPretrainedMeta(opt)" class="text-[11px] text-gray-500 mt-1">{{ getPretrainedMeta(opt) }}</div>
            </div>

            <div
              v-for="model in historyModels"
              :key="`h-${model.path}`"
              class="vt-choice-card vt-choice-card--interactive relative p-2.5"
              :class="[selectedModel === model.name ? 'vt-choice-card--selected' : '', isModelSelectionLocked ? 'pointer-events-none opacity-60' : '']"
              @click="selectModel(model.name)"
            >
              <span class="vt-tag vt-tag--sm absolute top-1.5 right-1.5 gap-1">
                <span class="vt-status-dot vt-status-dot--warn h-1.5 w-1.5"></span>历史
              </span>
              <div v-if="getHistoryMetricText(model)" class="text-[10px] font-mono text-emerald-700 mb-1">
                {{ getHistoryMetricText(model) }}
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

          <div v-if="advancedFields.length" class="border border-gray-200 overflow-hidden">
            <button @click="showAdvanced = !showAdvanced" class="w-full flex justify-between items-center p-2.5 hover:bg-gray-50 transition-colors text-sm font-medium text-gray-700">
              <span class="flex items-center gap-2">
                <AppIcon name="settings" class="h-4 w-4 text-gray-500" />
                高级增强参数
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
          <div class="vt-step-section-title">{{ trainingProfile.supports_batch_calibration ? '环境与校准' : '训练环境' }}</div>
          <div class="text-xs text-gray-500 mb-4">{{ trainingProfile.environment_hint }}</div>

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

          <div v-if="trainingProfile.supports_batch_calibration" class="border-t border-gray-200 pt-4">
            <div class="flex items-center justify-between gap-3 mb-3">
              <div>
                <div class="text-xs font-semibold text-slate-700">批次校准</div>
                <div class="text-[11px] text-gray-500 mt-1">用当前模型、图像尺寸和设备做一次短时试跑，确认可启动批次范围。</div>
              </div>
              <AsyncButton
                class="vt-btn-secondary text-xs"
                :disabled="!canCalibrate || selectedPresetNeedsPreparation || isTaskActive(batchCalibration)"
                :pending="isActionPending(CALIBRATION_ACTION_KEY) || isTaskActive(batchCalibration)"
                :loading-text="calibrationButtonLabel"
                @click="startBatchCalibration(shouldForceCalibration)"
              >
                {{ calibrationIdleButtonLabel }}
              </AsyncButton>
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
                {{ trainingProfile.empty_calibration_hint }}
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
      <AsyncButton
        @click="startTraining"
        class="vt-btn-solid-primary vt-btn-size-lg"
        :disabled="!isValid || selectedPresetNeedsPreparation"
        :pending="isActionPending(TRAINING_ACTION_KEY)"
        :loading-text="trainingButtonLabel"
      >
        <AppIcon name="train" class="h-4 w-4" />
        {{ trainingIdleButtonLabel }}
      </AsyncButton>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { useMainStore } from '../stores/main';
import { useTrainingStore } from '../stores/training';
import { useTrainingWorkflowStore } from '../stores/trainingWorkflow';
import { useApiCall } from '../composables/useApiCall';
import { useAsyncAction } from '../composables/useAsyncAction';
import { useDatasetCapabilities } from '../composables/useDatasetCapabilities';
import AppIcon from './ui/AppIcon.vue';
import AsyncButton from './ui/AsyncButton.vue';
import UiTooltip from './ui/Tooltip.vue';
import { getTaskStatusLabel, getTaskStatusTagClass, isTaskActive, isTaskCompleted } from '../taskStatus';
import { formatBytes } from '../utils';
import { resolveBatchCalibrationGuard, resolveTrainingModelGuard, resolveTrainingStartGuard } from '../trainingActionGuards';

const props = defineProps({
  workflowId: { type: String, default: '' },
});

const emit = defineEmits(['training-started', 'show-task-detail', 'workflow-bound']);

const store = useMainStore();
const trainingStore = useTrainingStore();
const workflowStore = useTrainingWorkflowStore();
const apiCall = useApiCall();
const asyncAction = useAsyncAction();

const currentTask = computed(() => trainingStore.currentTask);
const isRunning = computed(() => isTaskActive(currentTask.value));
const runtimeProfile = computed(() => trainingStore.runtimeProfile);
const batchCalibration = computed(() => trainingStore.batchCalibration);
const batchCalibrationResult = computed(() => batchCalibration.value?.artifacts?.calibration_result || null);
const calibrationPayload = computed(() => batchCalibration.value?.payload || {});
const selectedModelEntry = computed(() => allModels.value.find((item) => item.name === selectedModel.value) || null);
const selectedPresetOption = computed(() => presetOptions.value.find((item) => item.name === selectedModel.value) || null);
const {
  datasetCapabilities,
  trainingMode,
} = useDatasetCapabilities(computed(() => store.selectedDataset || null));
const trainingProfile = computed(() => datasetCapabilities.value.training_profile);
const trainingGuard = computed(() => resolveTrainingStartGuard({
  dataset: store.selectedDataset,
  model: selectedModelEntry.value || selectedPresetOption.value,
  requiresDownload: selectedPresetNeedsPreparation.value,
}));

const selectedModel = ref('');
const showAdvanced = ref(false);
let calibrationTimer = null;
const CALIBRATION_ACTION_KEY = 'training-panel:start-batch-calibration';
const TRAINING_ACTION_KEY = 'training-panel:start-training';
const isActionPending = (key) => asyncAction.isPending(key);
const isModelSelectionLocked = computed(() => (
  isActionPending(TRAINING_ACTION_KEY) || isActionPending(CALIBRATION_ACTION_KEY)
));

const presetOptions = computed(() => store.pretrainedOptions || []);
const downloadedOptions = computed(() => presetOptions.value.filter((o) => o.is_downloaded));
const allOptions = computed(() => presetOptions.value);
const historyModels = computed(() => (
  store.pretrainedModels
    .filter((m) => isModelOperationSupportedForTraining(m))
    .filter((m) => m.type === 'trained')
    .sort((a, b) => {
      if (a.created_at && b.created_at) {
        return new Date(b.created_at) - new Date(a.created_at);
      }
      return 0;
    })
));
const allModels = computed(() => [
  ...downloadedOptions.value
    .filter((o) => isModelOperationSupportedForTraining(o))
    .map((o) => ({ name: o.name, type: 'pretrained', path: o.local_path, size: o.size_bytes, capabilities: o.capabilities })),
  ...historyModels.value,
]);

const BASE_TRAINING_DEFAULTS = {
  epochs: 100,
  batch: 16,
  imgsz: 640,
  freeze: 0,
  lr0: 0.01,
  rect: false,
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
};

const trainingConfigDefaults = computed(() => ({
  ...BASE_TRAINING_DEFAULTS,
  ...(trainingProfile.value.default_config || {}),
}));

const config = reactive({
  ...BASE_TRAINING_DEFAULTS,
});

const basicFields = computed(() => trainingProfile.value.basic_fields || []);
const advancedFields = computed(() => trainingProfile.value.advanced_fields || []);

const isValid = computed(() => trainingGuard.value.enabled);
const parsedImgsz = computed(() => parseInt(config.imgsz, 10) || trainingConfigDefaults.value.imgsz);
const displayedCalibrationModel = computed(() => calibrationPayload.value.model_name || selectedModel.value || '-');
const displayedCalibrationImgsz = computed(() => calibrationPayload.value.imgsz || parsedImgsz.value || '-');
const batchCalibrationMatchesSelection = computed(() => (
  Boolean(selectedModel.value) &&
  calibrationPayload.value.model_name === selectedModel.value &&
  Number(calibrationPayload.value.imgsz || trainingConfigDefaults.value.imgsz) === Number(parsedImgsz.value || trainingConfigDefaults.value.imgsz)
));
const calibrationGuard = computed(() => resolveBatchCalibrationGuard({
  dataset: store.selectedDataset,
  model: selectedModelEntry.value || selectedPresetOption.value,
  supportsBatchCalibration: trainingProfile.value.supports_batch_calibration,
  requiresDownload: selectedPresetNeedsPreparation.value,
  isRunning: isTaskActive(batchCalibration.value),
  hasContext: Boolean(
    store.currentProject?.path
    && store.selectedDataset?.name
    && selectedModel.value
  ),
}));
const canCalibrate = computed(() => calibrationGuard.value.enabled);
const selectedPresetNeedsPreparation = computed(() => Boolean(
  selectedPresetOption.value && !selectedPresetOption.value.is_downloaded
));
const shouldForceCalibration = computed(() => isTaskCompleted(batchCalibration.value));
const calibrationIdleButtonLabel = computed(() => {
  if (selectedPresetNeedsPreparation.value) return '请先下载';
  return shouldForceCalibration.value ? '重新校准' : '开始校准';
});
const calibrationButtonLabel = computed(() => {
  if (isActionPending(CALIBRATION_ACTION_KEY)) {
    return '校准中...';
  }
  if (isTaskActive(batchCalibration.value)) return '校准中...';
  return calibrationIdleButtonLabel.value;
});
const trainingIdleButtonLabel = computed(() => (
  selectedPresetNeedsPreparation.value ? '请先下载' : '开始训练'
));
const trainingButtonLabel = computed(() => (
  '启动中...'
));

const selectModel = (name) => {
  if (isModelSelectionLocked.value) return;
  selectedModel.value = name;
};

const isPretrainedDownloading = (opt) => Boolean(opt && !opt.is_downloaded && opt.download_state === 'downloading');
const isPretrainedFailed = (opt) => Boolean(opt && !opt.is_downloaded && opt.download_state === 'failed');
const canStartPretrainedDownload = (opt) => Boolean(
  opt
  && !opt.is_downloaded
  && !isPretrainedDownloading(opt)
);

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

const getPretrainedProgressValue = (opt) => {
  const progress = Number(opt?.download_progress || 0);
  if (!Number.isFinite(progress)) return 0;
  return Math.max(0, Math.min(100, Math.round(progress)));
};

const getPretrainedProgressLabel = (opt) => `${getPretrainedProgressValue(opt)}%`;

const getPretrainedProgressRingStyle = (opt) => {
  const progress = getPretrainedProgressValue(opt);
  return {
    background: `conic-gradient(rgb(14 165 233) ${progress}%, rgb(186 230 253) ${progress}% 100%)`,
  };
};

const getHistoryMetricText = (model) => {
  if (!model?.metrics) return '';
  const metric = trainingProfile.value.history_metric || {};
  const value = model.metrics?.[metric.key];
  if (typeof value === 'number' && metric.label) {
    if (metric.format === 'percent') {
      return `${metric.label}: ${(value * 100).toFixed(1)}%`;
    }
    return `${metric.label}: ${value}`;
  }
  return '';
};

const FIELD_BUILDERS = {
  epochs: (value) => parseInt(value, 10) || null,
  batch: (value) => parseInt(value, 10) || null,
  imgsz: (value) => parseInt(value, 10) || null,
  freeze: (value) => value,
  lr0: (value) => parseFloat(value) || null,
  rect: (value) => !!value,
  mosaic: (value) => parseFloat(value) || null,
  mixup: (value) => parseFloat(value) || null,
  copy_paste: (value) => parseFloat(value) || null,
  degrees: (value) => parseFloat(value) || null,
  translate: (value) => parseFloat(value) || null,
  scale: (value) => parseFloat(value) || null,
  shear: (value) => parseFloat(value) || null,
  perspective: (value) => parseFloat(value) || null,
  flipud: (value) => parseFloat(value) || null,
  fliplr: (value) => parseFloat(value) || null,
  hsv_h: (value) => parseFloat(value) || null,
  hsv_s: (value) => parseFloat(value) || null,
  hsv_v: (value) => parseFloat(value) || null,
  close_mosaic: (value) => parseInt(value, 10) || null,
  cos_lr: (value) => !!value,
};

const buildTrainingConfig = () => {
  const keys = [
    ...basicFields.value.map((field) => field.key),
    ...advancedFields.value.map((field) => field.key),
  ];
  const uniqueKeys = [...new Set(keys)];
  const next = {};
  uniqueKeys.forEach((key) => {
    const builder = FIELD_BUILDERS[key];
    if (!builder) return;
    next[key] = builder(config[key]);
  });
  return next;
};

const startPretrainedDownload = async (opt) => {
  if (!canStartPretrainedDownload(opt)) return;
  if (opt?.name) {
    selectedModel.value = opt.name;
  }
  await apiCall(
    store.preparePretrainedModel(opt.name, store.selectedDataset?.vision_task_type),
    { errorMsg: '模型下载失败' },
  );
};

const syncConfigWithProfile = () => {
  Object.assign(config, {
    ...BASE_TRAINING_DEFAULTS,
    ...trainingConfigDefaults.value,
  });
  showAdvanced.value = false;
};

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
  if (!canCalibrate.value || selectedPresetNeedsPreparation.value || isTaskActive(batchCalibration.value)) return;
  await asyncAction.run(CALIBRATION_ACTION_KEY, async () => {
    const modelName = selectedModel.value;
    const selectedHistoryModelPath = selectedModelEntry.value?.type === 'trained' ? selectedModelEntry.value?.path : undefined;
    const data = await apiCall(trainingStore.startTrainingBatchCalibration({
      project_path: store.currentProject.path,
      dataset_name: store.selectedDataset.name,
      dataset_path: store.selectedDataset.path,
      vision_task_type: store.selectedDataset.vision_task_type,
      model_name: modelName,
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
  });
};

const startTraining = async () => {
  if (!isValid.value || selectedPresetNeedsPreparation.value) return;
  await asyncAction.run(TRAINING_ACTION_KEY, async () => {
    const modelName = selectedModel.value;
    const selectedHistoryModelPath = selectedModelEntry.value?.type === 'trained' ? selectedModelEntry.value?.path : undefined;
    let workflowId = props.workflowId || '';
    if (!workflowId) {
      const workflow = await apiCall(workflowStore.createWorkflow({
        project_path: store.currentProject.path,
        dataset_name: store.selectedDataset.name,
        dataset_path: store.selectedDataset.path,
        vision_task_type: store.selectedDataset.vision_task_type,
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
      vision_task_type: store.selectedDataset.vision_task_type,
      model_name: modelName,
      model_path: selectedHistoryModelPath,
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
  });
};

const isModelOperationSupportedForTraining = (model) => {
  return resolveTrainingModelGuard(store.selectedDataset, model).enabled;
};

onMounted(() => {
  store.fetchModels(store.selectedDataset?.vision_task_type).catch(() => {});
  store.fetchPretrainedOptions(store.selectedDataset?.vision_task_type).catch(() => {});
  if (!trainingStore.runtimeProfile) {
    trainingStore.fetchTrainingRuntimeProfile().catch(() => {});
  }
  refreshBatchCalibration().catch(() => {});
});

watch([() => store.selectedDataset?.path, () => store.selectedDataset?.vision_task_type], () => {
  if (selectedModel.value && !allModels.value.find((m) => m.name === selectedModel.value) && !selectedPresetOption.value) {
    selectedModel.value = '';
  }
  store.fetchModels(store.selectedDataset?.vision_task_type).catch(() => {});
  store.fetchPretrainedOptions(store.selectedDataset?.vision_task_type).catch(() => {});
  refreshBatchCalibration().catch(() => {});
});

watch(trainingMode, () => {
  syncConfigWithProfile();
}, { immediate: true });

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
