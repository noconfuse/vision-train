<template>
  <Teleport to="body">
    <Transition name="confirm-fade">
      <div v-if="state.visible" class="vt-modal-backdrop z-[60]"
           @click.self="onCancel">
        <div class="absolute inset-0 bg-black/40 backdrop-blur-sm"></div>
        <Transition name="confirm-scale" appear>
          <div class="vt-modal-panel vt-modal-panel--md relative mx-4 overflow-hidden">
            <!-- 头部：标题 + 图标 -->
            <div class="px-6 pt-5 pb-3 flex items-start gap-3">
              <AppIcon
                :name="state.danger ? 'alert' : 'help'"
                class="mt-0.5 h-5 w-5 shrink-0"
                :class="state.danger ? 'text-rose-600' : 'vt-text-accent'"
              />
              <div class="flex-1 min-w-0">
                <h3 class="text-base font-semibold text-slate-800">{{ state.title }}</h3>
              </div>
              <button class="vt-modal-close -mt-1 -mr-1" @click="onCancel">
                <AppIcon name="close" class="h-4 w-4" />
              </button>
            </div>

            <!-- 内容：消息 + 详情 -->
            <div class="px-6 pb-2 pl-[3.25rem]">
              <p v-if="state.message" class="text-sm text-slate-700 whitespace-pre-line">{{ state.message }}</p>
              <pre v-if="state.detail" class="mt-2 max-h-40 overflow-y-auto overflow-x-auto border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600 whitespace-pre-wrap break-all">{{ state.detail }}</pre>
            </div>

            <!-- 按钮 -->
            <div class="px-6 py-4 mt-2 flex justify-end gap-2 bg-gray-50 border-t border-gray-100">
              <button @click="onCancel"
                      class="vt-btn-secondary vt-btn-size-md">
                {{ state.cancelText }}
              </button>
              <button @click="onConfirm" ref="confirmBtn"
                      class="vt-btn-size-md"
                      :class="state.danger ? 'vt-btn-solid-danger' : 'vt-btn-solid-primary'">
                {{ state.confirmText }}
              </button>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>

<script setup>
import { ref, nextTick, watch, onUnmounted } from 'vue';
import { useConfirm } from '../composables/useConfirm';
import AppIcon from './ui/AppIcon.vue';

const { state } = useConfirm();
const confirmBtn = ref(null);

const closeWith = (val) => {
  const r = state.value.resolve;
  state.value = { ...state.value, visible: false, resolve: null };
  r && r(val);
};

const onConfirm = () => closeWith(true);
const onCancel = () => closeWith(false);

// 自动聚焦确认按钮
watch(() => state.value.visible, async (v) => {
  if (v) {
    await nextTick();
    confirmBtn.value && confirmBtn.value.focus();
  }
});

// ESC 取消
const onKeydown = (e) => {
  if (e.key === 'Escape' && state.value.visible) onCancel();
};
window.addEventListener('keydown', onKeydown);
onUnmounted(() => window.removeEventListener('keydown', onKeydown));
</script>

<style scoped>
.confirm-fade-enter-active, .confirm-fade-leave-active {
  transition: opacity 0.18s ease;
}
.confirm-fade-enter-from, .confirm-fade-leave-to {
  opacity: 0;
}
.confirm-scale-enter-active {
  transition: transform 0.18s ease, opacity 0.18s ease;
}
.confirm-scale-leave-active {
  transition: transform 0.12s ease, opacity 0.12s ease;
}
.confirm-scale-enter-from, .confirm-scale-leave-to {
  transform: scale(0.94);
  opacity: 0;
}
</style>
