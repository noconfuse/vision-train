<template>
  <div class="vt-view p-4">
    <!-- 视图标题（与视频列表 h2 "视频列表 (N)" 对等） -->
    <div class="flex items-center justify-between shrink-0">
      <h2 class="text-sm font-semibold text-slate-800">
        数据集列表 <span class="text-xs text-gray-400 font-normal">({{ allDatasets.length }})</span>
      </h2>
      <div class="flex items-center gap-2">
        <button
          @click="openCreateDatasetModal"
          class="vt-btn-solid-primary vt-btn-size-md"
        >
          <AppIcon name="plus" class="h-4 w-4" />
          <span>新建数据集</span>
        </button>
        <button
          @click="openImportDatasetModal"
          class="vt-btn-secondary vt-btn-size-md"
        >
          <AppIcon name="download" class="h-4 w-4" />
          <span>导入数据集</span>
        </button>
      </div>
    </div>

    <CreateDatasetModal
      v-if="showCreateModal"
      :project="store.currentProject"
      @close="closeCreateModal"
      @submit="handleCreateDataset"
    />

    <ImportDatasetModal
      v-if="showImportModal"
      :project="store.currentProject"
      @close="closeImportModal"
      @submit="handleImportDataset"
    />

    <!-- 数据集表格：当前项目下的标准训练数据集 -->
    <div v-if="allDatasets.length > 0" class="vt-table-shell">
      <div class="overflow-x-auto">
        <table class="vt-table min-w-[1120px] table-fixed">
          <colgroup>
            <col class="w-[28%]" />
            <col class="w-[100px]" />
            <col class="w-[140px]" />
            <col class="w-[220px]" />
            <col class="w-[420px]" />
          </colgroup>
          <thead class="vt-table-head">
            <tr>
              <th class="vt-table-head-cell">数据集</th>
              <th class="vt-table-head-cell">类型</th>
              <th class="vt-table-head-cell">总 / 已标 / 未标</th>
              <th class="vt-table-head-cell">进度</th>
              <th class="vt-table-head-cell text-right">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="ds in allDatasets"
              :key="ds.path"
              class="vt-table-row cursor-pointer"
              :class="store.selectedDataset?.path === ds.path ? 'vt-list-row--selected' : 'bg-white'"
              @click="openDataset(ds)"
            >
              <td class="vt-table-cell">
                <div class="min-w-0">
                  <div class="flex items-center gap-2 min-w-0">
                    <span class="truncate text-sm font-medium text-slate-800">{{ ds.name }}</span>
                    <span
                      v-if="getDatasetVersioningTagLabel(ds)"
                      class="vt-tag vt-tag--sm"
                      :class="getDatasetVersioningTagClass(ds)"
                    >
                      {{ getDatasetVersioningTagLabel(ds) }}
                    </span>
                    <span v-if="ds.tags && ds.tags.length > 0" class="truncate text-[11px] text-gray-500">
                      <span v-for="(tag, i) in ds.tags.slice(0, 3)" :key="tag">
                        <span v-if="i > 0" class="mx-0.5 text-gray-300">·</span>#{{ tag }}
                      </span>
                      <span v-if="ds.tags.length > 3" class="text-gray-400">+{{ ds.tags.length - 3 }}</span>
                    </span>
                  </div>
                  <div v-if="getDatasetVersioningHint(ds)" class="mt-1 text-[11px] text-slate-500">
                    {{ getDatasetVersioningHint(ds) }}
                  </div>
                </div>
              </td>
              <td class="vt-table-cell whitespace-nowrap">
                <span class="vt-tag" :class="getDatasetTypeTagClass(ds)">
                  {{ getDatasetTypeLabel(ds) }}
                </span>
              </td>
              <td class="vt-table-cell whitespace-nowrap">
                <div class="font-mono text-xs tabular-nums text-gray-600">
                  <span>{{ ds.image_count }}</span>
                  <span class="mx-1 text-gray-300">/</span>
                  <span>{{ ds.annotated_count ?? ds.label_count }}</span>
                  <span class="mx-1 text-gray-300">/</span>
                  <span>{{ ds.unannotated_count ?? Math.max(0, Number(ds.image_count || 0) - Number(ds.label_count || 0)) }}</span>
                </div>
              </td>
              <td class="vt-table-cell">
                <div class="flex min-w-0 items-center gap-2">
                  <div class="vt-meter flex-1">
                    <div
                      class="vt-meter__bar"
                      :class="getDatasetTypeProgressClass(ds)"
                      :style="{ width: `${getDatasetProgressPercent(ds)}%` }"
                    ></div>
                  </div>
                  <span class="w-12 shrink-0 text-right font-mono text-[11px] tabular-nums text-gray-500">
                    {{ getDatasetProgressPercent(ds).toFixed(1) }}%
                  </span>
                </div>
              </td>
              <td class="vt-table-cell">
                <div class="flex flex-wrap items-center justify-end gap-x-3 gap-y-1 whitespace-nowrap">
                  <button
                    class="vt-action-btn vt-action-btn--primary"
                    :class="!isTrainingSupported(ds) ? 'cursor-not-allowed opacity-50' : ''"
                    :disabled="!isTrainingSupported(ds)"
                    @click.stop="goToTraining(ds)"
                  >
                    <AppIcon name="train" class="h-3.5 w-3.5" />
                    <span>训练</span>
                  </button>
                  <button
                    v-if="isSplitSupported(ds)"
                    class="vt-action-btn vt-action-btn--warning"
                    @click.stop="openSplit(ds)"
                  >
                    <AppIcon name="split" class="h-3.5 w-3.5" />
                    <span>重切分</span>
                  </button>
                  <button class="vt-action-btn vt-action-btn--info" @click.stop="openTags(ds)">
                    <AppIcon name="tags" class="h-3.5 w-3.5" />
                    <span>标签</span>
                  </button>
                  <button class="vt-action-btn vt-action-btn--info" @click.stop="openVersions(ds)">
                    <AppIcon name="detail" class="h-3.5 w-3.5" />
                    <span>版本</span>
                  </button>
                  <button
                    class="vt-action-btn"
                    :class="downloadingMap[ds.path] ? 'cursor-wait text-gray-400' : 'vt-action-btn--success'"
                    :disabled="!!downloadingMap[ds.path]"
                    @click.stop="downloadDataset(ds)"
                  >
                    <AppIcon name="download" class="h-3.5 w-3.5" />
                    <span>{{ downloadingMap[ds.path] ? '打包中' : '下载' }}</span>
                  </button>
                  <button class="vt-action-btn vt-action-btn--danger" @click.stop="confirmDelete(ds)">
                    <AppIcon name="delete" class="h-3.5 w-3.5" />
                    <span>删除</span>
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="text-center py-10 text-gray-400 text-sm border border-dashed border-gray-300 bg-white flex-1 flex flex-col items-center justify-center">
      <div class="text-3xl mb-2 text-gray-300">📦</div>
      <div>当前项目下还没有数据集</div>
      <button @click="openImportDatasetModal"
              class="vt-btn-solid-primary vt-btn-size-md mt-3">
        <AppIcon name="download" class="h-4 w-4" />
        导入第一个数据集
      </button>
    </div>

    <!-- 重切分 Modal -->
    <div v-if="splitDataset" class="vt-modal-backdrop" @click.self="closeSplit">
      <div class="vt-modal-panel vt-modal-panel--md p-5">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-base font-semibold text-slate-800">重切分数据集：{{ splitDataset.name }}</h3>
          <button class="vt-modal-close" aria-label="关闭重切分数据集弹窗" @click="closeSplit">
            <AppIcon name="close" class="h-4 w-4" />
          </button>
        </div>
        <div class="space-y-4">
          <div class="text-sm leading-6 text-slate-500">
            按整个数据集总样本重新生成 `train / val / test`，并尽量保持类别分布一致。
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">val 占总样本比例</label>
            <input v-model.number="valRatio" type="number" min="0" max="0.9" step="0.05"
                   class="vt-input" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">test 占总样本比例</label>
            <input v-model.number="testRatio" type="number" min="0" max="0.9" step="0.05"
                   class="vt-input" />
          </div>
          <div class="flex justify-end gap-2">
            <button class="vt-btn-link" :disabled="isActionPending(SPLIT_ACTION_KEY)" @click="closeSplit">取消</button>
            <AsyncButton
              class="vt-btn-solid-primary vt-btn-size-md"
              :pending="isActionPending(SPLIT_ACTION_KEY)"
              loading-text="处理中..."
              @click="runSplit"
            >
              开始重切分
            </AsyncButton>
          </div>
        </div>
      </div>
    </div>

    <!-- 标签 Modal -->
    <div v-if="tagsDataset" class="vt-modal-backdrop" @click.self="closeTags">
      <div class="vt-modal-panel vt-modal-panel--lg p-5">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-base font-semibold text-slate-800">数据集标签：{{ tagsDataset.name }}</h3>
          <button class="vt-btn-link" @click="closeTags">关闭</button>
        </div>
        <div class="flex flex-wrap gap-2 mb-4">
          <span v-if="editTags.length === 0" class="text-sm text-gray-500">暂无标签</span>
          <button
            v-for="t in editTags"
            :key="t"
            class="vt-tag"
            @click="removeTag(t)"
          >
            {{ t }} <span class="text-gray-400 ml-1">×</span>
          </button>
        </div>
        <div class="flex gap-2 mb-6">
          <input v-model.trim="newTag" class="vt-input flex-1"
                 placeholder="输入标签后回车或点击添加" @keydown.enter.prevent="addTag" />
          <button class="vt-btn-solid-primary vt-btn-size-md" @click="addTag">添加</button>
        </div>
        <div class="flex justify-end gap-2">
          <button class="vt-btn-link" @click="closeTags">取消</button>
          <AsyncButton
            class="vt-btn-solid-primary vt-btn-size-md"
            :pending="isActionPending(TAGS_ACTION_KEY)"
            loading-text="保存中..."
            @click="saveTags"
          >
            保存
          </AsyncButton>
        </div>
      </div>
    </div>

    <div v-if="versionsDataset" class="vt-modal-backdrop" @click.self="closeVersions">
      <div class="vt-modal-panel vt-modal-panel--lg max-h-[80vh] overflow-y-auto p-5">
        <div class="flex items-start justify-between gap-3 mb-4">
          <div>
            <h3 class="text-base font-semibold text-slate-800">数据集版本：{{ versionsDataset.name }}</h3>
            <div class="mt-1 font-mono text-[11px] text-gray-400 break-all">
              <span>ID {{ versionsDataset.dataset_id || '-' }}</span>
              <span class="mx-1 text-gray-300">·</span>
              <span>当前 {{ getCurrentVersionDisplay(versionsDataset) }}</span>
            </div>
          </div>
          <div class="flex items-center gap-2">
            <button
              v-if="snapshotTask"
              class="vt-btn-link"
              type="button"
              @click="goToSnapshotTask"
            >
              查看任务中心
            </button>
            <AsyncButton
              class="vt-btn-solid-primary vt-btn-size-md"
              :pending="isActionPending(PUBLISH_VERSION_ACTION_KEY)"
              :disabled="isSnapshotInFlight"
              loading-text="发布中..."
              @click="publishVersion"
            >
              发布当前版本
            </AsyncButton>
            <button class="vt-modal-close" aria-label="关闭版本管理弹窗" @click="closeVersions">
              <AppIcon name="close" class="h-4 w-4" />
            </button>
          </div>
        </div>

        <div v-if="snapshotTask" class="mb-4 vt-note" :class="snapshotBannerClass">
          <div class="flex items-center gap-2">
            <span class="vt-tag vt-tag--sm" :class="getTaskStatusTagClass(snapshotTask)">{{ getTaskStatusLabel(snapshotTask) }}</span>
            <span class="text-xs">{{ snapshotTask.message || '快照进行中...' }}</span>
          </div>
          <div v-if="snapshotProgressTotal > 0" class="mt-2 vt-meter h-2 border border-gray-200">
            <div class="vt-meter__bar" :class="getTaskProgressBarClass(snapshotTask)" :style="{ width: `${snapshotProgress}%` }"></div>
          </div>
          <div v-if="snapshotProgressTotal > 0" class="mt-1 text-[11px] text-slate-500">
            {{ snapshotProgress }}% · 已处理 {{ snapshotTask.artifacts?.snapshot_processed || 0 }} / {{ snapshotProgressTotal }}
          </div>
        </div>

        <div v-if="versionsLoading" class="py-10 text-center text-sm text-gray-400">加载版本中...</div>
        <div v-else-if="versionRecords.length === 0" class="py-10 text-center text-sm text-gray-400">暂无版本记录</div>
        <div v-else class="space-y-2">
          <div
            v-for="version in versionRecords"
            :key="version.version_id"
            class="vt-choice-card"
            :class="version.version_id === versionsDataset.current_version_id ? 'vt-choice-card--selected' : 'vt-choice-card--interactive'"
          >
            <div class="flex items-start justify-between gap-3">
              <div class="min-w-0">
                <div class="flex items-center gap-2 flex-wrap">
                  <span class="font-mono text-sm font-semibold text-slate-800">{{ version.version_id }}</span>
                  <span class="vt-tag vt-tag--sm">{{ getVersionReasonLabel(version.reason) }}</span>
                  <span v-if="version.version_id === versionsDataset.current_version_id" class="vt-tag vt-tag--sm">当前</span>
                </div>
                <div class="mt-1 text-xs text-slate-500">
                  创建于 {{ formatVersionTime(version.created_at) }}
                </div>
                <div v-if="version.source_version_id" class="mt-1 font-mono text-[11px] text-gray-400">
                  来源 {{ version.source_version_id }}
                </div>
              </div>
              <div class="shrink-0 flex items-center gap-2">
                <UiTooltip v-if="version.version_id !== versionsDataset.current_version_id" side="top" align="end">
                  <template #trigger>
                    <span class="inline-block" :class="isRestoreRedundant(version) || isSnapshotInFlight ? 'cursor-not-allowed' : ''">
                      <AsyncButton
                        class="vt-btn-secondary vt-btn-size-sm"
                        :disabled="isRestoreRedundant(version) || isSnapshotInFlight"
                        :pending="isActionPending(restoreVersionActionKey(version.version_id))"
                        loading-text="恢复中..."
                        @click="restoreVersion(version)"
                      >
                        恢复为当前
                      </AsyncButton>
                    </span>
                  </template>
                  <template v-if="isRestoreRedundant(version)">当前已是该版本的恢复结果</template>
                  <template v-else-if="isSnapshotInFlight">请等待当前快照任务完成</template>
                  <template v-else>将该版本恢复为当前工作数据集</template>
                </UiTooltip>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 删除确认 Modal -->
    <div v-if="deleteDataset" class="vt-modal-backdrop" @click.self="closeDelete">
      <div class="vt-modal-panel vt-modal-panel--md p-5">
        <h3 class="text-base font-semibold text-rose-700 mb-2">删除数据集</h3>
        <div class="text-sm text-gray-600 mb-6">
          将删除目录：<span class="font-mono">{{ deleteDataset.path }}</span>
        </div>
        <div class="flex justify-end gap-2">
          <button class="vt-btn-link" :disabled="isActionPending(DELETE_ACTION_KEY)" @click="closeDelete">取消</button>
          <AsyncButton
            class="vt-btn-danger"
            :pending="isActionPending(DELETE_ACTION_KEY)"
            loading-text="删除中..."
            @click="runDelete"
          >
            确认删除
          </AsyncButton>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useMainStore } from '../stores/main';
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import api from '../api';
import { useAsyncAction } from '../composables/useAsyncAction';
import { useToast } from '../composables/useToast';
import { useApiCall } from '../composables/useApiCall';
import { useConfirm } from '../composables/useConfirm';
import { useDatasets } from '../composables/useDatasets';
import { useTrainingWorkflowStore } from '../stores/trainingWorkflow';
import { useDatasetSnapshotStore } from '../stores/datasetSnapshot';
import ImportDatasetModal from './ImportDatasetModal.vue';
import CreateDatasetModal from './CreateDatasetModal.vue';
import AppIcon from './ui/AppIcon.vue';
import AsyncButton from './ui/AsyncButton.vue';
import UiTooltip from './ui/Tooltip.vue';
import {
  getDatasetTypeLabel,
  getDatasetTypeProgressClass,
  getDatasetTypeTagClass,
} from '../domain/dataset/datasetType';
import { DATASET_OPERATION, resolveDatasetOperationGuard } from '../utils/datasetCapabilities';
import { assertCapabilityGuard } from '../utils/capabilityGuards';
import { resolveTrainingDatasetGuard } from '../utils/trainingActionGuards';
import { buildDatasetZipFilename, formatDateTime, triggerBlobDownload } from '../utils';
import { getTaskProgressBarClass, getTaskStatusLabel, getTaskStatusTagClass, getTaskTerminalSummaryClass, isTaskActive } from '../domain/task/taskStatus';

