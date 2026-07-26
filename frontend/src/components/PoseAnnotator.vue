<template>
  <div class="vt-workspace-backdrop" @click.self="$emit('close')">
    <div class="vt-workspace-panel vt-workspace-panel--row vt-workspace-panel--xl">
      <div class="flex-1 bg-gray-900 relative flex items-center justify-center overflow-hidden select-none" ref="containerRef">
        <div v-if="loading" class="absolute inset-0 flex items-center justify-center text-white">
          Loading...
        </div>

        <div class="relative" :style="imageStyle">
          <img
            ref="imgRef"
            :src="image.url"
            class="block w-full h-full"
            @load="onImageLoad"
            draggable="false"
          />

          <svg
            class="absolute inset-0 w-full h-full cursor-crosshair"
            :viewBox="`0 0 ${imgWidth} ${imgHeight}`"
            preserveAspectRatio="none"
            @pointerdown="onCanvasPointerDown"
          >
            <g v-for="(instance, instanceIdx) in instances" :key="instance.id">
              <g v-if="getInstanceSkeletonSegments(instance, instanceIdx).length">
                <line
                  v-for="segment in getInstanceSkeletonSegments(instance, instanceIdx)"
                  :key="`${instance.id}_${segment.from}_${segment.to}`"
                  :x1="segment.x1"
                  :y1="segment.y1"
                  :x2="segment.x2"
                  :y2="segment.y2"
                  :stroke="instance.is_auto ? 'rgba(34,211,238,0.9)' : (selectedInstanceIdx === instanceIdx ? getColor(instance.class) : 'rgba(255,255,255,0.65)')"
                  :stroke-width="instance.is_auto ? (2.2 / scale) : (selectedInstanceIdx === instanceIdx ? (2.8 / scale) : (1.8 / scale))"
                  :opacity="instance.is_auto ? 0.9 : (selectedInstanceIdx === instanceIdx ? 0.95 : 0.5)"
                  :stroke-dasharray="instance.is_auto ? '8 6' : '0'"
                  stroke-linecap="round"
                  style="pointer-events: none;"
                />
              </g>
              <rect
                v-if="instance.is_auto && getInstanceBBox(instance)"
                :x="getInstanceBBox(instance).x1"
                :y="getInstanceBBox(instance).y1"
                :width="getInstanceBBox(instance).width"
                :height="getInstanceBBox(instance).height"
                fill="rgba(34,211,238,0.08)"
                stroke="#22d3ee"
                :stroke-width="selectedInstanceIdx === instanceIdx ? (2.4 / scale) : (1.8 / scale)"
                stroke-dasharray="10 6"
                :opacity="selectedInstanceIdx === instanceIdx ? 1 : 0.88"
                style="pointer-events: none;"
              />
              <text
                v-if="instance.is_auto && getInstanceBBox(instance)"
                :x="getInstanceBBox(instance).x1"
                :y="Math.max(14 / scale, getInstanceBBox(instance).y1 - 6 / scale)"
                fill="#67e8f9"
                :font-size="11 / scale"
                font-weight="bold"
                style="text-shadow: 0 0 2px rgba(8, 47, 73, 0.95), 1px 1px 1px rgba(0, 0, 0, 0.9); pointer-events: none;"
              >
                AUTO
              </text>
              <rect
                v-if="selectedInstanceIdx === instanceIdx && getInstanceBBox(instance)"
                :x="getInstanceBBox(instance).x1"
                :y="getInstanceBBox(instance).y1"
                :width="getInstanceBBox(instance).width"
                :height="getInstanceBBox(instance).height"
                :stroke="instance.is_auto ? '#22d3ee' : 'rgba(255,255,255,0.7)'"
                :stroke-width="1.5 / scale"
                stroke-dasharray="8 6"
                fill="transparent"
                style="pointer-events: none;"
              />
              <text
                v-if="selectedInstanceIdx === instanceIdx && getInstanceBBox(instance)"
                :x="getInstanceBBox(instance).x1"
                :y="Math.max(14 / scale, getInstanceBBox(instance).y1 - 6 / scale)"
                :fill="instance.is_auto ? '#67e8f9' : '#ffffff'"
                :font-size="12 / scale"
                font-weight="bold"
                style="text-shadow: 0 0 2px rgba(8, 47, 73, 0.95), 1px 1px 1px rgba(0, 0, 0, 0.9); pointer-events: none;"
              >
                {{ getInstanceTitle(instance, instanceIdx) }} {{ instance.is_auto ? '(Auto)' : '' }}
              </text>

              <g v-for="(point, pointIdx) in instance.keypoints" :key="`${instance.id}-${pointIdx}`">
                <line
                  v-if="selectedInstanceIdx === instanceIdx && selectedKeypointIdx === pointIdx && hasPlacedKeypoint(point)"
                  :x1="point.x"
                  y1="0"
                  :x2="point.x"
                  :y2="imgHeight"
                  stroke="rgba(255,255,255,0.35)"
                  :stroke-width="1 / scale"
                  stroke-dasharray="6 6"
                  style="pointer-events: none;"
                />
                <line
                  v-if="selectedInstanceIdx === instanceIdx && selectedKeypointIdx === pointIdx && hasPlacedKeypoint(point)"
                  x1="0"
                  :y1="point.y"
                  :x2="imgWidth"
                  :y2="point.y"
                  stroke="rgba(255,255,255,0.35)"
                  :stroke-width="1 / scale"
                  stroke-dasharray="6 6"
                  style="pointer-events: none;"
                />
                <circle
                  v-if="selectedInstanceIdx === instanceIdx && selectedKeypointIdx === pointIdx && hasPlacedKeypoint(point)"
                  :cx="point.x"
                  :cy="point.y"
                  :r="11 / scale"
                  fill="rgba(255,255,255,0.1)"
                  stroke="rgba(255,255,255,0.75)"
                  :stroke-width="1.25 / scale"
                  style="pointer-events: none;"
                />
                <circle
                  v-if="hasPlacedKeypoint(point) && instance.is_auto"
                  :cx="point.x"
                  :cy="point.y"
                  :r="selectedInstanceIdx === instanceIdx && selectedKeypointIdx === pointIdx ? (8.5 / scale) : (6 / scale)"
                  fill="rgba(34,211,238,0.22)"
                  stroke="rgba(103,232,249,0.95)"
                  :stroke-width="1.25 / scale"
                  :opacity="selectedInstanceIdx === instanceIdx ? 1 : 0.9"
                  style="pointer-events: none;"
                />
                <circle
                  v-if="hasPlacedKeypoint(point)"
                  :cx="point.x"
                  :cy="point.y"
                  :r="selectedInstanceIdx === instanceIdx && selectedKeypointIdx === pointIdx ? (6 / scale) : (4 / scale)"
                  :fill="point.visible === 1 ? '#f59e0b' : (selectedInstanceIdx === instanceIdx ? getColor(instance.class) : '#ffffff')"
                  :stroke="instance.is_auto ? '#22d3ee' : 'white'"
                  :stroke-width="selectedInstanceIdx === instanceIdx && selectedKeypointIdx === pointIdx ? (2 / scale) : (1.25 / scale)"
                  :opacity="selectedInstanceIdx === instanceIdx ? 1 : 0.82"
                  style="cursor: move; touch-action: none;"
                  @pointerdown.stop="onPointPointerDown(instanceIdx, pointIdx, $event)"
                />
                <text
                  v-if="hasPlacedKeypoint(point) && selectedInstanceIdx === instanceIdx && selectedKeypointIdx === pointIdx"
                  :x="point.x + 7 / scale"
                  :y="point.y - 7 / scale"
                  fill="white"
                  :font-size="10 / scale"
                  font-weight="bold"
                  style="text-shadow: 0 0 2px rgba(0, 0, 0, 0.9); pointer-events: none;"
                >
                  {{ pointIdx + 1 }} {{ selectedKeypointNames[pointIdx] }}
                </text>
              </g>
            </g>
          </svg>
        </div>
      </div>

      <div class="w-80 bg-white border-l border-gray-200 flex flex-col">
        <div class="p-4 border-b border-gray-200">
          <h3 class="font-bold text-gray-800 mb-1">姿态标注</h3>
          <UiTooltip side="bottom" align="start" content-class="max-w-[24rem] break-all text-left">
            <template #trigger>
              <p class="text-xs text-gray-500 truncate">{{ getPathDisplayName(image.path) }}</p>
            </template>
            {{ image.path }}
          </UiTooltip>
          <div class="mt-2 text-xs text-gray-500">
            先选实例和关键点，再点击图片落点；默认保持当前关键点不跳转，按 `Tab` 切下一个。
          </div>
          <div
            v-if="autoInstanceCount > 0"
            class="mt-3 rounded-md border border-cyan-200 bg-cyan-50 px-3 py-2 text-xs text-cyan-700"
          >
            当前有 {{ autoInstanceCount }} 个自动标注实例，画面中会以青色虚线、青色外圈和 `AUTO` 标识显示，保存前请确认。
          </div>
        </div>

        <div class="flex-1 overflow-y-auto p-4 space-y-4">
          <div>
            <div class="mb-2 flex items-center justify-between gap-2">
              <h4 class="text-xs font-bold text-gray-500 uppercase">实例</h4>
              <button class="vt-btn-secondary vt-btn-size-sm" @click="addInstance">
                新增实例
              </button>
            </div>
            <div class="space-y-3">
              <div v-if="manualInstanceEntries.length" class="space-y-2">
                <div class="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wide text-gray-400">
                  <span>人工标注</span>
                  <span class="rounded bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500">{{ manualInstanceEntries.length }}</span>
                </div>
                <button
                  v-for="entry in manualInstanceEntries"
                  :key="entry.instance.id"
                  type="button"
                  class="vt-selectable w-full p-2 text-left"
                  :class="selectedInstanceIdx === entry.index ? 'vt-selectable--selected' : 'border-transparent'"
                  @click="selectInstance(entry.index)"
                >
                  <div class="flex items-center gap-2">
                    <div class="h-3 w-3 rounded-full" :style="{ backgroundColor: getColor(entry.instance.class) }"></div>
                    <span class="text-sm font-medium">{{ getInstanceTitle(entry.instance, entry.index) }}</span>
                    <span class="ml-auto rounded bg-gray-100 px-1.5 py-0.5 text-[10px] font-medium text-gray-500">人工</span>
                  </div>
                  <div class="mt-1 text-xs text-gray-500">
                    已标 {{ countPlacedKeypoints(entry.instance) }}/{{ keypointCount }} 个关键点
                  </div>
                </button>
              </div>

              <div v-if="autoInstanceEntries.length" class="space-y-2">
                <div class="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wide text-cyan-600">
                  <span>自动标注待确认</span>
                  <span class="rounded bg-cyan-100 px-1.5 py-0.5 text-[10px] text-cyan-700">{{ autoInstanceEntries.length }}</span>
                </div>
                <button
                  v-for="entry in autoInstanceEntries"
                  :key="entry.instance.id"
                  type="button"
                  class="vt-selectable w-full border-cyan-200 bg-cyan-50/80 p-2 text-left"
                  :class="selectedInstanceIdx === entry.index ? 'vt-selectable--selected ring-1 ring-cyan-300' : 'hover:border-cyan-300'"
                  @click="selectInstance(entry.index)"
                >
                  <div class="flex items-center gap-2">
                    <div class="h-3 w-3 rounded-full bg-cyan-400 shadow-[0_0_0_2px_rgba(34,211,238,0.18)]"></div>
                    <span class="text-sm font-medium text-slate-800">{{ getInstanceTitle(entry.instance, entry.index) }}</span>
                    <span class="ml-auto rounded bg-cyan-100 px-1.5 py-0.5 text-[10px] font-semibold text-cyan-700">AUTO</span>
                  </div>
                  <div class="mt-1 text-xs text-cyan-700/80">
                    待确认，已标 {{ countPlacedKeypoints(entry.instance) }}/{{ keypointCount }} 个关键点
                  </div>
                </button>
              </div>
            </div>
          </div>

          <div v-if="hasMultipleClasses">
            <h4 class="text-xs font-bold text-gray-500 uppercase mb-3">选择类别</h4>
            <div class="space-y-2">
              <div
                v-for="(name, idx) in classList"
                :key="idx"
                class="vt-selectable flex items-center gap-2 p-2 cursor-pointer"
                :class="currentClass === idx ? 'vt-selectable--selected' : 'border-transparent'"
                @click="updateSelectedInstanceClass(idx)"
              >
                <div class="w-4 h-4 rounded-full" :style="{ backgroundColor: getColor(idx) }"></div>
                <span class="text-sm font-medium">{{ name }}</span>
                <span class="text-xs text-gray-400 ml-auto">id: {{ idx }}</span>
              </div>
            </div>
          </div>

          <div>
            <div class="mb-2 flex items-center justify-between gap-2">
              <h4 class="text-xs font-bold text-gray-500 uppercase">关键点</h4>
              <span class="text-xs text-gray-400">{{ selectedKeypointLabel }}</span>
            </div>
            <div class="space-y-2">
              <div
                v-for="(name, idx) in selectedKeypointNames"
                :key="idx"
                class="vt-selectable w-full p-2 text-left cursor-pointer"
                :class="selectedKeypointIdx === idx ? 'vt-selectable--selected' : 'border-transparent'"
                @click="selectKeypoint(idx)"
              >
                <div class="flex items-center gap-2">
                  <span class="w-5 text-center text-xs font-mono text-gray-500">{{ idx + 1 }}</span>
                  <span class="min-w-0 flex-1 text-sm truncate">{{ name }}</span>
                  <select
                    class="vt-select vt-control-sm !w-20 text-xs"
                    :value="getSelectedKeypointVisibility(idx)"
                    @click.stop
                    @change="setKeypointVisibility(idx, Number($event.target.value))"
                  >
                    <option :value="0">缺失</option>
                    <option :value="1">遮挡</option>
                    <option :value="2">可见</option>
                  </select>
                  <button
                    type="button"
                    class="vt-btn-secondary vt-btn-size-sm shrink-0 text-xs"
                    :disabled="!hasPlacedKeypoint(getKeypointByIndex(idx)) && getSelectedKeypointVisibility(idx) === 0"
                    @click.stop="clearKeypoint(idx)"
                  >
                    清空
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="p-4 border-t border-gray-200 bg-gray-50 space-y-3">
          <div class="flex justify-between items-center text-sm text-gray-600">
            <span>实例数量: {{ instances.length }}</span>
            <span v-if="hasChanges" class="vt-tag vt-tag-warn">未保存</span>
          </div>

          <div class="rounded-md border border-gray-200 bg-white px-3 py-2 text-xs text-gray-500">
            当前关键点：
            <span class="font-medium text-slate-700">{{ selectedKeypointLabel }}</span>
            <span class="ml-2" :class="getVisibilityClass(getSelectedKeypointVisibility())">{{ getVisibilityText(getSelectedKeypointVisibility()) }}</span>
          </div>

          <button
            v-if="selectedInstanceIdx >= 0"
            @click="removeInstance(selectedInstanceIdx)"
            class="vt-btn-danger vt-btn-size-lg w-full justify-center"
          >
            <AppIcon name="delete" class="h-4 w-4" />
            删除当前实例 (Shift+Delete)
          </button>

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
import { computed, onMounted, onUnmounted, ref, watch } from 'vue';
import api from '../api';
import { useMainStore } from '../stores/main';
import { useApiCall } from '../composables/useApiCall';
import { useAsyncAction } from '../composables/useAsyncAction';
import { getPathDisplayName } from '../utils';
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
const SAVE_ACTION_KEY = 'pose-annotator:save';
const isActionPending = (key) => asyncAction.isPending(key);

