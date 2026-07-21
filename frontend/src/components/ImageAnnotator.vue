<template>
  <div class="vt-workspace-backdrop" @click.self="$emit('close')">
    <div class="vt-workspace-panel vt-workspace-panel--row vt-workspace-panel--xl">
      <!-- Canvas Area -->
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
          
          <!-- SVG Overlay for drawing -->
          <svg
            class="absolute inset-0 w-full h-full"
            :class="interactionMode === 'draw' ? 'cursor-crosshair' : 'cursor-default'"
            :viewBox="`0 0 ${imgWidth} ${imgHeight}`"
            preserveAspectRatio="none"
            @pointerdown="onPointerDownBg"
          >
            <!-- Existing Boxes -->
            <g v-for="(box, idx) in displayBoxes" :key="idx">
              <!-- Box Rect -->
              <rect
                :x="box.x1 * imgWidth"
                :y="box.y1 * imgHeight"
                :width="(box.x2 - box.x1) * imgWidth"
                :height="(box.y2 - box.y1) * imgHeight"
                :stroke="getColor(box.class)"
                :stroke-width="selectedBoxIdx === idx ? 3 / scale : 2 / scale"
                :stroke-opacity="box.is_auto ? 0.55 : 0.9"
                :stroke-dasharray="box.is_auto ? '4' : '0'"
                fill="transparent"
                :class="selectedBoxIdx === idx ? 'opacity-100' : 'opacity-80 hover:opacity-100'"
                style="cursor: move; touch-action: none;"
                @pointerdown="onBoxPointerDown(idx, $event)"
              />

              <!-- Resize Handles (only if selected) -->
              <g v-if="selectedBoxIdx === idx">
                <!-- TL -->
                <rect :x="box.x1 * imgWidth - 4 / scale" :y="box.y1 * imgHeight - 4 / scale" :width="8 / scale" :height="8 / scale" fill="white" stroke="black" :stroke-width="1 / scale" style="cursor: nw-resize; touch-action: none;" @pointerdown="onHandlePointerDown(idx, 'tl', $event)" />
                <!-- TR -->
                <rect :x="box.x2 * imgWidth - 4 / scale" :y="box.y1 * imgHeight - 4 / scale" :width="8 / scale" :height="8 / scale" fill="white" stroke="black" :stroke-width="1 / scale" style="cursor: ne-resize; touch-action: none;" @pointerdown="onHandlePointerDown(idx, 'tr', $event)" />
                <!-- BL -->
                <rect :x="box.x1 * imgWidth - 4 / scale" :y="box.y2 * imgHeight - 4 / scale" :width="8 / scale" :height="8 / scale" fill="white" stroke="black" :stroke-width="1 / scale" style="cursor: sw-resize; touch-action: none;" @pointerdown="onHandlePointerDown(idx, 'bl', $event)" />
                <!-- BR -->
                <rect :x="box.x2 * imgWidth - 4 / scale" :y="box.y2 * imgHeight - 4 / scale" :width="8 / scale" :height="8 / scale" fill="white" stroke="black" :stroke-width="1 / scale" style="cursor: se-resize; touch-action: none;" @pointerdown="onHandlePointerDown(idx, 'br', $event)" />
              </g>

              <!-- Label -->
              <text
                :x="box.x1 * imgWidth"
                :y="Math.max(12 / scale, box.y1 * imgHeight - 5 / scale)"
                :fill="getColor(box.class)"
                :font-size="12 / scale"
                font-weight="bold"
                :opacity="box.is_auto ? 0.8 : 1"
                style="text-shadow: 1px 1px 1px black; cursor: move; touch-action: none;"
                @pointerdown="onBoxPointerDown(idx, $event)"
              >
                {{ getClassName(box.class) }} {{ box.is_auto ? '(Auto)' : '' }}
              </text>
            </g>

            <g v-for="(box, idx) in suspectBoxes" :key="`suspect-${idx}`">
              <rect
                :x="box.x1 * imgWidth"
                :y="box.y1 * imgHeight"
                :width="(box.x2 - box.x1) * imgWidth"
                :height="(box.y2 - box.y1) * imgHeight"
                fill="rgba(239, 68, 68, 0.15)"
                stroke="#ef4444"
                :stroke-width="2 / scale"
                stroke-dasharray="6"
                pointer-events="none"
              />
              <text
                :x="box.x1 * imgWidth"
                :y="Math.max(14 / scale, box.y1 * imgHeight - 6 / scale)"
                fill="#ef4444"
                :font-size="12 / scale"
                font-weight="bold"
                style="text-shadow: 1px 1px 1px black; pointer-events: none;"
              >
                疑似误标 person
              </text>
            </g>

            <!-- Drawing Box (during create) -->
            <rect
              v-if="drawingBox"
              :x="drawingBox.x1 * imgWidth"
              :y="drawingBox.y1 * imgHeight"
              :width="(drawingBox.x2 - drawingBox.x1) * imgWidth"
              :height="(drawingBox.y2 - drawingBox.y1) * imgHeight"
              :stroke="getColor(currentClass)"
              :stroke-width="2 / scale"
              stroke-dasharray="4"
              fill="transparent"
              pointer-events="none"
            />
          </svg>
        </div>
      </div>

      <!-- Sidebar -->
      <div class="w-80 bg-white border-l border-gray-200 flex flex-col">
        <div class="p-4 border-b border-gray-200">
          <h3 class="font-bold text-gray-800 mb-1">图片标注</h3>
          <UiTooltip side="bottom" align="start" content-class="max-w-[24rem] break-all text-left">
            <template #trigger>
              <p class="text-xs text-gray-500 truncate">{{ getPathDisplayName(image.path) }}</p>
            </template>
            {{ image.path }}
          </UiTooltip>
          <div v-if="hasReviewIssue" class="mt-2 border border-red-200 bg-red-50 px-2 py-1 text-xs text-red-700">
            Person复核提示：检测到 {{ suspectBoxes.length }} 个疑似误标框，已在画面中红框标出
          </div>
        </div>

        <!-- Class Selection -->
        <div class="flex-1 overflow-y-auto p-4">
          <h4 class="text-xs font-bold text-gray-500 uppercase mb-3">选择类别</h4>
          <div class="space-y-2">
            <div 
              v-for="(name, idx) in classList" 
              :key="idx"
              class="vt-selectable flex items-center gap-2 p-2 cursor-pointer"
              :class="currentClass === idx ? 'vt-selectable--selected' : 'border-transparent'"
              @click="updateSelectedBoxClass(idx)"
            >
              <div class="w-4 h-4 rounded-full" :style="{ backgroundColor: getColor(idx) }"></div>
              <span class="text-sm font-medium">{{ name }}</span>
              <span class="text-xs text-gray-400 ml-auto">id: {{ idx }}</span>
            </div>
          </div>
        </div>

        <!-- Actions -->
        <div class="p-4 border-t border-gray-200 bg-gray-50 space-y-3">
          <div class="flex justify-between items-center text-sm text-gray-600">
             <span>标注数量: {{ boxes.length }}</span>
             <span v-if="hasChanges" class="vt-tag vt-tag-warn">未保存</span>
          </div>
          
          <button 
            v-if="selectedBoxIdx >= 0"
            @click="removeBox(selectedBoxIdx)"
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
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch, shallowRef } from 'vue';
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
  split: { type: String, default: 'train' }
});

