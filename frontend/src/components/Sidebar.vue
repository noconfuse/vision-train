<template>
  <div class="w-72 bg-white border-r border-gray-200 flex flex-col h-full">
    <div class="h-12 shrink-0 px-4 bg-slate-800 text-white flex items-center gap-2.5 z-20">
      <img src="/logo.svg" alt="Vision Train" class="w-6 h-6" />
      <div class="leading-tight">
        <div class="text-sm font-semibold tracking-wide">Vision Train</div>
        <div class="text-[10px] text-slate-300 -mt-0.5">视觉项目列表</div>
      </div>
    </div>

    <!-- 操作栏 -->
    <div class="px-2 pt-2 pb-1.5 border-b border-gray-100">
      <button
        @click="openCreateModal"
        class="vt-btn-solid-primary vt-btn-size-md w-full"
      >
        <AppIcon name="createProject" class="h-4 w-4" />
        <span>新建项目</span>
      </button>
    </div>

    <div class="flex-1 overflow-y-auto p-2">
      <div v-if="store.isLoading" class="p-4 text-center text-gray-500 text-sm flex items-center justify-center gap-2">
        <span class="vt-inline-spinner h-3 w-3"></span>
        <span>加载中…</span>
      </div>
      <div v-else-if="store.projects.length === 0" class="p-4 text-center text-gray-400 text-sm">
        暂无项目<br/>
        <span class="text-xs text-gray-400">点击上方"新建项目"开始</span>
      </div>

      <div v-for="p in store.projects"
           :key="p.id"
           class="vt-list-row group relative mb-1.5 cursor-pointer border p-3"
           :class="store.currentProject?.id === p.id ? 'vt-list-row--selected text-slate-900' : 'border-gray-200 bg-white'"
           @click="selectProject(p)">

        <div class="flex justify-between items-start gap-2">
          <div class="min-w-0 flex-1">
            <div class="font-semibold text-sm mb-0.5 truncate">{{ p.name }}</div>
            <div class="text-xs opacity-80" :class="store.currentProject?.id === p.id ? 'vt-text-accent-strong' : 'text-gray-500'">
              Datasets: {{ p.datasets?.length || 0 }}
            </div>
            <UiTooltip
              v-if="p.description"
              side="bottom"
              align="start"
              content-class="max-w-[22rem] break-words text-left"
            >
              <template #trigger>
                <div class="text-[11px] mt-0.5 truncate opacity-70">
                  {{ p.description }}
                </div>
              </template>
              {{ p.description }}
            </UiTooltip>
          </div>
          <!-- 卡片右上角的操作菜单（hover 显示） -->
          <div class="relative shrink-0">
            <button
              @click.stop="toggleMenu(p.id, $event)"
              class="vt-icon-btn h-7 w-7 border-transparent bg-transparent opacity-70 hover:opacity-100"
              :class="store.currentProject?.id === p.id ? 'vt-text-accent hover:bg-[color:var(--vt-color-primary-soft)]' : 'text-gray-600'"
            >
              <AppIcon name="moreHorizontal" class="h-4 w-4" />
            </button>
            <div v-if="openMenuId === p.id"
                 class="absolute right-0 top-8 z-50 w-36 border border-gray-200 bg-white py-1 text-gray-700"
                 @click.stop>
              <button class="w-full text-left px-3 py-1.5 text-xs hover:bg-gray-50 inline-flex items-center gap-2" @click.stop="openEditModal(p)">
                <AppIcon name="rename" class="h-3.5 w-3.5" />
                <span>重命名/编辑</span>
              </button>
              <button class="w-full text-left px-3 py-1.5 text-xs text-rose-600 hover:bg-rose-50 inline-flex items-center gap-2" @click.stop="askDelete(p)">
                <AppIcon name="delete" class="h-3.5 w-3.5" />
                <span>删除</span>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="relative shrink-0 border-t border-gray-100">
      <div
        v-if="showUserPanel"
        class="absolute inset-x-2 bottom-full mb-2 z-40 rounded-sm border border-slate-200 bg-white p-1.5 shadow-sm"
        @click.stop
      >
        <button
          type="button"
          class="vt-btn-ghost vt-btn-size-md flex w-full justify-start px-2"
          :class="route.name === 'tasks-center' ? 'vt-selectable--selected text-slate-900' : ''"
          @click="goToTasksCenter"
        >
          <AppIcon name="tasks" class="h-4 w-4" />
          <span>任务中心</span>
        </button>
        <button
          type="button"
          class="vt-btn-ghost vt-btn-size-md mt-1 flex w-full justify-start px-2 text-rose-600 hover:bg-rose-50 hover:text-rose-700"
          @click="askLogout"
        >
          <AppIcon name="logout" class="h-4 w-4" />
          <span>退出登录</span>
        </button>
      </div>

      <button
        type="button"
        class="flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-slate-50"
        @click.stop="toggleUserPanel"
      >
        <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-sm bg-slate-900 text-white">
          <AppIcon name="user" class="h-4 w-4" />
        </div>
        <div class="min-w-0 flex-1">
          <div class="truncate text-sm font-medium text-slate-900">{{ currentUsername }}</div>
          <div class="text-[11px] text-slate-500">账号</div>
        </div>
        <AppIcon :name="showUserPanel ? 'chevronDown' : 'chevronRight'" class="h-4 w-4 shrink-0 text-slate-400" />
      </button>
    </div>

    <!-- 新建项目弹窗 -->
    <ProjectEditModal
      v-if="modalMode === 'create'"
      mode="create"
      @close="closeModal"
      @submit="handleCreate"
    />

    <!-- 编辑项目弹窗 -->
    <ProjectEditModal
      v-if="modalMode === 'edit' && editingProject"
      mode="edit"
      :project="editingProject"
      @close="closeModal"
      @submit="handleUpdate"
    />

    <!-- 删除确认 -->
    <ConfirmDialog
      v-if="confirmDeleteProject"
      :title="`删除项目「${confirmDeleteProject.name}」？`"
      :description="`将永久删除目录 projects/${confirmDeleteProject.name}/ 及其全部数据（数据集、训练产物、模型）。该操作不可恢复。`"
      :loading="deleting"
      confirmText="确认删除"
      :danger="true"
      @confirm="handleDelete"
      @cancel="confirmDeleteProject = null"
    />

    <ConfirmDialog
      v-if="confirmLogout"
      title="退出登录？"
      description="退出后需要重新登录才能继续访问项目和任务。"
      :loading="loggingOut"
      confirmText="退出登录"
      :danger="true"
      @confirm="handleLogout"
      @cancel="confirmLogout = false"
    />
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onBeforeUnmount } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useMainStore } from '../stores/main';
import { useToast } from '../composables/useToast';
import { getStoredUser, clearAuth } from '../api';
import { authApi } from '../api/auth';
import ProjectEditModal from './ProjectEditModal.vue';
import ConfirmDialog from './ConfirmDialog.vue';
import UiTooltip from './ui/Tooltip.vue';
import AppIcon from './ui/AppIcon.vue';

