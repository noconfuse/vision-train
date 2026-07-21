<template>
  <div class="vt-shell">
    <AppHeader :crumbs="[{ label: '任务中心' }]" :back-href="backHref" />

    <main class="vt-body overflow-y-auto">
      <div class="p-4 space-y-4 flex-1 min-h-0">

        <!-- 统计 + 筛选 -->
        <div class="vt-section">
          <div class="vt-stat-grid grid-cols-2 md:grid-cols-4 mb-4">
            <div class="vt-stat-card">
              <div class="vt-stat-label">进行中</div>
              <div class="vt-stat-value vt-text-accent">{{ counts.running }}</div>
            </div>
            <div class="vt-stat-card">
              <div class="vt-stat-label">等待中</div>
              <div class="vt-stat-value text-slate-700">{{ counts.pending }}</div>
            </div>
            <div class="vt-stat-card">
              <div class="vt-stat-label">已完成</div>
              <div class="vt-stat-value text-emerald-600">{{ counts.completed }}</div>
            </div>
            <div class="vt-stat-card">
              <div class="vt-stat-label">失败 / 停止</div>
              <div class="vt-stat-value text-rose-600">{{ counts.failed + counts.stopped + counts.interrupted }}</div>
            </div>
          </div>

          <div class="flex items-center gap-3 flex-wrap text-xs">
            <span class="text-gray-500">项目</span>
            <select v-model="filterProject" class="vt-select vt-control-sm vt-control-auto min-w-32">
              <option value="">全部项目</option>
              <option v-for="p in store.projects" :key="p.id" :value="p.path">{{ p.name }}</option>
            </select>

            <span class="text-gray-500">类型</span>
            <select v-model="filterType" class="vt-select vt-control-sm vt-control-auto min-w-28">
              <option value="">全部类型</option>
              <option v-for="item in TASK_TYPE_FILTER_OPTIONS" :key="item.value" :value="item.value">
                {{ item.label }}
              </option>
            </select>

            <span class="text-gray-500">状态</span>
            <select v-model="filterStatus" class="vt-select vt-control-sm vt-control-auto min-w-28">
              <option value="">全部状态</option>
              <option v-for="item in TASK_STATUS_FILTER_OPTIONS" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>

            <span class="ml-auto text-gray-500">当前任务 · {{ filtered.length }} 条 · 每 2s 自动刷新</span>
          </div>
        </div>

        <!-- 列表 -->
        <div class="vt-table-shell">
          <div v-if="loading && tasks.length === 0" class="py-12 text-center text-gray-500">加载中...</div>
          <div v-else-if="filtered.length === 0" class="py-12 text-center text-gray-500">
            当前筛选下没有任务
          </div>
          <div v-else class="overflow-auto">
            <table class="vt-table">
              <thead class="vt-table-head">
                <tr>
                  <th class="vt-table-head-cell w-8"></th>
                  <th class="vt-table-head-cell">类型</th>
                  <th class="vt-table-head-cell">项目 / 数据集</th>
                  <th class="vt-table-head-cell">任务 ID</th>
                  <th class="vt-table-head-cell">状态</th>
                  <th class="vt-table-head-cell">进度</th>
                  <th class="vt-table-head-cell">创建时间</th>
                  <th class="vt-table-head-cell">操作</th>
                </tr>
              </thead>
              <tbody>
                <template v-for="t in filtered" :key="t.id">
                  <tr class="vt-table-row" :class="t.id === highlightedTaskId ? 'vt-list-row--selected' : ''">
                    <td class="px-2 py-3 align-top">
                      <UiTooltip side="top" align="center">
                        <template #trigger>
                          <button
                            class="vt-icon-btn h-6 w-6 border-transparent bg-transparent"
                            @click="toggleExpand(t.id)"
                          >
                            <AppIcon :name="expandedId === t.id ? 'chevronDown' : 'chevronRight'" class="h-3.5 w-3.5" />
                          </button>
                        </template>
                        {{ expandedId === t.id ? '收起' : '展开详情' }}
                      </UiTooltip>
                    </td>
                    <td class="vt-table-cell whitespace-nowrap">
                      <span class="mr-1">{{ typeIcon(t.type) }}</span>{{ typeLabel(t.type) }}
                    </td>
                    <td class="vt-table-cell">
                      <div class="text-xs text-gray-500">{{ projectName(t.project_path) }}</div>
                      <div class="text-sm">{{ t.dataset_name || '-' }}</div>
                    </td>
                    <td class="vt-table-cell text-xs">
                      <div class="font-mono whitespace-nowrap">{{ t.id }}</div>
                      <div v-if="t.workflow_id" class="mt-1 text-[10px] text-gray-500 font-mono whitespace-nowrap">
                        工作流 {{ t.workflow_id }}
                      </div>
                      <div v-if="resumeSourceText(t)" class="mt-1 flex items-center gap-2 text-[10px]">
                        <span class="vt-text-accent">{{ resumeSourceText(t) }}</span>
                        <AsyncButton
                          class="vt-text-accent hover:underline"
                          :pending="isActionPending(focusTaskActionKey(resumeFromTaskId(t)))"
                          loading-text="加载中..."
                          @click="focusTaskById(resumeFromTaskId(t))"
                        >
                          查看来源
                        </AsyncButton>
                      </div>
                      <div v-else-if="resumeChildrenCount(t.id) > 0" class="mt-1 text-[10px] text-emerald-700">
                        已续跑 {{ resumeChildrenCount(t.id) }} 次
                      </div>
                    </td>
                    <td class="vt-table-cell whitespace-nowrap">
                      <span class="vt-tag" :class="getTaskStatusTagClass(t.status)">{{ getTaskStatusLabel(t.status) }}</span>
                    </td>
                    <td class="vt-table-cell whitespace-nowrap">
                      <div class="flex items-center gap-2 min-w-[160px]">
                        <div class="vt-meter flex-1">
                          <div class="vt-meter__bar"
                               :class="getTaskProgressBarClass(t.status)"
                               :style="{ width: `${t.progress || 0}%` }"></div>
                        </div>
                        <span class="text-[10px] font-mono text-gray-500 w-9 text-right">
                          {{ t.progress || 0 }}%
                        </span>
                      </div>
                    </td>
                    <td class="vt-table-cell text-xs text-gray-500 whitespace-nowrap">{{ t.created_at || '-' }}</td>
                    <td class="vt-table-cell text-xs whitespace-nowrap">
                      <div class="flex flex-wrap items-center gap-x-3 gap-y-1">
                        <button v-if="canOpenTrainingWorkflow(t)"
                                class="vt-action-btn vt-action-btn--primary"
                                @click="openTrainingWorkflow(t)">
                          <AppIcon name="workflow" class="h-3.5 w-3.5" />
                          <span>工作流</span>
                        </button>
                        <AsyncButton v-if="canView(t)"
                                class="vt-action-btn vt-action-btn--info"
                                :pending="isActionPending(detailTaskActionKey(t.id))"
                                loading-text="加载中..."
                                @click="onView(t)">
                          <AppIcon name="detail" class="h-3.5 w-3.5" />
                          <span>详情</span>
                        </AsyncButton>
                        <button v-if="canJumpToEvaluate(t)"
                                class="vt-action-btn vt-action-btn--warning"
                                @click="openTrainingWorkflow(t, 'evaluate')">
                          <AppIcon name="evaluate" class="h-3.5 w-3.5" />
                          <span>评估</span>
                        </button>
                        <button v-if="canJumpToExport(t)"
                                class="vt-action-btn vt-action-btn--success"
                                @click="openTrainingWorkflow(t, 'export_config')">
                          <AppIcon name="export" class="h-3.5 w-3.5" />
                          <span>导出</span>
                        </button>
                      </div>
                    </td>
                  </tr>
                  <tr v-if="expandedId === t.id" class="vt-table-row bg-gray-50">
                    <td colspan="8" class="px-4 py-3 text-xs text-slate-700">
                      <div class="grid md:grid-cols-2 gap-3">
                        <div>
                          <div class="text-[10px] text-gray-500 mb-1 font-mono">MESSAGE</div>
                          <div class="whitespace-pre-wrap break-all">{{ t.message || '（无）' }}</div>
                        </div>
                        <div>
                          <div class="text-[10px] text-gray-500 mb-1 font-mono">ERROR</div>
                          <div class="whitespace-pre-wrap break-all text-rose-700">{{ t.error || '（无）' }}</div>
                        </div>
                        <div>
                          <div class="text-[10px] text-gray-500 mb-1 font-mono">PROJECT_PATH</div>
                          <div class="font-mono break-all">{{ t.project_path || '（无）' }}</div>
                        </div>
                        <div>
                          <div class="text-[10px] text-gray-500 mb-1 font-mono">DATASET_PATH</div>
                          <div class="font-mono break-all">{{ t.dataset_path || '（无）' }}</div>
                        </div>
                        <div>
                          <div class="text-[10px] text-gray-500 mb-1 font-mono">WORKFLOW_ID</div>
                          <div class="font-mono break-all">{{ t.workflow_id || '（无）' }}</div>
                        </div>
                        <div>
                          <div class="text-[10px] text-gray-500 mb-1 font-mono">STARTED_AT</div>
                          <div class="font-mono">{{ t.started_at || '-' }}</div>
                        </div>
                        <div>
                          <div class="text-[10px] text-gray-500 mb-1 font-mono">FINISHED_AT</div>
                          <div class="font-mono">{{ t.finished_at || '-' }}</div>
                        </div>
                      </div>
                    </td>
                  </tr>
                </template>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </main>

    <!-- 任务详情弹窗 -->
    <div v-if="detailTask" class="vt-modal-backdrop" @click.self="detailTask = null">
      <div class="vt-modal-panel vt-modal-panel--lg max-h-[80vh] overflow-y-auto p-5">
        <div class="flex items-center justify-between mb-3">
          <div>
            <h3 class="text-base font-semibold text-slate-800">任务详情</h3>
            <div class="text-xs text-gray-500 font-mono">{{ detailTask.id }} · {{ typeLabel(detailTask.type) }}</div>
          </div>
          <button class="vt-btn-secondary vt-btn-size-sm" @click="detailTask = null">
            <AppIcon name="close" class="h-4 w-4" />
            关闭
          </button>
        </div>
        <div v-if="detailLoading" class="text-center py-8 text-gray-500">加载中...</div>
        <div v-else-if="detailError" class="bg-red-50 text-red-700 text-sm p-3 border border-red-200">{{ detailError }}</div>
        <div v-else class="space-y-3 text-sm">
          <div class="grid grid-cols-2 gap-3">
            <div><span class="text-gray-500">状态</span> · <span class="vt-tag" :class="getTaskStatusTagClass(detailTask.status)">{{ getTaskStatusLabel(detailTask.status) }}</span></div>
            <div><span class="text-gray-500">进度</span> · <span class="font-mono">{{ detailTask.progress || 0 }}%</span></div>
            <div><span class="text-gray-500">项目</span> · <span class="font-mono">{{ projectName(detailTask.project_path) }}</span></div>
            <div><span class="text-gray-500">数据集</span> · <span>{{ detailTask.dataset_name || '-' }}</span></div>
            <div v-if="resumeFromTaskId(detailTask)">
              <span class="text-gray-500">继续自任务</span> ·
              <AsyncButton
                class="vt-btn-link vt-text-accent font-mono"
                :pending="isActionPending(focusTaskActionKey(resumeFromTaskId(detailTask)))"
                loading-text="加载中..."
                @click="focusTaskById(resumeFromTaskId(detailTask))"
              >
                {{ resumeFromTaskId(detailTask) }}
              </AsyncButton>
            </div>
            <div v-if="resumeWeight(detailTask)"><span class="text-gray-500">恢复权重</span> · <span class="font-mono">{{ resumeWeight(detailTask) }}</span></div>
            <div v-if="resumeChildrenCount(detailTask.id) > 0"><span class="text-gray-500">继续训练次数</span> · <span class="font-mono">{{ resumeChildrenCount(detailTask.id) }}</span></div>
          </div>
          <div>
            <div class="text-xs text-gray-500 mb-1">消息</div>
            <div class="bg-gray-50 border border-gray-200 p-2 text-xs whitespace-pre-wrap break-all">{{ detailTask.message || '（无）' }}</div>
          </div>
          <div v-if="detailTask.error">
            <div class="text-xs text-gray-500 mb-1">错误</div>
            <div class="bg-red-50 border border-red-200 p-2 text-xs whitespace-pre-wrap break-all text-rose-700">{{ detailTask.error }}</div>
          </div>
          <div v-if="artifacts.images && artifacts.images.length">
            <div class="text-xs text-gray-500 mb-1">产物图片</div>
            <div class="grid grid-cols-3 gap-2">
              <a v-for="img in artifacts.images" :key="img.url" :href="img.url" target="_blank" class="border border-gray-200 p-1">
                <img :src="img.url" class="w-full h-auto object-contain" />
              </a>
            </div>
          </div>
          <div v-if="artifacts.weights && artifacts.weights.length">
            <div class="text-xs text-gray-500 mb-1">权重文件</div>
            <div class="flex flex-wrap gap-2">
              <a v-for="w in artifacts.weights" :key="w.url" :href="w.url" target="_blank"
                 class="vt-btn-secondary vt-btn-size-sm">
                {{ w.name }}
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useMainStore } from '../stores/main';
import api from '../api';
import AppHeader from '../components/AppHeader.vue';
import AppIcon from '../components/ui/AppIcon.vue';
import AsyncButton from '../components/ui/AsyncButton.vue';
import UiTooltip from '../components/ui/Tooltip.vue';
import { useAsyncAction } from '../composables/useAsyncAction';
import { useToast } from '../composables/useToast';
import {
  TASK_STATUS,
  TASK_STATUS_FILTER_OPTIONS,
  getTaskProgressBarClass,
  getTaskStatusLabel,
  getTaskStatusTagClass,
  isTaskActive,
} from '../taskStatus';
import {
  TASK_TYPE_FILTER_OPTIONS,
  canViewTask,
  getTaskTypeIcon,
  getTaskTypeLabel,
  isTrainingTask,
  taskHasArtifactsView,
} from '../taskType';
import { isTrainingWorkflowType } from '../workflowType';
import { getResumeFromTaskId, getResumeSourceText, getResumeWeight } from '../utils/trainingTask';
import { getWorkflowPreferredStepFromTask } from '../utils/trainingWorkflow';

