import { createRouter, createWebHashHistory } from 'vue-router';
import HomePage from '../pages/HomePage.vue';
import DatasetDetailPage from '../pages/DatasetDetailPage.vue';
import TrainingPage from '../pages/TrainingPage.vue';
import LoginPage from '../pages/LoginPage.vue';
import SopLandingPage from '../pages/SopLandingPage.vue';
import TasksCenterPage from '../pages/TasksCenterPage.vue';
import NotFoundPage from '../pages/NotFoundPage.vue';
import { getAuthToken, clearAuth } from '../api';

// 路由设计（项目上下文全部由 URL 路径承载）：
// - /login                         -> LoginPage (public)
// - /landing                       -> Landing (public)
// - /tasks                         -> 全局任务中心
// - /                              -> HomePage（自动重定向到首个项目）
// - /projects/:project             -> HomePage
// - /projects/:project/dataset/:name           -> DatasetDetailPage
// - /projects/:project/dataset/:name/train     -> TrainingPage
const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    { path: '/login', name: 'login', component: LoginPage, meta: { public: true } },
    { path: '/landing', name: 'landing', component: SopLandingPage, meta: { public: true } },
    { path: '/', name: 'home', component: HomePage },
    { path: '/tasks', name: 'tasks-center', component: TasksCenterPage },
    { path: '/projects/:project', name: 'home-with-project', component: HomePage },
    { path: '/projects/:project/dataset/:name', name: 'dataset-detail', component: DatasetDetailPage },
    { path: '/projects/:project/dataset/:name/train', name: 'dataset-train', component: TrainingPage },
    { path: '/:pathMatch(.*)*', name: 'not-found', component: NotFoundPage, meta: { public: true } }
  ]
});

// 路由守卫：未登录时把当前路径塞到 redirect，登录后跳回来
router.beforeEach((to, _from, next) => {
  if (to.meta.public) {
    return next();
  }
  const token = getAuthToken();
  if (!token) {
    return next({ name: 'login', query: { redirect: to.fullPath } });
  }
  return next();
});

// 401 事件：后端报未登录就清掉本地 token 并跳登录
window.addEventListener('vt:auth-expired', () => {
  clearAuth();
  const here = router.currentRoute.value.fullPath;
  if (router.currentRoute.value.name !== 'login') {
    router.replace({ name: 'login', query: { redirect: here } });
  }
});

export default router;