const emit = defineEmits(['close', 'prev', 'next', 'update']);

const store = useMainStore();
const apiCall = useApiCall();
const asyncAction = useAsyncAction();
const containerRef = ref(null);
const imgRef = ref(null);
const boxes = ref([]);
const loading = ref(true);
const currentClass = ref(0);
const hasChanges = ref(false);
const SAVE_ACTION_KEY = 'image-annotator:save';
const isActionPending = (key) => asyncAction.isPending(key);
let activeLoadToken = 0;

// 用 shallowRef 存"拖动中的临时数据"——避免深度响应式追踪
// 拖动中频繁更新 4 个数字会触发 SVG 整树重新计算，
// shallowRef 只追踪引用变化（每次整个对象替换），性能更好
const drawingBox = shallowRef(null); // { x1, y1, x2, y2 } in normalized 0-1
const ghostBox = shallowRef(null);   // 拖动/缩放时正在编辑的框

const interactionMode = ref('none'); // none, draw, move, resize
const selectedBoxIdx = ref(-1);
const resizeHandle = ref(null); // tl, tr, bl, br
const startPosNorm = shallowRef({ x: 0, y: 0 }); // normalized 0-1
const dragStartBox = shallowRef(null); // Snapshot of box before drag

const imgWidth = ref(1);
const imgHeight = ref(1);
const scale = ref(1);
const containerWidth = ref(0);
const containerHeight = ref(0);
let resizeObserver = null;

