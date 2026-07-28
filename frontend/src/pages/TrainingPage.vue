<template>
  <div class="vt-shell">
    <AppHeader :crumbs="[
      { label: projectName, to: { name: 'home-with-project', params: { project: encodeURIComponent(projectName) } } },
      { label: datasetName || '数据集' }
    ]" :back-href="backHref">
      <template #meta>
        <span v-if="dataset" class="vt-tag" :class="getDatasetTypeTagClass(dataset)">{{ getDatasetTypeLabel(dataset) }}</span>
        <div v-if="isTrainingRunning" class="flex items-center gap-2 text-xs text-emerald-700">
          <span class="vt-status-dot vt-status-dot--success h-1.5 w-1.5"></span>
          <span class="font-mono">训练运行中</span>
        </div>
      </template>
    </AppHeader>

    <main class="vt-body overflow-hidden">
      <PageState
        v-if="loading || (!loading && (!dataset || loadError))"
        :loading="loading"
        :error="!loading ? loadError : ''"
        :empty="!loading && !dataset && !loadError"
        empty-icon="🚀"
        empty-text="无法进入训练"
        loading-text="加载中..."
        @back="goBack"
      />

      <div v-else class="flex flex-1 min-h-0 gap-3 p-3 overflow-hidden">
        <section class="flex-1 min-w-0 min-h-0 flex flex-col overflow-hidden">
          <div v-if="hasWorkflowContext && !isArchivedWorkflowSelected" class="mb-3 shrink-0 bg-white px-1 py-2">
            <div class="flex items-center gap-2 overflow-x-auto pb-1">
              <template v-for="(step, index) in workflowSteps" :key="step.key">
                <button
                  class="vt-step-button"
                  :class="stepButtonClass(step)"
                  :disabled="!step.enabled"
                  @click="goToWorkflowStep(step.key)"
                >
                  <div class="flex items-center gap-2 whitespace-nowrap">
                    <span
                      class="vt-step-dot"
                      :class="stepDotClass(step)"
                    >
                      {{ stepDotLabel(step) }}
                    </span>
                    <span class="text-sm font-medium">{{ step.title }}</span>
                    <span v-if="step.optional" class="text-[10px] text-amber-700">可跳过</span>
                  </div>
                </button>
                <div
                  v-if="index < workflowSteps.length - 1"
                  class="vt-step-connector"
                  :class="stepConnectorClass(step)"
                ></div>
              </template>
            </div>
          </div>

          <div v-if="isArchivedWorkflowSelected" class="flex-1 min-h-0 bg-white border border-dashed border-gray-300 px-8 py-10 flex items-center justify-center">
            <div class="max-w-md text-center">
              <div class="text-3xl leading-none text-slate-300">#</div>
              <div class="mt-4 text-base font-semibold text-slate-800">该工作流已归档</div>
              <div class="mt-2 text-sm leading-6 text-gray-500">归档后的工作流不再参与训练流程。如需彻底清理，请切到“已归档”列表后执行永久删除。</div>
            </div>
          </div>

          <TrainingPanel
            v-else-if="hasWorkflowContext && workflowStep === WORKFLOW_STEP.CONFIG"
            :key="dataset.path"
            :workflow-id="selectedWorkflow?.id || ''"
            @training-started="onTrainingStarted"
            @workflow-bound="onWorkflowBound"
            @show-task-detail="goToWorkflowStep(WORKFLOW_STEP.DETAIL)"
          />
          <TrainingTaskDetail
            v-else-if="workflowStep === WORKFLOW_STEP.DETAIL && workflowTrainingTask"
            :project-path="project?.path || ''"
            :project-name="projectName"
            :dataset-name="datasetName"
            :task="workflowTrainingTask"
            :can-open-evaluate="hasEvaluateStep"
            :has-test-split="hasDatasetTest"
            @training-started="onTrainingStarted"
            @evaluate="goToWorkflowStep(WORKFLOW_STEP.EVALUATE)"
            @export="goToWorkflowStep(WORKFLOW_STEP.EXPORT_CONFIG)"
          />
          <TrainingEvaluateStep
            v-else-if="workflowStep === WORKFLOW_STEP.EVALUATE && workflowTrainingTask"
            :project-path="project?.path || ''"
            :dataset-id="dataset?.dataset_id || ''"
            :dataset-name="datasetName"
            :workflow-id="selectedWorkflow?.id || ''"
            :training-task="workflowTrainingTask"
            :has-test-split="hasDatasetTest"
            @export="goToWorkflowStep(WORKFLOW_STEP.EXPORT_CONFIG)"
          />
          <TrainingExportStep
            v-else-if="workflowStep === WORKFLOW_STEP.EXPORT_CONFIG && workflowTrainingTask"
            :project-path="project?.path || ''"
            :dataset-id="dataset?.dataset_id || ''"
            :dataset-name="datasetName"
            :workflow-id="selectedWorkflow?.id || ''"
            :training-task="workflowTrainingTask"
            @deployment-template="goToDeploymentTemplate"
          />
          <TrainingTemplateStep
            v-else-if="workflowStep === WORKFLOW_STEP.DEPLOYMENT_TEMPLATE && workflowTrainingTask"
            :project-path="project?.path || ''"
            :dataset-name="datasetName"
            :workflow-id="selectedWorkflow?.id || ''"
            :training-task="workflowTrainingTask"
          />
          <div v-else-if="hasWorkflowContext" class="flex-1 min-h-0 bg-white border border-dashed border-gray-300 px-8 py-10 flex items-center justify-center">
            <div class="max-w-md text-center">
              <div class="text-3xl leading-none text-slate-300">...</div>
              <div class="mt-4 text-sm font-medium text-slate-700">当前工作流还没有训练记录</div>
              <div class="mt-2 text-sm text-gray-500">先在“训练配置”步骤启动训练，这里会持续展示任务进度、测试集评估（需数据集提供 test 划分）和导出结果。</div>
            </div>
          </div>
          <div v-else class="flex-1 min-h-0 bg-white border border-dashed border-gray-300 px-8 py-10 flex items-center justify-center">
            <div class="max-w-md text-center">
              <div class="text-4xl leading-none text-slate-300">+</div>
              <div class="mt-4 text-base font-semibold text-slate-800">尚未选择工作流</div>
              <div class="mt-2 text-sm leading-6 text-gray-500">请先选择一条工作流记录，或点击“新建工作流”开始新的训练流程。</div>
              <div class="mt-5 flex justify-center">
                <button
                  type="button"
                  class="vt-btn-solid-primary vt-btn-size-md"
                  @click="openCreateWorkflow"
                >
                  <AppIcon name="createProject" class="h-4 w-4" />
                  <span>新建工作流</span>
                </button>
              </div>
            </div>
          </div>
        </section>

        <aside class="w-72 shrink-0 min-h-0 flex flex-col gap-3">
          <div class="max-h-[22rem] shrink-0 bg-white border border-slate-300 p-3 flex flex-col overflow-hidden">
            <div class="flex items-start justify-between gap-2 mb-2.5">
              <div>
                <div class="text-sm font-semibold text-slate-900">工作流记录</div>
                <div class="mt-1.5 flex items-center gap-1.5 text-xs">
                  <button
                    class="vt-segmented-tab vt-segmented-tab--compact"
                    :class="{ 'vt-segmented-tab--active': !showArchivedWorkflows }"
                    @click="setWorkflowArchivedView(false)"
                  >
                    当前
                  </button>
                  <button
                    class="vt-segmented-tab vt-segmented-tab--compact"
                    :class="{ 'vt-segmented-tab--active': showArchivedWorkflows }"
                    @click="setWorkflowArchivedView(true)"
                  >
                    已归档
                  </button>
                </div>
              </div>
              <div class="vt-count-badge shrink-0">
                {{ trainingWorkflows.length }}
              </div>
            </div>
            <div v-if="!showArchivedWorkflows" class="mb-3 shrink-0">
              <button
                type="button"
                class="vt-btn-solid-primary vt-btn-size-md w-full justify-between"
                :class="isCreatingWorkflow ? 'shadow-sm ring-1 ring-[color:var(--vt-color-primary-border)]' : ''"
                @click="openCreateWorkflow"
              >
                <span class="inline-flex items-center gap-2">
                  <AppIcon name="createProject" class="h-4 w-4" />
                  <span>{{ isCreatingWorkflow ? '正在新建工作流' : '新建工作流' }}</span>
                </span>
                <span class="text-[11px] font-medium text-white/80">
                  {{ isCreatingWorkflow ? '已进入配置' : '开始训练流程' }}
                </span>
              </button>
              
            </div>
            <div v-if="workflowsLoading" class="text-xs text-gray-400 py-4 text-center">加载中...</div>
            <div v-else class="flex-1 min-h-0 space-y-1.5 overflow-y-auto pr-1">
              <div v-if="trainingWorkflows.length === 0" class="text-xs text-gray-400 py-2 text-center">
                {{ showArchivedWorkflows ? '暂无已归档工作流' : '暂无工作流记录' }}
              </div>
              <div
                v-for="workflow in trainingWorkflows"
                :key="workflow.id"
                class="vt-choice-card vt-choice-card--compact w-full"
                :class="selectedWorkflow?.id === workflow.id && !isCreatingWorkflow ? 'vt-choice-card--selected' : 'vt-choice-card--interactive'"
                role="button"
                tabindex="0"
                @click="selectTrainingWorkflow(workflow)"
                @keydown.enter.prevent="selectTrainingWorkflow(workflow)"
                @keydown.space.prevent="selectTrainingWorkflow(workflow)"
              >
                <div class="w-full text-left">
                  <div class="flex items-start justify-between gap-2">
                    <div class="min-w-0">
                      <div class="text-[13px] font-semibold text-slate-800 truncate">
                        {{ getWorkflowTitle(workflow) }}
                      </div>
                      <div
                        v-if="!workflow.is_archived && workflow.latest_training_task_resume_available === false && workflow.status === TASK_STATUS.FAILED"
                        class="vt-note vt-note--warn mt-0.5"
                      >
                        不可继续，需重新训练
                      </div>
                    </div>
                    <span
                      class="vt-tag vt-tag--sm shrink-0"
                      :class="workflow.is_archived ? '' : getTaskStatusTagClass(workflow.status)"
                    >
                      {{ workflow.is_archived ? '已归档' : getTaskStatusLabel(workflow.status) }}
                    </span>
                  </div>
                  <div class="mt-1.5 flex items-center justify-between gap-2 text-[10px] text-gray-400">
                    <span class="min-w-0 flex flex-wrap items-center gap-x-2 gap-y-0.5">
                      <span>创建 {{ formatRunTime(workflow.created_at) }}</span>
                      <span v-if="workflow.is_archived && workflow.archived_at">归档 {{ formatRunTime(workflow.archived_at) }}</span>
                    </span>
                    <span>
                      训 {{ workflow.summary?.training_count || 0 }}
                      · 评 {{ workflow.summary?.evaluate_count || 0 }}
                      · 导 {{ workflow.summary?.export_count || 0 }}
                    </span>
                  </div>
                </div>
                <div class="mt-1.5 flex justify-end">
                  <UiTooltip
                    v-if="!showArchivedWorkflows"
                    side="top"
                    content-class="max-w-[16rem] text-left"
                  >
                    <template #trigger>
                      <AsyncButton
                        class="vt-icon-btn vt-icon-btn--sm text-slate-500 hover:text-slate-800"
                        :disabled="isWorkflowActive(workflow)"
                        :pending="isActionPending(archiveWorkflowActionKey(workflow.id))"
                        @click.stop="archiveWorkflow(workflow)"
                      >
                        <AppIcon name="archive" class="h-3.5 w-3.5" />
                      </AsyncButton>
                    </template>
                    归档工作流
                  </UiTooltip>
                  <UiTooltip
                    v-else
                    side="top"
                    content-class="max-w-[16rem] text-left"
                  >
                    <template #trigger>
                      <AsyncButton
                        class="vt-icon-btn vt-icon-btn--sm vt-icon-btn--danger"
                        :disabled="isWorkflowActive(workflow)"
                        :pending="isActionPending(deleteWorkflowActionKey(workflow.id))"
                        @click.stop="deleteWorkflow(workflow)"
                      >
                        <AppIcon name="delete" class="h-3.5 w-3.5" />
                      </AsyncButton>
                    </template>
                    永久删除工作流
                  </UiTooltip>
                </div>
              </div>
            </div>
          </div>

          <div class="shrink-0 bg-white border border-gray-200 p-4">
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <div class="text-xs text-gray-500 mb-1">数据集</div>
                <UiTooltip
                  side="bottom"
                  align="start"
                  content-class="max-w-[24rem] break-all text-left"
                >
                  <template #trigger>
                    <div class="text-sm font-semibold text-slate-900 truncate">{{ datasetName }}</div>
                  </template>
                  {{ datasetName }}
                </UiTooltip>
                <div class="mt-2">
                  <span class="text-xs text-gray-500">当前版本</span>
                  <div class="font-mono text-[11px] text-slate-700 break-all mt-0.5">{{ currentVersionDisplay }}</div>
                </div>
              </div>
            </div>
            <div class="grid grid-cols-4 gap-3 mt-4">
              <div>
                <div class="text-xs text-gray-500">总样本</div>
                <div class="text-base font-mono text-slate-800">{{ dataset.image_count ?? '-' }}</div>
              </div>
              <div>
                <div class="text-xs text-gray-500">已标注</div>
                <div class="text-base font-mono text-slate-800">{{ dataset.annotated_count ?? dataset.label_count ?? '-' }}</div>
              </div>
              <div>
                <div class="text-xs text-gray-500">未标注</div>
                <div class="text-base font-mono text-slate-800">{{ dataset.unannotated_count ?? '-' }}</div>
              </div>
              <div>
                <div class="text-xs text-gray-500">类别数</div>
                <div class="text-base font-mono text-slate-800">{{ dataset.classes?.length ?? '-' }}</div>
              </div>
            </div>
          </div>

          <div v-if="dataset.classes && dataset.classes.length" class="flex-1 min-h-0 bg-white border border-gray-200 p-4 flex flex-col overflow-hidden">
            <div class="text-xs text-gray-500 mb-2 shrink-0">类别分布</div>
            <div class="flex-1 min-h-0 space-y-1.5 overflow-y-auto pr-1">
              <div v-for="c in classDistribution" :key="c.id ?? c.name"
                   class="flex items-center gap-2 text-xs">
                <UiTooltip
                  side="top"
                  align="start"
                  content-class="max-w-[20rem] break-all text-left"
                >
                  <template #trigger>
                    <span class="w-16 truncate font-mono text-slate-700">{{ c.name }}</span>
                  </template>
                  {{ c.name }}
                </UiTooltip>
                <div class="vt-meter flex-1 h-2">
                  <div class="vt-meter__bar vt-meter__bar--info"
                       :style="{ width: `${(c.percentage ?? 0).toFixed(1)}%` }"></div>
                </div>
                <span class="w-16 text-right font-mono text-gray-600 shrink-0">
                  {{ c.count ?? '-' }} · {{ c.percentage?.toFixed(1) ?? '0.0' }}%
                </span>
              </div>
              <div v-if="hiddenClassCount > 0" class="text-[10px] text-gray-400 text-center pt-1">
                + {{ hiddenClassCount }} 个类别未显示
              </div>
            </div>
          </div>
        </aside>
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, watch, ref, onBeforeUnmount } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useMainStore } from '../stores/main';
import { useTrainingStore } from '../stores/training';
import { useTrainingWorkflowStore } from '../stores/trainingWorkflow';
import { useConfirm } from '../composables/useConfirm';
import { useToast } from '../composables/useToast';
import TrainingPanel from '../components/TrainingPanel.vue';
import TrainingTaskDetail from '../components/TrainingTaskDetail.vue';
import TrainingEvaluateStep from '../components/TrainingEvaluateStep.vue';
import TrainingExportStep from '../components/TrainingExportStep.vue';
import TrainingTemplateStep from '../components/TrainingTemplateStep.vue';
import PageState from '../components/PageState.vue';
import AppHeader from '../components/AppHeader.vue';
import AppIcon from '../components/ui/AppIcon.vue';
import AsyncButton from '../components/ui/AsyncButton.vue';
import UiTooltip from '../components/ui/Tooltip.vue';
import { getDatasetTypeLabel, getDatasetTypeTagClass } from '../domain/dataset/datasetType';
import { TASK_STATUS, getTaskStatusLabel, getTaskStatusTagClass, isTaskActive, isTaskCompleted, isTaskTerminal } from '../domain/task/taskStatus';
import { isTrainingTask } from '../domain/task/taskType';
import { formatDateTime } from '../utils';
import { WORKFLOW_STEP, normalizeWorkflowStep } from '../utils/trainingWorkflow';
import { useAsyncAction } from '../composables/useAsyncAction';
import { resolveTrainingDatasetGuard } from '../utils/trainingActionGuards';