const store = useMainStore();
const workflowStore = useTrainingWorkflowStore();
const snapshotStore = useDatasetSnapshotStore();
const router = useRouter();
const route = useRoute();
const toast = useToast();
const { confirm: showConfirm } = useConfirm();
const apiCall = useApiCall();
const asyncAction = useAsyncAction();
const { allDatasets } = useDatasets();
const SPLIT_ACTION_KEY = 'dataset-list:split';
const TAGS_ACTION_KEY = 'dataset-list:save-tags';
const DELETE_ACTION_KEY = 'dataset-list:delete';
const PUBLISH_VERSION_ACTION_KEY = 'dataset-list:publish-version';
const isActionPending = (key) => asyncAction.isPending(key);

// 打开数据集详情页
const openDataset = (ds) => {
  if (!ds) return;
  store.selectDataset(ds);
  router.push({
    name: 'dataset-detail',
    params: {
      project: encodeURIComponent(store.currentProject?.name || ''),
      name: encodeURIComponent(ds.name),
    },
    query: {
      dataset_id: ds.dataset_id || '',
    },
  });
};

// 新建数据集弹窗
const showCreateModal = ref(false);
const openCreateDatasetModal = () => { showCreateModal.value = true; };
const closeCreateModal = () => { showCreateModal.value = false; };

