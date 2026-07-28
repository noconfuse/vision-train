<template>
  <div class="bg-white p-4 text-slate-800 h-full min-h-0 flex flex-col overflow-hidden">
    <div class="grid flex-1 min-h-0 gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
      <section class="min-h-0 flex flex-col">
        <div class="vt-step-section-title mb-4 shrink-0">导出参数</div>
        <div class="flex-1 min-h-0 overflow-y-auto pr-1">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-[11px] font-medium tracking-wide text-gray-500 mb-2">导出格式</label>
              <select v-model="exportConfig.format" class="vt-select">
                <option
                  v-for="option in exportFormatOptions"
                  :key="option.value"
                  :value="option.value"
                  :disabled="option.disabled"
                >
                  {{ option.label }}
                </option>
              </select>
              <div v-if="exportConfig.format === 'engine'" class="mt-1 text-xs text-gray-500">
                {{ engineExportHint }}
              </div>
            </div>
            <div>
              <label class="block text-[11px] font-medium tracking-wide text-gray-500 mb-2">图片尺寸</label>
              <input v-model.number="exportConfig.imgsz" type="number" class="vt-input">
            </div>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-3 mt-4">
            <label
              class="vt-check-card"
              :class="(exportOptionSupport.half && !halfDisabledByMutualExclusion) ? 'vt-check-card--interactive' : 'vt-check-card--disabled'"
            >
              <input
                v-model="exportConfig.half"
                type="checkbox"
                class="vt-checkbox"
                :disabled="!exportOptionSupport.half || halfDisabledByMutualExclusion"
              >
              <div>
                <div class="vt-check-card__title">半精度 FP16</div>
                <div class="vt-check-card__desc">
                  {{ !exportOptionSupport.half ? exportProfile.half_disabled_text : (halfDisabledByMutualExclusion ? exportProfile.half_conflict_text : exportProfile.half_enabled_text) }}
                </div>
              </div>
            </label>
            <label
              class="vt-check-card"
              :class="(exportOptionSupport.int8 && !int8DisabledByMutualExclusion) ? 'vt-check-card--interactive' : 'vt-check-card--disabled'"
            >
              <input
                v-model="exportConfig.int8"
                type="checkbox"
                class="vt-checkbox"
                :disabled="!exportOptionSupport.int8 || int8DisabledByMutualExclusion"
              >
              <div>
                <div class="vt-check-card__title">INT8 量化</div>
                <div class="vt-check-card__desc">
                  {{ !exportOptionSupport.int8 ? exportProfile.int8_disabled_text : (int8DisabledByMutualExclusion ? exportProfile.int8_conflict_text : exportProfile.int8_enabled_text) }}
                </div>
              </div>
            </label>
          </div>
        </div>
      </section>

      <section class="min-h-0 flex flex-col">
        <div class="shrink-0 mb-3 flex items-center justify-between gap-3">
          <div class="vt-step-section-title mb-0">导出记录</div>
          <div class="vt-count-badge">{{ displayExportRecords.length }}</div>
        </div>
        <div class="flex-1 min-h-0 overflow-y-auto pr-1">
          <div v-if="!displayExportRecords.length" class="h-full min-h-[12rem] flex items-center justify-center text-sm text-gray-400 border border-dashed border-gray-300 bg-white">
            暂无导出记录
          </div>
          <div v-else class="space-y-2">
            <article
              v-for="exp in displayExportRecords"
              :key="exp.export_task_id || exp.export_dir"
              class="vt-record-card"
              :class="isCurrentExportRecord(exp) ? 'vt-record-card--active' : ''"
            >
              <div class="vt-record-header">
                <div class="vt-record-main">
                  <div class="vt-record-title">{{ exportFormatLabel(exp) }}</div>
                  <div class="vt-record-meta">
                    {{ formatExportMeta(exp) }}
                  </div>
                  <UiTooltip
                    v-if="getExportRecordPath(exp)"
                    side="bottom"
                    align="start"
                    content-class="min-w-[20rem] max-w-[32rem] break-all text-left"
                  >
                    <template #trigger>
                      <div class="vt-record-path">
                        {{ getExportRecordPathLabel(exp) }}
                      </div>
                    </template>
                    {{ getExportRecordPath(exp) }}
                  </UiTooltip>
                  <div v-else class="vt-record-path">
                    {{ getExportRecordPathLabel(exp) }}
                  </div>
                </div>
                <div class="vt-record-side">
                  <div class="vt-record-badges">
                    <span
                      v-if="isCurrentExportRecord(exp)"
                      class="vt-tag vt-tag--sm vt-tag-info"
                    >
                      当前导出
                    </span>
                    <span
                      v-if="exp.status"
                      class="vt-tag vt-tag--sm"
                      :class="getTaskStatusTagClass(exp.status)"
                    >
                      {{ getTaskStatusLabel(exp.status) }}
                    </span>
                  </div>
                  <div class="vt-record-size">{{ formatBytes(exp.total_size_bytes) }}</div>
                </div>
              </div>

              <div v-if="showRecordProgress(exp)" class="vt-record-progress">
                <div class="mb-1.5 flex items-center justify-between gap-3">
                  <div class="text-[11px] font-medium text-slate-700">导出进度</div>
                  <div class="text-[11px] font-mono text-slate-600">{{ getRecordProgress(exp) }}%</div>
                </div>
                <div class="vt-meter h-2 border border-gray-200">
                  <div
                    class="vt-meter__bar"
                    :class="getTaskProgressBarClass(exp.status)"
                    :style="{ width: `${getRecordProgress(exp)}%` }"
                  ></div>
                </div>
              </div>

              <div
                v-if="getRecordError(exp)"
                class="vt-note mt-1.5 whitespace-pre-wrap break-words"
                :class="getRecordErrorClass(exp)"
              >
                {{ getRecordError(exp) }}
              </div>

              <div class="vt-record-actions">
                <a
                  v-if="isOpenVinoExport(exp) && exp.bundle_url"
                  :href="exp.bundle_url"
                  :download="getExportRecordDownloadFilename(exp, 'bundle')"
                  target="_blank"
                  class="vt-btn-secondary vt-btn-size-sm"
                >
                  <AppIcon name="download" class="h-3.5 w-3.5" />
                  <span>下载整包</span>
                </a>
                <a
                  v-else-if="exp.primary_model_url"
                  :href="exp.primary_model_url"
                  :download="getExportRecordDownloadFilename(exp, 'primary')"
                  target="_blank"
                  class="vt-btn-secondary vt-btn-size-sm"
                >
                  <AppIcon name="download" class="h-3.5 w-3.5" />
                  <span>下载主模型</span>
                </a>
                <UiTooltip side="top">
                  <template #trigger>
                    <AsyncButton
                      class="vt-icon-btn vt-icon-btn--sm vt-icon-btn--danger"
                      :disabled="isDeleteDisabled(exp)"
                      :pending="isActionPending(deleteExportActionKey(exp))"
                      @click="deleteExportRecord(exp)"
                    >
                      <AppIcon name="delete" class="h-3.5 w-3.5" />
                    </AsyncButton>
                  </template>
                  {{ isActionPending(deleteExportActionKey(exp)) ? '删除中...' : '删除记录' }}
                </UiTooltip>
              </div>
            </article>
          </div>
        </div>
      </section>
    </div>

    <div class="mt-4 pt-4 border-t border-gray-200 flex flex-wrap items-center justify-end gap-2 shrink-0">
      <AsyncButton
        @click="startExport"
        class="vt-btn-solid-primary vt-btn-size-lg"
        :disabled="exportActionDisabled"
        :pending="isActionPending(EXPORT_ACTION_KEY) || isExportRunning"
        :loading-text="exportActionLabel"
      >
        <AppIcon name="export" class="h-4 w-4" />
        {{ exportIdleActionLabel }}
      </AsyncButton>
      <button
        type="button"
        class="vt-btn-secondary vt-btn-size-lg"
        @click="emit('deployment-template')"
      >
        <AppIcon name="template" class="h-4 w-4" />
        部署模板
      </button>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue';
