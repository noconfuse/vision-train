<template>
  <div class="bg-white border border-gray-200 p-4 text-slate-800 h-full overflow-y-auto">
    <div class="mb-4">
      <div class="vt-step-section-title">训练参数</div>
      <div class="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <div class="vt-stat-card">
          <div class="text-xs text-gray-500 mb-1">当前模型</div>
          <div class="text-sm font-semibold text-slate-800 break-all">{{ modelName }}</div>
        </div>
        <div class="vt-stat-card">
          <div class="text-xs text-gray-500 mb-1">轮数</div>
          <div class="text-sm font-semibold text-slate-800">{{ trainingConfig?.epochs ?? '-' }}</div>
        </div>
        <div class="vt-stat-card">
          <div class="text-xs text-gray-500 mb-1">批次</div>
          <div class="text-sm font-semibold text-slate-800">{{ trainingConfig?.batch ?? '-' }}</div>
        </div>
        <div class="vt-stat-card">
          <div class="text-xs text-gray-500 mb-1">图像尺寸</div>
          <div class="text-sm font-semibold text-slate-800">{{ trainingConfig?.imgsz ?? '-' }}</div>
        </div>
        <div class="vt-stat-card">
          <div class="text-xs text-gray-500 mb-1">绑定版本</div>
          <div class="text-sm font-semibold font-mono text-slate-800 break-all">{{ boundDatasetVersion }}</div>
        </div>
        <div class="vt-stat-card">
          <div class="text-xs text-gray-500 mb-1">初始学习率</div>
          <div class="text-sm font-semibold text-slate-800">{{ formatConfigValue(trainingConfig?.lr0) }}</div>
        </div>
        <div class="vt-stat-card">
          <div class="text-xs text-gray-500 mb-1">冻结层数</div>
          <div class="text-sm font-semibold text-slate-800">{{ trainingConfig?.freeze ?? '-' }}</div>
        </div>
        <div class="vt-stat-card">
          <div class="text-xs text-gray-500 mb-1">开始时间</div>
          <div class="text-sm font-semibold text-slate-800 font-mono">{{ formatTime(localTask?.started_at || localTask?.created_at) }}</div>
        </div>
        <div class="vt-stat-card">
          <div class="text-xs text-gray-500 mb-1">结束时间</div>
          <div class="text-sm font-semibold text-slate-800 font-mono">{{ formatTime(localTask?.finished_at) }}</div>
        </div>
      </div>
    </div>

    <div class="mb-4">
      <div class="flex items-center justify-between gap-3 mb-3">
        <div>
          <div class="vt-step-section-title mb-1">训练进度</div>
          <div class="text-sm font-semibold text-slate-800">
            {{ localTask?.progress || 0 }}%
          </div>
        </div>
        <div class="flex items-center gap-2">
          <span class="vt-tag" :class="getTaskStatusTagClass(localTask?.status)">
            {{ getTaskStatusLabel(localTask?.status) }}
          </span>
          <div v-if="isRunning" class="animate-pulse flex items-center gap-2 text-xs text-emerald-700">
            <span class="vt-status-dot vt-status-dot--success"></span>
            <span class="font-mono">实时更新中</span>
          </div>
        </div>
      </div>
      <div class="vt-meter h-3 border border-gray-200">
        <div
          class="vt-meter__bar"
          :class="getTaskProgressBarClass(localTask?.status)"
          :style="{ width: `${localTask?.progress || 0}%` }"
        ></div>
      </div>
      <div
        v-if="progressSummary"
        class="mt-2 text-xs"
        :class="progressSummaryClass"
      >
        {{ progressSummary }}
      </div>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mt-4 text-sm">
        <div>
          <div class="text-[11px] font-medium tracking-wide text-gray-500">{{ primaryMetricLabel }}</div>
          <div class="mt-1 font-mono text-sm font-semibold text-slate-800">{{ primaryMetricValue }}</div>
        </div>
        <div>
          <div class="text-[11px] font-medium tracking-wide text-gray-500">{{ secondaryMetricLabel }}</div>
          <div class="mt-1 font-mono text-sm font-semibold text-slate-800">{{ secondaryMetricValue }}</div>
        </div>
        <div class="min-w-0">
          <div class="text-[11px] font-medium tracking-wide text-gray-500">训练输出</div>
          <div class="mt-1 min-w-0">
            <UiTooltip
              v-if="outputDirPath !== '-'"
              side="bottom"
              align="start"
              content-class="min-w-[20rem] max-w-[32rem] break-all text-left"
            >
              <template #trigger>
                <div class="font-mono text-sm font-semibold text-slate-800 truncate">
                  {{ outputDirPath }}
                </div>
              </template>
              {{ outputDirPath }}
            </UiTooltip>
            <div v-else class="font-mono text-sm font-semibold text-slate-800">
              {{ outputDirPath }}
            </div>
          </div>
        </div>
        <div>
          <div class="text-[11px] font-medium tracking-wide text-gray-500">恢复来源</div>
          <div class="mt-1 font-mono text-sm font-semibold text-slate-800">{{ resumeFromTaskId }}</div>
        </div>
      </div>
    </div>

    <div class="mb-4">
      <div class="vt-step-section-title">训练曲线与可视化</div>
      <div v-if="localMetricsHistory.length > 0" class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <button
          type="button"
          class="border border-gray-200 bg-white p-3 text-left hover:border-slate-400 transition-colors"
          @click="openCurvePreview('loss')"
        >
          <div class="flex justify-between items-center mb-2">
            <span class="text-xs font-semibold text-gray-700">Training Loss</span>
            <div class="flex gap-2 text-[10px]">
              <span
                v-for="series in resultProfile.task_detail?.loss_series || []"
                :key="series.key"
                :style="{ color: series.color }"
              >
                {{ series.label }}
              </span>
            </div>
          </div>
          <svg viewBox="0 0 100 50" class="w-full h-24 overflow-visible" preserveAspectRatio="none">
            <line x1="0" y1="0" x2="100" y2="0" stroke="gray" stroke-opacity="0.2" stroke-width="0.2" />
            <line x1="0" y1="50" x2="100" y2="50" stroke="gray" stroke-opacity="0.2" stroke-width="0.2" />
            <polyline
              v-for="series in resultProfile.task_detail?.loss_series || []"
              :key="series.key"
              :points="getPoints(localMetricsHistory, series.key)"
              fill="none"
              :stroke="series.color"
              stroke-width="0.5"
              vector-effect="non-scaling-stroke"
            />
          </svg>
        </button>
        <button
          type="button"
          class="border border-gray-200 bg-white p-3 text-left hover:border-slate-400 transition-colors"
          @click="openCurvePreview('metrics')"
        >
          <div class="flex justify-between items-center mb-2">
            <span class="text-xs font-semibold text-gray-700">{{ metricCurveTitle }}</span>
            <div class="flex gap-2 text-[10px]">
              <span
                v-for="series in resultProfile.task_detail?.metric_series || []"
                :key="series.key"
                :style="{ color: series.color }"
              >
                {{ series.label }}
              </span>
            </div>
          </div>
          <svg viewBox="0 0 100 50" class="w-full h-24 overflow-visible" preserveAspectRatio="none">
            <line x1="0" y1="0" x2="100" y2="0" stroke="gray" stroke-opacity="0.2" stroke-width="0.2" />
            <line x1="0" y1="25" x2="100" y2="25" stroke="gray" stroke-opacity="0.2" stroke-width="0.2" stroke-dasharray="2" />
            <line x1="0" y1="50" x2="100" y2="50" stroke="gray" stroke-opacity="0.2" stroke-width="0.2" />
            <polyline
              v-for="series in resultProfile.task_detail?.metric_series || []"
              :key="series.key"
              :points="getMetricsPoints(localMetricsHistory, series.key)"
              fill="none"
              :stroke="series.color"
              stroke-width="0.5"
              vector-effect="non-scaling-stroke"
            />
          </svg>
        </button>
      </div>
      <div v-else class="border border-dashed border-gray-300 p-6 text-center text-sm text-gray-400">
        暂无可展示的训练曲线，等待首轮 epoch 完成后自动更新。
      </div>

      <div v-if="artifactImages.length" class="mt-4">
        <div class="grid grid-cols-2 xl:grid-cols-4 gap-3">
          <button
            v-for="img in artifactImages"
            :key="img.url"
            type="button"
            class="border border-gray-200 bg-white p-2 hover:border-slate-400 transition-colors text-left"
            @click="openArtifactImage(img)"
          >
            <img :src="img.url" :alt="img.name" class="w-full h-36 object-contain bg-slate-50" />
            <UiTooltip
              side="bottom"
              align="start"
              content-class="max-w-[20rem] break-all text-left"
            >
              <template #trigger>
                <div class="mt-2 text-[11px] text-gray-500 truncate">{{ img.name }}</div>
              </template>
              {{ img.name }}
            </UiTooltip>
          </button>
        </div>
      </div>
    </div>

    <div class="mt-4">
      <div
        v-if="showEvaluateTestHint"
        class="mb-2 text-right text-xs leading-5 text-slate-500"
      >
        当前数据集没有 `test` 划分。训练过程已持续产出验证指标；如需独立测试集评估，请补充 `test` 集。
      </div>
      <div class="flex flex-wrap items-center justify-end gap-2">
        <AsyncButton
          v-if="canResume"
          @click="resumeTraining"
          class="vt-btn-solid-primary vt-btn-size-lg"
          :disabled="taskActionPending"
          :pending="isActionPending(resumeActionKey)"
          loading-text="启动中..."
        >
          <AppIcon name="workflow" class="h-4 w-4" />
          继续训练
        </AsyncButton>
        <AsyncButton
          v-else-if="canRetry"
          @click="retryTraining"
          class="vt-btn-solid-primary vt-btn-size-lg inline-flex items-center gap-2"
          :disabled="taskActionPending"
          :pending="isActionPending(retryActionKey)"
          loading-text="启动中..."
        >
          <span>重新训练</span>
          <UiTooltip
            side="top"
            align="center"
            content-class="min-w-[20rem] max-w-[28rem] break-words text-left"
          >
            <template #trigger>
              <span
                class="inline-flex h-4.5 w-4.5 cursor-help items-center justify-center rounded-full border border-white/35 bg-white/12 text-[10px] font-semibold leading-none text-white/90"
                aria-hidden="true"
              >
                <AppIcon name="help" class="h-3.5 w-3.5" :stroke-width="2.25" />
              </span>
            </template>
            {{ retryHintText }}
          </UiTooltip>
        </AsyncButton>
        <AsyncButton
          v-if="isRunning"
          @click="stopTraining"
          class="vt-btn-solid-danger vt-btn-size-lg"
          :disabled="taskActionPending || localTask?.status === TASK_STATUS.STOPPING"
          :pending="isActionPending(stopActionKey) || localTask?.status === TASK_STATUS.STOPPING"
          :loading-text="stopButtonLabel"
        >
          <AppIcon name="close" class="h-4 w-4" />
          停止训练
        </AsyncButton>
        <button
          v-if="canGoEvaluate"
          @click="$emit('evaluate')"
          class="vt-btn-secondary vt-btn-size-lg"
        >
          <AppIcon name="evaluate" class="h-4 w-4" />
          测试集评估
        </button>
        <button
          v-if="canGoExport"
          @click="$emit('export')"
          class="vt-btn-secondary vt-btn-size-lg"
        >
          <AppIcon name="export" class="h-4 w-4" />
          导出
        </button>
      </div>
    </div>

    <div
      v-if="previewImage || previewCurve"
      class="vt-workspace-backdrop"
      @click="closePreview"
    >
      <div
        class="vt-preview-panel"
        :class="previewCurve ? 'vt-preview-panel--curve' : 'vt-preview-panel--image'"
        @click.stop
      >
        <button
          type="button"
          class="vt-modal-close absolute right-2 top-2"
          @click="closePreview"
        >
          <AppIcon name="close" class="h-4 w-4" />
        </button>
        <template v-if="previewImage">
          <img
            :src="previewImage.url"
            :alt="previewImage.name"
            class="max-w-[88vw] max-h-[82vh] object-contain bg-slate-50"
          />
          <div class="mt-3 text-xs text-slate-600 break-all">
            {{ previewImage.name }}
          </div>
        </template>
        <template v-else-if="previewCurve">
          <div class="flex-1 min-h-0 flex flex-col pr-10">
            <div class="mb-3 flex justify-between items-center shrink-0">
              <div class="text-sm font-semibold text-slate-800">{{ previewCurveTitle }}</div>
              <div class="flex gap-2 text-[11px]">
                <template v-if="previewCurve === 'loss'">
                  <span
                    v-for="series in (resultProfile.task_detail?.loss_series || [])"
                    :key="series.key"
                    :style="{ color: series.color }"
                  >
                    {{ series.label }}
                  </span>
                </template>
                <template v-else>
                  <span
                    v-for="series in (resultProfile.task_detail?.metric_series || [])"
                    :key="series.key"
                    :style="{ color: series.color }"
                  >
                    {{ series.label }}
                  </span>
                </template>
              </div>
            </div>
            <div class="flex-1 min-h-0 border border-gray-200 bg-slate-50 p-3">
              <svg
                v-if="previewCurve === 'loss'"
                viewBox="-4 -2 108 54"
                class="w-full h-full"
                preserveAspectRatio="xMidYMid meet"
              >
                <line x1="0" y1="0" x2="100" y2="0" stroke="gray" stroke-opacity="0.2" stroke-width="0.2" />
                <line x1="0" y1="50" x2="100" y2="50" stroke="gray" stroke-opacity="0.2" stroke-width="0.2" />
                <template v-if="(resultProfile.task_detail?.loss_series || []).length">
                  <polyline
                    v-for="series in (resultProfile.task_detail?.loss_series || [])"
                    :key="series.key"
                    :points="getPoints(localMetricsHistory, series.key)"
                    fill="none"
                    :stroke="series.color"
                    stroke-width="0.45"
                    vector-effect="non-scaling-stroke"
                  />
                </template>
                <template v-else>
                  <polyline :points="getPoints(localMetricsHistory, 'box_loss')" fill="none" stroke="#ef4444" stroke-width="0.45" vector-effect="non-scaling-stroke" />
                  <polyline :points="getPoints(localMetricsHistory, 'cls_loss')" fill="none" stroke="#3b82f6" stroke-width="0.45" vector-effect="non-scaling-stroke" />
                  <polyline :points="getPoints(localMetricsHistory, 'dfl_loss')" fill="none" stroke="#eab308" stroke-width="0.45" vector-effect="non-scaling-stroke" />
                </template>
              </svg>
              <svg
                v-else
                viewBox="-4 -2 108 54"
                class="w-full h-full"
                preserveAspectRatio="xMidYMid meet"
              >
                <line x1="0" y1="0" x2="100" y2="0" stroke="gray" stroke-opacity="0.2" stroke-width="0.2" />
                <line x1="0" y1="25" x2="100" y2="25" stroke="gray" stroke-opacity="0.2" stroke-width="0.2" stroke-dasharray="2" />
                <line x1="0" y1="50" x2="100" y2="50" stroke="gray" stroke-opacity="0.2" stroke-width="0.2" />
                <polyline
                  v-for="series in (resultProfile.task_detail?.metric_series || [])"
                  :key="series.key"
                  :points="getMetricsPoints(localMetricsHistory, series.key)"
                  fill="none"
                  :stroke="series.color"
                  stroke-width="0.45"
                  vector-effect="non-scaling-stroke"
                />
              </svg>
              <div class="mt-2 text-[11px] text-gray-500">点击空白处或右上角关闭预览。</div>
            </div>
            <div v-if="localMetricsHistory.length < 2" class="mt-3 text-xs text-gray-500">
              当前曲线点位较少，放大后仍会显得比较空。
            </div>
            <div v-else class="mt-3 text-xs text-gray-500">
              共 {{ localMetricsHistory.length }} 个 epoch 点位。
            </div>
          </div>
        </template>
        <div v-else class="text-sm text-slate-500">
          暂无可预览内容
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import { useAsyncAction } from '../composables/useAsyncAction';
import { useConfirm } from '../composables/useConfirm';
import { useToast } from '../composables/useToast';
import api from '../api';
import AsyncButton from './ui/AsyncButton.vue';
import AppIcon from './ui/AppIcon.vue';
import UiTooltip from './ui/Tooltip.vue';
import { useTrainingStore } from '../stores/training';
import {
  TASK_STATUS,
  getTaskTerminalSummary,
  getTaskTerminalSummaryClass,
  getTaskProgressBarClass,
  getTaskStatusLabel,
  getTaskStatusTagClass,
  isTaskActive,
  isTaskCompleted,
  isTaskResumable,
  isTaskRetryable,
} from '../taskStatus';
import { formatDateTime } from '../utils';
import { getResumeFromTaskId } from '../utils/trainingTask';
import { resolveTrainingResultProfile } from '../trainingResultProfile';

