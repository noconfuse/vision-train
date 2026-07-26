<template>
  <div class="bg-white p-4 text-slate-800 h-full min-h-0 flex flex-col overflow-hidden">
    <div class="grid flex-1 min-h-0 gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
      <section class="min-h-0 flex flex-col">
        <div class="vt-step-section-title mb-4 shrink-0">部署模板参数</div>
        <div class="flex-1 min-h-0 overflow-y-auto pr-1">
          <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label class="block text-[11px] font-medium tracking-wide text-gray-500 mb-2">源模型</label>
              <select v-model="config.source" class="vt-select">
                <option v-for="option in sourceOptions" :key="option.key" :value="option.key" :disabled="!option.available">
                  {{ option.label }}
                </option>
              </select>
              <div v-if="!hasUsableSource" class="mt-1 text-xs text-rose-600">
                当前训练任务没有可用权重，无法生成模板
              </div>
            </div>
            <div>
              <label class="block text-[11px] font-medium tracking-wide text-gray-500 mb-2">模板类型</label>
              <select v-model="config.templateType" class="vt-select">
                <option v-for="spec in templateSpecs" :key="spec.template_type" :value="spec.template_type">
                  {{ spec.label }}
                </option>
              </select>
            </div>
          </div>
          <div v-if="selectedSpec" class="mt-3 text-xs text-slate-500">
            {{ selectedSpec.description }}
          </div>
          <div v-if="selectedSpec" class="mt-3 text-xs text-slate-500">
            <div>源模型格式：<span class="font-mono">{{ config.sourceFormat }}</span></div>
            <div>入口点：<span class="font-mono">{{ selectedSpec.entrypoint }}</span></div>
            <div class="mt-1 text-slate-400">仅开发环境提示：使用 pt 模板时，部署机需要安装匹配的 PyTorch / Ultralytics。</div>
          </div>
        </div>
      </section>

      <section class="min-h-0 flex flex-col">
        <div class="shrink-0 mb-3 flex items-center justify-between gap-3">
          <div class="vt-step-section-title mb-0">部署模板记录</div>
          <div class="vt-count-badge">{{ displayRecords.length }}</div>
        </div>
        <div class="flex-1 min-h-0 overflow-y-auto pr-1">
          <div v-if="!displayRecords.length" class="h-full min-h-[12rem] flex items-center justify-center text-sm text-gray-400 border border-dashed border-gray-300 bg-white">
            暂无部署模板记录
          </div>
          <div v-else class="space-y-2">
            <article
              v-for="record in displayRecords"
              :key="record.task_id"
              class="vt-record-card"
              :class="isCurrentTemplateRecord(record) ? 'vt-record-card--active' : ''"
            >
              <div class="vt-record-header">
                <div class="vt-record-main">
                  <div class="vt-record-title">{{ record.template_label || record.template_type }}</div>
                  <div class="vt-record-meta">
                    {{ formatRecordMeta(record) }}
                  </div>
                </div>
                <div class="vt-record-side">
                  <div class="vt-record-badges">
                    <span
                      v-if="isCurrentTemplateRecord(record)"
                      class="vt-tag vt-tag--sm vt-tag-info"
                    >
                      当前生成
                    </span>
                    <span
                      v-if="record.status"
                      class="vt-tag vt-tag--sm"
                      :class="getTaskStatusTagClass(record.status)"
                    >
                      {{ getTaskStatusLabel(record.status) }}
                    </span>
                  </div>
                </div>
              </div>

              <div v-if="showRecordProgress(record)" class="vt-record-progress">
                <div class="mb-1.5 flex items-center justify-between gap-3">
                  <div class="text-[11px] font-medium text-slate-700">生成进度</div>
                  <div class="text-[11px] font-mono text-slate-600">{{ getRecordProgress(record) }}%</div>
                </div>
                <div class="vt-meter h-2 border border-gray-200">
                  <div
                    class="vt-meter__bar"
                    :class="getTaskProgressBarClass(record.status)"
                    :style="{ width: `${getRecordProgress(record)}%` }"
                  ></div>
                </div>
              </div>

              <div
                v-if="getRecordError(record)"
                class="vt-note mt-1.5 whitespace-pre-wrap break-words"
                :class="getRecordErrorClass(record)"
              >
                {{ getRecordError(record) }}
              </div>

              <div class="vt-record-actions">
                <a
                  v-if="record.template_bundle_url"
                  :href="record.template_bundle_url"
                  :download="getTemplateBundleDownloadFilename(record)"
                  target="_blank"
                  class="vt-btn-secondary vt-btn-size-sm"
                >
                  <AppIcon name="download" class="h-3.5 w-3.5" />
                  <span>下载{{ record.template_label || '部署模板' }}</span>
                </a>
                <UiTooltip side="top">
                  <template #trigger>
                    <AsyncButton
                      class="vt-icon-btn vt-icon-btn--sm vt-icon-btn--danger"
                      :disabled="isDeleteDisabled(record)"
                      :pending="isActionPending(deleteActionKey(record))"
                      @click="deleteTemplateRecord(record)"
                    >
                      <AppIcon name="delete" class="h-3.5 w-3.5" />
                    </AsyncButton>
                  </template>
                  {{ isActionPending(deleteActionKey(record)) ? '删除中...' : '删除记录' }}
                </UiTooltip>
              </div>
            </article>
          </div>
        </div>
      </section>
    </div>

    <div class="mt-4 pt-4 border-t border-gray-200 flex flex-wrap items-center justify-end gap-2 shrink-0">
      <AsyncButton
        @click="startTemplate"
        class="vt-btn-solid-primary vt-btn-size-lg"
        :disabled="!canStart"
        :pending="isActionPending(START_ACTION_KEY) || isTemplateRunning"
        loading-text="生成中..."
      >
        <AppIcon name="template" class="h-4 w-4" />
        生成{{ selectedSpec?.label || '部署模板' }}
      </AsyncButton>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import api from '../api';
