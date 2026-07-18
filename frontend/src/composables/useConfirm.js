// 全局确认弹窗 composable
// 替代 12 处 window.confirm(...) 调用，统一 UI 风格
import { ref } from 'vue';

const state = ref({
  visible: false,
  title: '',
  message: '',
  detail: '',
  confirmText: '确定',
  cancelText: '取消',
  danger: false,
  resolve: null,
});

const show = (options) => {
  return new Promise((resolve) => {
    state.value = {
      visible: true,
      title: options.title || '确认操作',
      message: options.message || '',
      detail: options.detail || '',
      confirmText: options.confirmText || '确定',
      cancelText: options.cancelText || '取消',
      danger: options.danger || false,
      resolve,
    };
  });
};

export const useConfirm = () => {
  return {
    state,
    /**
     * 通用确认弹窗
     * @param {string|Object} messageOrOpts 简单用法：直接传 message；高级用法：传 options
     * @returns {Promise<boolean>} true=确认，false=取消
     */
    confirm(messageOrOpts) {
      const opts = typeof messageOrOpts === 'string'
        ? { message: messageOrOpts }
        : messageOrOpts;
      return show(opts);
    },
    /**
     * 删除等危险操作的快速确认
     */
    confirmDanger(message, opts = {}) {
      return show({ ...opts, message, danger: true, confirmText: opts.confirmText || '删除' });
    },
  };
};
