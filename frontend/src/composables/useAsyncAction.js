import { reactive } from 'vue';

export const useAsyncAction = () => {
  const pendingMap = reactive({});

  const isPending = (key) => {
    return !!pendingMap[String(key || '')];
  };

  const run = async (key, action) => {
    const actionKey = String(key || '').trim();
    if (!actionKey) {
      throw new Error('useAsyncAction 缺少 action key');
    }
    if (typeof action !== 'function') {
      throw new Error('useAsyncAction 需要传入可执行的异步函数');
    }
    if (isPending(actionKey)) {
      return null;
    }

    pendingMap[actionKey] = true;
    try {
      return await action();
    } finally {
      delete pendingMap[actionKey];
    }
  };

  return {
    run,
    isPending,
  };
};
