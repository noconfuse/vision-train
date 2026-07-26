<template>
  <div class="vt-workspace-backdrop" @click.self="$emit('close')">
    <div class="vt-workspace-panel vt-workspace-panel--row vt-workspace-panel--xl">
      <div class="flex-1 bg-gray-900 relative flex items-center justify-center overflow-hidden select-none" ref="containerRef">
        <div v-if="loading || refining" class="absolute inset-0 flex items-center justify-center text-white">
          {{ refining ? 'Processing...' : 'Loading...' }}
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
            class="absolute inset-0 w-full h-full"
            :class="canvasCursorClass"
            :viewBox="`0 0 ${imgWidth} ${imgHeight}`"
            preserveAspectRatio="none"
            @pointermove="onPointerMoveBg"
            @pointerdown="onPointerDownBg"
          >
            <g v-for="(poly, pIdx) in displayPolygons" :key="pIdx">
              <polygon
                v-if="poly.is_auto"
                :points="buildPointsString(poly.points)"
                stroke="rgba(255, 255, 255, 0.95)"
                :stroke-width="(selectedPolyIdx === pIdx ? 4.5 : 3.5) / scale"
                stroke-linejoin="round"
                fill="transparent"
                pointer-events="none"
              />
              <polygon
                :points="buildPointsString(poly.points)"
                :stroke="poly.is_auto ? '#22d3ee' : getColor(poly.class)"
                :stroke-width="poly.is_auto ? ((selectedPolyIdx === pIdx ? 3.25 : 2.5) / scale) : ((selectedPolyIdx === pIdx ? 3 : 2) / scale)"
                :stroke-opacity="poly.is_auto ? 1 : 0.9"
                :stroke-dasharray="poly.is_auto ? '10 6' : '0'"
                stroke-linejoin="round"
                :fill="poly.is_auto ? 'rgba(34, 211, 238, 0.08)' : (selectedPolyIdx === pIdx ? 'rgba(59, 130, 246, 0.12)' : 'rgba(0, 0, 0, 0)')"
                style="cursor: pointer; touch-action: none;"
                @pointerdown="onPolygonPointerDown(pIdx, $event)"
              />
              <text
                v-if="poly.points.length"
                :x="poly.points[0].x * imgWidth"
                :y="Math.max(14 / scale, poly.points[0].y * imgHeight - 6 / scale)"
                :fill="poly.is_auto ? '#67e8f9' : getColor(poly.class)"
                :font-size="12 / scale"
                font-weight="bold"
                style="text-shadow: 0 0 2px rgba(8, 47, 73, 0.95), 1px 1px 1px rgba(0, 0, 0, 0.9); cursor: pointer; touch-action: none;"
                @pointerdown="onPolygonPointerDown(pIdx, $event)"
              >
                {{ getClassName(poly.class) }} {{ poly.is_auto ? '(Auto)' : '' }}
              </text>
            </g>

            <g v-if="selectedPolyIdx >= 0 && displayPolygons[selectedPolyIdx]">
              <g v-for="idx in handlePointIndices" :key="idx">
                <circle
                  :cx="displayPolygons[selectedPolyIdx].points[idx].x * imgWidth"
                  :cy="displayPolygons[selectedPolyIdx].points[idx].y * imgHeight"
                  :r="5 / scale"
                  fill="white"
                  stroke="black"
                  :stroke-width="1 / scale"
                  style="cursor: move; touch-action: none;"
                  @pointerdown="onPointPointerDown(selectedPolyIdx, idx, $event)"
                />
              </g>
            </g>

            <g v-if="freehandPolygon">
              <template v-if="draftMode === 'manual'">
                <polyline
                  :points="buildPointsString(freehandPolygon.points, { includeCursor: !freehandActive })"
                  :stroke="getColor(currentClass)"
                  :stroke-width="2 / scale"
                  stroke-dasharray="4"
                  fill="transparent"
                  pointer-events="none"
                />
                <circle
                  v-for="(pt, idx) in freehandPolygon.points"
                  :key="`draft-${idx}`"
                  :cx="pt.x * imgWidth"
                  :cy="pt.y * imgHeight"
                  :r="idx === 0 ? 5 / scale : 4 / scale"
                  :fill="idx === 0 ? getColor(currentClass) : 'white'"
                  stroke="black"
                  :stroke-width="1 / scale"
                  pointer-events="none"
                />
              </template>
              <template v-else-if="draftMode === 'smart'">
                <rect
                  v-if="smartRect"
                  :x="smartRect.x"
                  :y="smartRect.y"
                  :width="smartRect.w"
                  :height="smartRect.h"
                  :stroke="getColor(currentClass)"
                  :stroke-width="2 / scale"
                  stroke-dasharray="6"
                  fill="transparent"
                  pointer-events="none"
                />
              </template>
              <template v-else-if="draftMode === 'erase'">
                <polyline
                  :points="buildPointsString(freehandPolygon.points, { includeCursor: freehandActive })"
                  stroke="rgba(239, 68, 68, 0.9)"
                  :stroke-width="ERASER_STROKE_WIDTH_PX / scale"
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  fill="transparent"
                  pointer-events="none"
                />
              </template>
            </g>

          </svg>
        </div>
      </div>

      <div class="w-80 bg-white border-l border-gray-200 flex flex-col">
        <div class="p-4 border-b border-gray-200">
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <h3 class="font-bold text-gray-800 mb-1">图片标注</h3>
              <UiTooltip side="bottom" align="start" content-class="max-w-[24rem] break-all text-left">
                <template #trigger>
                  <p class="text-xs text-gray-500 truncate">{{ getPathDisplayName(image.path) }}</p>
                </template>
                {{ image.path }}
              </UiTooltip>
            </div>
            <button
              type="button"
              class="shrink-0 text-gray-400 hover:text-gray-600 transition-colors"
              @click="$emit('close')"
            >
              <AppIcon name="close" class="h-4 w-4" />
            </button>
          </div>
        </div>

        <div class="flex-1 overflow-y-auto p-4">
          <div class="flex items-center justify-between gap-2 mb-3">
            <h4 class="text-xs font-bold text-gray-500 uppercase">辅助工具</h4>
            <button
              type="button"
              class="shrink-0 text-gray-400 hover:text-gray-600 transition-colors"
              @click="openGuideModal"
            >
              <AppIcon name="help" class="h-4 w-4" />
            </button>
          </div>
          <div class="flex flex-wrap gap-2 mb-4">
            <button
              type="button"
              class="vt-btn-size-sm inline-flex items-center gap-1.5 border px-3 py-1.5 text-sm transition-colors"
              :class="smartSelectMode ? 'border-blue-500 bg-blue-50 text-blue-600' : 'border-gray-300 bg-white text-gray-700 hover:border-gray-400'"
              :aria-pressed="smartSelectMode ? 'true' : 'false'"
              @click="toggleSmartMode"
            >
              <AppIcon name="sparkles" class="h-4 w-4" />
              <span>{{ smartSelectMode ? '退出智能选区' : '智能选区' }}</span>
            </button>
            <button
              v-if="selectedPolyIdx >= 0"
              type="button"
              class="vt-btn-size-sm inline-flex items-center gap-1.5 border px-3 py-1.5 text-sm transition-colors"
              :class="eraserMode ? 'border-red-500 bg-red-50 text-red-600' : 'border-gray-300 bg-white text-gray-700 hover:border-gray-400'"
              :aria-pressed="eraserMode ? 'true' : 'false'"
              @click="toggleEraserMode"
            >
              <AppIcon name="delete" class="h-4 w-4" />
              <span>{{ eraserMode ? '退出橡皮擦' : '橡皮擦' }}</span>
            </button>
          </div>
          <div class="mb-4 text-xs text-gray-500">
            {{ toolHintText }}
          </div>

          <div v-if="freehandPolygon && draftMode === 'manual'" class="flex gap-2 mb-4">
            <button
              type="button"
              class="vt-btn-secondary vt-btn-size-md flex-1 justify-center"
              :disabled="(freehandPolygon.points || []).length < 3"
              @click="commitManualPolygon"
            >
              完成包围
            </button>
            <button
              type="button"
              class="vt-btn-secondary vt-btn-size-md flex-1 justify-center"
              @click="cancelFreehand"
            >
              取消
            </button>
          </div>

          <h4 class="text-xs font-bold text-gray-500 uppercase mb-3">选择类别</h4>
          <div class="space-y-2">
            <div
              v-for="(name, idx) in classList"
              :key="idx"
              class="vt-selectable flex items-center gap-2 p-2 cursor-pointer"
              :class="currentClass === idx ? 'vt-selectable--selected' : 'border-transparent'"
              @click="updateSelectedPolygonClass(idx)"
            >
              <div class="w-4 h-4 rounded-full" :style="{ backgroundColor: getColor(idx) }"></div>
              <span class="text-sm font-medium">{{ name }}</span>
              <span class="text-xs text-gray-400 ml-auto">id: {{ idx }}</span>
            </div>
          </div>
        </div>

        <div class="p-4 border-t border-gray-200 bg-gray-50 space-y-3">
          <div class="flex justify-between items-center text-sm text-gray-600">
            <span>标注数量: {{ polygons.length }}</span>
            <span v-if="hasChanges" class="vt-tag vt-tag-warn">未保存</span>
          </div>

          <button
            v-if="selectedPolyIdx >= 0"
            @click="removePolygon(selectedPolyIdx)"
            class="vt-btn-danger vt-btn-size-lg w-full justify-center mb-2"
          >
            <AppIcon name="delete" class="h-4 w-4" />
            删除选中标注 (Delete)
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

    <div v-if="showGuideModal" class="vt-modal-backdrop" @click.self="closeGuideModal">
      <div class="w-[48rem] max-w-[calc(100vw-2rem)] bg-white shadow-xl border border-gray-200 overflow-hidden">
        <div class="p-4 border-b border-gray-200 flex items-center justify-between gap-4">
          <div>
            <h3 class="font-bold text-gray-800">如何标注分割目标</h3>
            <p class="mt-1 text-sm text-gray-500">先用手工链路保底，智能工具只负责提速。</p>
          </div>
          <button
            type="button"
            class="text-gray-400 hover:text-gray-600 transition-colors"
            @click="closeGuideModal"
          >
            <AppIcon name="close" class="h-4 w-4" />
          </button>
        </div>

        <div class="p-4 overflow-x-auto">
          <div class="flex gap-3 justify-center min-w-max">
          <div
            v-for="item in guideCards"
            :key="item.title"
            class="w-56 shrink-0 border border-gray-200 rounded-md overflow-hidden bg-white"
          >
            <button
              type="button"
              class="block w-full bg-gray-100"
              @click="previewGuideImage(item)"
            >
              <img :src="item.image" :alt="item.title" class="w-full h-28 object-cover" />
            </button>
            <div class="p-2.5">
              <div class="flex items-center gap-2 mb-2 text-gray-800">
                <AppIcon :name="item.icon" class="h-4 w-4" />
                <h4 class="font-semibold text-sm">{{ item.title }}</h4>
              </div>
              <p class="text-xs text-gray-600 leading-5">{{ item.description }}</p>
            </div>
          </div>
          </div>
        </div>

        <div class="p-4 border-t border-gray-200 bg-gray-50 flex items-center justify-between gap-3">
          <p class="text-xs text-gray-500">需要时可通过标注弹窗右上角帮助按钮再次查看。</p>
          <button type="button" class="vt-btn-secondary vt-btn-size-md" @click="closeGuideModal">
            我知道了
          </button>
        </div>
      </div>
    </div>

    <div v-if="guideImagePreview" class="vt-modal-backdrop" @click.self="closeGuideImagePreview">
      <div class="w-[min(92vw,64rem)] bg-white shadow-xl border border-gray-200 overflow-hidden">
        <div class="p-3 border-b border-gray-200 flex items-center justify-between gap-4">
          <div class="text-sm font-medium text-gray-800">{{ guideImagePreview.title }}</div>
          <button
            type="button"
            class="text-gray-400 hover:text-gray-600 transition-colors"
            @click="closeGuideImagePreview"
          >
            <AppIcon name="close" class="h-4 w-4" />
          </button>
        </div>
        <div class="bg-black/95 flex items-center justify-center p-4">
          <img :src="guideImagePreview.image" :alt="guideImagePreview.title" class="max-h-[80vh] w-auto max-w-full object-contain" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, shallowRef } from 'vue';