const containerRef = ref(null);
const imgRef = ref(null);
const loading = ref(true);
const hasChanges = ref(false);
const instances = ref([]);
const currentClass = ref(0);
const selectedInstanceIdx = ref(-1);
const selectedKeypointIdx = ref(0);
const keypointCount = ref(0);
const keypointDims = ref(3);
const flipIdx = ref([]);
const keypointNamesByClass = ref({});
const poseSkeleton = ref([]);
const imgWidth = ref(1);
const imgHeight = ref(1);
const scale = ref(1);
const containerWidth = ref(0);
const containerHeight = ref(0);

let resizeObserver = null;
let activeLoadToken = 0;
let activePointerId = null;
const draggingPoint = ref(null);

const colors = [
  '#ef4444', '#f97316', '#f59e0b', '#84cc16', '#22c55e',
  '#06b6d4', '#3b82f6', '#6366f1', '#a855f7', '#ec4899',
];

const COCO_KEYPOINT_NAMES = [
  'nose', 'left_eye', 'right_eye', 'left_ear', 'right_ear',
  'left_shoulder', 'right_shoulder', 'left_elbow', 'right_elbow', 'left_wrist',
  'right_wrist', 'left_hip', 'right_hip', 'left_knee', 'right_knee',
  'left_ankle', 'right_ankle',
];