const route = useRoute();
const router = useRouter();
const store = useMainStore();
const trainingStore = useTrainingStore();
const workflowStore = useTrainingWorkflowStore();
const { confirm: showConfirm } = useConfirm();
const toast = useToast();
const asyncAction = useAsyncAction();

const projectName = computed(() => decodeURIComponent(route.params.project || ''));
const routeDatasetName = computed(() => decodeURIComponent(route.params.name || ''));
const routeDatasetId = computed(() => String(route.query.dataset_id || '').trim());
const project = computed(() => store.projects.find(p => p.name === projectName.value) || null);
const dataset = computed(() => {
  const p = project.value;
  if (!p || !routeDatasetId.value) return null;
  return (p.datasets || []).find((item) => item.dataset_id === routeDatasetId.value) || null;
});
const datasetName = computed(() => dataset.value?.name || routeDatasetName.value);
const trainingGuard = computed(() => resolveTrainingDatasetGuard(dataset.value));
const currentVersionDisplay = computed(() => {
  if (dataset.value?.current_version_id) return dataset.value.current_version_id;
  if (dataset.value?.versioning_status === 'pending') return '首版快照中';
  if (dataset.value?.versioning_status === 'failed') return '首版快照失败';
  return '-';
});

const loadError = ref('');
const loading = ref(true);
const selectedWorkflow = ref(null);
const isCreatingWorkflow = ref(false);
const showArchivedWorkflows = ref(false);
const archiveWorkflowActionKey = (workflowId) => `training-page:archive-workflow:${String(workflowId || '')}`;
const deleteWorkflowActionKey = (workflowId) => `training-page:delete-workflow:${String(workflowId || '')}`;
const isActionPending = (key) => asyncAction.isPending(key);