const handleCreateDataset = async ({ datasetName, visionTaskType, initialClasses, files, projectPath, onProgress, onDone }) => {
  try {
    // 1) 建空目录（分类任务下传 initial_classes 一次性创建空分类目录）
    onProgress && onProgress({ phase: 'creating', progress: 5, message: '正在创建数据集目录…' });
    const created = await api.createEmptyDataset({
      project_path: projectPath,
      dataset_name: datasetName,
      vision_task_type: visionTaskType,
      initial_classes: Array.isArray(initialClasses) ? initialClasses : [],
    });
    onProgress && onProgress({ phase: 'creating', progress: 15, message: '目录已创建' });

    // 2) 上传图片（如有）
    if (Array.isArray(files) && files.length > 0) {
      const fd = new FormData();
      fd.append('project_path', projectPath);
      fd.append('dataset_name', datasetName);
      fd.append('split', 'train');
      for (const f of files) fd.append('files', f, f.name);
      onProgress && onProgress({ phase: 'uploading', progress: 20, message: '正在上传图片…' });
      await api.uploadDatasetImages(fd, (pct) => {
        // 整个上传阶段占 20~80 进度区间。
        const mapped = 20 + Math.round(pct * 0.6);
        onProgress && onProgress({ phase: 'uploading', progress: mapped, message: `上传中 ${pct}%` });
      });
      onProgress && onProgress({ phase: 'uploading', progress: 80, message: '上传完成' });
    } else {
      onProgress && onProgress({ phase: 'uploading', progress: 80, message: '跳过上传' });
    }

    // 3) 触发初始快照入库
    onProgress && onProgress({ phase: 'snapshot', progress: 85, message: '正在建立初始快照…' });
    const datasetRoot = created?.dataset_root || `${projectPath}/training/${datasetName}`;
    const snap = await api.startDatasetSnapshot({
      project_path: projectPath,
      dataset_root: datasetRoot,
      dataset_name: datasetName,
      mode: 'add',
      reason: 'create_empty',
    });
    const taskId = snap?.task_id;
    if (taskId) {
      await waitForSnapshot(taskId, datasetName, (state) => {
        if (state.status === 'completed') {
          onProgress && onProgress({ phase: 'snapshot', progress: 100, message: '快照完成' });
        } else if (state.status === 'failed' || state.status === 'stopped') {
          throw new Error(state.message || '快照任务失败');
        } else if (state.message) {
          onProgress && onProgress({ phase: 'snapshot', message: state.message });
        }
      });
    }
    toast.success(`数据集「${datasetName}」已创建`);
    await store.refreshKeepSelection();
    onDone && onDone();
  } catch (e) {
    toast.error(`创建失败: ${e?.message || e}`);
    onDone && onDone(e);
  }
};

