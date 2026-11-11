<template>
  <div v-if="report" class="text-xs">
    <div v-if="report.ok" class="flex flex-wrap gap-x-3 gap-y-1 text-slate-700">
      <span class="inline-flex items-center gap-1 text-emerald-700">
        <span class="vt-status-dot vt-status-dot--success h-1.5 w-1.5"></span>可以开始训练
      </span>
      <span v-if="gpuLabel">{{ gpuLabel }}</span>
      <span class="font-mono text-gray-500">python {{ report.python || '-' }}</span>
      <span class="font-mono text-gray-500">torch {{ report.torch || '-' }}</span>
      <span class="font-mono text-gray-500">ultralytics {{ report.ultralytics || '-' }}</span>
      <span class="font-mono text-gray-500">剩余空间 {{ freeLabel }}</span>
    </div>
    <div v-else class="border border-rose-200 bg-rose-50 p-2 text-rose-700">
      <div class="font-medium mb-1">预检未通过，这台服务器现在不能开始训练</div>
      <ul class="space-y-1">
        <li v-for="(problem, index) in report.problems || []" :key="index" class="whitespace-pre-wrap break-all">
          · {{ problem }}
        </li>
      </ul>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue';
import { formatBytes } from '../utils';

const props = defineProps({
  report: { type: Object, default: null },
});

const gpuLabel = computed(() => {
  const names = props.report?.gpu_names || [];
  if (!names.length) return `GPU ${props.report?.device || '-'}`;
  return names.join(' / ');
});

const freeLabel = computed(() => formatBytes(props.report?.free_bytes));
</script>
