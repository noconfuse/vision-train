<template>
  <header class="vt-header">
    <!-- 左：返回 + 面包屑 -->
    <div class="flex items-center gap-3 min-w-0 flex-1">
      <button v-if="backHref" @click="onBack" class="vt-btn-link">
        <AppIcon name="back" class="h-3.5 w-3.5" />
        <span>返回</span>
      </button>
      <span v-if="backHref" class="text-gray-300">/</span>
      <span v-for="(crumb, i) in normalizedCrumbs" :key="i" class="flex items-center gap-3 min-w-0">
        <button
          v-if="crumb.to"
          type="button"
          class="vt-header-title vt-hover-text-accent truncate text-left"
          @click="goToCrumb(crumb)"
        >
          {{ crumb.label }}
        </button>
        <span v-else class="vt-header-title truncate">
          {{ crumb.label }}
        </span>
        <span v-if="i < normalizedCrumbs.length - 1" class="text-gray-300">/</span>
      </span>
      <slot name="meta" />
    </div>

    <!-- 中：tabs（可选） -->
    <nav v-if="$slots.tabs" class="flex items-center gap-1 text-xs">
      <slot name="tabs" />
    </nav>

    <!-- 右：TaskDrawer 入口（永远在 nav 最右） -->
    <div class="flex items-center gap-2 shrink-0">
      <slot name="actions" />
      <TaskButton />
    </div>
  </header>
</template>

<script setup>
import { computed } from 'vue';
import { useRouter } from 'vue-router';
import TaskButton from './TaskButton.vue';
import AppIcon from './ui/AppIcon.vue';

const props = defineProps({
  crumbs: { type: Array, required: true },    // [{label, title?, to?}]
  backHref: { type: [String, Object], default: null },
});
const emit = defineEmits(['back']);

const router = useRouter();
const onBack = () => {
  if (emit) emit('back');
  if (props.backHref) {
    if (typeof props.backHref === 'string') router.push(props.backHref);
    else router.push(props.backHref);
  }
};

const goToCrumb = (crumb) => {
  if (!crumb?.to) return;
  router.push(crumb.to);
};

// 收口：strip label 前后多余斜杠（避免 "项目名 / / 数据集" 这种重复分隔符）
const normalizedCrumbs = computed(() =>
  (props.crumbs || []).map(c => ({
    ...c,
    label: (c.label || '').replace(/^\s*\/\s*|\s*\/\s*$/g, '').trim(),
  }))
);
</script>