const waitForSnapshot = (taskId, datasetName, onState) => {
  // 简单轮询：等到 completed/failed/stopped 才 resolve；其他异常走 reject。
  return new Promise((resolve, reject) => {
    let stopped = false;
    const poll = async () => {
      if (stopped) return;
      try {
        const task = await api.getTask(taskId);
        if (!task) {
          setTimeout(poll, 2000);
          return;
        }
        onState && onState(task);
        if (task.status === 'completed') {
          stopped = true;
          resolve(task);
        } else if (task.status === 'failed' || task.status === 'stopped' || task.status === 'interrupted') {
          stopped = true;
          resolve(task);
        } else {
          setTimeout(poll, 2000);
        }
      } catch (e) {
        stopped = true;
        reject(e);
      }
    };
    poll();
  });
};

// 导入数据集弹窗
const showImportModal = ref(false);
const openImportDatasetModal = () => { showImportModal.value = true; };
const closeImportModal = () => { showImportModal.value = false; };
const handleImportDataset = async ({ file, projectPath, targetName, visionTaskType, onProgress, onDone }) => {
  try {
    const res = await store.importDataset(file, projectPath, targetName, visionTaskType, onProgress);
    const fmt = res.source_format || 'yolo';
    const note = fmt === 'yolo' ? '' : `（原 ${fmt.toUpperCase()} 格式，已自动转换为 YOLO）`;
    toast.success(`数据集「${res.dataset_name}」已导入${note}`);
    // 通知 ImportDatasetModal: 成功，让它显示成功态后自动关闭
    onDone && onDone();
  } catch (e) {
    toast.error(`导入失败: ${e.message}`);
    // 通知 ImportDatasetModal: 失败，让它显示错误
    onDone && onDone(e);
  }
};

