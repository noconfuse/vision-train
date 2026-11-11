<template>
  <ModalShell title="GPU 服务器" size="lg" body-class="space-y-4" @close="emit('close')">
    <template #icon>
      <AppIcon name="settings" class="h-4 w-4 text-slate-600" />
    </template>

    <section class="space-y-2">
      <div class="flex items-center justify-between">
        <div class="vt-step-section-title">已配置的服务器</div>
        <div class="text-[11px] text-gray-500">训练时可选它作为运行位置</div>
      </div>

      <div v-if="!store.loaded" class="text-sm text-gray-400 py-4 text-center border border-dashed border-gray-200">
        正在读取服务器列表...
      </div>
      <div v-else-if="!store.targets.length" class="text-sm text-gray-400 py-4 text-center border border-dashed border-gray-200">
        还没有配置服务器，在下面填一台再保存。
      </div>
      <div v-else class="space-y-2">
        <div
          v-for="target in store.targets"
          :key="target.id"
          class="border border-gray-200 p-3"
          :class="[selectedClass(target.id)]"
        >
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="flex items-center gap-2">
                <span class="font-semibold text-sm text-slate-800 truncate">{{ target.name }}</span>
                <span class="vt-tag vt-tag--sm vt-tag-info">GPU {{ target.device }}</span>
                <span v-if="target.keep_remote_copy" class="vt-tag vt-tag--sm vt-tag-warn">保留远端副本</span>
                <span v-if="target.id === store.selectedTargetId" class="vt-tag vt-tag--sm vt-tag-success">当前运行位置</span>
              </div>
              <div class="mt-1 text-xs text-gray-500 font-mono break-all">
                ssh {{ target.ssh_host }} · {{ target.remote_workspace }}
              </div>
            </div>
            <div class="flex shrink-0 items-center gap-1.5">
              <AsyncButton
                class="vt-btn-secondary text-xs inline-flex items-center gap-1"
                :pending="pendingPreflightId === target.id"
                :loading-text="'检查中...'"
                @click="runPreflight(target.id)"
              >
                <AppIcon name="target" class="h-3.5 w-3.5" />
                连通性检查
              </AsyncButton>
              <button type="button" class="vt-btn-link text-xs" @click="startEdit(target)">编辑</button>
              <button type="button" class="vt-btn-link text-xs text-rose-600" @click="removeTarget(target)">删除</button>
            </div>
          </div>

          <div v-if="store.preflightReports[target.id]" class="mt-2 border-t border-gray-100 pt-2">
            <PreflightReport :report="store.preflightReports[target.id]" />
          </div>
        </div>
      </div>
    </section>

    <section class="border-t border-gray-200 pt-3">
      <div class="vt-step-section-title">{{ editingId ? '编辑服务器' : '新增服务器' }}</div>
      <div class="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">服务器名称 <span class="text-rose-500">*</span></label>
          <input v-model.trim="form.name" type="text" class="vt-input" placeholder="例如：机房 4090" />
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">SSH 主机 <span class="text-rose-500">*</span></label>
          <input v-model.trim="form.ssh_host" type="text" class="vt-input font-mono" placeholder="~/.ssh/config 里的别名，或 user@1.2.3.4" />
          <div class="mt-1 text-[11px] text-gray-500">
            要能用密钥直接登录：产品不会弹密码框，连不上就当场报错。
          </div>
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">远端工作目录</label>
          <input v-model.trim="form.remote_workspace" type="text" class="vt-input font-mono" placeholder="/dev/shm/vision-train" />
          <div class="mt-1 text-[11px] text-gray-500">
            留空用 /dev/shm/vision-train：Linux 上这是内存盘，数据不落服务器硬盘，训练结束随进程消失。
          </div>
        </div>
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">GPU 序号</label>
          <input v-model.trim="form.device" type="text" class="vt-input font-mono" placeholder="0 或 0,1" />
          <div class="mt-1 text-[11px] text-gray-500">按 nvidia-smi 里的编号填，多卡用逗号。</div>
        </div>
      </div>
      <label class="vt-check-card vt-check-card--interactive mt-3 items-center px-2 py-1.5">
        <input v-model="form.keep_remote_copy" type="checkbox" class="vt-checkbox" />
        <span class="text-xs font-medium text-gray-700 select-none">训练结束后保留服务器上的数据集和权重副本</span>
      </label>

      <div class="mt-3 flex items-center justify-end gap-2">
        <button v-if="editingId" type="button" class="vt-btn-secondary vt-btn-size-md" @click="resetForm">
          取消编辑
        </button>
        <AsyncButton
          class="vt-btn-solid-primary vt-btn-size-md inline-flex items-center gap-1.5"
          :disabled="!canSubmit"
          :pending="saving"
          :loading-text="editingId ? '保存中...' : '添加中...'"
          @click="submit"
        >
          <AppIcon name="plus" class="h-4 w-4" />
          {{ editingId ? '保存修改' : '添加服务器' }}
        </AsyncButton>
      </div>
    </section>
  </ModalShell>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue';
import { useConfirm } from '../composables/useConfirm';
import { useComputeStore } from '../stores/compute';
import AppIcon from './ui/AppIcon.vue';
import AsyncButton from './ui/AsyncButton.vue';
import ModalShell from './ui/ModalShell.vue';
import PreflightReport from './PreflightReport.vue';

const emit = defineEmits(['close']);

const store = useComputeStore();
const confirm = useConfirm();

const EMPTY_FORM = {
  name: '',
  ssh_host: '',
  remote_workspace: '',
  device: '',
  keep_remote_copy: false,
};

const form = reactive({ ...EMPTY_FORM });
const editingId = ref('');
const saving = ref(false);
const pendingPreflightId = ref('');

const canSubmit = computed(() => Boolean(form.name && form.ssh_host));

const selectedClass = (targetId) => (targetId === store.selectedTargetId ? 'border-slate-800 bg-slate-50/60' : '');

const resetForm = () => {
  Object.assign(form, EMPTY_FORM);
  editingId.value = '';
};

const startEdit = (target) => {
  editingId.value = target.id;
  Object.assign(form, {
    name: target.name,
    ssh_host: target.ssh_host,
    remote_workspace: target.remote_workspace,
    device: target.device,
    keep_remote_copy: Boolean(target.keep_remote_copy),
  });
};

const submit = async () => {
  if (!canSubmit.value) return;
  saving.value = true;
  try {
    const saved = editingId.value
      ? await store.updateComputeTarget({ target_id: editingId.value, ...form })
      : await store.createComputeTarget({ ...form });
    if (saved) resetForm();
  } finally {
    saving.value = false;
  }
};

const runPreflight = async (targetId) => {
  pendingPreflightId.value = targetId;
  try {
    await store.runPreflight(targetId);
  } finally {
    pendingPreflightId.value = '';
  }
};

const removeTarget = async (target) => {
  const ok = await confirm.confirmDanger(`删除「${target.name}」这台 GPU 服务器？`, {
    detail: '只是删掉这条配置，服务器上的文件不受影响。',
  });
  if (!ok) return;
  await store.deleteComputeTarget(target.id);
  if (editingId.value === target.id) resetForm();
};

onMounted(() => {
  if (!store.loaded) store.fetchComputeTargets().catch(() => {});
});
</script>