const store = useMainStore();
const route = useRoute();
const router = useRouter();
const toast = useToast();
const asyncAction = useAsyncAction();

const tasks = ref([]);
const loading = ref(false);
const filterProject = ref('');
const filterType = ref('');
const filterStatus = ref('');
const expandedId = ref('');
const highlightedTaskId = ref('');

const detailTask = ref(null);
const detailLoading = ref(false);
const detailError = ref('');
const artifacts = ref({ images: [], weights: [] });

let timer = null;
const detailTaskActionKey = (taskId) => `tasks-center:detail:${String(taskId || '')}`;
const focusTaskActionKey = (taskId) => `tasks-center:focus:${String(taskId || '')}`;
const isActionPending = (key) => asyncAction.isPending(key);

const typeLabel = (type) => getTaskTypeLabel(type);
const typeIcon = (type) => getTaskTypeIcon(type);
const backHref = computed(() => {
  const raw = route.query.return_to;
  if (typeof raw !== 'string' || !raw.trim()) return null;
  return raw;
});

const counts = computed(() => {
  const c = {
    [TASK_STATUS.RUNNING]: 0,
    [TASK_STATUS.STOPPING]: 0,
    [TASK_STATUS.PENDING]: 0,
    [TASK_STATUS.COMPLETED]: 0,
    [TASK_STATUS.FAILED]: 0,
    [TASK_STATUS.STOPPED]: 0,
    [TASK_STATUS.INTERRUPTED]: 0,
  };
  for (const t of tasks.value) {
    if (c[t.status] !== undefined) c[t.status]++;
  }
  return c;
});

