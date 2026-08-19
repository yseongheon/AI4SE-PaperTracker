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
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { title: '登录' },
    },
    {
      path: '/profile',
      name: 'profile',
      component: () => import('../views/ProfileView.vue'),
      meta: { title: '个人画像', requiresAuth: true },
    },
  ],
})

// M9 路由守卫：requiresAuth 页面未登录跳登录页（带 redirect 回跳）
router.beforeEach((to) => {
  if (to.meta.requiresAuth && !localStorage.getItem('auth_token')) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
})

export default router
