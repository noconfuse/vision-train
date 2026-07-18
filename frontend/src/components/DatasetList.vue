<template>
  <div class="vt-view p-4">
    <!-- 视图标题（与视频列表 h2 "视频列表 (N)" 对等） -->
    <div class="flex items-center justify-between shrink-0">
      <h2 class="text-sm font-semibold text-slate-800">
        数据集列表 <span class="text-xs text-gray-400 font-normal">({{ allDatasets.length }})</span>
      </h2>
      <button
        @click="openImportDatasetModal"
        class="vt-btn-solid-primary vt-btn-size-md"
      >
        <AppIcon name="download" class="h-4 w-4" />
        <span>导入数据集</span>
      </button>
    </div>

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
              <th class="vt-table-head-cell">图片 / 标签</th>
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
                    <span v-if="ds.tags && ds.tags.length > 0" class="truncate text-[11px] text-gray-500">
                      <span v-for="(tag, i) in ds.tags.slice(0, 3)" :key="tag">
                        <span v-if="i > 0" class="mx-0.5 text-gray-300">·</span>#{{ tag }}
                      </span>
                      <span v-if="ds.tags.length > 3" class="text-gray-400">+{{ ds.tags.length - 3 }}</span>
                    </span>
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
                  <span>{{ ds.label_count }}</span>
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
                <div class="flex flex-wrap items-center justify-end gap-x-3 gap-y-1 whitespace-nowrap" @click.stop>
                  <button class="vt-action-btn vt-action-btn--primary" @click="goToTraining(ds)">
                    <AppIcon name="train" class="h-3.5 w-3.5" />
                    <span>训练</span>
                  </button>
                  <button class="vt-action-btn vt-action-btn--warning" @click="openSplit(ds)">
                    <AppIcon name="split" class="h-3.5 w-3.5" />
                    <span>分割</span>
                  </button>
                  <button class="vt-action-btn vt-action-btn--info" @click="openTags(ds)">
                    <AppIcon name="tags" class="h-3.5 w-3.5" />
                    <span>标签</span>
                  </button>
                  <button
                    class="vt-action-btn"
                    :class="downloadingMap[ds.path] ? 'cursor-wait text-gray-400' : 'vt-action-btn--success'"
                    :disabled="!!downloadingMap[ds.path]"
                    @click="downloadDataset(ds)"
                  >
                    <AppIcon name="download" class="h-3.5 w-3.5" />
                    <span>{{ downloadingMap[ds.path] ? '打包中' : '下载' }}</span>
                  </button>
                  <button class="vt-action-btn vt-action-btn--danger" @click="confirmDelete(ds)">
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

    <!-- 分割 Modal -->
    <div v-if="splitDataset" class="vt-modal-backdrop" @click.self="closeSplit">
      <div class="vt-modal-panel vt-modal-panel--md p-5">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-base font-semibold text-slate-800">分割数据集：{{ splitDataset.name }}</h3>
          <button class="vt-modal-close" aria-label="关闭分割数据集弹窗" @click="closeSplit">
            <AppIcon name="close" class="h-4 w-4" />
          </button>
        </div>
        <div class="space-y-4">
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">验证集比例 (val)</label>
            <input v-model.number="valRatio" type="number" min="0" max="0.9" step="0.05"
                   class="vt-input" />
          </div>
          <div>
            <label class="block text-xs font-medium text-gray-700 mb-1">测试集比例 (test)</label>
            <input v-model.number="testRatio" type="number" min="0" max="0.9" step="0.05"
                   class="vt-input" />
          </div>
          <div class="flex justify-end gap-2">
            <button class="vt-btn-link" @click="closeSplit">取消</button>
            <button class="vt-btn-solid-primary vt-btn-size-md" :disabled="splitLoading" @click="runSplit">
              {{ splitLoading ? '处理中...' : '开始分割' }}
            </button>
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
          <button class="vt-btn-solid-primary vt-btn-size-md" :disabled="tagsSaving" @click="saveTags">
            {{ tagsSaving ? '保存中...' : '保存' }}
          </button>
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
          <button class="vt-btn-link" @click="closeDelete">取消</button>
          <button class="vt-btn-danger" :disabled="deleteLoading" @click="runDelete">
            {{ deleteLoading ? '删除中...' : '确认删除' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useMainStore } from '../stores/main';
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import api from '../api';
import { useToast } from '../composables/useToast';
import { useApiCall } from '../composables/useApiCall';
import { useDatasets } from '../composables/useDatasets';
import ImportDatasetModal from './ImportDatasetModal.vue';
import AppIcon from './ui/AppIcon.vue';
import {
  getDatasetTypeLabel,
  getDatasetTypeProgressClass,
  getDatasetTypeTagClass,
} from '../datasetType';
import { buildDatasetZipFilename, triggerBlobDownload } from '../utils';

const store = useMainStore();
const router = useRouter();
const toast = useToast();
const apiCall = useApiCall();
const { allDatasets } = useDatasets();

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
  });
};