const filtered = computed(() => {
  return tasks.value.filter(t => {
    if (filterType.value && t.type !== filterType.value) return false;
    if (filterStatus.value && t.status !== filterStatus.value) return false;
    if (filterProject.value) {
      const pname = projectName(t.project_path);
      if (pname !== filterProject.value) return false;
    }
    return true;
  });
});

const projectName = (path) => {
  if (!path) return '';
  const parts = String(path).replace(/\\/g, '/').split('/');
  return parts[parts.length - 1] || '';
};

const canView = (t) => canViewTask(t);
const canOpenTrainingWorkflow = (t) => (
  isTrainingWorkflowType(t?.workflow_type) &&
  !!t?.workflow_id &&
  !!t?.project_path &&
  !!t?.dataset_name
);
const canJumpToEvaluate = (t) => isTrainingTask(t) && t?.status === TASK_STATUS.COMPLETED && canOpenTrainingWorkflow(t);
const canJumpToExport = (t) => isTrainingTask(t) && t?.status === TASK_STATUS.COMPLETED && canOpenTrainingWorkflow(t);
const resumeFromTaskId = (task) => getResumeFromTaskId(task);
const resumeSourceText = (task) => getResumeSourceText(task);
const resumeWeight = (task) => getResumeWeight(task);
const resumeChildrenCount = (taskId) => tasks.value.filter((item) => resumeFromTaskId(item) === taskId).length;

