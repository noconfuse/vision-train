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
                <UiTooltip
                  :disabled="!step.reason"
                  side="top"
                  content-class="max-w-[16rem] text-left"
                >
                  <template #trigger>
                    <span class="inline-flex shrink-0" :class="step.reason ? 'cursor-not-allowed' : ''">
                      <button
                        class="vt-step-button"
                        :class="[stepButtonClass(step), step.reason ? 'pointer-events-none' : '']"
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
                    </span>
                  </template>
                  {{ step.reason }}
                </UiTooltip>
                <div
                  v-if="index < workflowSteps.length - 1"
                  class="vt-step-connector"
                  :class="stepConnectorClass(step)"
                ></div>
              </template>
            </div>
          </div>

          <div v-if="partialRunNotice" class="mb-3 shrink-0 vt-note vt-note--warn">
            {{ partialRunNotice }}
          </div>

          <div v-if="isArchivedWorkflowSelected" class="flex-1 min-h-0 bg-white border border-dashed border-gray-300 px-8 py-10 flex items-center justify-center">
            <div class="max-w-md text-center">
              <div class="text-3xl leading-none text-slate-300">#</div>
              <div class="mt-4 text-base font-semibold text-slate-800">该工作流已归档</div>
              <div class="mt-2 text-sm leading-6 text-gray-500">归档后的工作流不再参与训练流程。切到“已归档”列表可以恢复它，或永久删除其任务与产物。</div>
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
              <div class="mt-2 text-sm text-gray-500">先在“训练配置”步骤启动训练，这里会持续展示任务进度、测试集评估和导出结果。</div>
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
                    @click="showWorkflowList(false)"
                  >
                    当前
                  </button>
                  <button
                    class="vt-segmented-tab vt-segmented-tab--compact"
                    :class="{ 'vt-segmented-tab--active': showArchivedWorkflows }"
                    @click="showWorkflowList(true)"
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
                  <template v-else>
                    <UiTooltip
                      side="top"
                      content-class="max-w-[16rem] text-left"
                    >
                      <template #trigger>
                        <AsyncButton
                          class="vt-icon-btn vt-icon-btn--sm text-slate-500 hover:text-slate-800"
                          :disabled="isWorkflowActive(workflow)"
                          :pending="isActionPending(restoreWorkflowActionKey(workflow.id))"
                          @click.stop="restoreWorkflow(workflow)"
                        >
                          <AppIcon name="restore" class="h-3.5 w-3.5" />
                        </AsyncButton>
                      </template>
                      恢复到当前工作流
                    </UiTooltip>
                    <UiTooltip
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
                  </template>
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
import { TASK_STATUS, getTaskStatusLabel, getTaskStatusTagClass, isTaskActive, isTaskCompleted } from '../domain/task/taskStatus';
import { isTrainingTask } from '../domain/task/taskType';
import { formatDateTime } from '../utils';
import { WORKFLOW_STEP, WEIGHT_BASED_WORKFLOW_STEPS, hasUsableTrainingWeight, normalizeWorkflowStep } from '../utils/trainingWorkflow';
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
// 选中项是面板里唯一的本地状态，它始终由 URL 的 workflow_id 解析出来。
const selectedWorkflow = ref(null);
const archiveWorkflowActionKey = (workflowId) => `training-page:archive-workflow:${String(workflowId || '')}`;
const restoreWorkflowActionKey = (workflowId) => `training-page:restore-workflow:${String(workflowId || '')}`;
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
// 工作流面板的三个视图状态全部来自 URL：workflow_id=选中谁，draft=正在新建，archived=看归档列表。
const routeWorkflowId = computed(() => String(route.query.workflow_id || ''));
const routeDraft = computed(() => String(route.query.draft || '') === '1');
const routeArchived = computed(() => String(route.query.archived || '') === '1');
const isCreatingWorkflow = computed(() => routeDraft.value);
const showArchivedWorkflows = computed(() => routeArchived.value);
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
const workflowStepUnlocked = computed(() => hasUsableTrainingWeight(workflowTrainingTask.value));
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
  if (WEIGHT_BASED_WORKFLOW_STEPS.includes(normalized) && !hasUsableTrainingWeight(task)) {
    return workflowBaseStep(task);
  }
  return normalized;
};
const workflowStep = computed(() => resolveWorkflowStep(routeWorkflowStep.value));
const workflowCurrentIndex = computed(() => workflowStepOrder.indexOf(workflowStep.value));
const workflowSteps = computed(() => {
  const weightLockReason = '训练还没有产出可用权重';
  const definitions = [
    {
      key: WORKFLOW_STEP.CONFIG,
      title: '训练配置',
      optional: false,
      enabled: hasWorkflowContext.value,
      reason: '',
    },
    {
      key: WORKFLOW_STEP.DETAIL,
      title: '任务详情',
      optional: false,
      enabled: Boolean(workflowTrainingTask.value),
      reason: '还没有训练任务',
    },
    {
      key: WORKFLOW_STEP.EVALUATE,
      title: '测试集评估',
      optional: true,
      enabled: workflowStepUnlocked.value && hasEvaluateStep.value,
      reason: hasEvaluateStep.value ? weightLockReason : '数据集没有 test 划分',
    },
    {
      key: WORKFLOW_STEP.EXPORT_CONFIG,
      title: '模型导出',
      optional: false,
      enabled: workflowStepUnlocked.value,
      reason: weightLockReason,
    },
    {
      key: WORKFLOW_STEP.DEPLOYMENT_TEMPLATE,
      title: '部署模板',
      optional: false,
      enabled: workflowStepUnlocked.value,
      reason: weightLockReason,
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
      reason: isLocked ? step.reason : '',
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
// 训练没跑完但已经写出 best.pt 时，后续三步照样放行，同时把「用的不是跑满的模型」说清楚。
const partialRunNotice = computed(() => {
  if (!WEIGHT_BASED_WORKFLOW_STEPS.includes(workflowStep.value)) return '';
  if (!workflowStepUnlocked.value || isTaskCompleted(workflowTrainingTask.value)) return '';
  return `训练${getTaskStatusLabel(workflowTrainingTask.value)}，没有跑完全部轮数；这里使用的是已经产出的 best.pt。要拿到完整结果，可以回到任务详情继续训练。`;
});
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

// 视图状态的唯一写入口：只改传入的那几项，其余沿用当前 URL，然后整体替换一次。
const goWorkflow = async ({
  step = routeWorkflowStep.value,
  workflowId = routeWorkflowId.value,
  draft = routeDraft.value,
  archived = routeArchived.value,
} = {}) => {
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
    if (draft) {
      nextQuery.draft = '1';
    } else {
      delete nextQuery.draft;
    }
  }
  if (archived) {
    nextQuery.archived = '1';
  } else {
    delete nextQuery.archived;
  }
  delete nextQuery.export_task_id;
  await router.replace({
    name: route.name,
    params: route.params,
    query: nextQuery,
  });
};

// === Page sync ===
// 页面打开的数据集以 URL 里的 dataset_id 为准；store 只负责跟上它。
const syncStore = () => {
  if (project.value && store.currentProject?.path !== project.value.path) {
    store.selectProject(project.value);
  }
  if (dataset.value && store.selectedDatasetId !== dataset.value.dataset_id) {
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
    }
  } else if (project.value) {
    const target = datasetName.value || routeDatasetId.value || '未知数据集';
    loadError.value = `项目「${projectName.value}」下找不到数据集「${target}」`;
  } else {
    loadError.value = `项目「${projectName.value}」不存在`;
  }
  loading.value = false;
};

// 同一个列表视图的并发拉取共用一次请求：切 tab、改数据、开始训练都可能同时触发重拉。
let workflowsRequest = null;
const loadWorkflows = async () => {
  if (!project.value?.path || !dataset.value?.dataset_id || !trainingGuard.value.enabled) return;
  const key = workflowListKey.value;
  if (workflowsRequest?.key === key) return workflowsRequest.promise;
  const promise = workflowStore.fetchWorkflows({
    project_path: project.value.path,
    dataset_id: dataset.value.dataset_id,
    archived_only: showArchivedWorkflows.value,
  });
  workflowsRequest = { key, promise };
  try {
    await promise;
  } finally {
    if (workflowsRequest?.promise === promise) workflowsRequest = null;
  }
};

// 选中态只由 URL 的 workflow_id 决定：当前列表 → 缓存 → 详情接口，都找不到就回到空态。
const resolveSelectedWorkflow = async () => {
  const workflowId = routeWorkflowId.value;
  if (!workflowId) {
    selectedWorkflow.value = null;
    return;
  }
  const cachedWorkflow = trainingWorkflows.value.find((item) => item.id === workflowId)
    || workflowStore.getWorkflowFromState({
      project_path: project.value?.path || '',
      dataset_id: dataset.value?.dataset_id || '',
      workflow_id: workflowId,
      include_archived: true,
    });
  const workflow = cachedWorkflow?.id ? cachedWorkflow : await workflowStore.fetchWorkflowDetail({
    project_path: project.value?.path || '',
    dataset_id: dataset.value?.dataset_id || '',
    workflow_id: workflowId,
    include_archived: true,
  });
  selectedWorkflow.value = workflow?.id ? workflow : null;
  // 从任务中心等其他入口打开时，列表视图跟到这条工作流真正所在的那个列表
  if (workflow?.id && !!workflow.is_archived !== showArchivedWorkflows.value) {
    await goWorkflow({ archived: !!workflow.is_archived });
  }
};

const syncWorkflowView = async () => {
  await loadWorkflows();
  await resolveSelectedWorkflow();
};

const openCreateWorkflow = async () => {
  await goWorkflow({ step: WORKFLOW_STEP.CONFIG, workflowId: '', draft: true, archived: false });
};

const selectTrainingWorkflow = async (workflow) => {
  if (!workflow?.id) return;
  const nextStep = workflow.latest_training_task ? (workflow.current_step || WORKFLOW_STEP.DETAIL) : WORKFLOW_STEP.CONFIG;
  await goWorkflow({ step: nextStep, workflowId: workflow.id, archived: !!workflow.is_archived });
};

const goToWorkflowStep = async (step) => {
  await goWorkflow({ step: resolveWorkflowStep(step), workflowId: selectedWorkflow.value?.id || '' });
};

const goToDeploymentTemplate = async () => {
  await goToWorkflowStep(WORKFLOW_STEP.DEPLOYMENT_TEMPLATE);
};

// 切 tab 只做一件事：把视图写进 URL，同时取消选中（不带着别列表的选中项过来）。
const showWorkflowList = async (archived) => {
  if (archived === showArchivedWorkflows.value) return;
  await goWorkflow({ step: WORKFLOW_STEP.CONFIG, workflowId: '', draft: false, archived });
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
      await goWorkflow({ step: WORKFLOW_STEP.CONFIG, workflowId: archivedWorkflow.id, draft: false, archived: true });
      await syncWorkflowView();
      toast.success('工作流已归档');
    } catch (err) {
      toast.error(err?.message || '归档工作流失败');
    }
  });
};

