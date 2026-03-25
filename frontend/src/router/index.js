import { createRouter, createWebHashHistory } from 'vue-router';
import HomePage from '../pages/HomePage.vue';
import TrainingHistoryPage from '../pages/TrainingHistoryPage.vue';

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      component: HomePage
    },
    {
      path: '/training-history',
      component: TrainingHistoryPage
    }
  ]
});

export default router;