const openTrainingWorkflow = async (task, step = '') => {
  if (!canOpenTrainingWorkflow(task)) return;
  const resolvedStep = getWorkflowPreferredStepFromTask(task, step);
  await router.push({
    name: 'dataset-train',
    params: {
      project: encodeURIComponent(projectName(task.project_path)),
      name: encodeURIComponent(task.dataset_name),
    },
    query: {
      return_to: route.fullPath,
      workflow_id: task.workflow_id,
      step: resolvedStep,
    },
  });
};

const focusTaskById = async (taskId) => {
  if (!taskId) return;
  await asyncAction.run(focusTaskActionKey(taskId), async () => {
    highlightedTaskId.value = taskId;
    const inList = tasks.value.find((item) => item.id === taskId);
    if (inList) {
      expandedId.value = taskId;
      await onView(inList);
    } else {
      try {
        const task = await api.getTask(taskId);
        if (task?.id) {
          detailTask.value = task;
          detailLoading.value = false;
          detailError.value = '';
        }
      } catch (e) {
        toast.error(e?.message || '加载来源任务失败');
      }
    }
    setTimeout(() => { if (highlightedTaskId.value === taskId) highlightedTaskId.value = ''; }, 4000);
  });
};

const refreshDetailTask = async (taskList = tasks.value) => {
  if (!detailTask.value?.id) return;
  const latest = taskList.find((item) => item.id === detailTask.value.id);
  if (latest) {
    detailTask.value = latest;
  }
  if (!isTaskActive(detailTask.value)) return;
  try {
    const fresh = await api.getTask(detailTask.value.id);
    if (fresh?.id) detailTask.value = fresh;
  } catch (e) {
    console.error(e);
  }
};