const restoreWorkflow = async (workflow) => {
  if (!workflow?.id) return;
  await asyncAction.run(restoreWorkflowActionKey(workflow.id), async () => {
    try {
      const restoredWorkflow = await workflowStore.restoreWorkflow({
        project_path: project.value?.path || '',
        workflow_id: workflow.id,
      }, {
        dataset_id: dataset.value?.dataset_id || '',
      });
      await goWorkflow({ step: WORKFLOW_STEP.CONFIG, workflowId: restoredWorkflow.id, draft: false, archived: false });
      await syncWorkflowView();
      toast.success('工作流已恢复到当前列表');
    } catch (err) {
      toast.error(err?.message || '恢复工作流失败');
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
      await goWorkflow({ step: WORKFLOW_STEP.CONFIG, workflowId: '', draft: false });
      await syncWorkflowView();
      toast.success('工作流已永久删除');
    } catch (err) {
      toast.error(err?.message || '删除工作流失败');
    }
  });
};

watch([projectName, routeDatasetId], syncPageState, { immediate: true });

// 后台刷新换了 dataset 对象（不是身份）时，让 store 重新跟上页面正在看的这个数据集。
watch([project, dataset], syncStore);

// 换视图（数据集 / 当前·已归档列表）→ 重拉列表并重新定位选中项；换 workflow_id → 只重新定位。
watch(workflowListKey, () => {
  syncWorkflowView().catch(() => {});
}, { immediate: true });

