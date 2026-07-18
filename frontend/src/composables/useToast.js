// 全局 toast composable
// 依赖 ToastHost 组件（在 App.vue 中挂载一次）
import { ref } from 'vue';

const toasts = ref([]);
let _id = 0;

const add = (type, message, timeout = 3500) => {
  const id = ++_id;
  toasts.value.push({ id, type, message });
  if (timeout > 0) {
    setTimeout(() => remove(id), timeout);
  }
  return id;
};

const remove = (id) => {
  toasts.value = toasts.value.filter(t => t.id !== id);
};

export const useToast = () => {
  return {
    success: (msg, t) => add('success', msg, t),
    error: (msg, t = 5000) => add('error', msg, t),
    warn: (msg, t = 4500) => add('warn', msg, t),
    info: (msg, t) => add('info', msg, t),
    remove,
    toasts,
  };
};