// Colors for classes
const colors = [
  '#ef4444', '#f97316', '#f59e0b', '#84cc16', '#22c55e',
  '#06b6d4', '#3b82f6', '#6366f1', '#a855f7', '#ec4899'
];

const getColor = (idx) => colors[idx % colors.length];
const getClassName = (idx) => props.classList[idx] || `Class ${idx}`;
const suspectBoxes = computed(() => {
  const arr = props.image?.review?.suspect_boxes;
  if (!Array.isArray(arr)) return [];
  return arr
    .map((b) => {
      const x1 = Number(b?.x1);
      const y1 = Number(b?.y1);
      const x2 = Number(b?.x2);
      const y2 = Number(b?.y2);
      return { x1, y1, x2, y2 };
    })
    .filter((b) => Number.isFinite(b.x1) && Number.isFinite(b.y1) && Number.isFinite(b.x2) && Number.isFinite(b.y2));
});
const hasReviewIssue = computed(() => suspectBoxes.value.length > 0);

// 计算当前显示的 boxes：拖动中用 ghost 覆盖原值
const displayBoxes = computed(() => {
  const base = boxes.value;
  if (ghostBox.value && selectedBoxIdx.value >= 0) {
    return base.map((b, i) => (i === selectedBoxIdx.value ? { ...b, ...ghostBox.value } : b));
  }
  return base;
});

// Image layout logic
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

const updateContainerSize = () => {
  if (containerRef.value) {
    containerWidth.value = containerRef.value.clientWidth;
    containerHeight.value = containerRef.value.clientHeight;
  }
};

onMounted(() => {
  updateContainerSize();
  resizeObserver = new ResizeObserver(updateContainerSize);
  if (containerRef.value) {
    resizeObserver.observe(containerRef.value);
  }
  if (imgRef.value && imgRef.value.complete) {
    onImageLoad();
  }
});

onUnmounted(() => {
  if (resizeObserver) resizeObserver.disconnect();
});

const onImageLoad = () => {
  if (imgRef.value) {
    imgWidth.value = imgRef.value.naturalWidth;
    imgHeight.value = imgRef.value.naturalHeight;
  }
};

// ────────────────────────────────────────────────────────────
// 交互核心：PointerEvent + window-level + requestAnimationFrame
// ────────────────────────────────────────────────────────────

// 屏幕坐标 → 图像 normalized 坐标 (0-1)
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

let pendingPointer = null;   // 最新一次 pointer 坐标
let rafScheduled = false;    // 是否已预约下一帧
let activePointerId = null;  // 当前抓取此 SVG 的 pointer

const scheduleDrag = () => {
  if (rafScheduled) return;
  rafScheduled = true;
  requestAnimationFrame(() => {
    rafScheduled = false;
    if (!pendingPointer) return;
    applyDrag(pendingPointer);
  });
};

const applyDrag = (p) => {
  if (interactionMode.value === 'draw') {
    drawingBox.value = {
      x1: Math.min(p.startX, p.x),
      y1: Math.min(p.startY, p.y),
      x2: Math.max(p.startX, p.x),
      y2: Math.max(p.startY, p.y),
    };
  } else if (interactionMode.value === 'move' && dragStartBox.value) {
    const dx = p.x - p.startX;
    const dy = p.y - p.startY;
    const b = dragStartBox.value;
    const w = b.x2 - b.x1;
    const h = b.y2 - b.y1;
    let nx1 = Math.max(0, Math.min(1 - w, b.x1 + dx));
    let ny1 = Math.max(0, Math.min(1 - h, b.y1 + dy));
    // 贴边：超出右/下边就吸住
    if (b.x1 + dx + w > 1) { nx1 = 1 - w; }
    if (b.y1 + dy + h > 1) { ny1 = 1 - h; }
    ghostBox.value = { x1: nx1, y1: ny1, x2: nx1 + w, y2: ny1 + h };
  } else if (interactionMode.value === 'resize' && dragStartBox.value) {
    const b = dragStartBox.value;
    let { x1, y1, x2, y2 } = b;
    const h = resizeHandle.value;
    if (h === 'tl') { x1 = Math.min(p.x, x2 - 0.005); y1 = Math.min(p.y, y2 - 0.005); }
    else if (h === 'tr') { x2 = Math.max(p.x, x1 + 0.005); y1 = Math.min(p.y, y2 - 0.005); }
    else if (h === 'bl') { x1 = Math.min(p.x, x2 - 0.005); y2 = Math.max(p.y, y1 + 0.005); }
    else if (h === 'br') { x2 = Math.max(p.x, x1 + 0.005); y2 = Math.max(p.y, y1 + 0.005); }
    ghostBox.value = { x1, y1, x2, y2 };
  }
};

