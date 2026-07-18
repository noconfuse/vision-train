// 把 "emit('submit', payload)" 包装成可 await 的 Promise。
//
// 背景：Vue 3 的 emit 是同步的，await emit(...) 不会等待父组件的 handler。
// 父组件必须显式把 handler 作为参数传过来，或用回调方式：
//   emit('submit', { ...payload, onDone: (err) => { ... } });
//
// 这个 composable 把这种 6 行模板统一收口成 1 行：
//   const asyncEmit = useAsyncEmit(emit);
//   await asyncEmit('submit', { ... });
//   await asyncEmit('confirm', { ... }, { timeoutMs: 30000 });
export const useAsyncEmit = (emit) => {
  /**
   * 包装 emit 为可 await 的 Promise
   * @param {string} eventName
   * @param {Object} payload 父组件可以拿到这个对象
   * @param {Object} [opts]
   * @param {number} [opts.timeoutMs=0] 0 表示不超时
   * @returns {Promise<void>} resolve 表示 onDone() 无参调用；reject 表示 onDone(err) 有参调用
   */
  return (eventName, payload = {}, opts = {}) => {
    const { timeoutMs = 0 } = opts;
    return new Promise((resolve, reject) => {
      let settled = false;
      const settle = (fn, arg) => {
        if (settled) return;
        settled = true;
        if (timeoutTimer) clearTimeout(timeoutTimer);
        fn(arg);
      };
      let timeoutTimer = null;
      if (timeoutMs > 0) {
        timeoutTimer = setTimeout(() => {
          settle(reject, new Error(`emit("${eventName}") 超时（${timeoutMs}ms 内未收到 onDone）`));
        }, timeoutMs);
      }
      emit(eventName, {
        ...payload,
        onDone: (err) => settle(err ? reject : resolve, err),
      });
    });
  };
};
