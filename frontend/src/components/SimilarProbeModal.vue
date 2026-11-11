<template>
  <ModalShell
    title="找同类"
    size="md"
    body-class="p-5 space-y-4"
    @close="emit('close')"
  >
    <template #icon>
      <AppIcon name="search" class="h-4 w-4 text-slate-600" />
    </template>

    <p class="text-sm leading-relaxed text-gray-600">
      在 {{ datasetName }} · {{ split }} 找跟这个框外观接近的区域，命中写进「待复核」，人工标签不动。
    </p>

    <div class="flex items-center gap-2 text-xs text-gray-500">
      <span class="inline-block h-2.5 w-2.5 shrink-0" :style="{ backgroundColor: classColor }"></span>
      <span class="truncate">{{ sample.class_name }}</span>
      <span class="truncate font-mono">{{ getPathDisplayName(sample.image_path) }}</span>
    </div>

    <div>
      <label class="vt-field-label">相似下限</label>
      <input v-model.number="thresh" :disabled="probe.running" type="number" min="0" max="1" step="0.05" class="vt-input" />
      <p class="mt-1 text-xs text-gray-500">调低找得多，也杂。</p>
    </div>

    <div v-if="probe.running">
      <div class="flex items-center justify-between text-xs">
        <span>{{ probe.message }}</span>
        <span>{{ probe.progress }}%</span>
      </div>
      <div class="vt-meter mt-1">
        <div class="vt-meter__bar vt-meter__bar--info rounded-full transition-all duration-300" :style="{ width: `${probe.progress}%` }"></div>
      </div>
    </div>
    <p v-else-if="probe.done && !probe.error" class="text-sm leading-relaxed text-gray-600">
      候选 {{ probe.added }} 个，分在 {{ probe.pending }} 张图上。
    </p>
    <p v-if="probe.error" class="text-xs leading-relaxed text-red-600">{{ probe.error }}</p>

    <template #footer>
      <button class="vt-btn-secondary vt-btn-size-md" @click="emit('close')">取消</button>
      <button
        v-if="!probe.done"
        class="vt-btn-solid-primary vt-btn-size-md"
        :disabled="probe.running || thresh > 1 || thresh <= 0"
        @click="emit('start', thresh)"
      >
        {{ probe.running ? '探测中...' : '开始探测' }}
      </button>
      <button v-else class="vt-btn-solid-primary vt-btn-size-md" @click="emit('review')">去复核</button>
    </template>
  </ModalShell>
</template>

<script setup>
import { computed, ref } from 'vue';
import { getPathDisplayName } from '../utils';
import { getClassColor } from '../utils/classColors';
import AppIcon from './ui/AppIcon.vue';
import ModalShell from './ui/ModalShell.vue';

const props = defineProps({
  // 样本框：{ image_path, class_id, class_name, sample_box }，sample_box 是像素坐标，由标注弹窗交出
  sample: { type: Object, required: true },
  datasetName: { type: String, required: true },
  split: { type: String, required: true },
  // 探测状态归列表页管：关掉弹窗任务还在跑，重新打开要看得见进度和结果
  probe: { type: Object, required: true },
});

const emit = defineEmits(['close', 'start', 'review']);

const thresh = ref(props.probe.thresh);
const classColor = computed(() => getClassColor(props.sample.class_id));
</script>