const props = defineProps({
  projectPath: { type: String, required: true },
  projectName: { type: String, required: true },
  datasetName: { type: String, required: true },
  task: { type: Object, default: null },
  canOpenEvaluate: { type: Boolean, default: false },
  hasTestSplit: { type: Boolean, default: false },
});

const emit = defineEmits(['evaluate', 'export', 'training-started']);
const asyncAction = useAsyncAction();
const { confirm: showConfirm } = useConfirm();
const toast = useToast();
const trainingStore = useTrainingStore();

const localTask = ref(props.task || null);
const localMetricsHistory = ref([]);
const localArtifacts = ref({ images: [], weights: [], config: null });
const previewImage = ref(null);
const previewCurve = ref('');
const buildTaskActionKey = (action) => `training-task-detail:${action}:${localTask.value?.id || ''}`;
const stopActionKey = computed(() => buildTaskActionKey('stop'));
const resumeActionKey = computed(() => buildTaskActionKey('resume'));
const retryActionKey = computed(() => buildTaskActionKey('retry'));
const isActionPending = (keyRef) => {
  const key = typeof keyRef === 'string' ? keyRef : keyRef?.value;
  return key ? asyncAction.isPending(key) : false;
};
const taskActionPending = computed(() => (
  isActionPending(stopActionKey)
  || isActionPending(resumeActionKey)
  || isActionPending(retryActionKey)
));
const isRunning = computed(() => isTaskActive(localTask.value));
const stopButtonLabel = computed(() => {
  if (isActionPending(stopActionKey) || localTask.value?.status === TASK_STATUS.STOPPING) return '停止中...';
  return '停止训练';
});
const trainingConfig = computed(() => localTask.value?.payload?.training_config || {});
const canResume = computed(() => isTaskResumable(localTask.value) && !!localTask.value?.resume_available);
const canRetry = computed(() => isTaskRetryable(localTask.value) && !localTask.value?.resume_available);
const retryHintText = computed(() => {
  if (!canRetry.value) return '';
  const status = localTask.value?.status;
  if (status === TASK_STATUS.STOPPED) {
    return '本次为手动停止，但停止时尚未生成可恢复权重（last.pt / best.pt），因此当前只能重新训练。';
  }
  if (status === TASK_STATUS.INTERRUPTED) {
    return '任务中断时尚未保留可恢复权重（last.pt / best.pt），因此当前只能重新训练。';
  }
  return '当前任务没有可恢复权重（last.pt / best.pt），因此无法继续训练，只能重新训练。';
});
const canGoEvaluate = computed(() => isTaskCompleted(localTask.value) && props.canOpenEvaluate);
const canGoExport = computed(() => isTaskCompleted(localTask.value));
const showEvaluateTestHint = computed(() => (
  isTaskCompleted(localTask.value)
  && !props.hasTestSplit
  && !props.canOpenEvaluate
));
const modelName = computed(() => localTask.value?.payload?.model_name || '-');
const boundDatasetVersion = computed(() => (
  localTask.value?.dataset_version_id
  || localTask.value?.payload?.dataset_version_id
  || '-'
));
const outputDirPath = computed(() => {
  const outputDir = localTask.value?.artifacts?.output_dir || '';
  return outputDir || '-';
});
const resumeFromTaskId = computed(() => getResumeFromTaskId(localTask.value, '-'));
const latestMetrics = computed(() => {
  if (!localMetricsHistory.value.length) return null;
  return localMetricsHistory.value[localMetricsHistory.value.length - 1];
});
const resultProfile = computed(() => resolveTrainingResultProfile(localTask.value));
const primaryMetricKey = computed(() => resultProfile.value.task_detail?.primary_metric?.key || '');
const secondaryMetricKey = computed(() => resultProfile.value.task_detail?.secondary_metric?.key || '');
const primaryMetricLabel = computed(() => resultProfile.value.task_detail?.primary_metric?.label || '最新指标');
const secondaryMetricLabel = computed(() => resultProfile.value.task_detail?.secondary_metric?.label || '综合指标');
const formatMetricText = (value) => (typeof value === 'number' ? value.toFixed(3) : '-');
const resolveHistoryMetricValue = (entry, key) => {
  if (!entry || !key) return undefined;
  if (typeof entry[key] === 'number') return entry[key];
  if (typeof entry?.extra?.[key] === 'number') return entry.extra[key];
  return undefined;
};
const primaryMetricValue = computed(() => (
  `${resultProfile.value.task_detail?.primary_metric?.value_prefix || primaryMetricLabel.value} ${formatMetricText(resolveHistoryMetricValue(latestMetrics.value, primaryMetricKey.value))}`
));
const secondaryMetricValue = computed(() => (
  `${resultProfile.value.task_detail?.secondary_metric?.value_prefix || secondaryMetricLabel.value} ${formatMetricText(resolveHistoryMetricValue(latestMetrics.value, secondaryMetricKey.value))}`
));
const progressSummary = computed(() => getTaskTerminalSummary(localTask.value, ''));
const progressSummaryClass = computed(() => getTaskTerminalSummaryClass(localTask.value));
const artifactImages = computed(() => Array.isArray(localArtifacts.value?.images) ? localArtifacts.value.images : []);
const previewCurveTitle = computed(() => {
  if (previewCurve.value === 'loss') return 'Training Loss';
  if (previewCurve.value === 'metrics') return metricCurveTitle.value;
  return '';
});
const metricCurveTitle = computed(() => resultProfile.value.task_detail?.metric_curve_title || 'Metrics');

