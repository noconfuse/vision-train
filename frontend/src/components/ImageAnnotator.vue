<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4" @click.self="$emit('close')">
    <div class="bg-white rounded-xl overflow-hidden shadow-2xl w-full max-w-6xl flex h-[85vh]">
      <!-- Canvas Area -->
      <div class="flex-1 bg-gray-900 relative flex items-center justify-center overflow-hidden select-none" ref="containerRef">
        <div v-if="loading" class="absolute inset-0 flex items-center justify-center text-white">
          Loading...
        </div>
        
        <div class="relative" :style="imageStyle">
          <img 
            ref="imgRef" 
            :src="image.url" 
            class="max-w-none block" 
            @load="onImageLoad" 
            draggable="false"
          />
          
          <!-- SVG Overlay for drawing -->
          <svg 
            class="absolute inset-0 w-full h-full cursor-crosshair"
            @mousedown="onMouseDown"
            @mousemove="onMouseMove"
            @mouseup="onMouseUp"
            @mouseleave="onMouseUp"
          >
            <!-- Existing Boxes -->
            <g v-for="(box, idx) in boxes" :key="idx">
              <!-- Box Rect -->
              <rect 
                :x="box.x1 * imgWidth" 
                :y="box.y1 * imgHeight" 
                :width="(box.x2 - box.x1) * imgWidth" 
                :height="(box.y2 - box.y1) * imgHeight" 
                :stroke="getColor(box.class)" 
                stroke-width="2" 
                :stroke-opacity="box.is_auto ? 0.55 : 0.9"
                :stroke-dasharray="box.is_auto ? '4' : '0'"
                fill="transparent"
                class="transition-all"
                :class="selectedBoxIdx === idx ? 'stroke-[3px] opacity-100' : 'opacity-80 hover:opacity-100'"
                @mousedown.stop="startMove(idx, $event)"
              />
              
              <!-- Resize Handles (only if selected) -->
              <g v-if="selectedBoxIdx === idx">
                <!-- TL -->
                <rect :x="box.x1 * imgWidth - 4" :y="box.y1 * imgHeight - 4" width="8" height="8" fill="white" stroke="black" class="cursor-nw-resize" @mousedown.stop="startResize(idx, 'tl', $event)" />
                <!-- TR -->
                <rect :x="box.x2 * imgWidth - 4" :y="box.y1 * imgHeight - 4" width="8" height="8" fill="white" stroke="black" class="cursor-ne-resize" @mousedown.stop="startResize(idx, 'tr', $event)" />
                <!-- BL -->
                <rect :x="box.x1 * imgWidth - 4" :y="box.y2 * imgHeight - 4" width="8" height="8" fill="white" stroke="black" class="cursor-sw-resize" @mousedown.stop="startResize(idx, 'bl', $event)" />
                <!-- BR -->
                <rect :x="box.x2 * imgWidth - 4" :y="box.y2 * imgHeight - 4" width="8" height="8" fill="white" stroke="black" class="cursor-se-resize" @mousedown.stop="startResize(idx, 'br', $event)" />
              </g>

              <!-- Label -->
              <text 
                :x="box.x1 * imgWidth" 
                :y="Math.max(12, box.y1 * imgHeight - 5)" 
                :fill="getColor(box.class)" 
                font-size="12" 
                font-weight="bold"
                :opacity="box.is_auto ? 0.8 : 1"
                style="text-shadow: 1px 1px 1px black; pointer-events: none;"
              >
                {{ getClassName(box.class) }} {{ box.is_auto ? '(Auto)' : '' }}
              </text>
            </g>

            <!-- Drawing Box -->
            <rect 
              v-if="interactionMode === 'draw'"
              :x="Math.min(startPos.x, currentPos.x)" 
              :y="Math.min(startPos.y, currentPos.y)" 
              :width="Math.abs(currentPos.x - startPos.x)" 
              :height="Math.abs(currentPos.y - startPos.y)" 
              :stroke="getColor(currentClass)" 
              stroke-width="2" 
              stroke-dasharray="4"
              fill="transparent"
            />
          </svg>
        </div>
      </div>

      <!-- Sidebar -->
      <div class="w-80 bg-white border-l border-gray-200 flex flex-col">
        <div class="p-4 border-b border-gray-200">
          <h3 class="font-bold text-gray-800 mb-1">图片标注</h3>
          <p class="text-xs text-gray-500 truncate" :title="image.path">{{ image.path.split('/').pop() }}</p>
        </div>

        <!-- Class Selection -->
        <div class="flex-1 overflow-y-auto p-4">
          <h4 class="text-xs font-bold text-gray-500 uppercase mb-3">选择类别</h4>
          <div class="space-y-2">
            <div 
              v-for="(name, idx) in classList" 
              :key="idx"
              class="flex items-center gap-2 p-2 rounded cursor-pointer transition-colors border"
              :class="currentClass === idx ? 'bg-indigo-50 border-indigo-500' : 'hover:bg-gray-50 border-transparent'"
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
             <span v-if="hasChanges" class="text-amber-500 font-medium">未保存</span>
          </div>
          
          <button 
            v-if="selectedBoxIdx >= 0"
            @click="removeBox(selectedBoxIdx)"
            class="w-full bg-red-100 hover:bg-red-200 text-red-600 py-2 rounded-lg font-medium shadow-sm transition-colors flex justify-center items-center gap-2 mb-2"
          >
            删除选中标注 (Delete)
          </button>

          <button 
            @click="save" 
            class="w-full bg-blue-600 hover:bg-blue-700 text-white py-2 rounded-lg font-medium shadow-sm transition-colors flex justify-center items-center gap-2"
            :disabled="saving"
          >
            <span v-if="saving" class="animate-spin h-4 w-4 border-2 border-white border-t-transparent rounded-full"></span>
            {{ saving ? '保存标注 (Ctrl+S)' : '保存标注 (Ctrl+S)' }}
          </button>
          
          <div class="flex gap-2">
            <button @click="$emit('prev')" class="flex-1 py-2 border border-gray-300 rounded-lg hover:bg-gray-100 text-sm">上一张</button>
            <button @click="$emit('next')" class="flex-1 py-2 border border-gray-300 rounded-lg hover:bg-gray-100 text-sm">下一张</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import api from '../api';