import api from '../api';
import { useMainStore } from '../stores/main';
import { useApiCall } from '../composables/useApiCall';
import { useAsyncAction } from '../composables/useAsyncAction';
import { getPathDisplayName } from '../utils';
import helpOp1 from '../assets/images/help/op1.png';
import helpOp2 from '../assets/images/help/op2.png';
import helpOp3 from '../assets/images/help/op3.png';
import AppIcon from './ui/AppIcon.vue';
import AsyncButton from './ui/AsyncButton.vue';
import UiTooltip from './ui/Tooltip.vue';

const props = defineProps({
  image: { type: Object, required: true },
  classList: { type: Array, default: () => [] },
  datasetName: { type: String, required: true },
  split: { type: String, default: 'train' }
});

const emit = defineEmits(['close', 'prev', 'next', 'update']);

const store = useMainStore();
const apiCall = useApiCall();
const asyncAction = useAsyncAction();
const containerRef = ref(null);
const imgRef = ref(null);
const loading = ref(true);
const refining = ref(false);
const polygons = ref([]);
const freehandPolygon = shallowRef(null);
const selectedPolyIdx = ref(-1);
const currentClass = ref(0);
const hasChanges = ref(false);
const smartSelectMode = ref(false);
const eraserMode = ref(false);
const draftMode = ref(null);
const SAVE_ACTION_KEY = 'segment-annotator:save';
const REFINE_ACTION_KEY = 'segment-annotator:refine';
const ERASE_ACTION_KEY = 'segment-annotator:erase';
const isActionPending = (key) => asyncAction.isPending(key);
let activeLoadToken = 0;
const TARGET_POINT_SPACING_PX = 10;
const SMART_POINT_SPACING_PX = 16;
const MAX_HANDLE_POINTS = 80;
const EDGE_SNAP_RADIUS_PX = 6;
const ERASER_STROKE_WIDTH_PX = 12;
const GUIDE_STORAGE_KEY = 'segment-annotator:guide-shown:v1';
const showGuideModal = ref(false);
const guideImagePreview = ref(null);