import { useApiCall } from '../composables/useApiCall';
import { useAsyncAction } from '../composables/useAsyncAction';
import { useConfirm } from '../composables/useConfirm';
import { useToast } from '../composables/useToast';
import AsyncButton from './ui/AsyncButton.vue';
import AppIcon from './ui/AppIcon.vue';
import UiTooltip from './ui/Tooltip.vue';
import { useTrainingWorkflowStore } from '../stores/trainingWorkflow';
import { getTaskProgressBarClass, getTaskStatusLabel, getTaskStatusTagClass, isTaskActive } from '../taskStatus';
import { formatDateTime, getTemplateBundleDownloadFilename } from '../utils';

const props = defineProps({
  projectPath: { type: String, required: true },
  datasetName: { type: String, required: true },
  trainingTask: { type: Object, default: null },
  workflowId: { type: String, default: '' },
  templateTaskId: { type: String, default: '' },
});

const apiCall = useApiCall();
const asyncAction = useAsyncAction();
const { confirm: showConfirm } = useConfirm();
const workflowStore = useTrainingWorkflowStore();
const toast = useToast();

const templateSpecs = ref([]);
const sourceOptions = ref([]);
const records = ref([]);
const currentTemplateTask = ref(null);
let pollTimer = null;

const START_ACTION_KEY = 'training-template:start';
const isActionPending = (key) => asyncAction.isPending(key);
const deleteActionKey = (record) => `training-template:delete:${String(record?.task_id || '')}`;

const config = reactive({
  source: 'best',
  sourceFormat: 'pt',
  sourceModelPath: '',
  templateType: 'fastapi_service',
});

const selectedSpec = computed(() => templateSpecs.value.find((item) => item.template_type === config.templateType) || null);
const hasUsableSource = computed(() => sourceOptions.value.some((item) => item.available));
const isTemplateRunning = computed(() => isTaskActive(currentTemplateTask.value));
const canStart = computed(() => Boolean(
  props.trainingTask?.id
  && hasUsableSource.value
  && !isTemplateRunning.value
));

const displayRecords = computed(() => {
  const list = Array.isArray(records.value) ? [...records.value] : [];
  return list.sort((a, b) => new Date(b?.created_at || 0) - new Date(a?.created_at || 0));
});

const isCurrentTemplateRecord = (record) => String(record?.task_id || '') === String(currentTemplateTask.value?.id || '');
const showRecordProgress = (record) => Boolean(record?.status) && isTaskActive(record) && Number(record?.progress || 0) < 100;
const getRecordProgress = (record) => Number(record?.progress ?? (isCurrentTemplateRecord(record) ? currentTemplateTask.value?.progress : 100) ?? 0);
const isDeleteDisabled = (record) => isTaskActive(record);
const getRecordError = (record) => record?.error || '';
const getRecordErrorClass = () => 'vt-note--error';

const clearPollTimer = () => {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
};

const scheduleTemplatePoll = () => {
  clearPollTimer();
  pollTimer = setTimeout(() => {
    pollTemplateTask().catch(() => {});
  }, 1500);
};

const formatRecordMeta = (record) => {
  const parts = [];
  if (record?.source_format) parts.push(record.source_format);
  if (record?.template_type) parts.push(record.template_type);
  if (record?.created_at) parts.push(formatDateTime(record.created_at));
  return parts.join(' · ');
};