// === 类别分布（按 count 倒序，最多显示 12 个） ===
const MAX_CLASSES_SHOWN = 12;
const classDistribution = computed(() => {
  const cls = dataset.value?.classes;
  if (!Array.isArray(cls)) return [];
  const sorted = [...cls].sort((a, b) => (b.count ?? 0) - (a.count ?? 0));
  return sorted.slice(0, MAX_CLASSES_SHOWN);
});
const hiddenClassCount = computed(() => {
  const total = dataset.value?.classes?.length ?? 0;
  return Math.max(0, total - MAX_CLASSES_SHOWN);
});
const backHref = computed(() => {
  const raw = route.query.return_to;
  if (typeof raw === 'string' && raw.trim()) return raw;
  return {
    name: 'dataset-detail',
    params: {
      project: encodeURIComponent(projectName.value),
      name: encodeURIComponent(datasetName.value),
    },
    query: {
      dataset_id: dataset.value?.dataset_id || '',
    },
  };
});
const routeWorkflowId = computed(() => String(route.query.workflow_id || ''));
const routeDraft = computed(() => String(route.query.draft || '') === '1');
const workflowListKey = computed(() => workflowStore.getDatasetCacheKey({
  project_path: project.value?.path || '',
  dataset_id: dataset.value?.dataset_id || '',
  archived_only: showArchivedWorkflows.value,
}));
const trainingWorkflows = computed(() => workflowStore.workflowLists[workflowListKey.value] || []);
const workflowsLoading = computed(() => !!workflowStore.workflowLoading[workflowListKey.value]);

