<template>
  <Teleport to="body">
    <div class="vt-modal-backdrop" @click.self="onBackdrop">
      <div class="vt-modal-panel" :class="[sizeClass, panelClass]" role="dialog" :aria-label="title">
        <div class="vt-modal-header">
          <div class="flex min-w-0 items-center gap-2">
            <slot name="icon" />
            <h3 class="truncate text-base font-semibold text-slate-800">{{ title }}</h3>
          </div>
          <div class="flex shrink-0 items-center gap-1">
            <slot name="header-extra" />
            <button
              type="button"
              class="vt-modal-close"
              :title="closeTitle"
              :aria-label="closeTitle"
              :disabled="!dismissible"
              @click="emit('close')"
            >
              <AppIcon name="close" class="h-4 w-4" />
            </button>
          </div>
        </div>

        <div class="vt-modal-body" :class="bodyClass">
          <slot />
        </div>

        <div v-if="$slots.footer" class="vt-modal-footer">
          <slot name="footer" />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup>
import { computed, onMounted, onUnmounted } from 'vue';
import AppIcon from './AppIcon.vue';
import { useConfirm } from '../../composables/useConfirm';

// 弹窗的唯一外壳：标题栏 + 右上角叉号关闭 + 点遮罩关闭 + Esc 关闭，全部在这里给齐。
// 叠了多层弹窗时 Esc 只关最上面那层，所以按挂载顺序记一个栈。
const openStack = [];
const { state: confirmState } = useConfirm();

const props = defineProps({
  title: { type: String, default: '' },
  // md / lg / xl 对应 .vt-modal-panel--*；传空串则由 panelClass 自己给宽度
  size: { type: String, default: 'md' },
  panelClass: { type: [String, Array, Object], default: '' },
  bodyClass: { type: [String, Array, Object], default: '' },
  // false = 正在跑、不能被关掉的弹窗（叉号显示为禁用，不给点）
  dismissible: { type: Boolean, default: true },
  closeTitle: { type: String, default: '关闭（Esc）' },
});
const emit = defineEmits(['close']);

const sizeClass = computed(() => (props.size ? `vt-modal-panel--${props.size}` : ''));
const onBackdrop = () => {
  if (props.dismissible) emit('close');
};
const self = {};
const onKeydown = (e) => {
  if (e.key !== 'Escape' || !props.dismissible) return;
  // 二次确认框浮在所有弹窗之上，这时候 Esc 归它
  if (confirmState.value.visible) return;
  if (openStack[openStack.length - 1] !== self) return;
  emit('close');
};

onMounted(() => {
  openStack.push(self);
  window.addEventListener('keydown', onKeydown);
});
onUnmounted(() => {
  const idx = openStack.indexOf(self);
  if (idx >= 0) openStack.splice(idx, 1);
  window.removeEventListener('keydown', onKeydown);
});
</script>