const splitDataset = ref(null);
const valRatio = ref(0.2);
const testRatio = ref(0.0);

const tagsDataset = ref(null);
const editTags = ref([]);
const newTag = ref('');
const versionsDataset = ref(null);
const versionsLoading = ref(false);
const versionRecords = ref([]);
const snapshotRefreshPending = ref(false);

const deleteDataset = ref(null);

const downloadingMap = ref({});

const getDatasetProgressPercent = (dataset) => Math.min(100, (Number(dataset?.annotation_rate) || 0) * 100);
const getTrainingGuard = (dataset) => resolveTrainingDatasetGuard(dataset);
const getSplitGuard = (dataset) => resolveDatasetOperationGuard(dataset, DATASET_OPERATION.SPLIT_DATASET);
const isTrainingSupported = (dataset) => getTrainingGuard(dataset).enabled;
const isSplitSupported = (dataset) => getSplitGuard(dataset).enabled;
const formatVersionTime = (value) => formatDateTime(value, { dateStyle: 'compact', timeStyle: 'short' });
const restoreVersionActionKey = (versionId) => `dataset-list:restore-version:${String(versionId || '')}`;

// 数据集版本就绪状态：写在与 ``.vision-train.meta.json`` 同文件里的衍生字段，
// 用于判断数据集是否已经产生过至少一个可用快照。和任务状态（TASK_STATUS_*）无关。
const DATASET_VERSIONING_STATUS = Object.freeze({
  PENDING: 'pending', // 首个快照入库中
  READY:   'ready',   // 有 current_version_id 可用
  FAILED:  'failed',  // 首个快照失败
});