const guideCards = [
  {
    title: '手工包围',
    icon: 'target',
    description: '默认逐点连线，最后点击首点闭合。需要精确控制时，优先走这条链路。',
    image: helpOp1,
  },
  {
    title: '智能框选',
    icon: 'sparkles',
    description: '需要提速时开启智能选区，拖一个水平矩形框，系统会先给出一个可继续编辑的初稿。',
    image: helpOp2,
  },
  {
    title: '橡皮擦裁减',
    icon: 'delete',
    description: '初稿多包时，选中轮廓后用橡皮擦轻扫多余边缘，只做局部裁减。',
    image: helpOp3,
  },
];

const imgWidth = ref(1);
const imgHeight = ref(1);
const scale = ref(1);
const containerWidth = ref(0);
const containerHeight = ref(0);
let resizeObserver = null;

const colors = [
  '#ef4444', '#f97316', '#f59e0b', '#84cc16', '#22c55e',
  '#06b6d4', '#3b82f6', '#6366f1', '#a855f7', '#ec4899'
];
const getColor = (idx) => colors[idx % colors.length];
const getClassName = (idx) => props.classList[idx] || `Class ${idx}`;
const toolHintText = computed(() => {
  if (eraserMode.value) return '拖一笔擦掉多余区域，松手后只裁减当前选中轮廓。';
  if (smartSelectMode.value) return '拖一个水平矩形框，系统会在框内自动生成分割初稿。';
  if (freehandPolygon.value && draftMode.value === 'manual') return '继续点下一个点，回到首点闭合，或按 Enter 完成包围。';
  return '默认直接点连线标注；需要提速时再开启智能选区或橡皮擦。';
});
const canvasCursorClass = computed(() => {
  if (eraserMode.value) return 'vt-cursor-eraser';
  if (freehandActive || smartSelectMode.value) return 'cursor-crosshair';
  return 'cursor-default';
});

const displayPolygons = computed(() => polygons.value);
const handlePointIndices = computed(() => {
  const poly = selectedPolyIdx.value >= 0 ? displayPolygons.value[selectedPolyIdx.value] : null;
  const pts = poly?.points || [];
  if (!pts.length) return [];
  const stride = Math.max(1, Math.ceil(pts.length / MAX_HANDLE_POINTS));
  const indices = [];
  for (let i = 0; i < pts.length; i += stride) indices.push(i);
  if (indices[indices.length - 1] !== pts.length - 1) indices.push(pts.length - 1);
  return indices;
});

const imageStyle = computed(() => {
  if (!imgWidth.value || !imgHeight.value || !containerWidth.value || !containerHeight.value) return {};
  const imgRatio = imgWidth.value / imgHeight.value;
  const containerRatio = containerWidth.value / containerHeight.value;
  let w, h;
  if (imgRatio > containerRatio) {
    w = containerWidth.value - 40;
    h = w / imgRatio;
  } else {
    h = containerHeight.value - 40;
    w = h * imgRatio;
  }
  scale.value = w / imgWidth.value;
  return { width: `${w}px`, height: `${h}px` };
});

