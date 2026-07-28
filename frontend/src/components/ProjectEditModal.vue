<template>
  <div class="vt-modal-backdrop" @click.self="onCancel">
    <div class="vt-modal-panel vt-modal-panel--md flex flex-col">
      <div class="vt-modal-header">
        <h3 class="text-base font-semibold text-slate-800">
          {{ mode === 'create' ? '新建项目' : '编辑项目' }}
        </h3>
        <button class="vt-modal-close" :disabled="submitting || success" @click="onCancel">
          <AppIcon name="close" class="h-4 w-4" />
        </button>
      </div>

      <form class="vt-modal-body space-y-3" @submit.prevent="onSubmit">
        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">
            项目名 <span class="text-rose-500">*</span>
          </label>
          <input
            v-model="name"
            type="text"
            :readonly="mode === 'edit' || submitting"
            :class="mode === 'edit' ? 'bg-gray-100 cursor-not-allowed' : ''"
            placeholder="仅支持字母/数字/下划线/短横线，1~64 字符"
            class="vt-input"
            @input="onNameInput"
          />
          <div class="mt-1 text-xs flex items-center gap-1"
               :class="nameCheckState === 'checking' ? 'text-gray-400' :
                       nameCheckState === 'failed' ? 'text-rose-500' :
                       (validationError ? 'text-rose-500' : 'text-emerald-600')">
            <span v-if="nameCheckState === 'checking'">检查中...</span>
            <span v-else-if="nameCheckState === 'failed'">校验失败（服务异常，请稍后再试）</span>
            <span v-else-if="validationError">{{ validationError }}</span>
            <span v-else-if="name && mode === 'create' && nameCheckState === 'ok'">项目名可用</span>
            <span v-else>目录规范：字母/数字/_-，1~64 字符</span>
          </div>
        </div>

        <div v-if="mode === 'edit'">
          <label class="block text-xs font-medium text-gray-700 mb-1">
            新项目名（可选，不填则不修改）
          </label>
          <input
            v-model="newName"
            type="text"
            :disabled="submitting"
            placeholder="留空保留原名"
            class="vt-input"
            @input="onNewNameInput"
          />
          <div class="mt-1 text-xs"
               :class="newNameError ? 'text-rose-500' : 'text-gray-400'">
            {{ newNameError || '改名会同步移动目录' }}
          </div>
        </div>

        <div>
          <label class="block text-xs font-medium text-gray-700 mb-1">描述（可选）</label>
          <textarea
            v-model="description"
            rows="3"
            :disabled="submitting"
            placeholder="项目用途、负责人、备注..."
            class="vt-textarea resize-none"
          ></textarea>
        </div>

        <div v-if="mode === 'create'" class="vt-section-muted text-xs text-gray-600 leading-relaxed">
          将自动创建以下子目录：
          <div class="mt-1.5 font-mono text-[11px] text-slate-700 leading-relaxed">
            projects/{{ name || '<name>' }}/<br/>
            ├── training/&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; # YOLO 训练集<br/>
            ├── training_outputs/&nbsp;&nbsp; # 训练 / 评估 / 导出产物<br/>
            └── videos/&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; # 原始视频<br/>
            <span class="text-gray-500">+ (可选) projects/&lt;name&gt;/.description</span>
          </div>
        </div>

        <div v-if="submitError" class="border border-rose-200 bg-rose-50 p-2 text-xs text-rose-700">
          {{ submitError }}
        </div>

        <div class="flex justify-end gap-2 pt-2">
          <button type="button"
                  class="vt-btn-secondary vt-btn-size-md"
                  :disabled="submitting || success"
                  @click="onCancel">
            取消
          </button>
          <button type="submit"
                  :disabled="!!validationError || submitting || success || (mode === 'create' && nameCheckState !== 'ok' && !!name)"
                  :class="success ? 'vt-btn-muted' : 'vt-btn-solid-primary'"
                  class="vt-btn-size-md min-w-[88px]">
            <span v-if="submitting" class="inline-block w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
            <AppIcon v-else-if="success" name="check" class="h-3.5 w-3.5" />
            <span>{{ submitting ? (mode === 'create' ? '创建中…' : '保存中…') : (success ? (mode === 'create' ? '创建成功' : '保存成功') : (mode === 'create' ? '创建' : '保存')) }}</span>
          </button>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue';
import { useMainStore } from '../stores/main';
import { useAsyncEmit } from '../composables/useAsyncEmit';
import { validateResourceName } from '../utils';
import AppIcon from './ui/AppIcon.vue';

const props = defineProps({
  mode: { type: String, default: 'create' }, // 'create' | 'edit'
  project: { type: Object, default: null }
});
const emit = defineEmits(['close', 'submit']);
const store = useMainStore();
const asyncEmit = useAsyncEmit(emit);

const name = ref(props.mode === 'edit' ? props.project?.name : '');
const newName = ref('');
const description = ref(props.mode === 'edit' ? (props.project?.description || '') : '');
const validationError = ref('');
const newNameError = ref('');
const nameCheckState = ref('idle'); // 'idle' | 'checking' | 'ok' | 'invalid'
const submitting = ref(false);
const submitError = ref('');
const success = ref(false);

const validateSync = (val) => validateResourceName(val, {
  emptyMessage: '项目名不能为空',
  reservedNames: ['.git', '__pycache__', 'pretrained_models', 'config'],
});

let nameTimer = null;
const onNameInput = () => {
  validationError.value = validateSync(name.value);
  if (validationError.value) {
    nameCheckState.value = 'invalid';
    return;
  }
  nameCheckState.value = 'checking';
  if (nameTimer) clearTimeout(nameTimer);
  nameTimer = setTimeout(async () => {
    try {
      const res = await store.validateProjectName(name.value);
      if (res && !res.valid) {
        validationError.value = res.reason || '项目名不可用';
        nameCheckState.value = 'invalid';
      } else {
        nameCheckState.value = 'ok';
      }
    } catch (_) {
      // 接口异常：明确显示为失败，绝不静默回落到"成功"
      nameCheckState.value = 'failed';
      validationError.value = '';
    }
  }, 300);
};
const onNewNameInput = () => {
  if (!newName.value) { newNameError.value = ''; return; }
  newNameError.value = validateSync(newName.value);
};

watch(name, () => { if (validationError.value === '' && name.value) onNameInput(); });
watch(newName, () => { if (newName.value) onNewNameInput(); });

const onCancel = () => {
  if (submitting.value) return;
  emit('close');
};

const onSubmit = async () => {
  if (submitting.value || success.value) return;
  if (validationError.value) return;
  if (newNameError.value) return;
  submitting.value = true;
  submitError.value = '';

  const payload = props.mode === 'create'
    ? { name: name.value.trim(), description: description.value.trim() }
    : { name: name.value.trim(), new_name: newName.value.trim() || undefined, description: description.value };

  try {
    await asyncEmit('submit', payload);
    success.value = true;
    setTimeout(() => {
      if (success.value) emit('close');
    }, 600);
  } catch (e) {
    submitError.value = e?.message || '操作失败';
  } finally {
    submitting.value = false;
  }
};
</script>