const onPointerDownBg = (e) => {
  if (e.button !== undefined && e.button !== 0) return;
  // PointerEvent 抓取，确保鼠标移出元素也能继续收到 move/up
  e.currentTarget.setPointerCapture(e.pointerId);
  activePointerId = e.pointerId;

  selectedBoxIdx.value = -1;
  interactionMode.value = 'draw';
  const norm = clientToNorm(e.clientX, e.clientY);
  startPosNorm.value = norm;
  drawingBox.value = { x1: norm.x, y1: norm.y, x2: norm.x, y2: norm.y };
  pendingPointer = { ...norm, startX: norm.x, startY: norm.y };
  // 阻止触屏滚动 / 浏览器选词
  e.preventDefault();
};

const onBoxPointerDown = (idx, e) => {
  if (e.button !== undefined && e.button !== 0) return;
  e.currentTarget.setPointerCapture(e.pointerId);
  activePointerId = e.pointerId;
  selectedBoxIdx.value = idx;
  const norm = clientToNorm(e.clientX, e.clientY);
  startPosNorm.value = norm;
  dragStartBox.value = { ...boxes.value[idx] };
  ghostBox.value = { ...boxes.value[idx] };
  interactionMode.value = 'move';
  currentClass.value = boxes.value[idx].class;
  pendingPointer = { ...norm, startX: norm.x, startY: norm.y };
  e.preventDefault();
  e.stopPropagation();
};

const onHandlePointerDown = (idx, handle, e) => {
  if (e.button !== undefined && e.button !== 0) return;
  e.currentTarget.setPointerCapture(e.pointerId);
  activePointerId = e.pointerId;
  selectedBoxIdx.value = idx;
  resizeHandle.value = handle;
  const norm = clientToNorm(e.clientX, e.clientY);
  startPosNorm.value = norm;
  dragStartBox.value = { ...boxes.value[idx] };
  ghostBox.value = { ...boxes.value[idx] };
  interactionMode.value = 'resize';
  pendingPointer = { ...norm, startX: norm.x, startY: norm.y };
  e.preventDefault();
  e.stopPropagation();
};

// window-level 监听，鼠标移出 SVG 也能继续拖
const onWindowPointerMove = (e) => {
  if (interactionMode.value === 'none') return;
  if (activePointerId !== null && e.pointerId !== activePointerId) return;
  const norm = clientToNorm(e.clientX, e.clientY);
  if (interactionMode.value === 'resize') {
    pendingPointer = { ...norm, startX: norm.x, startY: norm.y };
  } else {
    pendingPointer = { ...norm, startX: startPosNorm.value.x, startY: startPosNorm.value.y };
  }
  scheduleDrag();
};

const onWindowPointerUp = (e) => {
  if (interactionMode.value === 'none') return;
  if (activePointerId !== null && e.pointerId !== activePointerId) return;
  // 同步应用最后一帧
  if (pendingPointer) applyDrag(pendingPointer);
  finalizeDrag();
  activePointerId = null;
};

