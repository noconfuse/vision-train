<template>
  <div class="bg-white border border-gray-200 p-4 text-slate-800 h-full overflow-y-auto">
    <div class="mb-4">
      <div class="vt-step-section-title">训练得到的指标</div>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div
          v-for="item in trainingMetricCards"
          :key="item.key"
          class="vt-stat-card"
        >
          <div class="flex items-center gap-1 text-[11px] font-medium tracking-wide text-gray-500">
            <span>{{ item.label }}</span>
            <UiTooltip
              v-if="item.helpText"
              side="top"
              align="start"
              content-class="max-w-[18rem] whitespace-pre-line text-left"
            >
              <template #trigger>
                <span class="inline-flex h-3.5 w-3.5 cursor-help items-center justify-center rounded-full border border-slate-300 text-slate-400 transition-colors hover:border-slate-400 hover:text-slate-600">
                  <AppIcon name="help" class="h-3 w-3" :stroke-width="2.25" />
                </span>
              </template>
              {{ item.helpText }}
            </UiTooltip>
          </div>
          <div class="mt-1 text-xl font-semibold" :class="item.valueClass">{{ item.value }}</div>
        </div>
      </div>
    </div>

    <div class="mb-4">
      <div class="flex items-center justify-between gap-3 mb-3">
        <div>
          <div class="vt-step-section-title mb-1">测试评估进度</div>
          <div class="text-sm font-semibold text-slate-800">
            {{ evaluateProgress }}%
          </div>
        </div>
        <div class="flex items-center gap-2">
          <span v-if="evaluateTask" class="vt-tag" :class="getTaskStatusTagClass(evaluateTask)">
            {{ getTaskStatusLabel(evaluateTask) }}
          </span>
          <div v-if="isEvaluateRunning" class="animate-pulse flex items-center gap-2 text-xs text-emerald-700">
            <span class="vt-status-dot vt-status-dot--success"></span>
            <span class="font-mono">实时更新中</span>
          </div>
        </div>
      </div>
      <div class="vt-meter h-3 border border-gray-200">
        <div
          class="vt-meter__bar"
          :class="getTaskProgressBarClass(evaluateTask)"
          :style="{ width: `${evaluateProgress}%` }"
        ></div>
      </div>
      <div
        v-if="evaluateProgressSummary"
        class="mt-2 text-xs"
        :class="evaluateProgressSummaryClass"
      >
        {{ evaluateProgressSummary }}
      </div>
    </div>

    <div v-if="metrics" class="mb-4 space-y-3">
      <div class="vt-step-section-title">评估结果</div>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div
          v-for="item in evaluateMetricCards"
          :key="item.key"
          class="vt-stat-card"
        >
          <div class="flex items-center gap-1 text-[11px] font-medium tracking-wide text-gray-500">
            <span>{{ item.label }}</span>
            <UiTooltip
              v-if="item.helpText"
              side="top"
              align="start"
              content-class="max-w-[18rem] whitespace-pre-line text-left"
            >
              <template #trigger>
                <span class="inline-flex h-3.5 w-3.5 cursor-help items-center justify-center rounded-full border border-slate-300 text-slate-400 transition-colors hover:border-slate-400 hover:text-slate-600">
                  <AppIcon name="help" class="h-3 w-3" :stroke-width="2.25" />
                </span>
              </template>
              {{ item.helpText }}
            </UiTooltip>
          </div>
          <div class="mt-1 text-xl font-semibold" :class="item.valueClass">{{ item.value }}</div>
        </div>
      </div>

      <div v-if="recommendations.length" class="space-y-2">
        <div class="vt-step-section-title mb-0">结果建议</div>
        <div
          v-for="(item, index) in recommendations"
          :key="`${item.title}-${index}`"
          class="border p-4"
          :class="recommendationClass(item.tone)"
        >
          <div class="text-sm font-semibold">{{ item.title }}</div>
          <div class="mt-1 text-sm leading-6">{{ item.content }}</div>
        </div>
      </div>
    </div>

    <div class="mt-4 flex flex-wrap items-center justify-end gap-2">
      <button @click="$emit('export')" class="vt-btn-secondary vt-btn-size-lg">导出</button>
      <button
        @click="startEvaluate"
        class="vt-btn-solid-primary vt-btn-size-lg"
        :disabled="evaluateActionDisabled"
      >
        <span
          v-if="starting || isEvaluateRunning"
          class="inline-block h-3 w-3 rounded-full border-2 border-white/30 border-t-white animate-spin"
        ></span>
        {{ evaluateActionLabel }}
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue';
import api from '../api';
import { useApiCall } from '../composables/useApiCall';
import { useTrainingWorkflowStore } from '../stores/trainingWorkflow';
import AppIcon from './ui/AppIcon.vue';
import UiTooltip from './ui/Tooltip.vue';
import {
  getTaskTerminalSummary,
  getTaskTerminalSummaryClass,
  getTaskProgressBarClass,
  getTaskStatusLabel,
  getTaskStatusTagClass,
  isTaskActive,
} from '../taskStatus';