const VERSION_REASON_LABELS = Object.freeze({
  bootstrap: '初始化',
  import: '导入',
  manual_publish: '手动发布',
  restore: '恢复版本',
  create_subset: '生成子集',
  augment_subset: '弱类补偿',
  merge_dataset_pair: '合并数据集',
  split_dataset: '重切分',
  deduplicate_dataset: '图片去重',
  create_empty: '新建数据集',
});

const getVersionReasonLabel = (reason) => VERSION_REASON_LABELS[String(reason || '').trim()] || String(reason || '未知变更');

// 根据数据集的就绪状态汇总出 UI 展示文案 / tag class / hint，
// 统一避免分散的 if-chain；数据集已有 current_version_id 时按 ready 处理。
const VERSIONING_PRESENTATION = Object.freeze({
  pending: {
    tag:        '快照中',
    tagClass:   'vt-tag-info',
    hint:       '建立初始快照中，版本任务可在任务中心查看',
    fallback:   '首版快照中',
  },
  failed: {
    tag:        '快照失败',
    tagClass:   'vt-tag-danger',
    hint:       '初始快照失败，请到任务中心处理',
    fallback:   '首版快照失败',
  },
});

const presentVersioning = (dataset) => {
  const status = dataset?.current_version_id
    ? DATASET_VERSIONING_STATUS.READY
    : dataset?.versioning_status;
  return VERSIONING_PRESENTATION[status] || null;
};

const getDatasetVersioningTagLabel = (dataset) => presentVersioning(dataset)?.tag || '';
const getDatasetVersioningTagClass = (dataset) => presentVersioning(dataset)?.tagClass || '';
const getDatasetVersioningHint     = (dataset) => presentVersioning(dataset)?.hint || '';
const getCurrentVersionDisplay     = (dataset) => {
  if (dataset?.current_version_id) return dataset.current_version_id;
  return presentVersioning(dataset)?.fallback || '-';
};

const isRestoreRedundant = (version) => {
  if (!version || !versionsDataset.value?.current_version_id) return false;
  if (version.version_id === versionsDataset.value.current_version_id) return false;
  const current = versionRecords.value.find((item) => item.version_id === versionsDataset.value.current_version_id);
  if (!current) return false;
  return current.reason === 'restore' && current.source_version_id === version.version_id;
};

// 快照任务相关（统一走 taskStatus.js 的状态语义，不另造一份标签表）
const snapshotTask = computed(() => {
  const ds = versionsDataset.value;
  if (!ds || !ds.dataset_id) return null;
  return snapshotStore.activeTaskFor(ds.dataset_id);
});
const snapshotProgress = computed(() => {
  const t = snapshotTask.value;
  if (!t) return 0;
  const processed = t.artifacts?.snapshot_processed || 0;
  const total = t.artifacts?.snapshot_total || 0;
  if (!total) return 0;
  return Math.min(100, Math.round((processed * 100) / total));
});
const snapshotProgressTotal = computed(() => {
  const t = snapshotTask.value;
  return t?.artifacts?.snapshot_total || 0;
});
const isSnapshotInFlight = computed(() => isTaskActive(snapshotTask.value));
const snapshotBannerClass = computed(() => getTaskTerminalSummaryClass(snapshotTask.value));
const goToSnapshotTask = () => {
  const t = snapshotTask.value;
  if (!t || !t.id) return;
  router.push({
    name: 'tasks-center',
    query: {
      task_id: t.id,
      return_to: route.fullPath,
    },
  });
};

onMounted(() => {
  store.refreshKeepSelection();
  store.ensureVersioningPoll();
});

onBeforeUnmount(() => {
  store.stopVersioningPoll();
  // 组件卸载时清理所有 dataset 的轮询，避免泄漏 setInterval
  Object.keys(snapshotStore.pollTimers || {}).forEach((id) => snapshotStore.stopPolling(id));
});