import api from '../api';
import { useApiCall } from '../composables/useApiCall';
import { useAsyncAction } from '../composables/useAsyncAction';
import { useConfirm } from '../composables/useConfirm';
import { useToast } from '../composables/useToast';
import { assertCapabilityGuard } from '../utils/capabilityGuards';
import AsyncButton from './ui/AsyncButton.vue';
import AppIcon from './ui/AppIcon.vue';
import UiTooltip from './ui/Tooltip.vue';
import { useTrainingStore } from '../stores/training';
import { useTrainingWorkflowStore } from '../stores/trainingWorkflow';
import { resolveTrainingExportProfile } from '../utils/trainingExportProfile';
import {
  resolveExportDeleteGuard,
  resolveExportStartGuard,
} from '../utils/trainingActionGuards';
import {
  formatBytes,
  formatDateTime,
  getModelExportDownloadFilename,
  getModelExportFormatLabel,
  getPathDisplayName,
  isOpenVinoExportPath,
} from '../utils';
import {
  getTaskProgressBarClass,
  getTaskStatusLabel,
  getTaskStatusTagClass,
  isTaskActive,
} from '../domain/task/taskStatus';

const props = defineProps({
  projectPath: { type: String, required: true },
  datasetId: { type: String, required: true },
  datasetName: { type: String, required: true },
  trainingTask: { type: Object, default: null },
  workflowId: { type: String, default: '' },
  exportTaskId: { type: String, default: '' },
});
const emit = defineEmits(['deployment-template']);