import { useMainStore } from '../stores/main';

const props = defineProps({
  image: { type: Object, required: true },
  classList: { type: Array, default: () => [] },
  datasetName: { type: String, required: true },
  split: { type: String, default: 'train' }
});

const emit = defineEmits(['close', 'prev', 'next', 'update']);

const store = useMainStore();
const containerRef = ref(null);
const imgRef = ref(null);
const boxes = ref([]);
const loading = ref(true);
const saving = ref(false);
const currentClass = ref(0);
const hasChanges = ref(false);

const interactionMode = ref('none'); // none, draw, move, resize
const selectedBoxIdx = ref(-1);
const resizeHandle = ref(null); // tl, tr, bl, br
const startPos = ref({ x: 0, y: 0 });
const currentPos = ref({ x: 0, y: 0 });
const dragStartBox = ref(null); // Snapshot of box before drag

const imgWidth = ref(1);
const imgHeight = ref(1);
const scale = ref(1);

// Colors for classes
const colors = [
  '#ef4444', '#f97316', '#f59e0b', '#84cc16', '#22c55e', 
  '#06b6d4', '#3b82f6', '#6366f1', '#a855f7', '#ec4899'
];

const getColor = (idx) => colors[idx % colors.length];
const getClassName = (idx) => props.classList[idx] || `Class ${idx}`;

// Image layout logic
const imageStyle = computed(() => {
  if (!imgWidth.value || !imgHeight.value) return {};
  return {}; 
});