let pollingTimer = null;

const formatTime = (iso) => formatDateTime(iso, { withSeconds: true });

const formatConfigValue = (value) => {
  if (value === null || value === undefined || value === '') return '-';
  return String(value);
};

const getPoints = (data, key, height = 50, width = 100) => {
  if (!data || data.length < 2) return '';
  const values = data.map((d) => Number(d[key] || d?.extra?.[key] || 0));
  const maxVal = Math.max(...values, 0.0001) * 1.1;
  return values.map((v, i) => {
    const x = (i / (values.length - 1)) * width;
    const y = height - (v / maxVal) * height;
    return `${x},${y}`;
  }).join(' ');
};

const getMetricsPoints = (data, key, height = 50, width = 100) => {
  if (!data || data.length < 2) return '';
  return data.map((d, i) => {
    const x = (i / (data.length - 1)) * width;
    const value = Number(d[key] || d?.extra?.[key] || 0);
    const y = height - (value * height);
    return `${x},${y}`;
  }).join(' ');
};

const stopPolling = () => {
  if (pollingTimer) {
    clearTimeout(pollingTimer);
    pollingTimer = null;
  }
};

const openArtifactImage = (img) => {
  previewCurve.value = '';
  previewImage.value = img || null;
};

const closeArtifactPreview = () => {
  previewImage.value = null;
};