const store = useMainStore();
const route = useRoute();
const router = useRouter();
const toast = useToast();
const loggingOut = ref(false);
const showUserPanel = ref(false);
const confirmLogout = ref(false);
const currentUser = computed(() => getStoredUser());
const currentUsername = computed(() => {
  const user = currentUser.value;
  return user?.display_name || user?.username || user?.name || '当前用户';
});

// 弹窗状态
const modalMode = ref(null); // 'create' | 'edit' | null
const editingProject = ref(null);
const confirmDeleteProject = ref(null);
const deleting = ref(false);

// 操作菜单状态
const openMenuId = ref(null);
const toggleMenu = (id, ev) => {
  ev.stopPropagation();
  openMenuId.value = openMenuId.value === id ? null : id;
};
const toggleUserPanel = () => {
  showUserPanel.value = !showUserPanel.value;
  openMenuId.value = null;
};
const onDocClick = () => {
  openMenuId.value = null;
  showUserPanel.value = false;
};
onMounted(() => {
  document.addEventListener('click', onDocClick);
  store.fetchProjects();
});
onBeforeUnmount(() => {
  document.removeEventListener('click', onDocClick);
});

const selectProject = (project) => {
  if (!project || !project.name) return;
  store.selectProject(project);
  router.push({
    name: 'home-with-project',
    params: { project: encodeURIComponent(project.name) },
  });
};

const goToTasksCenter = () => {
  showUserPanel.value = false;
  router.push({
    name: 'tasks-center',
    query: route.fullPath ? { return_to: route.fullPath } : {},
  });
};

const askLogout = () => {
  showUserPanel.value = false;
  confirmLogout.value = true;
};

const handleLogout = async () => {
  if (loggingOut.value) return;
  confirmLogout.value = false;
  loggingOut.value = true;
  try {
    await authApi.logout();
  } catch (_) {
    // 本地退出优先，服务端会话失败不阻塞离开
  } finally {
    clearAuth();
    loggingOut.value = false;
    router.replace({ name: 'login' });
  }
};

// 新建
const openCreateModal = () => { modalMode.value = 'create'; };
const handleCreate = async ({ name, description, onDone }) => {
  try {
    await store.createProject(name, description);
    toast.success(`项目「${name}」已创建`);
    onDone && onDone();
  } catch (e) {
    onDone && onDone(e);
  }
};

// 编辑 / 重命名
const openEditModal = (p) => {
  openMenuId.value = null;
  editingProject.value = p;
  modalMode.value = 'edit';
};
const handleUpdate = async ({ name, new_name, description, onDone }) => {
  try {
    await store.updateProject({ name, new_name, description });
    toast.success(new_name ? `已重命名为「${new_name}」` : '已保存');
    onDone && onDone();
  } catch (e) {
    onDone && onDone(e);
  }
};

// 删除
const askDelete = (p) => {
  openMenuId.value = null;
  confirmDeleteProject.value = p;
};
const handleDelete = async () => {
  const p = confirmDeleteProject.value;
  if (!p || deleting.value) return;
  deleting.value = true;
  try {
    await store.deleteProject(p.name);
    toast.success(`项目「${p.name}」已删除`);
    confirmDeleteProject.value = null;
  } catch (e) {
    toast.error(`删除失败: ${e.message}`);
  } finally {
    deleting.value = false;
  }
};

const closeModal = () => {
  modalMode.value = null;
  editingProject.value = null;
};
</script>