const onImageLoad = () => {
  if (imgRef.value) {
    imgWidth.value = imgRef.value.naturalWidth;
    imgHeight.value = imgRef.value.naturalHeight;
  }
};

const fetchAnnotations = async () => {
  loading.value = true;
  boxes.value = [];
  hasChanges.value = false;
  selectedBoxIdx.value = -1;
  try {
    const res = await api.getAnnotation({
      project_path: store.currentProject.path,
      dataset_name: props.datasetName,
      split: props.split,
      image_path: props.image.path
    });
    if (res.data.success) {
      const w = Number(res.data.width || 0);
      const h = Number(res.data.height || 0);
      if (w > 0 && h > 0) {
        imgWidth.value = w;
        imgHeight.value = h;
      }
      const toNorm = (b) => {
        const x1 = Number(b.x1);
        const y1 = Number(b.y1);
        const x2 = Number(b.x2);
        const y2 = Number(b.y2);
        if (w > 0 && h > 0 && (x2 > 1 || y2 > 1 || x1 > 1 || y1 > 1)) {
          return {
            class: Number(b.class) || 0,
            x1: x1 / w,
            y1: y1 / h,
            x2: x2 / w,
            y2: y2 / h
          };
        }
        return {
          class: Number(b.class) || 0,
          x1,
          y1,
          x2,
          y2
        };
      };
      const manual = (res.data.boxes || []).map((b) => ({ ...toNorm(b), is_auto: false }));
      const auto = (res.data.auto_boxes || []).map((b) => ({ ...toNorm(b), is_auto: true }));
      boxes.value = [...manual, ...auto].filter((b) => {
        return (
          Number.isFinite(b.x1) &&
          Number.isFinite(b.y1) &&
          Number.isFinite(b.x2) &&
          Number.isFinite(b.y2)
        );
      });
    }
  } catch (err) {
    console.error(err);
  } finally {
    loading.value = false;
  }
};

const save = async () => {
  saving.value = true;
  try {
    const w = imgWidth.value || (imgRef.value ? imgRef.value.naturalWidth : 0);
    const h = imgHeight.value || (imgRef.value ? imgRef.value.naturalHeight : 0);
    const res = await api.saveAnnotation({
      project_path: store.currentProject.path,
      dataset_name: props.datasetName,
      split: props.split,
      image_path: props.image.path,
      labels: boxes.value
        .filter(b => !b.is_auto)
        .map((b) => ({
          class: b.class,
          x1: b.x1 * w,
          y1: b.y1 * h,
          x2: b.x2 * w,
          y2: b.y2 * h
        }))
    });
    if (res.data.success) {
      hasChanges.value = false;
      // Refresh to get clean state (e.g. auto become manual)
      fetchAnnotations();
      emit('update', props.image); 
    }
  } catch (err) {
    alert('保存失败: ' + err.message);
  } finally {
    saving.value = false;
  }
};

// Interaction Logic
const getRelativePos = (e) => {
  const rect = imgRef.value.getBoundingClientRect();
  return {
    x: Math.max(0, Math.min(rect.width, e.clientX - rect.left)),
    y: Math.max(0, Math.min(rect.height, e.clientY - rect.top))
  };
};

const onMouseDown = (e) => {
  if (e.button !== 0) return;
  // If clicked on background (and not stopped by other handlers), start drawing
  // But wait, if we are in 'none' mode.
  // The event handlers on rects use .stop, so this only fires for bg.
  
  // Deselect if clicking bg
  selectedBoxIdx.value = -1;
  
  interactionMode.value = 'draw';
  const pos = getRelativePos(e);
  startPos.value = pos;
  currentPos.value = pos;
};

const startMove = (idx, e) => {
  if (e.button !== 0) return;
  selectedBoxIdx.value = idx;
  interactionMode.value = 'move';
  const pos = getRelativePos(e);
  startPos.value = pos;
  dragStartBox.value = { ...boxes.value[idx] };
  
  // Update current class to match selected box
  currentClass.value = boxes.value[idx].class;
};