const COCO_SKELETON = [
  [15, 13], [13, 11], [16, 14], [14, 12], [11, 12],
  [5, 11], [6, 12], [5, 6], [5, 7], [6, 8],
  [7, 9], [8, 10], [1, 2], [0, 1], [0, 2],
  [1, 3], [2, 4], [3, 5], [4, 6],
];

const getColor = (idx) => colors[Math.abs(Number(idx || 0)) % colors.length];
const getClassName = (idx) => props.classList[idx] || `Class ${idx}`;
const normalizeKptName = (name) => String(name || '').trim().toLowerCase().replace(/[\s-]+/g, '_');

const imageStyle = computed(() => {
  if (!imgWidth.value || !imgHeight.value || !containerWidth.value || !containerHeight.value) return {};
  const imgRatio = imgWidth.value / imgHeight.value;
  const containerRatio = containerWidth.value / containerHeight.value;
  let width;
  let height;
  if (imgRatio > containerRatio) {
    width = containerWidth.value - 40;
    height = width / imgRatio;
  } else {
    height = containerHeight.value - 40;
    width = height * imgRatio;
  }
  scale.value = width / imgWidth.value;
  return { width: `${width}px`, height: `${height}px` };
});

const selectedInstance = computed(() => {
  if (selectedInstanceIdx.value < 0 || selectedInstanceIdx.value >= instances.value.length) return null;
  return instances.value[selectedInstanceIdx.value] || null;
});