const apiCall = useApiCall();
const asyncAction = useAsyncAction();
const { confirm: showConfirm } = useConfirm();
const trainingStore = useTrainingStore();
const workflowStore = useTrainingWorkflowStore();
const toast = useToast();

const currentExports = ref([]);
const currentExportTask = ref(null);
let pollTimer = null;
const EXPORT_ACTION_KEY = 'training-export:start';
const deleteExportActionKey = (exp) => `training-export:delete:${String(exp?.export_task_id || '')}`;
const isActionPending = (key) => asyncAction.isPending(key);

const exportConfig = reactive({
  format: 'onnx',
  imgsz: 640,
  half: false,
  int8: false,
});
const runtimeProfile = computed(() => trainingStore.runtimeProfile || null);
const runtimeExportFormats = computed(() => runtimeProfile.value?.export?.formats || {});
const exportProfile = computed(() => resolveTrainingExportProfile(props.trainingTask));
const exportFormatOptions = computed(() => {
  return (exportProfile.value.formats || []).map((item) => {
    const hardwareKey = item.hardware_key;
    const hardwareAvailable = hardwareKey ? Boolean(runtimeExportFormats.value?.[hardwareKey]?.available) : true;
    const hardwareReason = hardwareKey ? String(runtimeExportFormats.value?.[hardwareKey]?.reason || '').trim() : '';
    return {
      value: item.value,
      label: hardwareAvailable ? item.label : `${item.label}（需要NVIDIA支持）`,
      disabled: !hardwareAvailable,
      supports_half: !!item.supports_half,
      supports_int8: !!item.supports_int8,
      hardware_reason: hardwareReason,
      hardware_key: hardwareKey,
    };
  });
});
const currentExportFormatOption = computed(() => {
  return exportFormatOptions.value.find((item) => item.value === exportConfig.format) || null;
});
const hardwareSupportsEngine = computed(() => Boolean(runtimeExportFormats.value?.engine?.available));
const engineUnavailableReason = computed(() => String(runtimeExportFormats.value?.engine?.reason || '').trim());
const exportOptionSupport = computed(() => ({
  half: !!currentExportFormatOption.value?.supports_half,
  int8: !!currentExportFormatOption.value?.supports_int8,
}));
const halfDisabledByMutualExclusion = computed(() => Boolean(exportConfig.int8));
const int8DisabledByMutualExclusion = computed(() => Boolean(exportConfig.half));
const engineExportHint = computed(() => (
  hardwareSupportsEngine.value
    ? exportProfile.value.engine_hint_supported
    : `${exportProfile.value.engine_hint_unsupported}${engineUnavailableReason.value ? `，${engineUnavailableReason.value}` : ''}。`
));
const exportHistory = computed(() => {
  const exports = Array.isArray(currentExports.value) ? [...currentExports.value] : [];
  return exports.sort((a, b) => {
    const bTime = new Date(b?.created_at || b?.updated_at || 0).getTime();
    const aTime = new Date(a?.created_at || a?.updated_at || 0).getTime();
    return bTime - aTime;
  });
});
const displayExportRecords = computed(() => {
  const current = currentExportTask.value;
  const records = exportHistory.value.map((item) => {
    if (!current?.id || item?.export_task_id !== current.id) return item;
    return {
      ...item,
      status: current.status,
      message: current.message,
      error: current.error,
      payload: current.payload || item.payload,
      created_at: current.created_at || item.created_at,
      updated_at: current.updated_at || item.updated_at,
      progress: current.progress ?? item.progress,
    };
  });
  if (!current?.id) return records;
  if (records.some((item) => item?.export_task_id === current.id)) return records;
  return [
    {
      export_task_id: current.id,
      status: current.status,
      message: current.message,
      error: current.error,
      payload: current.payload || {},
      created_at: current.created_at,
      updated_at: current.updated_at,
      total_size_bytes: 0,
      primary_model_path: '',
      primary_model_url: null,
      bundle_url: null,
      export_path: '',
      export_dir: '',
      progress: current.progress ?? 0,
      templates: [],
    },
    ...records,
  ];
});
const isExportRunning = computed(() => isTaskActive(currentExportTask.value));
const exportIdleActionLabel = computed(() => (
  exportHistory.value.length ? '重新导出' : '开始导出'
));
const exportActionLabel = computed(() => {
  if (isActionPending(EXPORT_ACTION_KEY) || isExportRunning.value) return '导出中...';
  return exportIdleActionLabel.value;
});