const startResize = (idx, handle, e) => {
  if (e.button !== 0) return;
  selectedBoxIdx.value = idx;
  interactionMode.value = 'resize';
  resizeHandle.value = handle;
  const pos = getRelativePos(e);
  startPos.value = pos; // Not used much for resize but consistency
  dragStartBox.value = { ...boxes.value[idx] };
};

const onMouseMove = (e) => {
  const pos = getRelativePos(e);
  currentPos.value = pos;
  
  if (interactionMode.value === 'draw') {
    // Just visual update
  } else if (interactionMode.value === 'move') {
    if (selectedBoxIdx.value === -1 || !dragStartBox.value) return;
    
    const dx = (pos.x - startPos.value.x) / imgRef.value.offsetWidth;
    const dy = (pos.y - startPos.value.y) / imgRef.value.offsetHeight;
    
    const box = boxes.value[selectedBoxIdx.value];
    const newX1 = Math.max(0, Math.min(1, dragStartBox.value.x1 + dx));
    const newY1 = Math.max(0, Math.min(1, dragStartBox.value.y1 + dy));
    const w = dragStartBox.value.x2 - dragStartBox.value.x1;
    const h = dragStartBox.value.y2 - dragStartBox.value.y1;
    
    // Clamp to boundaries
    if (newX1 + w <= 1) {
      box.x1 = newX1;
      box.x2 = newX1 + w;
    }
    if (newY1 + h <= 1) {
      box.y1 = newY1;
      box.y2 = newY1 + h;
    }
    hasChanges.value = true;
    
  } else if (interactionMode.value === 'resize') {
    if (selectedBoxIdx.value === -1 || !dragStartBox.value) return;
    
    const box = boxes.value[selectedBoxIdx.value];
    const w = imgRef.value.offsetWidth;
    const h = imgRef.value.offsetHeight;
    const normX = pos.x / w;
    const normY = pos.y / h;
    
    // Based on handle, update coords
    // We update box in place
    if (resizeHandle.value === 'tl') {
      box.x1 = Math.min(normX, box.x2 - 0.01);
      box.y1 = Math.min(normY, box.y2 - 0.01);
    } else if (resizeHandle.value === 'tr') {
      box.x2 = Math.max(normX, box.x1 + 0.01);
      box.y1 = Math.min(normY, box.y2 - 0.01);
    } else if (resizeHandle.value === 'bl') {
      box.x1 = Math.min(normX, box.x2 - 0.01);
      box.y2 = Math.max(normY, box.y1 + 0.01);
    } else if (resizeHandle.value === 'br') {
      box.x2 = Math.max(normX, box.x1 + 0.01);
      box.y2 = Math.max(normY, box.y1 + 0.01);
    }
    hasChanges.value = true;
  }
};

const onMouseUp = () => {
  if (interactionMode.value === 'draw') {
    const rect = imgRef.value.getBoundingClientRect();
    const w = rect.width;
    const h = rect.height;
    
    const x1 = Math.min(startPos.value.x, currentPos.value.x) / w;
    const y1 = Math.min(startPos.value.y, currentPos.value.y) / h;
    const x2 = Math.max(startPos.value.x, currentPos.value.x) / w;
    const y2 = Math.max(startPos.value.y, currentPos.value.y) / h;
    
    if ((x2 - x1) > 0.01 && (y2 - y1) > 0.01) {
      boxes.value.push({
        class: currentClass.value,
        x1, y1, x2, y2,
        is_auto: false
      });
      hasChanges.value = true;
      // Select the new box
      selectedBoxIdx.value = boxes.value.length - 1;
    }
  }
  
  interactionMode.value = 'none';
  dragStartBox.value = null;
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
});

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown);
});
</script>