const fetchTemplateSpecs = async () => {
  // 后端暂未提供动态拉取接口，使用稳定规格列表
  templateSpecs.value = [
    {
      template_type: 'fastapi_service',
      label: 'FastAPI 服务',
      description: '容器化 HTTP 推理服务，适合在线 API 部署。',
      runtime_mode: 'http_service',
      entrypoint: 'app.main:app',
    },
    {
      template_type: 'python_sdk',
      label: 'Python SDK',
      description: '嵌入现有 Python 服务或业务代码，直接调用预测器。',
      runtime_mode: 'python_sdk',
      entrypoint: 'sdk.predictor:Predictor',
    },
    {
      template_type: 'batch_processor',
      label: '批处理任务',
      description: '离线批量推理任务模板，适合定时任务与数据回刷。',
      runtime_mode: 'batch_job',
      entrypoint: 'runner.main:main',
    },
  ];
  if (!templateSpecs.value.find((item) => item.template_type === config.templateType)) {
    config.templateType = templateSpecs.value[0]?.template_type || '';
  }
};

const resolveSourceOptions = async () => {
  if (!props.trainingTask?.id || !props.projectPath) {
    sourceOptions.value = [];
    return;
  }
  const list = await api.getTrainingTemplateSourceChoices({
    project_path: props.projectPath,
    training_id: props.trainingTask.id,
  });
  const options = Array.isArray(list) ? list : [];
  sourceOptions.value = options.map((item) => ({
    key: item.key,
    label: item.label,
    format: item.format,
    source_model_path: item.source_model_path || '',
    available: Boolean(item.source_model_path) || ['best', 'last'].includes(item.key),
  }));
  const usable = sourceOptions.value.find((item) => item.available);
  if (usable && !sourceOptions.value.find((item) => item.key === config.source && item.available)) {
    config.source = usable.key;
  }
  const current = sourceOptions.value.find((item) => item.key === config.source);
  config.sourceFormat = current?.format || 'pt';
  if (current?.source_model_path) {
    config.sourceModelPath = current.source_model_path;
  }
};

const fetchRecords = async () => {
  if (!props.trainingTask?.id) {
    records.value = [];
    currentTemplateTask.value = null;
    clearPollTimer();
    return;
  }
  const list = await api.getTrainingTemplates({
    project_path: props.projectPath,
    training_id: props.trainingTask.id,
  });
  records.value = Array.isArray(list) ? list : [];
  const activeRecord = records.value.find((item) => isTaskActive(item));
  if (activeRecord) {
    currentTemplateTask.value = activeRecord;
    scheduleTemplatePoll();
    return;
  }
  currentTemplateTask.value = null;
  clearPollTimer();
};

const startTemplate = async () => {
  if (!canStart.value) return;
  await asyncAction.run(START_ACTION_KEY, async () => {
    const data = await apiCall(api.startTrainingTemplate({
      project_path: props.projectPath,
      task_id: props.trainingTask.id,
      source: config.source,
      source_format: config.sourceFormat,
      source_model_path: config.sourceModelPath,
      template_type: config.templateType,
    }), { errorMsg: '模板生成失败' });
    if (data?.task_id) {
      currentTemplateTask.value = { id: data.task_id, status: 'pending' };
      scheduleTemplatePoll();
    }
    toast.success('模板生成已启动');
  });
};

const pollTemplateTask = async () => {
  if (!currentTemplateTask.value?.id) return;
  await fetchRecords();
  const found = records.value.find((item) => item.task_id === currentTemplateTask.value.id);
  if (found) {
    currentTemplateTask.value = found;
    if (isTaskActive(found)) {
      scheduleTemplatePoll();
    } else {
      clearPollTimer();
      await workflowStore.fetchWorkflows({
        project_path: props.projectPath,
        dataset_id: props.trainingTask?.dataset_id || '',
      }).catch(() => {});
    }
    return;
  }
  currentTemplateTask.value = null;
  clearPollTimer();
};

const deleteTemplateRecord = async (record) => {
  if (!record?.task_id) return;
  const ok = await showConfirm({
    title: '删除部署模板',
    message: '删除后将无法下载该模板包，确认继续？',
    confirmText: '删除',
    danger: true,
  });
  if (!ok) return;
  await asyncAction.run(deleteActionKey(record), async () => {
    await apiCall(api.deleteTrainingTemplate({
      project_path: props.projectPath,
      template_task_id: record.task_id,
    }), { errorMsg: '删除模板记录失败' });
    if (currentTemplateTask.value?.id === record.task_id) {
      currentTemplateTask.value = null;
    }
    await fetchRecords();
  });
};

watch(() => props.trainingTask?.id, async () => {
  await resolveSourceOptions();
  await fetchRecords();
}, { immediate: true });

watch(() => config.source, (value) => {
  const found = sourceOptions.value.find((item) => item.key === value);
  if (found) {
    config.sourceFormat = found.format;
    config.sourceModelPath = found.source_model_path || '';
  }
});

onMounted(() => {
  fetchTemplateSpecs();
});

onBeforeUnmount(() => {
  clearPollTimer();
});
</script>