const props = defineProps({
  projectPath: { type: String, required: true },
  datasetName: { type: String, required: true },
  trainingTask: { type: Object, default: null },
  workflowId: { type: String, default: '' },
  hasTestSplit: { type: Boolean, default: false },
});

defineEmits(['export']);

const apiCall = useApiCall();
const workflowStore = useTrainingWorkflowStore();

const evaluateTask = ref(null);
const trainingMetricsHistory = ref([]);
const starting = ref(false);
let pollTimer = null;

const metrics = computed(() => evaluateTask.value?.artifacts?.results || null);
const latestTrainingMetrics = computed(() => {
  if (!trainingMetricsHistory.value.length) return null;
  return trainingMetricsHistory.value[trainingMetricsHistory.value.length - 1];
});
const recommendations = computed(() => {
  const items = metrics.value?.recommendations;
  return Array.isArray(items) ? items : [];
});
const evaluateProgress = computed(() => evaluateTask.value?.progress || 0);
const isEvaluateRunning = computed(() => isTaskActive(evaluateTask.value));
const evaluateActionDisabled = computed(() => starting.value || isEvaluateRunning.value || !props.trainingTask || !props.hasTestSplit);
const evaluateActionLabel = computed(() => {
  if (starting.value || isEvaluateRunning.value) return '评估中...';
  return evaluateTask.value ? '重新测试评估' : '开始测试评估';
});
const evaluateProgressSummary = computed(() => getTaskTerminalSummary(evaluateTask.value, '尚未开始测试评估'));
const evaluateProgressSummaryClass = computed(() => getTaskTerminalSummaryClass(evaluateTask.value));
const evaluateSplitLabel = computed(() => {
  const split = String(metrics.value?.split || evaluateTask.value?.payload?.split || '').trim();
  if (split === 'test') return '测试集';
  return props.hasTestSplit ? '测试集' : '无测试集';
});
const METRIC_GUIDE_MAP = Object.freeze({
  precision: {
    description: '关注误报，越高越稳。',
    range: '建议区间：>= 0.70 较稳，0.55~0.70 可继续观察，< 0.55 需重点排查误报',
  },
  recall: {
    description: '关注漏检，越高越全。',
    range: '建议区间：>= 0.70 较稳，0.55~0.70 可继续观察，< 0.55 需重点补漏检样本',
  },
  map50: {
    description: '看整体可用性，越高越好。',
    range: '建议区间：>= 0.75 表现较好，0.55~0.75 可按场景继续验证，< 0.55 需继续迭代',
  },
  map50_95: {
    description: '更严格，适合做最终验收。',
    range: '建议区间：>= 0.60 较稳，0.35~0.60 需结合场景验证，< 0.35 不建议直接导出上线',
  },
});
const getMetricHelpText = (key) => {
  const guide = METRIC_GUIDE_MAP[key];
  if (!guide) return '';
  return `${guide.description}\n${guide.range}`;
};
const trainingMetricCards = computed(() => ([
  {
    key: 'train-map50',
    label: '训练 mAP50',
    value: formatMetric(latestTrainingMetrics.value?.map50),
    valueClass: 'text-emerald-700',
    helpText: getMetricHelpText('map50'),
  },
  {
    key: 'train-map50-95',
    label: '训练 mAP50-95',
    value: formatMetric(latestTrainingMetrics.value?.map50_95),
    valueClass: 'vt-text-accent',
    helpText: getMetricHelpText('map50_95'),
  },
  {
    key: 'eval-data',
    label: '评估数据',
    value: evaluateSplitLabel.value,
    valueClass: 'text-slate-800',
    helpText: '',
  },
  {
    key: 'eval-status',
    label: '当前状态',
    value: evaluateTask.value ? getTaskStatusLabel(evaluateTask.value) : '未开始',
    valueClass: 'text-slate-800',
    helpText: '',
  },
]));
const evaluateMetricCards = computed(() => ([
  {
    key: 'precision',
    label: 'Precision',
    value: formatMetric(metrics.value?.precision),
    valueClass: 'text-slate-800',
    helpText: getMetricHelpText('precision'),
  },
  {
    key: 'recall',
    label: 'Recall',
    value: formatMetric(metrics.value?.recall),
    valueClass: 'text-slate-800',
    helpText: getMetricHelpText('recall'),
  },
  {
    key: 'map50',
    label: 'mAP50',
    value: formatMetric(metrics.value?.map50),
    valueClass: 'text-emerald-700',
    helpText: getMetricHelpText('map50'),
  },
  {
    key: 'map50-95',
    label: 'mAP50-95',
    value: formatMetric(metrics.value?.map50_95),
    valueClass: 'vt-text-accent',
    helpText: getMetricHelpText('map50_95'),
  },
]));