const findDatasetAfterRefresh = (source) => {
  if (!source) return null;
  return allDatasets.value.find((item) => item.dataset_id && item.dataset_id === source.dataset_id)
    || allDatasets.value.find((item) => item.path === source.path)
    || allDatasets.value.find((item) => item.name === source.name)
    || null;
};

const loadVersions = async (dataset = versionsDataset.value) => {
  if (!dataset || !store.currentProject?.path) return;
  versionsLoading.value = true;
  try {
    const result = await api.getDatasetVersions({
      project_path: store.currentProject.path,
      dataset_name: dataset.name,
    });
    const hasCurrentVersionId = Object.prototype.hasOwnProperty.call(result || {}, 'current_version_id');
    const hasVersioningStatus = Object.prototype.hasOwnProperty.call(result || {}, 'versioning_status');
    versionRecords.value = Array.isArray(result?.versions) ? result.versions : [];
    versionsDataset.value = {
      ...dataset,
      dataset_id: result?.dataset_id || dataset.dataset_id,
      versioning_status: hasVersioningStatus ? result.versioning_status : dataset.versioning_status,
      current_version_id: hasCurrentVersionId ? result.current_version_id : dataset.current_version_id,
    };
  } finally {
    versionsLoading.value = false;
  }
};

const downloadDataset = async (ds) => {
  if (!ds) return;
  downloadingMap.value = { ...downloadingMap.value, [ds.path]: true };
  try {
    const blob = await api.downloadDatasetZip({
      project_path: store.currentProject.path,
      dataset_name: ds.name
    });
    triggerBlobDownload(blob, buildDatasetZipFilename(ds.name));
  } catch (e) {
    console.error(e);
    toast.error('下载失败');
  } finally {
    const next = { ...downloadingMap.value };
    delete next[ds.path];
    downloadingMap.value = next;
  }
};

const goToTraining = (ds) => {
  if (!store.currentProject || !ds) return;
  if (!assertCapabilityGuard(getTrainingGuard(ds), toast.warn)) return;
  store.selectDataset(ds);
  router.push({
    name: 'dataset-train',
    params: {
      project: encodeURIComponent(store.currentProject.name),
      name: encodeURIComponent(ds.name),
    },
    query: {
      dataset_id: ds.dataset_id || '',
    },
  });
};

const openSplit = (ds) => {
  if (!assertCapabilityGuard(getSplitGuard(ds), toast.warn)) return;
  splitDataset.value = ds;
  valRatio.value = 0.2;
  testRatio.value = 0.0;
};

const closeSplit = () => {
  splitDataset.value = null;
};

const runSplit = async () => {
  if (!splitDataset.value) return;
  if (valRatio.value < 0 || testRatio.value < 0 || valRatio.value + testRatio.value >= 1) {
    toast.warn('比例设置不合法：val + test 占比之和需要小于 1');
    return;
  }
  await asyncAction.run(SPLIT_ACTION_KEY, async () => {
    await apiCall(api.splitDataset({
      project_path: store.currentProject.path,
      dataset_name: splitDataset.value.name,
      val_ratio: valRatio.value,
      test_ratio: testRatio.value
    }), {
      onSuccess: async (data) => {
        await store.refreshKeepSelection();
        closeSplit();
        const c = data.counts || {};
        toast.success(`重切分完成：train=${c.train ?? '-'} val=${c.val ?? '-'} test=${c.test ?? '-'}`);
      },
    });
  });
};

const openTags = (ds) => {
  tagsDataset.value = ds;
  editTags.value = Array.isArray(ds.tags) ? [...ds.tags] : [];
  newTag.value = '';
};

const closeTags = () => {
  tagsDataset.value = null;
  editTags.value = [];
  newTag.value = '';
};

const openVersions = async (ds) => {
  versionsDataset.value = ds;
  versionRecords.value = [];
  try {
    await loadVersions(ds);
    const dsId = versionsDataset.value?.dataset_id;
    if (dsId) {
      snapshotStore.startPolling(dsId, {
        projectPath: store.currentProject?.path,
      });
    }
  } catch (e) {
    versionsDataset.value = null;
    toast.error(e?.message || '加载版本失败');
  }
};

const closeVersions = () => {
  const dsId = versionsDataset.value?.dataset_id;
  if (dsId) snapshotStore.stopPolling(dsId);
  versionsDataset.value = null;
  versionRecords.value = [];
  versionsLoading.value = false;
};

