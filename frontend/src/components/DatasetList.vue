<template>
  <div class="bg-white rounded-xl shadow-sm p-6 mb-6">
    <h2 class="text-xl font-semibold text-slate-800 mb-5">数据集列表</h2>
    
    <!-- Trainable Datasets -->
    <div v-if="datasets.trainable && datasets.trainable.length > 0" class="mb-8">
      <h3 class="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3">可训练数据集</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
        <div v-for="ds in datasets.trainable" 
             :key="ds.path"
             class="border-2 rounded-xl p-5 cursor-pointer transition-all duration-200"
             :class="store.selectedDataset?.path === ds.path ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-blue-400'"
             @click="store.selectDataset(ds)">
          
          <div class="flex justify-between items-start mb-4">
            <span class="font-semibold text-lg truncate pr-2">{{ ds.name }}</span>
            <span class="px-2 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
              就绪
            </span>
          </div>
          
          <div class="space-y-2 text-sm text-gray-600">
            <div class="flex justify-between">
              <span>图片数</span>
              <span class="font-mono">{{ ds.image_count }}</span>
            </div>
            <div class="flex justify-between">
              <span>标签数</span>
              <span class="font-mono">{{ ds.label_count }}</span>
            </div>
          </div>
          
          <div class="mt-4 h-1.5 w-full bg-gray-200 rounded-full overflow-hidden">
            <div class="h-full bg-blue-500 transition-all duration-300" 
                 :style="{ width: `${ds.annotation_rate * 100}%` }"></div>
          </div>

          <div v-if="ds.tags && ds.tags.length > 0" class="mt-3 flex flex-wrap gap-1">
            <span v-for="tag in ds.tags" :key="tag" class="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">
              #{{ tag }}
            </span>
          </div>
          
          <div class="mt-4 pt-4 border-t border-gray-100 flex gap-2 justify-end" @click.stop>
            <button @click="openHistory(ds)" class="px-3 py-1.5 text-xs font-medium bg-emerald-50 text-emerald-700 hover:bg-emerald-100 rounded-lg transition-colors">
              📜 历史
            </button>
            <button @click="openSplit(ds)" class="px-3 py-1.5 text-xs font-medium bg-amber-50 text-amber-700 hover:bg-amber-100 rounded-lg transition-colors">
              ✂️ 分割
            </button>
            <button @click="openTags(ds)" class="px-3 py-1.5 text-xs font-medium bg-slate-50 text-slate-700 hover:bg-slate-100 rounded-lg transition-colors">
              🏷️ 标签
            </button>
            <button @click="downloadDataset(ds)" class="px-3 py-1.5 text-xs font-medium bg-sky-50 text-sky-700 hover:bg-sky-100 rounded-lg transition-colors disabled:opacity-50" :disabled="!!downloadingMap[ds.path]">
              {{ downloadingMap[ds.path] ? '⏳ 打包中...' : '⬇️ 下载' }}
            </button>
            <button @click="confirmDelete(ds)" class="px-3 py-1.5 text-xs font-medium bg-rose-50 text-rose-700 hover:bg-rose-100 rounded-lg transition-colors">
              🗑️ 删除
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Annotatable Datasets -->
    <div v-if="datasets.annotatable && datasets.annotatable.length > 0">
      <h3 class="text-sm font-bold text-gray-500 uppercase tracking-wider mb-3">Need Annotation</h3>
      <div class="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-5">
        <div v-for="ds in datasets.annotatable" 
             :key="ds.path"
             class="border-2 rounded-xl p-5 cursor-pointer transition-all duration-200"
             :class="store.selectedDataset?.path === ds.path ? 'border-blue-500 bg-blue-50' : 'border-gray-200 hover:border-blue-400'"
             @click="store.selectDataset(ds)">
             
          <div class="flex justify-between items-start mb-4">
            <span class="font-semibold text-lg truncate pr-2">{{ ds.name }}</span>
            <span class="px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
              草稿
            </span>
          </div>
          
           <div class="space-y-2 text-sm text-gray-600">
            <div class="flex justify-between">
              <span>图片数</span>
              <span class="font-mono">{{ ds.image_count }}</span>
            </div>
            <div class="flex justify-between">
              <span>进度</span>
              <span class="font-mono">{{ (ds.annotation_rate * 100).toFixed(1) }}%</span>
            </div>
          </div>
          
          <div class="mt-4 h-1.5 w-full bg-gray-200 rounded-full overflow-hidden">
            <div class="h-full bg-yellow-500 transition-all duration-300" 
                 :style="{ width: `${ds.annotation_rate * 100}%` }"></div>
          </div>

          <div v-if="ds.tags && ds.tags.length > 0" class="mt-3 flex flex-wrap gap-1">
            <span v-for="tag in ds.tags" :key="tag" class="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">
              #{{ tag }}
            </span>
          </div>
          
          <div class="mt-4 pt-4 border-t border-gray-100 flex gap-2 justify-end" @click.stop>
            <button @click="openHistory(ds)" class="px-3 py-1.5 text-xs font-medium bg-emerald-50 text-emerald-700 hover:bg-emerald-100 rounded-lg transition-colors">
              📜 历史
            </button>
            <button @click="openSplit(ds)" class="px-3 py-1.5 text-xs font-medium bg-amber-50 text-amber-700 hover:bg-amber-100 rounded-lg transition-colors">
              ✂️ 分割
            </button>
            <button @click="openTags(ds)" class="px-3 py-1.5 text-xs font-medium bg-slate-50 text-slate-700 hover:bg-slate-100 rounded-lg transition-colors">
              🏷️ 标签
            </button>
            <button @click="downloadDataset(ds)" class="px-3 py-1.5 text-xs font-medium bg-sky-50 text-sky-700 hover:bg-sky-100 rounded-lg transition-colors disabled:opacity-50" :disabled="!!downloadingMap[ds.path]">
              {{ downloadingMap[ds.path] ? '⏳ 打包中...' : '⬇️ 下载' }}
            </button>
            <button @click="confirmDelete(ds)" class="px-3 py-1.5 text-xs font-medium bg-rose-50 text-rose-700 hover:bg-rose-100 rounded-lg transition-colors">
              🗑️ 删除
            </button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="(!datasets.trainable?.length) && (!datasets.annotatable?.length)" class="text-center py-10 text-gray-400">
      No datasets found in this project.
    </div>
  </div>

  <div v-if="historyDataset" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="closeHistory">
    <div class="bg-white rounded-xl shadow-xl w-full max-w-3xl p-6">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-bold">训练历史：{{ historyDataset.name }}</h3>
        <button class="text-gray-500 hover:text-gray-700" @click="closeHistory">关闭</button>
      </div>
      <div v-if="historyLoading" class="py-10 text-center text-gray-500">加载中...</div>
      <div v-else-if="historyRuns.length === 0" class="py-10 text-center text-gray-500">暂无训练记录</div>
      <div v-else class="overflow-auto max-h-[70vh] border border-gray-100 rounded-lg">
        <table class="min-w-full text-sm">
          <thead class="sticky top-0 bg-gray-50 text-gray-600">
            <tr>
              <th class="text-left px-4 py-2 font-medium">训练ID</th>
              <th class="text-left px-4 py-2 font-medium">模型</th>
              <th class="text-left px-4 py-2 font-medium">epochs</th>
              <th class="text-left px-4 py-2 font-medium">imgsz</th>
              <th class="text-left px-4 py-2 font-medium">mAP50</th>
              <th class="text-left px-4 py-2 font-medium">mAP50-95</th>
              <th class="text-left px-4 py-2 font-medium">产物</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-gray-100">
            <tr v-for="r in historyRuns" :key="r.training_id" class="hover:bg-gray-50">
              <td class="px-4 py-2 font-mono text-xs text-gray-700">{{ r.training_id || r.id }}</td>
              <td class="px-4 py-2 text-gray-700">{{ r.model_name || r.config?.model_name || '-' }}</td>
              <td class="px-4 py-2 text-gray-700">{{ r.config?.epochs ?? '-' }}</td>
              <td class="px-4 py-2 text-gray-700">{{ r.config?.imgsz ?? '-' }}</td>
              <td class="px-4 py-2 text-gray-700">{{ metric(r, 'mAP50') ?? metric(r, 'map50') ?? '-' }}</td>
              <td class="px-4 py-2 text-gray-700">{{ metric(r, 'mAP50-95') ?? metric(r, 'map') ?? '-' }}</td>
              <td class="px-4 py-2 text-gray-700 text-xs space-x-2">
                <a :href="`/api/file?path=${encodePath(r.path + '/weights/best.pt')}`" target="_blank" class="text-blue-600 hover:underline">best.pt</a>
                <a :href="`/api/file?path=${encodePath(r.path + '/confusion_matrix.png')}`" target="_blank" class="text-blue-600 hover:underline">matrix</a>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <div v-if="splitDataset" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="closeSplit">
    <div class="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-bold">分割数据集：{{ splitDataset.name }}</h3>
        <button class="text-gray-500 hover:text-gray-700" @click="closeSplit">关闭</button>
      </div>
      <div class="space-y-4">
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">验证集比例 (val)</label>
          <input v-model.number="valRatio" type="number" min="0" max="0.9" step="0.05" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" />
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-700 mb-1">测试集比例 (test)</label>
          <input v-model.number="testRatio" type="number" min="0" max="0.9" step="0.05" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm" />
        </div>
        <div class="flex justify-end gap-2">
          <button class="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg text-sm" @click="closeSplit">取消</button>
          <button class="px-4 py-2 bg-amber-500 hover:bg-amber-600 text-white rounded-lg text-sm disabled:opacity-50" :disabled="splitLoading" @click="runSplit">
            {{ splitLoading ? '处理中...' : '开始分割' }}
          </button>
        </div>
      </div>
    </div>
  </div>

  <div v-if="tagsDataset" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="closeTags">
    <div class="bg-white rounded-xl shadow-xl w-full max-w-lg p-6">
      <div class="flex items-center justify-between mb-4">
        <h3 class="text-lg font-bold">数据集标签：{{ tagsDataset.name }}</h3>
        <button class="text-gray-500 hover:text-gray-700" @click="closeTags">关闭</button>
      </div>
      <div class="flex flex-wrap gap-2 mb-4">
        <span v-if="editTags.length === 0" class="text-sm text-gray-500">暂无标签</span>
        <button
          v-for="t in editTags"
          :key="t"
          class="inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm bg-slate-100 text-slate-700 hover:bg-slate-200"
          @click="removeTag(t)"
        >
          {{ t }}
          <span class="text-slate-500">×</span>
        </button>
      </div>
      <div class="flex gap-2 mb-6">
        <input v-model.trim="newTag" class="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm" placeholder="输入标签后回车或点击添加" @keydown.enter.prevent="addTag" />
        <button class="px-4 py-2 bg-slate-700 hover:bg-slate-800 text-white rounded-lg text-sm" @click="addTag">添加</button>
      </div>
      <div class="flex justify-end gap-2">
        <button class="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg text-sm" @click="closeTags">取消</button>
        <button class="px-4 py-2 bg-slate-700 hover:bg-slate-800 text-white rounded-lg text-sm disabled:opacity-50" :disabled="tagsSaving" @click="saveTags">
          {{ tagsSaving ? '保存中...' : '保存' }}
        </button>
      </div>
    </div>
  </div>

  <div v-if="deleteDataset" class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" @click.self="closeDelete">
    <div class="bg-white rounded-xl shadow-xl w-full max-w-md p-6">
      <h3 class="text-lg font-bold mb-2 text-rose-700">删除数据集</h3>
      <div class="text-sm text-gray-600 mb-6">
        将删除目录：<span class="font-mono">{{ deleteDataset.path }}</span>
      </div>
      <div class="flex justify-end gap-2">
        <button class="px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg text-sm" @click="closeDelete">取消</button>
        <button class="px-4 py-2 bg-rose-600 hover:bg-rose-700 text-white rounded-lg text-sm disabled:opacity-50" :disabled="deleteLoading" @click="runDelete">
          {{ deleteLoading ? '删除中...' : '确认删除' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useMainStore } from '../stores/main';
import { computed, ref } from 'vue';
import api from '../api';

const store = useMainStore();
const datasets = computed(() => store.currentProject?.datasets || {});

const metric = (run, key) => {
  const m = run?.metrics;
  if (!m || typeof m !== 'object') return undefined;
  return m[key];
};

const encodePath = (p) => encodeURIComponent(p);

const historyDataset = ref(null);
const historyRuns = ref([]);
const historyLoading = ref(false);

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

const refreshProjectsKeepSelection = async () => {
  const cur = store.currentProject;
  const selectedPath = store.selectedDataset?.path;
  await store.fetchProjects();
  if (cur) {
    const next = store.projects.find(p => p.id === cur.id) || store.projects.find(p => p.path === cur.path);
    store.currentProject = next || null;
    if (store.currentProject && selectedPath) {
      const all = [
        ...(store.currentProject.datasets?.trainable || []),
        ...(store.currentProject.datasets?.annotatable || [])
      ];
      store.selectedDataset = all.find(d => d.path === selectedPath) || null;
    } else {
      store.selectedDataset = null;
    }
  }
};

const parseDownloadFilename = (contentDisposition, fallback) => {
  if (!contentDisposition || typeof contentDisposition !== 'string') return fallback;
  const parts = contentDisposition.split(';').map(s => s.trim());
  const star = parts.find(p => p.toLowerCase().startsWith('filename*='));
  if (star) {
    const v = star.split('=', 2)[1] || '';
    const s = v.replace(/^utf-8''/i, '').trim();
    try {
      return decodeURIComponent(s);
    } catch {
      return s || fallback;
    }
  }
  const normal = parts.find(p => p.toLowerCase().startsWith('filename='));
  if (normal) {
    const v = normal.split('=', 2)[1] || '';
    return v.trim().replace(/^\"|\"$/g, '') || fallback;
  }
  return fallback;
};

const downloadDataset = async (ds) => {
  if (!ds) return;
  downloadingMap.value = { ...downloadingMap.value, [ds.path]: true };
  try {
    const res = await api.downloadDatasetZip({
      project_path: store.currentProject.path,
      dataset_name: ds.name
    });
    const disp = res?.headers?.['content-disposition'];
    const filename = parseDownloadFilename(disp, `${ds.name}.zip`);
    const blob = res.data instanceof Blob ? res.data : new Blob([res.data], { type: 'application/zip' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  } catch (e) {
    console.error(e);
    alert('下载失败');
  } finally {
    const next = { ...downloadingMap.value };
    delete next[ds.path];
    downloadingMap.value = next;
  }
};

const openHistory = async (ds) => {
  historyDataset.value = ds;
  historyLoading.value = true;
  historyRuns.value = [];
  try {
    const res = await api.getTrainingHistory({
      project_path: store.currentProject.path,
      dataset_name: ds.name
    });
    if (res.data.success) {
      historyRuns.value = res.data.history || [];
    } else {
      alert(res.data.error || '加载失败');
    }
  } catch (e) {
    console.error(e);
    alert('请求失败');
  } finally {
    historyLoading.value = false;
  }
};

const closeHistory = () => {
  historyDataset.value = null;
  historyRuns.value = [];
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
    alert('比例设置不合法：val + test 需要小于 1');
    return;
  }
  splitLoading.value = true;
  try {
    const res = await api.splitDataset({
      project_path: store.currentProject.path,
      dataset_name: splitDataset.value.name,
      val_ratio: valRatio.value,
      test_ratio: testRatio.value
    });
    if (res.data.success) {
      await refreshProjectsKeepSelection();
      closeSplit();
      alert(`分割完成：train=${res.data.counts?.train ?? '-'} val=${res.data.counts?.val ?? '-'} test=${res.data.counts?.test ?? '-'}`);
    } else {
      alert(res.data.error || '分割失败');
    }
  } catch (e) {
    console.error(e);
    alert('请求失败');
  } finally {
    splitLoading.value = false;
  }
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
  try {
    const res = await api.updateDatasetTags({
      project_path: store.currentProject.path,
      dataset_name: tagsDataset.value.name,
      tags: editTags.value
    });
    if (res.data.success) {
      await refreshProjectsKeepSelection();
      closeTags();
    } else {
      alert(res.data.error || '保存失败');
    }
  } catch (e) {
    console.error(e);
    alert('请求失败');
  } finally {
    tagsSaving.value = false;
  }
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
  try {
    const res = await api.deleteDatasetFolder({
      project_path: store.currentProject.path,
      dataset_name: deleteDataset.value.name,
      dataset_path: deleteDataset.value.path
    });
    if (res.data.success) {
      await refreshProjectsKeepSelection();
      closeDelete();
    } else {
      alert(res.data.error || '删除失败');
    }
  } catch (e) {
    console.error(e);
    alert('请求失败');
  } finally {
    deleteLoading.value = false;
  }
};
</script>
