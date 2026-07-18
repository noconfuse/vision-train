<template>
  <div class="flex-1 flex flex-col items-center justify-center text-gray-400 gap-2 px-4 text-center">
    <!-- 加载中 -->
    <template v-if="loading">
      <div class="flex items-center gap-2 text-sm">
        <div class="animate-spin rounded-full h-5 w-5 border-b-2 border-[var(--vt-color-primary)]"></div>
        <span>{{ loadingText || '加载中...' }}</span>
      </div>
    </template>

    <!-- 错误 -->
    <template v-else-if="error">
      <div class="text-3xl">⚠️</div>
      <div class="text-rose-500 text-sm max-w-md">{{ error }}</div>
      <button v-if="showBack" @click="$emit('back')"
              class="mt-2 vt-btn-secondary vt-btn-size-sm">
        ← 返回
      </button>
    </template>

    <!-- 空状态 -->
    <template v-else-if="empty">
      <div class="text-3xl">{{ emptyIcon || '📭' }}</div>
      <div class="text-sm">{{ emptyText || '暂无内容' }}</div>
      <slot name="empty" />
    </template>
  </div>
</template>

<script setup>
defineProps({
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
  empty: { type: Boolean, default: false },
  emptyIcon: { type: String, default: '' },
  emptyText: { type: String, default: '' },
  loadingText: { type: String, default: '' },
  showBack: { type: Boolean, default: true },
});
defineEmits(['back']);
</script>