const smartRect = computed(() => {
  if (draftMode.value !== 'smart' || !freehandPolygon.value) return null;
  const pts = freehandPolygon.value.points || [];
  if (pts.length < 2) return null;
  const a = pts[0];
  const b = pts[1];
  const minX = Math.max(0, Math.min(1, Math.min(Number(a.x), Number(b.x))));
  const maxX = Math.max(0, Math.min(1, Math.max(Number(a.x), Number(b.x))));
  const minY = Math.max(0, Math.min(1, Math.min(Number(a.y), Number(b.y))));
  const maxY = Math.max(0, Math.min(1, Math.max(Number(a.y), Number(b.y))));
  const x = minX * imgWidth.value;
  const y = minY * imgHeight.value;
  const w = (maxX - minX) * imgWidth.value;
  const h = (maxY - minY) * imgHeight.value;
  if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(w) || !Number.isFinite(h)) return null;
  if (w < 2 || h < 2) return null;
  return { x, y, w, h, minX, minY, maxX, maxY };
});

const updateContainerSize = () => {
  if (containerRef.value) {
    containerWidth.value = containerRef.value.clientWidth;
    containerHeight.value = containerRef.value.clientHeight;
  }
};

const onImageLoad = () => {
  if (imgRef.value) {
    imgWidth.value = imgRef.value.naturalWidth;
    imgHeight.value = imgRef.value.naturalHeight;
  }
  edgeField.value = null;
};

const clientToNorm = (clientX, clientY) => {
  if (!imgRef.value) return { x: 0, y: 0 };
  const rect = imgRef.value.getBoundingClientRect();
  if (rect.width === 0 || rect.height === 0) return { x: 0, y: 0 };
  const x = (clientX - rect.left) / rect.width;
  const y = (clientY - rect.top) / rect.height;
  return {
    x: Math.max(0, Math.min(1, x)),
    y: Math.max(0, Math.min(1, y)),
  };
};

const cursorNorm = shallowRef({ x: 0, y: 0 });
let activePointerId = null;
let dragPoint = null;
let freehandActive = false;
let eraseTarget = null;
const edgeField = shallowRef(null);

const buildPointsString = (points, options = {}) => {
  const { includeCursor = false } = options || {};
  const pts = Array.isArray(points) ? points : [];
  const coords = pts.map((p) => `${p.x * imgWidth.value},${p.y * imgHeight.value}`);
  if (includeCursor) {
    coords.push(`${cursorNorm.value.x * imgWidth.value},${cursorNorm.value.y * imgHeight.value}`);
  }
  return coords.join(' ');
};

const distPx = (a, b) => {
  const dx = (Number(a.x) - Number(b.x)) * imgWidth.value;
  const dy = (Number(a.y) - Number(b.y)) * imgHeight.value;
  return Math.hypot(dx, dy);
};

const removeNearDuplicates = (pointsPx, minDistPx = 1.0) => {
  const pts = Array.isArray(pointsPx) ? pointsPx : [];
  const out = [];
  for (const p of pts) {
    const x = Number(p.x);
    const y = Number(p.y);
    if (!Number.isFinite(x) || !Number.isFinite(y)) continue;
    const cur = { x, y };
    const last = out.length ? out[out.length - 1] : null;
    if (!last) {
      out.push(cur);
      continue;
    }
    if (Math.hypot(cur.x - last.x, cur.y - last.y) >= minDistPx) out.push(cur);
  }
  if (out.length >= 2) {
    const first = out[0];
    const last = out[out.length - 1];
    if (Math.hypot(first.x - last.x, first.y - last.y) < minDistPx) out.pop();
  }
  return out;
};

const polygonPerimeterPx = (pointsPx) => {
  const pts = Array.isArray(pointsPx) ? pointsPx : [];
  if (pts.length < 2) return 0;
  let peri = 0;
  for (let i = 0; i < pts.length; i += 1) {
    const a = pts[i];
    const b = pts[(i + 1) % pts.length];
    peri += Math.hypot(b.x - a.x, b.y - a.y);
  }
  return peri;
};

const pointToSegmentDistancePx = (p, a, b) => {
  const vx = b.x - a.x;
  const vy = b.y - a.y;
  const wx = p.x - a.x;
  const wy = p.y - a.y;
  const c1 = vx * wx + vy * wy;
  if (c1 <= 0) return Math.hypot(p.x - a.x, p.y - a.y);
  const c2 = vx * vx + vy * vy;
  if (c2 <= c1) return Math.hypot(p.x - b.x, p.y - b.y);
  const t = c1 / c2;
  const projX = a.x + t * vx;
  const projY = a.y + t * vy;
  return Math.hypot(p.x - projX, p.y - projY);
};

const rdpSimplify = (pointsPx, epsilonPx) => {
  const pts = Array.isArray(pointsPx) ? pointsPx : [];
  if (pts.length < 3) return pts;
  const epsilon = Math.max(0.0, Number(epsilonPx) || 0.0);
  if (epsilon <= 0) return pts;

  let dmax = 0;
  let index = 0;
  const start = pts[0];
  const end = pts[pts.length - 1];
  for (let i = 1; i < pts.length - 1; i += 1) {
    const d = pointToSegmentDistancePx(pts[i], start, end);
    if (d > dmax) {
      index = i;
      dmax = d;
    }
  }
  if (dmax > epsilon) {
    const rec1 = rdpSimplify(pts.slice(0, index + 1), epsilon);
    const rec2 = rdpSimplify(pts.slice(index), epsilon);
    return rec1.slice(0, -1).concat(rec2);
  }
  return [start, end];
};

const resampleClosedPolygon = (pointsPx, spacingPx) => {
  const pts = removeNearDuplicates(pointsPx, 0.5);
  if (pts.length < 3) return pts;
  const peri = polygonPerimeterPx(pts);
  if (!Number.isFinite(peri) || peri <= 0) return pts;
  const targetCount = Math.max(3, Math.round(peri / Math.max(1, spacingPx)));
  const step = peri / targetCount;
  if (!Number.isFinite(step) || step <= 0) return pts;

  const out = [];
  let curSeg = 0;
  let curDist = 0;
  for (let k = 0; k < targetCount; k += 1) {
    const target = k * step;
    while (curSeg < pts.length) {
      const a = pts[curSeg];
      const b = pts[(curSeg + 1) % pts.length];
      const segLen = Math.hypot(b.x - a.x, b.y - a.y);
      if (segLen <= 0) {
        curSeg += 1;
        continue;
      }
      if (curDist + segLen >= target) {
        const t = (target - curDist) / segLen;
        out.push({ x: a.x + (b.x - a.x) * t, y: a.y + (b.y - a.y) * t });
        break;
      }
      curDist += segLen;
      curSeg += 1;
    }
  }
  return removeNearDuplicates(out, 0.1);
};

