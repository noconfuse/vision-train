<template>
  <div class="h-screen w-screen flex bg-gray-50 overflow-hidden">
    <!-- 左侧品牌区 -->
    <div class="hidden lg:flex lg:w-1/2 bg-slate-900 text-white flex-col justify-between p-12 relative overflow-hidden">
      <!-- 装饰：网格 + 渐变 -->
      <div class="absolute inset-0 opacity-20"
           style="background-image:
                  linear-gradient(rgba(255,255,255,.07) 1px, transparent 1px),
                  linear-gradient(90deg, rgba(255,255,255,.07) 1px, transparent 1px);
                  background-size: 32px 32px;"></div>
      <div class="absolute -top-32 -right-32 w-96 h-96 rounded-full bg-blue-500/20 blur-3xl"></div>
      <div class="absolute -bottom-32 -left-32 w-96 h-96 rounded-full bg-emerald-500/10 blur-3xl"></div>

      <div class="relative z-10">
        <div class="flex items-center gap-3">
          <div class="flex h-10 w-10 items-center justify-center bg-blue-600 text-white">
            <AppIcon name="target" class="h-5 w-5" />
          </div>
          <div>
            <div class="text-lg font-semibold">Vision Train</div>
            <div class="text-xs text-gray-400">视觉模型训练工作台</div>
          </div>
        </div>
      </div>

      <div class="relative z-10 space-y-6">
        <h1 class="text-4xl font-bold leading-tight">
          工业级视觉模型<br />
          <span class="text-blue-400">训练工作流</span>
        </h1>
        <p class="text-gray-400 text-sm leading-relaxed max-w-md">
          一站式管理数据集、训练任务、模型评估与导出。
          面向生产环境的端到端视觉模型工具链。
        </p>
        <div class="grid grid-cols-3 gap-4 pt-2">
          <div>
            <div class="text-2xl font-bold text-blue-400">YOLO</div>
            <div class="text-[10px] text-gray-500 mt-1">检测 / 分类 / 分割</div>
          </div>
          <div>
            <div class="text-2xl font-bold text-emerald-400">VLM</div>
            <div class="text-[10px] text-gray-500 mt-1">多模态模型</div>
          </div>
          <div>
            <div class="text-2xl font-bold text-amber-400">Export</div>
            <div class="text-[10px] text-gray-500 mt-1">OpenVINO / ONNX</div>
          </div>
        </div>
      </div>

      <div class="relative z-10 text-xs text-gray-500">
        © 2026 Vision Train · v{{ appVersion }}
      </div>
    </div>

    <!-- 右侧登录区 -->
    <div class="flex-1 flex flex-col min-w-0">
      <div class="flex-1 flex items-center justify-center p-6">
        <div class="w-full max-w-sm">
          <!-- 移动端 logo（lg 以下显示） -->
          <div class="lg:hidden mb-8 flex items-center gap-3">
            <div class="flex h-10 w-10 items-center justify-center bg-blue-600 text-white">
              <AppIcon name="target" class="h-5 w-5" />
            </div>
            <div>
              <div class="text-lg font-semibold text-slate-800">Vision Train</div>
              <div class="text-xs text-gray-500">视觉模型训练工作台</div>
            </div>
          </div>

          <div class="mb-8">
            <h2 class="text-2xl font-semibold text-slate-800">欢迎回来</h2>
            <p class="text-sm text-gray-500 mt-1">登录以继续你的工作</p>
          </div>

          <form @submit.prevent="onSubmit" class="space-y-4">
            <div>
              <label class="block text-xs text-gray-500 mb-1.5">用户名</label>
              <div class="relative">
                <span class="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400">
                  <AppIcon name="user" class="h-4 w-4" />
                </span>
                <input v-model="username" type="text" required autocomplete="username"
                       class="vt-input vt-input--with-leading h-10"
                       :class="error ? 'border-rose-400' : ''"
                       placeholder="请输入用户名" autofocus />
              </div>
            </div>
            <div>
              <label class="block text-xs text-gray-500 mb-1.5">密码</label>
              <div class="relative">
                <span class="absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400">
                  <AppIcon name="lock" class="h-4 w-4" />
                </span>
                <input v-model="password" :type="showPassword ? 'text' : 'password'" required
                       autocomplete="current-password"
                       class="vt-input vt-input--with-both h-10"
                       :class="error ? 'border-rose-400' : ''"
                       placeholder="请输入密码" />
                <button type="button" @click="showPassword = !showPassword"
                        class="absolute right-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center text-gray-400 hover:text-gray-700">
                  <AppIcon :name="showPassword ? 'eyeOff' : 'eye'" class="h-4 w-4" />
                </button>
              </div>
            </div>

            <transition name="vt-fade">
              <div v-if="error" class="flex items-start gap-2 text-xs text-rose-600 bg-rose-50 border border-rose-200 px-3 py-2">
                <AppIcon name="alert" class="mt-0.5 h-4 w-4 shrink-0" />
                <span class="flex-1">{{ error }}</span>
              </div>
            </transition>

            <button type="submit" :disabled="loading"
                    class="vt-btn-solid-primary w-full h-10 flex items-center justify-center gap-2 text-sm font-medium">
              <span v-if="loading" class="inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
              <span>{{ loading ? '登录中...' : '登 录' }}</span>
            </button>
          </form>

          <!-- 提示 / 状态 -->
          <div v-if="authEnabled === false" class="mt-6 text-xs text-gray-500 bg-gray-100 border border-gray-200 px-3 py-2 flex items-start gap-2">
            <AppIcon name="help" class="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />
            <span>当前后端未启用认证，3 秒后自动进入...</span>
          </div>

          <div v-else-if="authEnabled === true" class="mt-6 text-xs text-gray-400 text-center">
            没有账号？联系管理员开通
          </div>
        </div>
      </div>

      <!-- 底部 footer -->
      <div class="px-6 py-3 text-xs text-gray-400 flex items-center justify-between border-t border-gray-200">
        <span>Vision Train</span>
        <span>登录遇到问题？请联系管理员</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import { authApi } from '../api/auth';