const hasCurrentTaskForPage = computed(() => {
  const task = trainingStore.currentTask;
  if (!task) return false;
  return isTrainingTask(task) && task.dataset_id === dataset.value?.dataset_id;
});
const isTrainingRunning = computed(() => hasCurrentTaskForPage.value && isTaskActive(trainingStore.currentTask));

const workflowTrainingTask = computed(() => selectedWorkflow.value?.latest_training_task || null);
const hasDatasetTest = computed(() => !!dataset.value?.has_test);
const hasEvaluateStep = computed(() => hasDatasetTest.value || !!selectedWorkflow.value?.latest_evaluate_task?.id);
const hasWorkflowContext = computed(() => isCreatingWorkflow.value || Boolean(selectedWorkflow.value?.id));
const isArchivedWorkflowSelected = computed(() => !!selectedWorkflow.value?.is_archived);

const routeWorkflowStep = computed(() => normalizeWorkflowStep(String(route.query.step || WORKFLOW_STEP.CONFIG)));
const workflowTaskCompleted = computed(() => isTaskCompleted(selectedWorkflow.value?.latest_training_task));
const workflowStepOrder = [
  WORKFLOW_STEP.CONFIG,
  WORKFLOW_STEP.DETAIL,
  WORKFLOW_STEP.EVALUATE,
  WORKFLOW_STEP.EXPORT_CONFIG,
  WORKFLOW_STEP.DEPLOYMENT_TEMPLATE,
];
const resolveWorkflowStep = (step, task = workflowTrainingTask.value) => {
  const normalized = normalizeWorkflowStep(step);
  if (!hasWorkflowContext.value) return WORKFLOW_STEP.CONFIG;
  if (normalized !== WORKFLOW_STEP.CONFIG && !task?.id) return WORKFLOW_STEP.CONFIG;
  if (normalized === WORKFLOW_STEP.EVALUATE && !hasEvaluateStep.value) return workflowBaseStep(task);
  if ([WORKFLOW_STEP.EVALUATE, WORKFLOW_STEP.EXPORT_CONFIG].includes(normalized) && !isTaskCompleted(task)) {
    return workflowBaseStep(task);
  }
  return normalized;
};
const workflowStep = computed(() => resolveWorkflowStep(routeWorkflowStep.value));
const workflowCurrentIndex = computed(() => workflowStepOrder.indexOf(workflowStep.value));
const workflowSteps = computed(() => {
  const definitions = [
    {
      key: WORKFLOW_STEP.CONFIG,
      title: '训练配置',
      optional: false,
      enabled: hasWorkflowContext.value,
    },
    {
      key: WORKFLOW_STEP.DETAIL,
      title: '任务详情',
      optional: false,
      enabled: Boolean(workflowTrainingTask.value),
    },
    {
      key: WORKFLOW_STEP.EVALUATE,
      title: '测试集评估',
      optional: true,
      enabled: workflowTaskCompleted.value && hasEvaluateStep.value,
    },
    {
      key: WORKFLOW_STEP.EXPORT_CONFIG,
      title: '模型导出',
      optional: false,
      enabled: workflowTaskCompleted.value,
    },
    {
      key: WORKFLOW_STEP.DEPLOYMENT_TEMPLATE,
      title: '部署模板',
      optional: false,
      enabled: workflowTaskCompleted.value,
    },
  ];
  return definitions.map((step, index) => {
    const isCurrent = workflowStep.value === step.key;
    const isCompleted = step.enabled && workflowCurrentIndex.value > index;
    const isLocked = !step.enabled;
    return {
      ...step,
      index,
      isCurrent,
      isCompleted,
      isLocked,
    };
  });
});
const stepButtonClass = (step) => {
  if (step.isCurrent) return 'vt-step-button--current';
  if (step.isCompleted) return 'vt-step-button--completed';
  if (step.isLocked) return 'vt-step-button--locked';
  return 'vt-step-button--idle';
};
const stepDotClass = (step) => {
  if (step.isCurrent) return 'vt-step-dot--current';
  if (step.isCompleted) return 'vt-step-dot--completed';
  if (step.isLocked) return 'vt-step-dot--locked';
  return 'vt-step-dot--idle';
};
const stepDotLabel = (step) => {
  if (step.isCompleted) return '✓';
  return String(step.index + 1);
};
const stepConnectorClass = (step) => (step.isCompleted ? 'vt-step-connector--completed' : step.isCurrent ? 'vt-step-connector--current' : '');
const formatRunTime = (iso) => formatDateTime(iso, { dateStyle: 'compact' });
const getWorkflowTitle = (workflow) => {
  const payload = workflow?.latest_training_task?.payload || {};
  const rawModel = String(payload.model_name || payload.model_path || '').trim();
  if (!rawModel) return '未开始训练';
  const baseName = rawModel.split('/').pop()?.split('\\').pop() || rawModel;
  const normalized = baseName.replace(/\.(pt|pth|onnx|engine|xml)$/i, '');
  return `训练模型 · ${normalized || baseName}`;
};
const isWorkflowActive = (workflow) => isTaskActive(workflow?.active_task?.status || workflow?.status);
const workflowBaseStep = (task) => (task?.id ? WORKFLOW_STEP.DETAIL : WORKFLOW_STEP.CONFIG);
const setWorkflowContext = (workflow = null, { creating = false, archived = showArchivedWorkflows.value } = {}) => {
  selectedWorkflow.value = workflow;
  isCreatingWorkflow.value = creating;
  showArchivedWorkflows.value = archived;
  return workflow;
};
const selectWorkflowById = (workflowId) => {
  if (!workflowId) return selectedWorkflow.value;
  const workflow = trainingWorkflows.value.find((item) => item.id === workflowId)
    || workflowStore.getWorkflowFromState({
      project_path: project.value?.path || '',
      dataset_id: dataset.value?.dataset_id || '',
      workflow_id: workflowId,
      include_archived: true,
    })
    || selectedWorkflow.value;
  if (workflow) {
    setWorkflowContext(workflow, { archived: !!workflow.is_archived });
  }
  return workflow;
};
const refreshWorkflowList = async (workflowId = '') => {
  await loadTrainingWorkflows().catch(() => {});
  return selectWorkflowById(workflowId);
};