const buildEdgeField = () => {
  try {
    const img = imgRef.value;
    if (!img || !img.complete) return null;
    const w = img.naturalWidth || imgWidth.value;
    const h = img.naturalHeight || imgHeight.value;
    if (!w || !h) return null;
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });
    if (!ctx) return null;
    ctx.drawImage(img, 0, 0, w, h);
    const imageData = ctx.getImageData(0, 0, w, h);
    const data = imageData.data;
    const gray = new Float32Array(w * h);
    for (let i = 0, j = 0; i < data.length; i += 4, j += 1) {
      gray[j] = 0.299 * data[i] + 0.587 * data[i + 1] + 0.114 * data[i + 2];
    }
    const mag = new Float32Array(w * h);
    const idx = (x, y) => y * w + x;
    for (let y = 1; y < h - 1; y += 1) {
      for (let x = 1; x < w - 1; x += 1) {
        const gx =
          -gray[idx(x - 1, y - 1)] + gray[idx(x + 1, y - 1)] +
          -2 * gray[idx(x - 1, y)] + 2 * gray[idx(x + 1, y)] +
          -gray[idx(x - 1, y + 1)] + gray[idx(x + 1, y + 1)];
        const gy =
          -gray[idx(x - 1, y - 1)] - 2 * gray[idx(x, y - 1)] - gray[idx(x + 1, y - 1)] +
          gray[idx(x - 1, y + 1)] + 2 * gray[idx(x, y + 1)] + gray[idx(x + 1, y + 1)];
        mag[idx(x, y)] = Math.abs(gx) + Math.abs(gy);
      }
    }
    return { w, h, mag };
  } catch (_e) {
    return null;
  }
};

const ensureEdgeField = () => {
  const cur = edgeField.value;
  if (cur && cur.w === imgWidth.value && cur.h === imgHeight.value) return cur;
  const built = buildEdgeField();
  edgeField.value = built;
  return built;
};

const snapPointToEdge = (ptPx, field, radiusPx) => {
  if (!field) return ptPx;
  const w = field.w;
  const h = field.h;
  const mag = field.mag;
  const r = Math.max(1, Math.floor(radiusPx || 1));
  const cx = Math.max(0, Math.min(w - 1, Math.round(ptPx.x)));
  const cy = Math.max(0, Math.min(h - 1, Math.round(ptPx.y)));
  let bestX = cx;
  let bestY = cy;
  let best = mag[cy * w + cx] || 0;
  for (let dy = -r; dy <= r; dy += 1) {
    const y = cy + dy;
    if (y < 0 || y >= h) continue;
    for (let dx = -r; dx <= r; dx += 1) {
      const x = cx + dx;
      if (x < 0 || x >= w) continue;
      const m = mag[y * w + x] || 0;
      if (m > best) {
        best = m;
        bestX = x;
        bestY = y;
      }
    }
  }
  return { x: bestX, y: bestY };
};

const snapPolygonToEdges = (pointsPx) => {
  const field = ensureEdgeField();
  if (!field) return pointsPx;
  return (pointsPx || []).map((pt) => snapPointToEdge(pt, field, EDGE_SNAP_RADIUS_PX));
};

const previewDraggedPoint = (pointsNorm, pointIdx, currentNorm) => {
  const pts = Array.isArray(pointsNorm) ? pointsNorm : [];
  if (pts.length < 3 || pointIdx < 0 || pointIdx >= pts.length || !currentNorm) return pts;
  return pts.map((pt, idx) => (idx === pointIdx ? { x: currentNorm.x, y: currentNorm.y } : pt));
};

const ensureMaxPointSpacing = (pointsPx, maxSpacingPx) => {
  const pts = removeNearDuplicates(pointsPx, 0.5);
  if (pts.length < 3) return pts;
  const peri = polygonPerimeterPx(pts);
  const spacing = peri / pts.length;
  if (Number.isFinite(spacing) && spacing <= maxSpacingPx) return pts;
  return resampleClosedPolygon(pts, maxSpacingPx);
};

const normalizeForSave = (poly) => {
  const pts = (poly?.points || []).map((p) => ({ x: Number(p.x), y: Number(p.y) }));
  const px = pts.map((p) => ({ x: p.x * imgWidth.value, y: p.y * imgHeight.value }));
  return ensureMaxPointSpacing(px, TARGET_POINT_SPACING_PX);
};

const cancelFreehand = () => {
  freehandPolygon.value = null;
  freehandActive = false;
  draftMode.value = null;
  eraseTarget = null;
};

const buildFallbackPolygon = (strokePoints) => {
  const pts = strokePoints || [];
  if (pts.length < 3) return null;
  const pxRaw = pts.map((p) => ({ x: Number(p.x) * imgWidth.value, y: Number(p.y) * imgHeight.value }));
  const pxDedup = removeNearDuplicates(pxRaw, 1.0);
  const pxSimplified = rdpSimplify(pxDedup, 1.5);
  const pxResampled = resampleClosedPolygon(pxSimplified, TARGET_POINT_SPACING_PX);
  const pxSnapped = snapPolygonToEdges(pxResampled);
  const normPoints = pxSnapped.map((p) => ({ x: p.x / imgWidth.value, y: p.y / imgHeight.value }));
  if (normPoints.length < 3) return null;
  return { class: currentClass.value, points: normPoints, is_auto: false, source: 'freehand' };
};