watch([routeWorkflowId, routeDraft], () => {
  resolveSelectedWorkflow().catch(() => {});
});

const onTrainingStarted = async (data) => {
  const taskId = data?.task_id || data;
  const workflowId = data?.workflow_id || '';
  if (taskId) {
    trainingStore.currentTaskId = taskId;
    await trainingStore.fetchCurrentTask().catch(() => {});
    await trainingStore.pollCurrentTask().catch(() => {});
    await goWorkflow({
      step: WORKFLOW_STEP.DETAIL,
      workflowId: workflowId || trainingStore.currentTask?.workflow_id || '',
      archived: false,
    });
    await syncWorkflowView();
  }
};

const onWorkflowBound = async (workflowId) => {
  if (!workflowId) return;
  await goWorkflow({ step: WORKFLOW_STEP.CONFIG, workflowId, archived: false });
  await syncWorkflowView();
};

watch(() => trainingStore.currentTask?.status, async (status) => {
  if (isTaskActive(status) && hasCurrentTaskForPage.value && !routeWorkflowId.value && isCreatingWorkflow.value) {
    await goWorkflow({ step: WORKFLOW_STEP.DETAIL, workflowId: trainingStore.currentTask?.workflow_id || '' });
    await syncWorkflowView();
  }
});

// 步骤条解锁看的是工作流快照里的 latest_training_task，快照里有任务在跑就定时重取这条工作流，
// 跑完即停。不能只靠 trainingStore.currentTask 的轮询——那只在本会话从本页启动训练时才有，
// 训练中刷新/重开页面后 currentTaskId 是空的，训练跑完了快照也不会自己更新。
let workflowPollTimer = null;
let workflowPollDisposed = false;
const stopWorkflowPolling = () => {
  if (workflowPollTimer) {
    clearTimeout(workflowPollTimer);
    workflowPollTimer = null;
  }
};
const workflowPollActive = computed(() => (
  Boolean(selectedWorkflow.value?.id) && !isArchivedWorkflowSelected.value && isWorkflowActive(selectedWorkflow.value)
));
const pollSelectedWorkflow = async () => {
  workflowPollTimer = null;
  const workflowId = routeWorkflowId.value;
  if (!workflowId || !project.value?.path || !dataset.value?.dataset_id) return;
  const fresh = await workflowStore.refreshWorkflow({
    project_path: project.value.path,
    dataset_id: dataset.value.dataset_id,
    workflow_id: workflowId,
  }).catch(() => null);
  if (fresh?.id && routeWorkflowId.value === fresh.id) {
    selectedWorkflow.value = fresh;
  }
  if (!workflowPollDisposed && workflowPollActive.value) {
    workflowPollTimer = setTimeout(pollSelectedWorkflow, 2000);
  }
};
watch(workflowPollActive, (active) => {
  stopWorkflowPolling();
  if (active && !workflowPollDisposed) {
    workflowPollTimer = setTimeout(pollSelectedWorkflow, 2000);
  }
}, { immediate: true });
// 页面进入时主动拉一次训练状态（解决刷新后 / 直开 URL 时本地状态丢失）
trainingStore.fetchCurrentTask().then(() => {
  if (isTaskActive(trainingStore.currentTask)) {
    trainingStore.pollCurrentTask();
  }
});

// 立即刷新项目 + 绑定版本状态轮询，确保 versioning_status 等快照状态是最新的
store.fetchProjects({ silent: true });
store.ensureVersioningPoll();

onBeforeUnmount(() => {
  workflowPollDisposed = true;
  stopWorkflowPolling();
  trainingStore.stopCurrentTaskPolling();
  store.stopVersioningPoll();
});
</script>