const normalizedClassList = computed(() => (props.classList || []).map((name) => String(name || '').trim()).filter(Boolean));
const hasMultipleClasses = computed(() => normalizedClassList.value.length > 1);

const selectedKeypointNames = computed(() => {
  const classId = selectedInstance.value ? Number(selectedInstance.value.class || 0) : Number(currentClass.value || 0);
  const names = keypointNamesByClass.value?.[classId] || keypointNamesByClass.value?.[0] || [];
  if (Array.isArray(names) && names.length === keypointCount.value) {
    const normalized = names.map((name) => String(name || '').trim());
    const allGeneric = normalized.every((name, index) => normalizeKptName(name) === `kpt_${index}`);
    if (allGeneric && keypointCount.value === COCO_KEYPOINT_NAMES.length) {
      return COCO_KEYPOINT_NAMES;
    }
    return normalized;
  }
  if (keypointCount.value === COCO_KEYPOINT_NAMES.length) {
    return COCO_KEYPOINT_NAMES;
  }
  return Array.from({ length: keypointCount.value }, (_, index) => `kpt_${index}`);
});

const selectedKeypointLabel = computed(() => {
  if (!selectedKeypointNames.value.length) return '无关键点';
  const index = Math.max(0, Math.min(selectedKeypointIdx.value, selectedKeypointNames.value.length - 1));
  return `${index + 1}. ${selectedKeypointNames.value[index]}`;
});