const finalizeDrag = () => {
  if (interactionMode.value === 'draw' && drawingBox.value) {
    const b = drawingBox.value;
    const w = (b.x2 - b.x1) * imgWidth.value;
    const h = (b.y2 - b.y1) * imgHeight.value;
    if (w > 5 && h > 5) {
      const idx = boxes.value.length;
      boxes.value.push({
        class: currentClass.value,
        x1: b.x1, y1: b.y1, x2: b.x2, y2: b.y2,
        is_auto: false,
      });
      hasChanges.value = true;
      selectedBoxIdx.value = idx;
    }
    drawingBox.value = null;
  } else if ((interactionMode.value === 'move' || interactionMode.value === 'resize') && ghostBox.value) {
    // 把 ghost 应用到真正的 box
    if (selectedBoxIdx.value >= 0 && boxes.value[selectedBoxIdx.value]) {
      boxes.value[selectedBoxIdx.value] = {
        ...boxes.value[selectedBoxIdx.value],
        ...ghostBox.value,
      };
      hasChanges.value = true;
    }
    ghostBox.value = null;
    dragStartBox.value = null;
    resizeHandle.value = null;
  }
  interactionMode.value = 'none';
  pendingPointer = null;
};

const fetchAnnotations = async () => {
  const token = ++activeLoadToken;
  loading.value = true;
  boxes.value = [];
  hasChanges.value = false;
  selectedBoxIdx.value = -1;
  drawingBox.value = null;
  ghostBox.value = null;
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
      const toNorm = (b) => {
        const x1 = Number(b.x1);
        const y1 = Number(b.y1);
        const x2 = Number(b.x2);
        const y2 = Number(b.y2);
        if (w > 0 && h > 0 && (x2 > 1 || y2 > 1 || x1 > 1 || y1 > 1)) {
          return { class: Number(b.class) || 0, x1: x1 / w, y1: y1 / h, x2: x2 / w, y2: y2 / h };
        }
        return { class: Number(b.class) || 0, x1, y1, x2, y2 };
      };
      const manual = (res.manual_annotation?.boxes || []).map((b) => ({ ...toNorm(b), is_auto: false }));
      const auto = (res.auto_annotation?.boxes || []).map((b) => ({ ...toNorm(b), is_auto: true }));
      boxes.value = [...manual, ...auto].filter((b) =>
        Number.isFinite(b.x1) && Number.isFinite(b.y1) && Number.isFinite(b.x2) && Number.isFinite(b.y2)
      );
    }
  } catch (err) {
    console.error(err);
  } finally {
    if (token !== activeLoadToken) return;
    loading.value = false;
  }
};

const save = async () => {
  const w = imgWidth.value || (imgRef.value ? imgRef.value.naturalWidth : 0);
  const h = imgHeight.value || (imgRef.value ? imgRef.value.naturalHeight : 0);
  await asyncAction.run(SAVE_ACTION_KEY, async () => {
    await apiCall(api.saveAnnotation({
      project_path: store.currentProject.path,
      dataset_name: props.datasetName,
      split: props.split,
      image_path: props.image.path,
      annotation: {
        boxes: boxes.value.map((b) => ({
          class: b.class,
          x1: b.x1 * w,
          y1: b.y1 * h,
          x2: b.x2 * w,
          y2: b.y2 * h,
        })),
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

const removeBox = (idx) => {
  boxes.value.splice(idx, 1);
  selectedBoxIdx.value = -1;
  hasChanges.value = true;
};

const updateSelectedBoxClass = (idx) => {
  currentClass.value = idx;
  if (selectedBoxIdx.value >= 0) {
    boxes.value[selectedBoxIdx.value].class = idx;
    hasChanges.value = true;
  }
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
  } else if (e.key === 'Delete' || e.key === 'Backspace') {
    if (selectedBoxIdx.value >= 0) {
      removeBox(selectedBoxIdx.value);
    }
  }
};

watch(() => props.image, () => {
  fetchAnnotations();
}, { immediate: true });

onMounted(() => {
  window.addEventListener('keydown', handleKeydown);
  // window 级监听：即使鼠标飞出 SVG 也能继续
  window.addEventListener('pointermove', onWindowPointerMove, { passive: false });
  window.addEventListener('pointerup', onWindowPointerUp, { passive: true });
  window.addEventListener('pointercancel', onWindowPointerUp, { passive: true });
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown);
  window.removeEventListener('pointermove', onWindowPointerMove);
  window.removeEventListener('pointerup', onWindowPointerUp);
  window.removeEventListener('pointercancel', onWindowPointerUp);
});
</script>