const openCurvePreview = (type) => {
  previewImage.value = null;
  previewCurve.value = type || '';
};

const closePreview = () => {
  previewCurve.value = '';
  closeArtifactPreview();
};

const loadTaskSnapshot = async () => {
  const taskId = props.task?.id || localTask.value?.id;
  if (!taskId) {
    localTask.value = null;
    localMetricsHistory.value = [];
    localArtifacts.value = { images: [], weights: [], config: null };
    return;
  }
  try {
    const [taskRes, historyRes, artifactsRes] = await Promise.all([
      api.getTask(taskId),
      api.getTrainingMetricsHistory(taskId),
      api.getTrainingRunArtifacts({
        project_path: props.projectPath,
        dataset_name: props.datasetName,
        task_id: taskId,
      }).catch(() => ({ images: [], weights: [], config: null })),
    ]);
    if (taskRes?.id) localTask.value = taskRes;
    localMetricsHistory.value = Array.isArray(historyRes) ? historyRes : [];
    localArtifacts.value = artifactsRes || { images: [], weights: [], config: null };
    if (isTaskActive(localTask.value)) {
      stopPolling();
      pollingTimer = setTimeout(() => {
        loadTaskSnapshot().catch(() => {});
      }, 2000);
    } else {
      stopPolling();
    }
  } catch (err) {
    console.error(err);
  }
};