import { setAuthToken, setStoredUser, getAuthToken } from '../api';
import { useMainStore } from '../stores/main';
import AppIcon from '../components/ui/AppIcon.vue';

const router = useRouter();
const route = useRoute();
const store = useMainStore();

const username = ref('');
const password = ref('');
const showPassword = ref(false);
const error = ref('');
const loading = ref(false);
const authEnabled = ref(null);   // null = 加载中
const appVersion = '1.0';

let redirectTimer = null;

onMounted(async () => {
  try {
    // interceptor 已自动 unwrap：拿到的就是业务数据 {enabled, authenticated, user}
    const data = await authApi.status();
    if (data && 'enabled' in data) {
      authEnabled.value = !!data.enabled;
      store.setAuthEnabled(data.enabled);
      if (!data.enabled) {
        // 后端未启用认证：用 sentinel token 让路由守卫放行
        if (!getAuthToken()) setAuthToken('auth-disabled');
        // 已有 token 直接跳走，避免 3 秒等待
        if (getAuthToken() === 'auth-disabled') {
          const target = (route.query.redirect && String(route.query.redirect)) || '/';
          router.replace(target);
          return;
        }
        redirectTimer = setTimeout(() => {
          const target = (route.query.redirect && String(route.query.redirect)) || '/';
          router.replace(target);
        }, 3000);
      }
    } else {
      authEnabled.value = true;
    }
  } catch (_) {
    authEnabled.value = true;
  }
});

const onSubmit = async () => {
  if (loading.value) return;
  error.value = '';
  if (redirectTimer) {
    clearTimeout(redirectTimer);
    redirectTimer = null;
  }
  loading.value = true;
  try {
    // interceptor 已自动 unwrap：拿到的就是业务数据 {token, user, expires_at}
    const data = await authApi.login(username.value, password.value);
    if (data && data.token && data.user) {
      setAuthToken(data.token);
      setStoredUser(data.user);
      const target = (route.query.redirect && String(route.query.redirect)) || '/';
      router.replace(target);
    } else {
      error.value = '登录失败：响应格式异常';
    }
  } catch (e) {
    error.value = e.message || '登录失败，请检查网络';
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.vt-fade-enter-active,
.vt-fade-leave-active {
  transition: opacity 0.2s;
}
.vt-fade-enter-from,
.vt-fade-leave-to {
  opacity: 0;
}
</style>