const load = async (manual = false) => {
  if (manual) loading.value = true;
  try {
    const params = { limit: 200 };
    if (filterProject.value) params.project_path = filterProject.value;
    const data = await api.listTasks(params);
    const nextTasks = Array.isArray(data) ? data : [];
    tasks.value = nextTasks;
    await refreshDetailTask(nextTasks);
  } catch (e) {
    console.error(e);
  } finally {
    loading.value = false;
  }
};

const toggleExpand = (id) => {
  expandedId.value = expandedId.value === id ? '' : id;
};

const onView = async (t) => {
  if (!t?.id) return;
  await asyncAction.run(detailTaskActionKey(t.id), async () => {
    detailTask.value = t;
    detailLoading.value = true;
    detailError.value = '';
    artifacts.value = { images: [], weights: [] };
    try {
      const fresh = await api.getTask(t.id);
      detailTask.value = fresh?.id ? fresh : t;
      if (taskHasArtifactsView(t)) {
        const res = await api.getTrainingRunArtifacts({
          project_path: t.project_path,
          dataset_name: t.dataset_name,
          task_id: t.id,
        });
        artifacts.value = {
          images: res?.images || [],
          weights: res?.weights || [],
        };
      }
    } catch (e) {
      detailError.value = e?.message || '加载失败';
    } finally {
      detailLoading.value = false;
    }
  });
};

onMounted(async () => {
  if (store.projects.length === 0) {
    try { await store.fetchProjects({ silent: true }); } catch (_) {}
  }
  await load();
  timer = setInterval(() => load(false), 2000);
});
onUnmounted(() => {
  if (timer) clearInterval(timer);
});
</script>