const selectedSkeleton = computed(() => {
  if (Array.isArray(poseSkeleton.value) && poseSkeleton.value.length) {
    return poseSkeleton.value;
  }
  const names = selectedKeypointNames.value.map(normalizeKptName);
  if (names.length !== COCO_KEYPOINT_NAMES.length) return [];
  const isCocoNames = COCO_KEYPOINT_NAMES.every((name, index) => names[index] === normalizeKptName(name));
  if (!isCocoNames) return [];
  return COCO_SKELETON;
});

const manualInstanceEntries = computed(() => (
  instances.value
    .map((instance, index) => ({ instance, index }))
    .filter((entry) => !entry.instance.is_auto)
));

const autoInstanceEntries = computed(() => (
  instances.value
    .map((instance, index) => ({ instance, index }))
    .filter((entry) => entry.instance.is_auto)
));

const autoInstanceCount = computed(() => autoInstanceEntries.value.length);

const normalizeSkeleton = (rawSkeleton, keypointTotal) => {
  if (!Array.isArray(rawSkeleton) || !Number.isFinite(Number(keypointTotal)) || Number(keypointTotal) <= 0) {
    return [];
  }
  const count = Number(keypointTotal);
  const normalizedPairs = [];
  const oneBasedPairs = [];
  rawSkeleton.forEach((pair) => {
    if (!Array.isArray(pair) || pair.length !== 2) return;
    const start = Number(pair[0]);
    const end = Number(pair[1]);
    if (!Number.isInteger(start) || !Number.isInteger(end)) return;
    normalizedPairs.push([start, end]);
    oneBasedPairs.push([start - 1, end - 1]);
  });
  const isValid = (pairs) => pairs.every(([start, end]) => start >= 0 && end >= 0 && start < count && end < count && start !== end);
  if (normalizedPairs.length && isValid(normalizedPairs)) {
    return normalizedPairs;
  }
  if (oneBasedPairs.length && isValid(oneBasedPairs)) {
    return oneBasedPairs;
  }
  return [];
};

const hasPlacedKeypoint = (point) => {
  if (!point || Number(point.visible || 0) <= 0) return false;
  const x = Number(point.x || 0);
  const y = Number(point.y || 0);
  return x > 0 || y > 0;
};

const buildBlankKeypoints = () => {
  return Array.from({ length: keypointCount.value }, () => ({ x: 0, y: 0, visible: 0 }));
};