// === Page sync ===
const syncStore = () => {
  if (project.value && store.currentProject?.path !== project.value.path) {
    store.selectProject(project.value);
  }
  if (dataset.value && store.selectedDataset?.path !== dataset.value.path) {
    store.selectDataset(dataset.value);
  }
};

const goBack = () => {
  router.push({
    name: 'dataset-detail',
    params: {
      project: encodeURIComponent(projectName.value),
      name: encodeURIComponent(datasetName.value),
    },
    query: {
      dataset_id: dataset.value?.dataset_id || '',
    },
  });
};

const syncPageState = async () => {
  loading.value = true;
  loadError.value = '';
  if (dataset.value) {
    syncStore();
    if (!trainingGuard.value.enabled) {
      loadError.value = trainingGuard.value.reason;
    } else {
      await loadTrainingWorkflows().catch(() => {});
    }
  } else if (project.value) {
    const target = datasetName.value || routeDatasetId.value || '未知数据集';
    loadError.value = `项目「${projectName.value}」下找不到数据集「${target}」`;
  } else {
    loadError.value = `项目「${projectName.value}」不存在`;
  }
  loading.value = false;
};

const loadTrainingWorkflows = async () => {
  if (!project.value?.path || !dataset.value?.dataset_id) {
    workflowStore.invalidateDataset({
      project_path: project.value?.path || '',
      dataset_id: dataset.value?.dataset_id || '',
    });
    return;
  }
  await workflowStore.fetchWorkflows({
    project_path: project.value.path,
    dataset_id: dataset.value.dataset_id,
    archived_only: showArchivedWorkflows.value,
  });
};

