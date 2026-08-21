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
      path: '/authors',
      name: 'author-board',
      component: () => import('../views/AuthorBoardView.vue'),
      meta: { title: '作者榜' },
    },
    {
      path: '/institutions',
      name: 'institution-board',
      component: () => import('../views/InstitutionBoardView.vue'),
      meta: { title: '机构榜' },
    },
    {
      path: '/institutions/:name',
      name: 'institution-detail',
      component: () => import('../views/InstitutionDetailView.vue'),
      meta: { title: '机构详情' },
    },
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { title: '登录', public: true },
    },
    {
      path: '/profile',
      name: 'profile',
      component: () => import('../views/ProfileView.vue'),
      meta: { title: '个人画像' },
    },
  ],
})

// M9 路由守卫：课题组工具，全站登录墙（未登录访问任何页面 → 登录页，带 redirect 回跳）
router.beforeEach((to) => {
  const loggedIn = !!localStorage.getItem('auth_token')
  if (to.path === '/login' && loggedIn) {
    return '/'
  }
  if (!to.meta.public && !loggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }
})

export default router