const responseToNormPoints = (res) => {
  const w = Number(res?.width || imgWidth.value || 1);
  const h = Number(res?.height || imgHeight.value || 1);
  const p0 = (res?.polygons || [])[0] || null;
  const pointsPx = (p0?.points || [])
    .map((pt) => ({ x: Number(pt.x), y: Number(pt.y) }))
    .filter((pt) => Number.isFinite(pt.x) && Number.isFinite(pt.y));
  return pointsPx
    .map((pt) => ({ x: pt.x / w, y: pt.y / h }))
    .filter((pt) => Number.isFinite(pt.x) && Number.isFinite(pt.y));
};

const responseToNormPolygons = (res) => {
  const w = Number(res?.width || imgWidth.value || 1);
  const h = Number(res?.height || imgHeight.value || 1);
  return (res?.polygons || [])
    .map((p) => ({
      class: Number(p.class) || 0,
      points: (p.points || [])
        .map((pt) => ({ x: Number(pt.x) / w, y: Number(pt.y) / h }))
        .filter((pt) => Number.isFinite(pt.x) && Number.isFinite(pt.y)),
      is_auto: false,
      source: 'erased',
    }))
    .filter((p) => (p.points || []).length >= 3);
};

const commitManualPolygon = () => {
  if (!freehandPolygon.value || draftMode.value !== 'manual') return;
  const normPoints = (freehandPolygon.value.points || [])
    .map((pt) => ({ x: Number(pt.x), y: Number(pt.y) }))
    .filter((pt) => Number.isFinite(pt.x) && Number.isFinite(pt.y));
  if (normPoints.length < 3) return;
  const next = [...polygons.value, { class: currentClass.value, points: normPoints, is_auto: false, source: 'manual' }];
  polygons.value = next;
  selectedPolyIdx.value = next.length - 1;
  hasChanges.value = true;
  cancelFreehand();
};

const commitSmartSelection = async () => {
  if (!freehandPolygon.value) return;
  const rect = smartRect.value;
  if (!rect) {
    cancelFreehand();
    return;
  }
  const strokePoints = [
    { x: rect.minX, y: rect.minY },
    { x: rect.maxX, y: rect.minY },
    { x: rect.maxX, y: rect.maxY },
    { x: rect.minX, y: rect.maxY },
  ];
  cancelFreehand();

  refining.value = true;
  try {
    const res = await asyncAction.run(REFINE_ACTION_KEY, async () => (
      await apiCall(api.refineSegmentAnnotation({
        project_path: store.currentProject.path,
        dataset_name: props.datasetName,
        split: props.split,
        image_path: props.image.path,
        class_id: currentClass.value,
        spacing_px: SMART_POINT_SPACING_PX,
        stroke: { points: strokePoints },
      }), { errorMsg: '拟合失败' })
    ));
    const normPoints = responseToNormPoints(res);
    if (normPoints.length >= 3) {
      const next = [...polygons.value, { class: currentClass.value, points: normPoints, is_auto: false, source: 'refined' }];
      polygons.value = next;
      selectedPolyIdx.value = next.length - 1;
      hasChanges.value = true;
      return;
    }
    const fallback = buildFallbackPolygon(strokePoints);
    if (fallback) {
      const next = [...polygons.value, fallback];
      polygons.value = next;
      selectedPolyIdx.value = next.length - 1;
      hasChanges.value = true;
    }
  } finally {
    refining.value = false;
  }
};

const commitEraseStroke = async () => {
  if (!freehandPolygon.value || !eraseTarget) {
    cancelFreehand();
    return;
  }
  const strokePoints = (freehandPolygon.value.points || [])
    .map((p) => ({ x: Number(p.x), y: Number(p.y) }))
    .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y));
  if (strokePoints.length < 2) {
    cancelFreehand();
    return;
  }
  const target = eraseTarget;
  cancelFreehand();
  refining.value = true;
  try {
    const res = await asyncAction.run(ERASE_ACTION_KEY, async () => (
      await apiCall(api.eraseSegmentAnnotation({
        project_path: store.currentProject.path,
        dataset_name: props.datasetName,
        split: props.split,
        image_path: props.image.path,
        class_id: target.originalPolygon.class,
        spacing_px: SMART_POINT_SPACING_PX,
        stroke_width_px: ERASER_STROKE_WIDTH_PX,
        polygon: {
          points: (target.originalPolygon.points || []).map((pt) => ({ x: Number(pt.x), y: Number(pt.y) })),
        },
        stroke: { points: strokePoints },
      }), { errorMsg: '橡皮擦失败' })
    ));
    const newPolys = responseToNormPolygons(res);
    const next = polygons.value.slice();
    next.splice(target.polyIdx, 1, ...newPolys);
    polygons.value = next;
    selectedPolyIdx.value = newPolys.length ? target.polyIdx : -1;
    hasChanges.value = true;
  } finally {
    refining.value = false;
  }
};

const commitPointDrag = async (drag) => {
  if (!drag) return;
  const originalPolygon = drag.originalPolygon;
  if (!originalPolygon || !Array.isArray(originalPolygon.points) || originalPolygon.points.length < 3) return;
  const currentPoint = drag.currentPoint;
  if (!currentPoint) {
    polygons.value = polygons.value.map((p, idx) => (idx === drag.polyIdx ? originalPolygon : p));
    return;
  }
  const normPoints = previewDraggedPoint(originalPolygon.points || [], drag.pointIdx, currentPoint);
  polygons.value = polygons.value.map((p, idx) => (
    idx === drag.polyIdx
      ? { ...p, class: originalPolygon.class, points: normPoints, is_auto: false, source: 'manual-edited' }
      : p
  ));
  selectedPolyIdx.value = drag.polyIdx;
  hasChanges.value = true;
};

