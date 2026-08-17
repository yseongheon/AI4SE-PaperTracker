import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'papers',
      component: () => import('../views/PaperListView.vue'),
      meta: { title: '论文列表' },
    },
    {
      path: '/papers/:id',
      name: 'paper-detail',
      component: () => import('../views/PaperDetailView.vue'),
      meta: { title: '论文详情' },
    },
    {
      path: '/trend',
      name: 'trend',
      component: () => import('../views/TrendView.vue'),
      meta: { title: '主题趋势' },
    },
  ],
})

export default router
