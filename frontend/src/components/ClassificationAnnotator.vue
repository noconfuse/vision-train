<template>
  <div class="vt-workspace-backdrop" @click.self="$emit('close')">
    <div class="vt-workspace-panel vt-workspace-panel--row vt-workspace-panel--xl">
      <div class="flex-1 bg-gray-900 flex items-center justify-center overflow-hidden p-6">
        <div v-if="loading" class="text-sm text-white">加载中...</div>
        <img
          v-else
          :src="image.url"
          class="max-h-full max-w-full rounded-lg object-contain shadow-2xl"
          draggable="false"
        />
      </div>

      <div class="w-80 bg-white border-l border-gray-200 flex flex-col">
        <div class="p-4 border-b border-gray-200">
          <h3 class="font-bold text-gray-800 mb-1">图片分类</h3>
          <UiTooltip side="bottom" align="start" content-class="max-w-[24rem] break-all text-left">
            <template #trigger>
              <p class="text-xs text-gray-500 truncate">{{ getPathDisplayName(image.path) }}</p>
            </template>
            {{ image.path }}
          </UiTooltip>
          <div v-if="autoClassId !== null" class="mt-2 text-xs text-amber-700">
            待复核建议：{{ getClassName(autoClassId) }}
          </div>
        </div>

        <div class="flex-1 overflow-y-auto p-4">
          <div class="mb-3 flex items-center justify-between gap-2">
            <h4 class="text-xs font-bold text-gray-500 uppercase">选择类别</h4>
            <button
              type="button"
              class="vt-btn-link text-xs"
              :disabled="currentClassId === null"
              @click="clearSelection"
            >
              清空
            </button>
          </div>
          <div class="space-y-2">
            <button
              v-for="(name, idx) in classList"
              :key="idx"
              type="button"
              class="vt-selectable flex w-full items-center gap-2 p-2 text-left"
              :class="currentClassId === idx ? 'vt-selectable--selected' : 'border-transparent'"
              @click="selectClass(idx)"
            >
              <span class="text-sm font-medium">{{ name }}</span>
              <span class="ml-auto text-xs text-gray-400">id: {{ idx }}</span>
            </button>
          </div>
        </div>

        <div class="p-4 border-t border-gray-200 bg-gray-50 space-y-3">
          <div class="flex justify-between items-center text-sm text-gray-600">
            <span>当前标签: {{ currentClassId === null ? '未标注' : getClassName(currentClassId) }}</span>
            <span v-if="hasChanges" class="vt-tag vt-tag-warn">未保存</span>
          </div>

          <AsyncButton
            @click="save"
            class="vt-btn-solid-primary vt-btn-size-lg w-full justify-center"
            :disabled="loading"
            :pending="isActionPending(SAVE_ACTION_KEY)"
            loading-text="保存标注 (Ctrl+S)"
          >
            <AppIcon name="check" class="h-4 w-4" />
            保存标注 (Ctrl+S)
          </AsyncButton>

          <div class="flex gap-2">
            <button @click="$emit('prev')" class="vt-btn-secondary vt-btn-size-lg flex-1" :disabled="loading || isActionPending(SAVE_ACTION_KEY)">
              <AppIcon name="previous" class="h-4 w-4" />
              <span>上一张</span>
            </button>
            <button @click="$emit('next')" class="vt-btn-secondary vt-btn-size-lg flex-1" :disabled="loading || isActionPending(SAVE_ACTION_KEY)">
              <span>下一张</span>
              <AppIcon name="next" class="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue';
import api from '../api';
import { useMainStore } from '../stores/main';
import { useApiCall } from '../composables/useApiCall';
import { useAsyncAction } from '../composables/useAsyncAction';
import { getPathDisplayName, parseOptionalNumber } from '../utils';
import AppIcon from './ui/AppIcon.vue';
import AsyncButton from './ui/AsyncButton.vue';
import UiTooltip from './ui/Tooltip.vue';

const props = defineProps({
  image: { type: Object, required: true },
  classList: { type: Array, default: () => [] },
  datasetName: { type: String, required: true },
  split: { type: String, default: 'train' },
});

const emit = defineEmits(['close', 'prev', 'next', 'update']);

const store = useMainStore();
const apiCall = useApiCall();
const asyncAction = useAsyncAction();
const loading = ref(true);
const currentClassId = ref(null);
const autoClassId = ref(null);
const hasChanges = ref(false);
const SAVE_ACTION_KEY = 'classification-annotator:save';
const isActionPending = (key) => asyncAction.isPending(key);
let activeLoadToken = 0;

const getClassName = (idx) => props.classList[idx] || `Class ${idx}`;

const fetchAnnotation = async () => {
  const token = ++activeLoadToken;
  loading.value = true;
  hasChanges.value = false;
  currentClassId.value = null;
  autoClassId.value = null;
  try {
    const res = await api.getAnnotation({
      project_path: store.currentProject.path,
      dataset_name: props.datasetName,
      split: props.split,
      image_path: props.image.path,
    });
    if (token !== activeLoadToken) return;
    currentClassId.value = parseOptionalNumber(res?.manual_annotation?.class_id, { integer: true });
    autoClassId.value = parseOptionalNumber(res?.auto_annotation?.class_id, { integer: true });
  } catch (err) {
    console.error(err);
  } finally {
    if (token !== activeLoadToken) return;
    loading.value = false;
  }
};

const selectClass = (classId) => {
  currentClassId.value = Number(classId);
  hasChanges.value = true;
};

const clearSelection = () => {
  currentClassId.value = null;
  hasChanges.value = true;
};

const save = async () => {
  await asyncAction.run(SAVE_ACTION_KEY, async () => {
    await apiCall(api.saveAnnotation({
      project_path: store.currentProject.path,
      dataset_name: props.datasetName,
      split: props.split,
      image_path: props.image.path,
      annotation: {
        class_id: currentClassId.value,
      },
    }), {
      errorMsg: '保存失败',
      onSuccess: (data) => {
        hasChanges.value = false;
        const nextImage = {
          ...props.image,
          old_path: props.image.path,
          path: data?.image_path || props.image.path,
          url: data?.image_url || props.image.url,
          pending: false,
          has_auto_label: false,
          annotated: currentClassId.value !== null,
        };
        emit('update', nextImage);
        if ((data?.image_path || props.image.path) === props.image.path) {
          fetchAnnotation();
        }
      },
    });
  });
};

const handleKeydown = (e) => {
  if (e.defaultPrevented) return;
  if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    save();
    return;
  }
  if (e.ctrlKey || e.metaKey || e.altKey) return;

  const el = e.target;
  const tag = el?.tagName?.toLowerCase?.();
  if (tag === 'input' || tag === 'textarea' || tag === 'select' || el?.isContentEditable) return;

  if (e.key === 'Escape') {
    emit('close');
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault();
    emit('prev');
  } else if (e.key === 'ArrowRight') {
    e.preventDefault();
    emit('next');
  }
};

watch(() => props.image, () => {
  fetchAnnotation();
}, { immediate: true });

onMounted(() => {
  window.addEventListener('keydown', handleKeydown);
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown);
});
</script>