const onPointerDownBg = (e) => {
  if (e.button !== undefined && e.button !== 0) return;
  const norm = clientToNorm(e.clientX, e.clientY);
  cursorNorm.value = norm;
  if (eraserMode.value && selectedPolyIdx.value < 0) return;
  if (eraserMode.value && selectedPolyIdx.value >= 0) {
    const poly = polygons.value[selectedPolyIdx.value];
    if (!poly || !Array.isArray(poly.points) || poly.points.length < 3) return;
    e.currentTarget.setPointerCapture(e.pointerId);
    activePointerId = e.pointerId;
    eraseTarget = {
      polyIdx: selectedPolyIdx.value,
      originalPolygon: { ...poly, points: (poly.points || []).map((pt) => ({ x: Number(pt.x), y: Number(pt.y) })) },
    };
    freehandPolygon.value = { class: poly.class, points: [norm] };
    draftMode.value = 'erase';
    freehandActive = true;
    e.preventDefault();
    return;
  }
  if (!smartSelectMode.value) {
    const current = freehandPolygon.value;
    if (!current || draftMode.value !== 'manual') {
      selectedPolyIdx.value = -1;
      freehandPolygon.value = {
        class: currentClass.value,
        points: [norm],
      };
      draftMode.value = 'manual';
      freehandActive = false;
      e.preventDefault();
      return;
    }
    const points = current.points || [];
    const first = points[0];
    if (first && points.length >= 3 && distPx(first, norm) <= 10) {
      commitManualPolygon();
      e.preventDefault();
      return;
    }
    freehandPolygon.value = {
      ...current,
      points: [...points, norm],
    };
    e.preventDefault();
    return;
  }
  e.currentTarget.setPointerCapture(e.pointerId);
  activePointerId = e.pointerId;
  selectedPolyIdx.value = -1;
  freehandPolygon.value = {
    class: currentClass.value,
    points: [norm, norm],
  };
  draftMode.value = 'smart';
  freehandActive = true;
  e.preventDefault();
};

const onPointerMoveBg = (e) => {
  const norm = clientToNorm(e.clientX, e.clientY);
  cursorNorm.value = norm;
};

const onPolygonPointerDown = (idx, e) => {
  if (e.button !== undefined && e.button !== 0) return;
  e.currentTarget.setPointerCapture(e.pointerId);
  activePointerId = e.pointerId;
  selectedPolyIdx.value = idx;
  currentClass.value = polygons.value[idx]?.class ?? 0;
  e.preventDefault();
  e.stopPropagation();
};

const onPointPointerDown = (polyIdx, pointIdx, e) => {
  if (e.button !== undefined && e.button !== 0) return;
  e.currentTarget.setPointerCapture(e.pointerId);
  activePointerId = e.pointerId;
  selectedPolyIdx.value = polyIdx;
  const poly = polygons.value[polyIdx];
  if (!poly) return;
  const originalPoints = (poly.points || []).map((pt) => ({ x: Number(pt.x), y: Number(pt.y) }));
  const startPoint = originalPoints[pointIdx];
  dragPoint = {
    polyIdx,
    pointIdx,
    originalPolygon: { ...poly, points: originalPoints },
    moved: false,
    startPoint: startPoint ? { x: startPoint.x, y: startPoint.y } : null,
    currentPoint: startPoint ? { x: startPoint.x, y: startPoint.y } : null,
  };
  e.preventDefault();
  e.stopPropagation();
};

const onWindowPointerMove = (e) => {
  if (activePointerId === null) return;
  if (e.pointerId !== activePointerId) return;
  const norm = clientToNorm(e.clientX, e.clientY);
  cursorNorm.value = norm;
  if (freehandActive && freehandPolygon.value) {
    if (draftMode.value === 'erase') {
      const pts = freehandPolygon.value.points || [];
      const last = pts.length ? pts[pts.length - 1] : null;
      if (!last || distPx(last, norm) >= 1.5) {
        freehandPolygon.value = { ...freehandPolygon.value, points: [...pts, norm] };
      }
      e.preventDefault();
      return;
    }
    if (draftMode.value === 'smart') {
      const a = (freehandPolygon.value.points || [])[0] || norm;
      freehandPolygon.value = {
        ...freehandPolygon.value,
        points: [a, norm],
      };
      e.preventDefault();
      return;
    }
    const pts = freehandPolygon.value.points || [];
    const last = pts.length ? pts[pts.length - 1] : null;
    if (!last || distPx(last, norm) >= 1.5) {
      freehandPolygon.value = {
        ...freehandPolygon.value,
        points: [...pts, norm],
      };
    }
    e.preventDefault();
    return;
  }
  if (dragPoint) {
    const poly = dragPoint.originalPolygon;
    if (!poly) return;
    dragPoint.currentPoint = { x: norm.x, y: norm.y };
    dragPoint.moved = true;
    const nextPoints = previewDraggedPoint(poly.points || [], dragPoint.pointIdx, norm);
    const next = polygons.value.map((p, idx) => (
      idx === dragPoint.polyIdx ? { ...p, points: nextPoints, source: 'repair-preview' } : p
    ));
    polygons.value = next;
  }
};

const onWindowPointerUp = (e) => {
  if (activePointerId === null) return;
  if (e.pointerId !== activePointerId) return;
  activePointerId = null;
  const drag = dragPoint;
  dragPoint = null;
  if (freehandActive) {
    if (draftMode.value === 'erase') {
      commitEraseStroke().catch(() => {});
    } else {
      commitSmartSelection().catch(() => {});
    }
    return;
  }
  if (drag) {
    commitPointDrag(drag).catch(() => {});
  }
};

const toggleSmartMode = () => {
  smartSelectMode.value = !smartSelectMode.value;
  eraserMode.value = false;
  cancelFreehand();
};

const toggleEraserMode = () => {
  eraserMode.value = !eraserMode.value;
  if (eraserMode.value) smartSelectMode.value = false;
  cancelFreehand();
};

const openGuideModal = () => {
  showGuideModal.value = true;
};

const closeGuideModal = () => {
  showGuideModal.value = false;
  try {
    window.localStorage.setItem(GUIDE_STORAGE_KEY, '1');
  } catch (_e) {
    // ignore storage failures
  }
};