const stopPolling = () => {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
};

const pollEvaluateTask = async (taskId) => {
  if (!taskId) return;
  stopPolling();
  const tick = async () => {
    try {
      const task = await api.getTask(taskId);
      if (task?.id) {
        evaluateTask.value = task;
      }
      if (isTaskActive(task)) {
        pollTimer = setTimeout(tick, 1000);
      } else {
        pollTimer = null;
      }
    } catch (_) {
      pollTimer = null;
    }
  };
  await tick();
};

const loadEvaluateTask = async () => {
  stopPolling();
  evaluateTask.value = null;
  trainingMetricsHistory.value = [];
  if (!props.projectPath || !props.datasetName || !props.trainingTask?.id || !props.workflowId) return;
  try {
    const [latestEvaluateTask] = await Promise.all([
      workflowStore.fetchLatestWorkflowTask({
        project_path: props.projectPath,
        dataset_name: props.datasetName,
        workflow_id: props.workflowId,
        task_type: 'evaluate',
      }),
      api.getTrainingMetricsHistory(props.trainingTask.id).then((items) => {
        trainingMetricsHistory.value = Array.isArray(items) ? items : [];
      }).catch(() => {
        trainingMetricsHistory.value = [];
      }),
    ]);
    evaluateTask.value = latestEvaluateTask || null;
    if (isTaskActive(evaluateTask.value)) {
      await pollEvaluateTask(evaluateTask.value.id);
    }
  } catch (err) {
    console.error(err);
  }
};

const startEvaluate = async () => {
  if (!props.trainingTask?.id || starting.value || !props.hasTestSplit) return;
  starting.value = true;
  try {
    const data = await apiCall(api.startEvaluate({
      project_path: props.projectPath,
      dataset_name: props.datasetName,
      task_id: props.trainingTask.id,
      use_best: true,
    }), {
      successMsg: '测试评估已启动',
      errorMsg: '启动测试评估失败',
    });
    if (data?.task_id) {
      await pollEvaluateTask(data.task_id);
    } else {
      await loadEvaluateTask();
    }
  } finally {
    starting.value = false;
  }
};

const formatMetric = (value) => {
  if (typeof value !== 'number') return '-';
  return value.toFixed(4);
};

const recommendationClass = (tone) => {
  if (tone === 'success') return 'border-emerald-200 bg-emerald-50 text-emerald-800';
  if (tone === 'warn') return 'border-amber-200 bg-amber-50 text-amber-800';
  return 'border-slate-200 bg-slate-50 text-slate-700';
};

watch(() => [props.trainingTask?.id, props.workflowId], () => {
  loadEvaluateTask().catch(() => {});
}, { immediate: true });

onBeforeUnmount(() => {
  stopPolling();
});
</script>