const stopPolling = () => {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
};

const resetExportResultState = () => {
  stopPolling();
  currentExportTask.value = null;
  currentExports.value = [];
};

const ensureRuntimeProfile = async () => {
  if (!trainingStore.runtimeProfile) {
    await trainingStore.fetchTrainingRuntimeProfile().catch(() => {});
  }
};

const loadExports = async () => {
  currentExports.value = [];
  if (!props.projectPath || !props.trainingTask?.id) return;
  try {
    const res = await api.getTrainingModelExports({
      project_path: props.projectPath,
      task_id: props.trainingTask.id,
    });
    currentExports.value = Array.isArray(res) ? res : [];
  } catch (err) {
    console.error(err);
  }
};

const loadExportTask = async ({ forceRefreshWorkflow = false } = {}) => {
  stopPolling();
  currentExportTask.value = null;
  if (!props.projectPath || !props.datasetId || !props.trainingTask?.id) return;
  try {
    if (props.exportTaskId) {
      const task = await api.getTask(props.exportTaskId);
      currentExportTask.value = task?.id ? task : null;
    } else if (props.workflowId) {
      const workflow = forceRefreshWorkflow
        ? await workflowStore.fetchWorkflowDetail({
            project_path: props.projectPath,
            dataset_id: props.datasetId,
            workflow_id: props.workflowId,
            include_archived: true,
          })
        : workflowStore.getWorkflowFromState({
            project_path: props.projectPath,
            dataset_id: props.datasetId,
            workflow_id: props.workflowId,
            include_archived: true,
          }) || await workflowStore.fetchWorkflowDetail({
            project_path: props.projectPath,
            dataset_id: props.datasetId,
            workflow_id: props.workflowId,
            include_archived: true,
          });
      currentExportTask.value = workflow?.active_task?.type === 'export' ? workflow.active_task : null;
    } else {
      return;
    }
    if (isTaskActive(currentExportTask.value)) {
      await pollExportTask(currentExportTask.value.id);
    }
  } catch (err) {
    console.error(err);
  }
};

const getExportValidationError = () => {
  if (!currentExportFormatOption.value) {
    return '当前任务类型暂未接入该导出格式。';
  }
  if (currentExportFormatOption.value.disabled) {
    return `${exportProfile.value.engine_hint_unsupported}${currentExportFormatOption.value.hardware_reason ? `，${currentExportFormatOption.value.hardware_reason}` : ''}。`;
  }
  if (exportConfig.half && !exportOptionSupport.value.half) {
    return '当前导出格式不支持 FP16。';
  }
  if (exportConfig.int8 && !exportOptionSupport.value.int8) {
    return '当前导出配置不支持 INT8。';
  }
  return '';
};
const exportStartGuard = computed(() => resolveExportStartGuard({
  trainingTaskId: props.trainingTask?.id,
  isRunning: isExportRunning.value,
  validationError: getExportValidationError(),
}));
const exportActionDisabled = computed(() => !exportStartGuard.value.enabled);

