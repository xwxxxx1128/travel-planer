import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', redirect: () => (localStorage.getItem('token') ? '/route-planner' : '/login') },
  { path: '/login', component: () => import('@/views/Login.vue') },
  { path: '/register', component: () => import('@/views/Register.vue') },
  { path: '/route-planner', component: () => import('@/views/RoutePlanner.vue'), meta: { requiresAuth: true } },
  { path: '/chat', component: () => import('@/views/Chat.vue'), meta: { requiresAuth: true } },
  { path: '/profile', component: () => import('@/views/Profile.vue'), meta: { requiresAuth: true } },
]

const router = createRouter({ history: createWebHistory('/ui'), routes })
router.beforeEach((to) => {
  const token = localStorage.getItem('token')
  if (to.meta.requiresAuth && !token) return '/login'
  if ((to.path === '/login' || to.path === '/register') && token) return '/route-planner'
})
export default router