const nextInstanceId = () => `${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;

const clampPoint = (x, y) => ({
  x: Math.max(0, Math.min(imgWidth.value, Number(x || 0))),
  y: Math.max(0, Math.min(imgHeight.value, Number(y || 0))),
});

const normalizeVisibilityValue = (visible) => {
  const numeric = Number(visible || 0);
  return Math.max(0, Math.min(2, numeric));
};

const normalizeKeypoint = (point) => {
  const visible = normalizeVisibilityValue(point?.visible || 0);
  const { x, y } = clampPoint(point?.x, point?.y);
  return visible > 0 ? { x, y, visible } : { x: 0, y: 0, visible: 0 };
};

const normalizeInstance = (instance, { isAuto = false } = {}) => {
  const keypoints = Array.from({ length: keypointCount.value }, (_, index) => {
    const point = Array.isArray(instance?.keypoints) ? instance.keypoints[index] : null;
    return normalizeKeypoint(point || {});
  });
  return {
    id: nextInstanceId(),
    class: Number(instance?.class || 0),
    is_auto: !!isAuto,
    keypoints,
  };
};

const countPlacedKeypoints = (instance) => {
  return (instance?.keypoints || []).filter((point) => hasPlacedKeypoint(point)).length;
};

const getInstanceBBox = (instance) => {
  const visiblePoints = (instance?.keypoints || []).filter((point) => hasPlacedKeypoint(point));
  if (!visiblePoints.length) return null;
  const xs = visiblePoints.map((point) => Number(point.x || 0));
  const ys = visiblePoints.map((point) => Number(point.y || 0));
  const x1 = Math.min(...xs);
  const y1 = Math.min(...ys);
  const x2 = Math.max(...xs);
  const y2 = Math.max(...ys);
  return {
    x1,
    y1,
    x2,
    y2,
    width: Math.max(1, x2 - x1),
    height: Math.max(1, y2 - y1),
  };
};

const instanceSkeletonSegments = (instance) => {
  if (!instance || !selectedSkeleton.value.length) return [];
  return selectedSkeleton.value
    .map(([from, to]) => {
      const first = instance.keypoints?.[from];
      const second = instance.keypoints?.[to];
      if (!first || !second) return null;
      if (!hasPlacedKeypoint(first) || !hasPlacedKeypoint(second)) return null;
      return {
        from,
        to,
        x1: first.x,
        y1: first.y,
        x2: second.x,
        y2: second.y,
      };
    })
    .filter(Boolean);
};

const skeletonSegmentCache = computed(() => instances.value.map((instance) => instanceSkeletonSegments(instance)));
const getInstanceSkeletonSegments = (_instance, index) => skeletonSegmentCache.value[index] || [];

const selectInstance = (index) => {
  if (index < 0 || index >= instances.value.length) return;
  selectedInstanceIdx.value = index;
  currentClass.value = Number(instances.value[index]?.class || 0);
  if (selectedKeypointIdx.value >= keypointCount.value) {
    selectedKeypointIdx.value = 0;
  }
};

const selectKeypoint = (index) => {
  if (index < 0 || index >= keypointCount.value) return;
  selectedKeypointIdx.value = index;
};

const addInstance = () => {
  const index = instances.value.length;
  instances.value.push({
    id: nextInstanceId(),
    class: Number(currentClass.value || 0),
    is_auto: false,
    keypoints: buildBlankKeypoints(),
  });
  selectedInstanceIdx.value = index;
  selectedKeypointIdx.value = 0;
  hasChanges.value = true;
};

const removeInstance = (index) => {
  if (index < 0 || index >= instances.value.length) return;
  instances.value.splice(index, 1);
  if (!instances.value.length) {
    selectedInstanceIdx.value = -1;
    selectedKeypointIdx.value = 0;
  } else if (selectedInstanceIdx.value >= instances.value.length) {
    selectedInstanceIdx.value = instances.value.length - 1;
  }
  hasChanges.value = true;
};

const updateSelectedInstanceClass = (classId) => {
  currentClass.value = Number(classId || 0);
  if (!selectedInstance.value) return;
  selectedInstance.value.class = currentClass.value;
  hasChanges.value = true;
};

const getSelectedKeypointVisibility = (index = selectedKeypointIdx.value) => {
  const point = selectedInstance.value?.keypoints?.[index];
  return Number(point?.visible || 0);
};

const getKeypointByIndex = (index = selectedKeypointIdx.value) => {
  return selectedInstance.value?.keypoints?.[index] || null;
};

const getInstanceTitle = (instance, index) => {
  if (!hasMultipleClasses.value) {
    return `实例 #${index + 1}`;
  }
  return `${getClassName(instance?.class)} #${index + 1}`;
};

const getVisibilityText = (visible) => {
  if (visible === 2) return '可见';
  if (visible === 1) return '遮挡';
  return '缺失';
};

const getVisibilityClass = (visible) => {
  if (visible === 2) return 'text-emerald-600';
  if (visible === 1) return 'text-amber-600';
  return 'text-slate-400';
};

const clearKeypoint = (index = selectedKeypointIdx.value) => {
  const point = getKeypointByIndex(index);
  if (!point) return;
  point.x = 0;
  point.y = 0;
  point.visible = 0;
  hasChanges.value = true;
};