const pollExportTask = async (taskId) => {
  if (!taskId) return;
  stopPolling();
  const tick = async () => {
    try {
      const task = await api.getTask(taskId);
      if (task?.id) currentExportTask.value = task;
      await loadExports();
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

const startExport = async () => {
  if (!assertCapabilityGuard(exportStartGuard.value, toast.error)) return;
  await asyncAction.run(EXPORT_ACTION_KEY, async () => {
    const data = await apiCall(api.trainingExport({
      project_path: props.projectPath,
      task_id: props.trainingTask.id,
      format: exportConfig.format,
      imgsz: exportConfig.imgsz,
      half: exportConfig.half,
      int8: exportConfig.int8,
    }), {
      successMsg: '导出已启动',
      errorMsg: '启动导出失败',
    });
    if (data?.task_id) {
      await pollExportTask(data.task_id);
    } else {
      await loadExportTask();
      await loadExports();
    }
  });
};

const deleteExportRecord = async (exp) => {
  const exportTaskId = String(exp?.export_task_id || '');
  if (!exportTaskId) return;
  if (!assertCapabilityGuard(resolveExportDeleteGuard({ isRunning: isDeleteDisabled(exp) }), toast.error)) return;
  const ok = await showConfirm({
    title: '删除导出记录？',
    message: '将永久删除该导出记录及对应导出产物。',
    detail: '该操作不可恢复。',
    confirmText: '删除',
    cancelText: '取消',
    danger: true,
  });
  if (!ok) return;
  await asyncAction.run(deleteExportActionKey(exp), async () => {
    await apiCall(api.deleteTrainingModelExport({
      project_path: props.projectPath,
      export_task_id: exportTaskId,
    }), {
      successMsg: '导出记录已删除',
      errorMsg: '删除导出记录失败',
    });
    await loadExports();
    if (currentExportTask.value?.id === exportTaskId) {
      currentExportTask.value = null;
    }
    await loadExportTask({ forceRefreshWorkflow: true });
  });
};

const exportFormatLabel = (exp) => {
  return getModelExportFormatLabel({
    path: exp?.primary_model_path || '',
    format: exp?.payload?.format || '',
  });
};

const isOpenVinoExport = (exp) => isOpenVinoExportPath(exp?.primary_model_path || '');
const getExportRecordPath = (exp) => exp?.primary_model_path || exp?.export_path || exp?.export_dir || '';
const getExportRecordPathLabel = (exp) => {
  const path = getExportRecordPath(exp);
  return path ? getPathDisplayName(path) : '导出产物生成中...';
};
const getExportRecordDownloadFilename = (exp, target = 'primary') => (
  getModelExportDownloadFilename(exp, target)
);

const formatExportMeta = (exp) => {
  const format = exportFormatLabel(exp);
  const imgsz = exp?.payload?.imgsz || '-';
  const half = exp?.payload?.half ? 'FP16' : 'FP32';
  const int8 = exp?.payload?.int8 ? 'INT8' : null;
  const time = formatDateTime(exp?.created_at || exp?.updated_at);
  return [format, `imgsz ${imgsz}`, half, int8, time].filter(Boolean).join(' · ');
};
const isCurrentExportRecord = (exp) => String(exp?.export_task_id || '') === String(currentExportTask.value?.id || '');
const getRecordProgress = (exp) => Number(exp?.progress ?? (isCurrentExportRecord(exp) ? currentExportTask.value?.progress : 100) ?? 0);
const showRecordProgress = (exp) => isCurrentExportRecord(exp) || ['pending', 'running', 'failed', 'stopped', 'interrupted'].includes(String(exp?.status || ''));
const getRecordError = (exp) => {
  if (String(exp?.status || '') !== 'failed') return '';
  if (isCurrentExportRecord(exp)) {
    return currentExportTask.value?.error || '';
  }
  return exp?.error || '';
};
const getRecordErrorClass = () => 'text-rose-600';
const isDeleteDisabled = (exp) => isTaskActive(exp);

watch(() => [props.trainingTask?.id, props.workflowId, props.exportTaskId, props.datasetId], () => {
  resetExportResultState();
  ensureRuntimeProfile().catch(() => {});
  loadExportTask().catch(() => {});
  loadExports().catch(() => {});
}, { immediate: true });

watch(() => exportConfig.format, () => {
  if (!exportOptionSupport.value.half) exportConfig.half = false;
  if (!exportOptionSupport.value.int8) exportConfig.int8 = false;
}, { immediate: true });

watch(exportProfile, (profile) => {
  const selected = exportFormatOptions.value.find((item) => item.value === exportConfig.format);
  if (!selected) {
    exportConfig.format = profile?.default_format || 'onnx';
  }
}, { immediate: true });

watch(exportFormatOptions, (options) => {
  const selected = options.find((item) => item.value === exportConfig.format);
  if (selected?.disabled) {
    exportConfig.format = exportProfile.value.default_format || 'onnx';
  }
}, { immediate: true });

onBeforeUnmount(() => {
  stopPolling();
});
</script>
