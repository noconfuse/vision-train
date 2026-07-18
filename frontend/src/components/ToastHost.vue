<template>
  <Teleport to="body">
    <div class="vt-toast-stack">
      <TransitionGroup name="toast">
        <div
          v-for="t in toasts"
          :key="t.id"
          class="vt-toast"
          :class="classMap[t.type] || classMap.info"
        >
          <AppIcon :name="iconMap[t.type] || 'help'" class="vt-toast__icon h-4 w-4" />
          <div class="vt-toast__message">{{ t.message }}</div>
          <button class="vt-toast__close" @click="remove(t.id)">
            <AppIcon name="close" class="h-4 w-4" />
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>

<script setup>
import { useToast as _toast } from '../composables/useToast';
import AppIcon from './ui/AppIcon.vue';

const { toasts, remove } = _toast();

const classMap = {
  success: 'vt-toast--success',
  error: 'vt-toast--error',
  warn: 'vt-toast--warn',
  info: 'vt-toast--info',
};
const iconMap = {
  success: 'check',
  error: 'alert',
  warn: 'alert',
  info: 'help',
};
</script>

<style scoped>
.toast-enter-active, .toast-leave-active {
  transition: all .25s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateY(-8px) translateX(8px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(20px);
}
</style>