const clearSelectedKeypoint = () => clearKeypoint(selectedKeypointIdx.value);

const setKeypointVisibility = (index, visible) => {
  const point = getKeypointByIndex(index);
  if (!point) return;
  const nextVisible = normalizeVisibilityValue(visible);
  point.visible = nextVisible;
  if (nextVisible === 0) {
    point.x = 0;
    point.y = 0;
  }
  hasChanges.value = true;
};

const setSelectedKeypointVisibility = (visible) => setKeypointVisibility(selectedKeypointIdx.value, visible);

const clientToImage = (clientX, clientY) => {
  if (!imgRef.value) return { x: 0, y: 0 };
  const rect = imgRef.value.getBoundingClientRect();
  if (!rect.width || !rect.height) return { x: 0, y: 0 };
  const ratioX = (clientX - rect.left) / rect.width;
  const ratioY = (clientY - rect.top) / rect.height;
  return clampPoint(ratioX * imgWidth.value, ratioY * imgHeight.value);
};

const ensureSelection = () => {
  if (!instances.value.length) {
    selectedInstanceIdx.value = -1;
    return;
  }
  if (selectedInstanceIdx.value < 0 || selectedInstanceIdx.value >= instances.value.length) {
    selectedInstanceIdx.value = 0;
  }
  if (selectedKeypointIdx.value < 0 || selectedKeypointIdx.value >= keypointCount.value) {
    selectedKeypointIdx.value = 0;
  }
  currentClass.value = Number(instances.value[selectedInstanceIdx.value]?.class || 0);
};

const moveSelection = (step = 1) => {
  if (!keypointCount.value) return;
  selectedKeypointIdx.value = (selectedKeypointIdx.value + step + keypointCount.value) % keypointCount.value;
};

const placeSelectedKeypoint = (x, y, { advance = false } = {}) => {
  if (!selectedInstance.value) {
    addInstance();
  }
  const point = selectedInstance.value?.keypoints?.[selectedKeypointIdx.value];
  if (!point) return;
  const nextPoint = clampPoint(x, y);
  point.x = nextPoint.x;
  point.y = nextPoint.y;
  if (Number(point.visible || 0) === 0) {
    point.visible = 2;
  }
  hasChanges.value = true;
  if (advance && !draggingPoint.value) {
    moveSelection(1);
  }
};

const onCanvasPointerDown = (event) => {
  if (event.button !== undefined && event.button !== 0) return;
  if (event.target !== event.currentTarget) return;
  const point = clientToImage(event.clientX, event.clientY);
  placeSelectedKeypoint(point.x, point.y, { advance: false });
};

const onPointPointerDown = (instanceIdx, pointIdx, event) => {
  if (event.button !== undefined && event.button !== 0) return;
  selectInstance(instanceIdx);
  selectKeypoint(pointIdx);
  draggingPoint.value = { instanceIdx, pointIdx };
  activePointerId = event.pointerId;
  event.currentTarget.setPointerCapture?.(event.pointerId);
  const point = clientToImage(event.clientX, event.clientY);
  placeSelectedKeypoint(point.x, point.y, { advance: false });
  event.preventDefault();
};

const onWindowPointerMove = (event) => {
  if (!draggingPoint.value) return;
  if (activePointerId !== null && event.pointerId !== activePointerId) return;
  const point = clientToImage(event.clientX, event.clientY);
  placeSelectedKeypoint(point.x, point.y, { advance: false });
};

const onWindowPointerUp = (event) => {
  if (!draggingPoint.value) return;
  if (activePointerId !== null && event.pointerId !== activePointerId) return;
  draggingPoint.value = null;
  activePointerId = null;
};

const onImageLoad = () => {
  if (!imgRef.value) return;
  imgWidth.value = imgRef.value.naturalWidth || 1;
  imgHeight.value = imgRef.value.naturalHeight || 1;
};

const updateContainerSize = () => {
  if (!containerRef.value) return;
  containerWidth.value = containerRef.value.clientWidth;
  containerHeight.value = containerRef.value.clientHeight;
};