const refreshVersionsAfterSnapshot = async (datasetId) => {
  if (!datasetId || snapshotRefreshPending.value) return;
  const currentDataset = versionsDataset.value;
  if (!currentDataset || currentDataset.dataset_id !== datasetId) return;
  snapshotRefreshPending.value = true;
  try {
    await store.refreshKeepSelection();
    const refreshedDataset = findDatasetAfterRefresh(currentDataset) || currentDataset;
    versionsDataset.value = refreshedDataset;
    workflowStore.invalidateDataset({
      project_path: store.currentProject?.path,
      dataset_name: refreshedDataset.name,
      dataset_id: refreshedDataset.dataset_id,
    });
    await loadVersions(refreshedDataset);
  } finally {
    snapshotRefreshPending.value = false;
  }
};

const addTag = () => {
  const t = (newTag.value || '').trim();
  if (!t) return;
  if (!editTags.value.includes(t)) {
    editTags.value.push(t);
  }
  newTag.value = '';
};

const removeTag = (t) => {
  editTags.value = editTags.value.filter(x => x !== t);
};

const saveTags = async () => {
  if (!tagsDataset.value) return;
  await asyncAction.run(TAGS_ACTION_KEY, async () => {
    await apiCall(api.updateDatasetTags({
      project_path: store.currentProject.path,
      dataset_name: tagsDataset.value.name,
      tags: editTags.value
    }), {
      onSuccess: async () => {
        await store.refreshKeepSelection();
        closeTags();
        toast.success('标签已保存');
      },
    });
  });
};

const publishVersion = async () => {
  if (!versionsDataset.value || !store.currentProject?.path) return;
  if (isSnapshotInFlight.value) {
    toast.warn('请等待当前快照任务完成');
    return;
  }
  const ds = versionsDataset.value;
  const payload = {
    project_path: store.currentProject.path,
    dataset_root: ds.path,
    dataset_name: ds.name,
    mode: 'commit',
    reason: 'manual_publish',
  };
  await asyncAction.run(PUBLISH_VERSION_ACTION_KEY, async () => {
    const result = await apiCall(api.startDatasetSnapshot(payload), {
      successMsg: '快照任务已启动，版本将在完成后生成',
    });
    if (!result || !result.task_id) return;
    // 立即拉一次任务详情作为种子，避免首屏白屏；拉失败时降级为本地占位
    const seed = await apiCall(api.getTask(result.task_id), { silent: true }) || {
      id: result.task_id,
      type: 'dataset_snapshot',
      status: 'pending',
      progress: 0,
      message: '快照任务排队中',
      artifacts: { snapshot_processed: 0, snapshot_total: 0 },
    };
    if (ds.dataset_id) {
      snapshotStore.startPolling(ds.dataset_id, {
        projectPath: store.currentProject.path,
        taskId: result.task_id,
        seed,
        onTerminal: async (task) => {
          if (task?.status === 'completed') {
            await refreshVersionsAfterSnapshot(ds.dataset_id);
          }
        },
      });
    }
  });
};

const restoreVersion = async (version) => {
  if (!versionsDataset.value || !version?.version_id || !store.currentProject?.path) return;
  const ok = await showConfirm({
    title: '恢复数据集版本',
    message: `将把当前工作数据集恢复为版本 ${version.version_id}，并生成一个新的当前版本，是否继续？`,
    confirmText: '恢复',
  });
  if (!ok) return;
  await asyncAction.run(restoreVersionActionKey(version.version_id), async () => {
    await apiCall(api.restoreDatasetVersion({
      project_path: store.currentProject.path,
      dataset_name: versionsDataset.value.name,
      version_id: version.version_id,
    }), {
      onSuccess: async () => {
        await store.refreshKeepSelection();
        const refreshedDataset = findDatasetAfterRefresh(versionsDataset.value) || versionsDataset.value;
        versionsDataset.value = refreshedDataset;
        workflowStore.invalidateDataset({
          project_path: store.currentProject.path,
          dataset_name: refreshedDataset.name,
          dataset_id: refreshedDataset.dataset_id,
        });
        await loadVersions(refreshedDataset);
        toast.success('已恢复到指定版本');
      },
    });
  });
};

const confirmDelete = (ds) => {
  deleteDataset.value = ds;
};

const closeDelete = () => {
  deleteDataset.value = null;
};

const runDelete = async () => {
  if (!deleteDataset.value) return;
  await asyncAction.run(DELETE_ACTION_KEY, async () => {
    await apiCall(api.deleteDatasetFolder({
      project_path: store.currentProject.path,
      dataset_name: deleteDataset.value.name,
      dataset_path: deleteDataset.value.path
    }), {
      onSuccess: async () => {
        workflowStore.invalidateDataset({
          project_path: store.currentProject.path,
          dataset_name: deleteDataset.value.name,
          dataset_id: deleteDataset.value.dataset_id,
        });
        await store.refreshKeepSelection();
        closeDelete();
        toast.success('数据集已删除');
      },
    });
  });
};
</script>