const updateSelectedPolygonClass = (idx) => {
  currentClass.value = idx;
  if (selectedPolyIdx.value >= 0 && polygons.value[selectedPolyIdx.value]) {
    const next = polygons.value.map((p, i) => (i === selectedPolyIdx.value ? { ...p, class: idx } : p));
    polygons.value = next;
    hasChanges.value = true;
  }
};

const removePolygon = (idx) => {
  polygons.value = polygons.value.filter((_p, i) => i !== idx);
  selectedPolyIdx.value = -1;
  hasChanges.value = true;
};

const fetchAnnotations = async () => {
  const token = ++activeLoadToken;
  loading.value = true;
  polygons.value = [];
  freehandPolygon.value = null;
  freehandActive = false;
  draftMode.value = null;
  smartSelectMode.value = false;
  eraserMode.value = false;
  hasChanges.value = false;
  selectedPolyIdx.value = -1;
  try {
    const res = await api.getAnnotation({
      project_path: store.currentProject.path,
      dataset_name: props.datasetName,
      split: props.split,
      image_path: props.image.path
    });
    if (token !== activeLoadToken) return;
    const w = Number(res.width || 0);
    const h = Number(res.height || 0);
    if (w > 0 && h > 0) {
      imgWidth.value = w;
      imgHeight.value = h;
    }
    const toNormPoint = (pt) => {
      const x = Number(pt.x);
      const y = Number(pt.y);
      if (w > 0 && h > 0 && (x > 1 || y > 1)) {
        return { x: x / w, y: y / h };
      }
      return { x, y };
    };
    const toNormPolygon = (p) => ({
      class: Number(p.class) || 0,
      points: (p.points || []).map(toNormPoint).filter((pt) => Number.isFinite(pt.x) && Number.isFinite(pt.y)),
      is_auto: !!p.is_auto,
      source: 'loaded',
    });
    const manual = (res.manual_annotation?.polygons || []).map((p) => ({ ...toNormPolygon(p), is_auto: false }));
    const auto = (res.auto_annotation?.polygons || []).map((p) => ({ ...toNormPolygon(p), is_auto: true }));
    polygons.value = [...manual, ...auto].filter((p) => (p.points || []).length >= 3);
  } catch (err) {
    console.error(err);
  } finally {
    if (token !== activeLoadToken) return;
    loading.value = false;
  }
};

const previewGuideImage = (item) => {
  guideImagePreview.value = item;
};

const closeGuideImagePreview = () => {
  guideImagePreview.value = null;
};

const save = async () => {
  await asyncAction.run(SAVE_ACTION_KEY, async () => {
    const payloadPolygons = polygons.value
      .filter((p) => !p.is_auto)
      .map((p) => ({ class: p.class, points: normalizeForSave(p) }))
      .filter((p) => (p.points || []).length >= 3)
      .map((p) => ({
        class: p.class,
        points: (p.points || []).map((pt) => ({ x: pt.x, y: pt.y })),
      }));
    await apiCall(api.saveAnnotation({
      project_path: store.currentProject.path,
      dataset_name: props.datasetName,
      split: props.split,
      image_path: props.image.path,
      annotation: {
        polygons: payloadPolygons,
      },
    }), {
      errorMsg: '保存失败',
      onSuccess: () => {
        hasChanges.value = false;
        fetchAnnotations();
        emit('update', props.image);
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
  const el = e.target;
  const tag = el?.tagName?.toLowerCase?.();
  if (tag === 'input' || tag === 'textarea' || tag === 'select' || el?.isContentEditable) return;
  if (e.ctrlKey || e.metaKey || e.altKey) return;

  if (e.key === 'Escape') {
    if (guideImagePreview.value) {
      closeGuideImagePreview();
      return;
    }
    if (showGuideModal.value) {
      closeGuideModal();
      return;
    }
    if (freehandPolygon.value) {
      cancelFreehand();
      return;
    }
    emit('close');
  } else if (e.key === 'ArrowLeft') {
    e.preventDefault();
    emit('prev');
  } else if (e.key === 'ArrowRight') {
    e.preventDefault();
    emit('next');
  } else if (e.key === 'Delete' || e.key === 'Backspace') {
    if (selectedPolyIdx.value >= 0) {
      removePolygon(selectedPolyIdx.value);
    }
  } else if (e.key === 'Enter') {
    if (freehandPolygon.value && draftMode.value === 'manual' && (freehandPolygon.value.points || []).length >= 3) {
      e.preventDefault();
      commitManualPolygon();
    }
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
  if (imgRef.value && imgRef.value.complete) {
    onImageLoad();
  }
  try {
    if (!window.localStorage.getItem(GUIDE_STORAGE_KEY)) {
      showGuideModal.value = true;
    }
  } catch (_e) {
    showGuideModal.value = true;
  }
  window.addEventListener('keydown', handleKeydown);
  window.addEventListener('pointermove', onWindowPointerMove, { passive: false });
  window.addEventListener('pointerup', onWindowPointerUp, { passive: true });
});

onUnmounted(() => {
  if (resizeObserver) resizeObserver.disconnect();
  window.removeEventListener('keydown', handleKeydown);
  window.removeEventListener('pointermove', onWindowPointerMove);
  window.removeEventListener('pointerup', onWindowPointerUp);
});
</script>

<style scoped>
.vt-cursor-eraser {
  cursor: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='20' height='20' viewBox='0 0 20 20'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cpath d='M12.8 2.3l4.9 4.9a1.5 1.5 0 0 1 0 2.1l-7.8 7.8a2 2 0 0 1-1.4.6H3.8a1 1 0 0 1-.7-1.7l7.6-7.6 2.1-2.1z' fill='%23fca5a5' stroke='%23b91c1c' stroke-width='1.2'/%3E%3Cpath d='M9.7 5.4l4.9 4.9' stroke='%23ffffff' stroke-width='1.2' stroke-linecap='round'/%3E%3C/g%3E%3C/svg%3E") 4 16, auto;
}
</style>