const fetchAnnotations = async () => {
  const token = ++activeLoadToken;
  loading.value = true;
  hasChanges.value = false;
  instances.value = [];
  try {
    const res = await api.getAnnotation({
      project_path: store.currentProject.path,
      dataset_name: props.datasetName,
      split: props.split,
      image_path: props.image.path,
    });
    if (token !== activeLoadToken) return;
    imgWidth.value = Number(res.width || imgWidth.value || 1);
    imgHeight.value = Number(res.height || imgHeight.value || 1);
    const poseMeta = res.pose_meta || {};
    keypointCount.value = Math.max(0, Number(poseMeta.keypoint_count || poseMeta.kpt_shape?.[0] || 0));
    keypointDims.value = Math.max(2, Number(poseMeta.dims || poseMeta.kpt_shape?.[1] || 3));
    flipIdx.value = Array.isArray(poseMeta.flip_idx) ? poseMeta.flip_idx : [];
    keypointNamesByClass.value = poseMeta.kpt_names && typeof poseMeta.kpt_names === 'object' ? poseMeta.kpt_names : {};
    poseSkeleton.value = normalizeSkeleton(poseMeta.skeleton, keypointCount.value);
    const manual = (res.manual_annotation?.instances || []).map((instance) => normalizeInstance(instance, { isAuto: false }));
    const auto = (res.auto_annotation?.instances || []).map((instance) => normalizeInstance(instance, { isAuto: true }));
    instances.value = [...manual, ...auto];
    ensureSelection();
  } catch (error) {
    console.error(error);
  } finally {
    if (token !== activeLoadToken) return;
    loading.value = false;
  }
};

const buildSavePayload = () => {
  return {
    instances: instances.value
      .map((instance) => ({
        class: Number(instance.class || 0),
        keypoints: (instance.keypoints || []).map((point) => ({
          x: Number(point.x || 0),
          y: Number(point.y || 0),
          visible: Number(point.visible || 0),
        })),
      }))
      .filter((instance) => instance.keypoints.some((point) => Number(point.visible || 0) > 0)),
  };
};

const save = async () => {
  await asyncAction.run(SAVE_ACTION_KEY, async () => {
    await apiCall(api.saveAnnotation({
      project_path: store.currentProject.path,
      dataset_name: props.datasetName,
      split: props.split,
      image_path: props.image.path,
      annotation: buildSavePayload(),
    }), {
      errorMsg: '保存失败',
      onSuccess: async () => {
        hasChanges.value = false;
        await fetchAnnotations();
        emit('update', props.image);
      },
    });
  });
};

const handleKeydown = (event) => {
  if (event.defaultPrevented) return;
  if (event.key === 's' && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
    save();
    return;
  }
  if (event.ctrlKey || event.metaKey || event.altKey) return;
  const element = event.target;
  const tag = element?.tagName?.toLowerCase?.();
  if (tag === 'input' || tag === 'textarea' || tag === 'select' || element?.isContentEditable) return;
  if (event.key === 'Escape') {
    emit('close');
    return;
  }
  if (event.key === 'ArrowLeft') {
    event.preventDefault();
    emit('prev');
    return;
  }
  if (event.key === 'ArrowRight') {
    event.preventDefault();
    emit('next');
    return;
  }
  if ((event.key === 'Delete' || event.key === 'Backspace') && event.shiftKey) {
    if (selectedInstanceIdx.value >= 0) {
      removeInstance(selectedInstanceIdx.value);
    }
    return;
  }
  if (event.key === 'Delete' || event.key === 'Backspace') {
    clearSelectedKeypoint();
    return;
  }
  if (event.key.toLowerCase() === 'n') {
    addInstance();
    return;
  }
  if (event.key.toLowerCase() === 'v') {
    const currentVisible = getSelectedKeypointVisibility();
    setSelectedKeypointVisibility(currentVisible === 2 ? 1 : currentVisible === 1 ? 0 : 2);
    return;
  }
  if (event.key.toLowerCase() === 'c') {
    clearSelectedKeypoint();
    return;
  }
  if (event.key === 'Tab') {
    event.preventDefault();
    const step = event.shiftKey ? -1 : 1;
    moveSelection(step);
  }
};

watch(() => props.image, () => {
  fetchAnnotations();
}, { immediate: true });

onMounted(() => {
  updateContainerSize();
  resizeObserver = new ResizeObserver(updateContainerSize);
  if (containerRef.value) {
    resizeObserver.observe(containerRef.value);
  }
  window.addEventListener('keydown', handleKeydown);
  window.addEventListener('pointermove', onWindowPointerMove, { passive: false });
  window.addEventListener('pointerup', onWindowPointerUp, { passive: true });
  window.addEventListener('pointercancel', onWindowPointerUp, { passive: true });
});

onUnmounted(() => {
  resizeObserver?.disconnect();
  window.removeEventListener('keydown', handleKeydown);
  window.removeEventListener('pointermove', onWindowPointerMove);
  window.removeEventListener('pointerup', onWindowPointerUp);
  window.removeEventListener('pointercancel', onWindowPointerUp);
});
</script>