const replaceWorkflowQuery = async (step = WORKFLOW_STEP.CONFIG, workflowId = '') => {
  const nextQuery = { ...route.query };
  const normalized = normalizeWorkflowStep(step);
  if (normalized === WORKFLOW_STEP.CONFIG) {
    delete nextQuery.step;
  } else {
    nextQuery.step = normalized;
  }
  if (workflowId) {
    nextQuery.workflow_id = workflowId;
    delete nextQuery.draft;
  } else {
    delete nextQuery.workflow_id;
    if (isCreatingWorkflow.value) {
      nextQuery.draft = '1';
    } else {
      delete nextQuery.draft;
    }
  }
  delete nextQuery.export_task_id;
  await router.replace({
    name: route.name,
    params: route.params,
    query: nextQuery,
  });
};

const loadSelectedWorkflow = async () => {
  if (!routeWorkflowId.value) {
    setWorkflowContext(null, {
      creating: routeDraft.value,
      archived: routeDraft.value ? false : showArchivedWorkflows.value,
    });
    return;
  }
  const existingWorkflow = routeWorkflowId.value
    ? trainingWorkflows.value.find((item) => item.id === routeWorkflowId.value)
    : null;
  if (existingWorkflow) {
    setWorkflowContext(existingWorkflow, { archived: !!existingWorkflow.is_archived });
    return;
  }
  const storedWorkflow = workflowStore.getWorkflowFromState({
    project_path: project.value?.path || '',
    dataset_id: dataset.value?.dataset_id || '',
    workflow_id: routeWorkflowId.value,
    include_archived: true,
  });
  if (storedWorkflow?.id) {
    setWorkflowContext(storedWorkflow, { archived: !!storedWorkflow.is_archived });
    return;
  }
  if (workflowsLoading.value) return;
  if (routeWorkflowId.value && project.value?.path) {
    const workflow = await workflowStore.fetchWorkflowDetail({
      project_path: project.value.path,
      dataset_id: dataset.value?.dataset_id || '',
      workflow_id: routeWorkflowId.value,
      include_archived: true,
    });
    if (workflow?.id) {
      setWorkflowContext(workflow, { archived: !!workflow.is_archived });
      return;
    }
  }
  setWorkflowContext(null, {
    creating: routeDraft.value,
    archived: routeDraft.value ? false : showArchivedWorkflows.value,
  });
};

