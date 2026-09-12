import { createRouter, createWebHistory } from 'vue-router'
import { authApi } from '@/api/auth'

const routes = [
  { path: '/', redirect: () => (localStorage.getItem('token') ? '/route-planner' : '/login') },
  { path: '/login', component: () => import('@/views/Login.vue') },
  { path: '/register', component: () => import('@/views/Register.vue') },
  { path: '/route-planner', component: () => import('@/views/RoutePlanner.vue'), meta: { requiresAuth: true } },
  { path: '/chat', component: () => import('@/views/Chat.vue'), meta: { requiresAuth: true } },
  { path: '/profile', component: () => import('@/views/Profile.vue'), meta: { requiresAuth: true } },
]

const router = createRouter({ history: createWebHistory('/ui'), routes })

function clearAuth() {
  localStorage.removeItem('token')
  localStorage.removeItem('refreshToken')
  localStorage.removeItem('userInfo')
}

router.beforeEach(async (to) => {
  const token = localStorage.getItem('token')

  if (to.meta.requiresAuth) {
    if (!token) return { path: '/login' }
    try {
      // 交由后端校验令牌真实有效性（401 时 axios 拦截器会先尝试用 refresh 静默续期）
      await authApi.me()
      return true
    } catch (e) {
      clearAuth()
      return { path: '/login' }
    }
  }

  if ((to.path === '/login' || to.path === '/register') && token) {
    return { path: '/route-planner' }
  }
  return true
})

export default router
