<template>
  <button
    v-bind="$attrs"
    :type="type"
    :disabled="disabled || pending"
    @click="$emit('click', $event)"
  >
    <slot v-if="!pending" />
    <slot v-else name="loading">
      <span class="inline-block h-3.5 w-3.5 rounded-full border-2 border-current/25 border-t-current animate-spin"></span>
      <span v-if="loadingText">{{ loadingText }}</span>
    </slot>
  </button>
</template>

<script setup>
defineOptions({ inheritAttrs: false });

defineEmits(['click']);

defineProps({
  pending: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false },
  loadingText: { type: String, default: '' },
  type: { type: String, default: 'button' },
});
</script>