const openCreateWorkflow = async () => {
  setWorkflowContext(null, { creating: true, archived: false });
  await replaceWorkflowQuery(WORKFLOW_STEP.CONFIG, '');
};

const selectTrainingWorkflow = async (workflow) => {
  if (!workflow?.id) return;
  setWorkflowContext(workflow, { archived: !!workflow.is_archived });
  const nextStep = workflow.latest_training_task ? (workflow.current_step || WORKFLOW_STEP.DETAIL) : WORKFLOW_STEP.CONFIG;
  await replaceWorkflowQuery(nextStep, workflow.id);
};

const goToWorkflowStep = async (step) => {
  const normalized = resolveWorkflowStep(step);
  const workflowId = selectedWorkflow.value?.id || '';
  await replaceWorkflowQuery(normalized, workflowId);
};

const goToDeploymentTemplate = async () => {
  await goToWorkflowStep(WORKFLOW_STEP.DEPLOYMENT_TEMPLATE);
};

const setWorkflowArchivedView = async (value) => {
  if (showArchivedWorkflows.value === value) return;
  showArchivedWorkflows.value = value;
  isCreatingWorkflow.value = false;
  const shouldClearSelection = !selectedWorkflow.value?.id || (!!selectedWorkflow.value?.is_archived !== value);
  if (shouldClearSelection) {
    setWorkflowContext(null, { archived: value });
    await replaceWorkflowQuery(WORKFLOW_STEP.CONFIG, '');
  }
  await refreshWorkflowList();
};