const stopTraining = async () => {
  if (localTask.value?.status === TASK_STATUS.STOPPING) return;
  const ok = await showConfirm({
    message: '确定要停止当前训练吗？\n当前进度会保存到 checkpoint，下次可继续。',
    title: '停止训练',
    danger: true,
    confirmText: '停止',
  });
  if (!ok || !localTask.value?.id) return;
  await asyncAction.run(stopActionKey.value, async () => {
    try {
      await api.stopTask(localTask.value.id);
      localTask.value = {
        ...localTask.value,
        status: TASK_STATUS.STOPPING,
        message: '已发送停止请求，等待任务安全退出...',
      };
      if (trainingStore.currentTask?.id === localTask.value.id) {
        trainingStore.currentTask = {
          ...trainingStore.currentTask,
          status: TASK_STATUS.STOPPING,
          message: '已发送停止请求，等待任务安全退出...',
        };
      }
      toast.success('已请求停止训练');
      await loadTaskSnapshot();
    } catch (err) {
      toast.error(err?.message || '停止训练失败');
    }
  });
};

const resumeTraining = async () => {
  if (!localTask.value?.id) return;
  const ok = await showConfirm({
    message: '确定继续当前训练吗？系统会从最近可恢复的权重继续执行。',
    title: '继续训练',
    confirmText: '继续',
  });
  if (!ok) return;
  await asyncAction.run(resumeActionKey.value, async () => {
    try {
      const data = await api.resumeTraining({
        project_path: props.projectPath,
        dataset_name: props.datasetName,
        task_id: localTask.value.id,
      });
      if (data?.task_id) {
        toast.success('已开始继续训练');
        emit('training-started', data);
      }
    } catch (err) {
      toast.error(err?.message || '继续训练失败');
    }
  });
};

const retryTraining = async () => {
  if (!localTask.value?.id) return;
  const ok = await showConfirm({
    message: '当前任务没有可恢复权重。系统会清理这次失败训练的中间产物，并在当前工作流下重新启动一次训练。',
    title: '重新训练',
    confirmText: '重新训练',
  });
  if (!ok) return;
  await asyncAction.run(retryActionKey.value, async () => {
    try {
      const data = await api.retryTraining({
        project_path: props.projectPath,
        dataset_name: props.datasetName,
        task_id: localTask.value.id,
      });
      if (data?.task_id) {
        toast.success('已开始重新训练');
        emit('training-started', data);
      }
    } catch (err) {
      toast.error(err?.message || '重新训练失败');
    }
  });
};

watch(() => props.task?.id, () => {
  localTask.value = props.task || null;
  loadTaskSnapshot().catch(() => {});
}, { immediate: true });

onBeforeUnmount(() => {
  stopPolling();
  closePreview();
});
</script>