// 导入数据集弹窗
const showImportModal = ref(false);
const openImportDatasetModal = () => { showImportModal.value = true; };
const closeImportModal = () => { showImportModal.value = false; };
const handleImportDataset = async ({ file, projectPath, targetName, onProgress, onDone }) => {
  try {
    const res = await store.importDataset(file, projectPath, targetName, onProgress);
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
const splitLoading = ref(false);
const valRatio = ref(0.2);
const testRatio = ref(0.0);

const tagsDataset = ref(null);
const editTags = ref([]);
const newTag = ref('');
const tagsSaving = ref(false);

const deleteDataset = ref(null);
const deleteLoading = ref(false);

const downloadingMap = ref({});

const getDatasetProgressPercent = (dataset) => Math.min(100, (Number(dataset?.annotation_rate) || 0) * 100);

const refreshProjectsKeepSelection = async () => {
  const cur = store.currentProject;
  const selectedPath = store.selectedDataset?.path;
  // silent 刷新：不触发 Sidebar 的 loading
  await store.fetchProjects({ silent: true });
  if (cur) {
    const next = store.projects.find(p => p.id === cur.id) || store.projects.find(p => p.path === cur.path);
    store.currentProject = next || null;
    if (store.currentProject && selectedPath) {
      store.selectedDataset = allDatasets.value.find(d => d.path === selectedPath) || null;
    } else {
      store.selectedDataset = null;
    }
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
  store.selectDataset(ds);
  router.push({
    name: 'dataset-train',
    params: {
      project: encodeURIComponent(store.currentProject.name),
      name: encodeURIComponent(ds.name),
    },
  });
};

const openSplit = (ds) => {
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
    toast.warn('比例设置不合法：val + test 需要小于 1');
    return;
  }
  splitLoading.value = true;
  await apiCall(api.splitDataset({
    project_path: store.currentProject.path,
    dataset_name: splitDataset.value.name,
    val_ratio: valRatio.value,
    test_ratio: testRatio.value
  }), {
    onSuccess: async (data) => {
      await refreshProjectsKeepSelection();
      closeSplit();
      const c = data.counts || {};
      toast.success(`分割完成：train=${c.train ?? '-'} val=${c.val ?? '-'} test=${c.test ?? '-'}`);
    },
    finally: () => { splitLoading.value = false; },
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
  tagsSaving.value = true;
  await apiCall(api.updateDatasetTags({
    project_path: store.currentProject.path,
    dataset_name: tagsDataset.value.name,
    tags: editTags.value
  }), {
    onSuccess: async () => {
      await refreshProjectsKeepSelection();
      closeTags();
      toast.success('标签已保存');
    },
    finally: () => { tagsSaving.value = false; },
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
  deleteLoading.value = true;
  await apiCall(api.deleteDatasetFolder({
    project_path: store.currentProject.path,
    dataset_name: deleteDataset.value.name,
    dataset_path: deleteDataset.value.path
  }), {
    onSuccess: async () => {
      await refreshProjectsKeepSelection();
      closeDelete();
      toast.success('数据集已删除');
    },
    finally: () => { deleteLoading.value = false; },
  });
};
</script>