const archiveWorkflow = async (workflow) => {
  if (!workflow?.id) return;
  if (isWorkflowActive(workflow)) {
    toast.warn('请先停止工作流中的运行任务');
    return;
  }
  const ok = await showConfirm({
    title: '归档工作流',
    message: '归档后会从当前工作流列表中隐藏，但会保留该工作流关联的训练任务与产物。',
    confirmText: '归档',
  });
  if (!ok) return;
  await asyncAction.run(archiveWorkflowActionKey(workflow.id), async () => {
    try {
      const archivedWorkflow = await workflowStore.archiveWorkflow({
        project_path: project.value?.path || '',
        workflow_id: workflow.id,
      }, {
        dataset_id: dataset.value?.dataset_id || '',
      });
      setWorkflowContext(archivedWorkflow, { archived: true });
      await refreshWorkflowList(archivedWorkflow.id);
      await replaceWorkflowQuery(WORKFLOW_STEP.CONFIG, archivedWorkflow.id);
      toast.success('工作流已归档');
    } catch (err) {
      toast.error(err?.message || '归档工作流失败');
    }
  });
};

const deleteWorkflow = async (workflow) => {
  if (!workflow?.id) return;
  if (isWorkflowActive(workflow)) {
    toast.warn('请先停止工作流中的运行任务');
    return;
  }
  const ok = await showConfirm({
    title: '永久删除工作流',
    message: '这会永久删除该工作流、关联任务记录以及相关训练产物，操作不可恢复。',
    danger: true,
    confirmText: '永久删除',
  });
  if (!ok) return;
  await asyncAction.run(deleteWorkflowActionKey(workflow.id), async () => {
    try {
      await workflowStore.deleteWorkflow({
        project_path: project.value?.path || '',
        workflow_id: workflow.id,
      }, {
        dataset_id: dataset.value?.dataset_id || '',
      });
      if (selectedWorkflow.value?.id === workflow.id) {
        setWorkflowContext(null, { archived: true });
      }
      await replaceWorkflowQuery(WORKFLOW_STEP.CONFIG, '');
      await refreshWorkflowList();
      toast.success('工作流已永久删除');
    } catch (err) {
      toast.error(err?.message || '删除工作流失败');
    }
  });
};

watch([projectName, routeDatasetId], syncPageState, { immediate: true });

watch([routeWorkflowId, routeDraft, routeDatasetId, workflowsLoading, trainingWorkflows], () => {
  loadSelectedWorkflow().catch(() => {});
}, { immediate: true });

const onTrainingStarted = async (data) => {
  const taskId = data?.task_id || data;
  const workflowId = data?.workflow_id || '';
  if (taskId) {
    showArchivedWorkflows.value = false;
    trainingStore.currentTaskId = taskId;
    await trainingStore.fetchCurrentTask().catch(() => {});
    await trainingStore.pollCurrentTask().catch(() => {});
    await refreshWorkflowList();
    const resolvedWorkflowId = workflowId || trainingStore.currentTask?.workflow_id || '';
    if (resolvedWorkflowId) {
      selectWorkflowById(resolvedWorkflowId);
    }
    await replaceWorkflowQuery(WORKFLOW_STEP.DETAIL, resolvedWorkflowId);
  }
};

const onWorkflowBound = async (workflowId) => {
  if (!workflowId) return;
  showArchivedWorkflows.value = false;
  await refreshWorkflowList(workflowId);
  await replaceWorkflowQuery(WORKFLOW_STEP.CONFIG, workflowId);
};

watch(() => trainingStore.currentTask?.status, async (status) => {
  if (isTaskActive(status) && hasCurrentTaskForPage.value && !routeWorkflowId.value && isCreatingWorkflow.value) {
    await refreshWorkflowList();
    const workflowId = trainingStore.currentTask?.workflow_id || '';
    selectWorkflowById(workflowId);
    await replaceWorkflowQuery(WORKFLOW_STEP.DETAIL, workflowId);
  }
  if (isTaskTerminal(status) && routeWorkflowId.value === trainingStore.currentTask?.workflow_id) {
    await refreshWorkflowList(trainingStore.currentTask?.workflow_id || '');
    await loadSelectedWorkflow();
  }
});
// 页面进入时主动拉一次训练状态（解决刷新后 / 直开 URL 时本地状态丢失）
trainingStore.fetchCurrentTask().then(() => {
  if (isTaskActive(trainingStore.currentTask)) {
    trainingStore.pollCurrentTask();
  }
});

// 立即刷新项目 + 绑定版本状态轮询，确保 versioning_status 等快照状态是最新的
store.refreshKeepSelection();
store.ensureVersioningPoll();

onBeforeUnmount(() => {
  trainingStore.stopCurrentTaskPolling();
  store.stopVersioningPoll();
});
</script>
