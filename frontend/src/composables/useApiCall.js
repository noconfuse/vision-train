// 统一 API 调用器：API 成功时直接返回业务数据，失败走异常
// 业务代码里只需：
//   const api = useApiCall();
//   await api(store.someAction(...), { successMsg: '保存成功', onSuccess: (data) => {...} });
//
// 替代重复的 try/catch + toast 模板
import { useToast } from './useToast';

/**
 * 统一 API 调用执行器
 * @returns {(promise, opts) => Promise<any|null>}
 *   返回业务数据（成功时）或 null（失败时）
 *   opts: { successMsg, errorMsg, onSuccess, onError, silent, finally }
 */
export const useApiCall = () => {
  const toast = useToast();
  return async (promise, opts = {}) => {
    const {
      successMsg,
      errorMsg,
      onSuccess,
      onError,
      silent = false,
      finally: finallyFn,
    } = opts;

    try {
      const data = await promise;
      if (successMsg) toast.success(successMsg);
      if (onSuccess) await onSuccess(data);
      return data;
    } catch (e) {
      if (!silent) {
        toast.error(e?.message || errorMsg || '请求失败');
      }
      if (onError) await onError(null, e);
      return null;
    } finally {
      if (finallyFn) await finallyFn();
    }
  };
};
