import axios from 'axios'
import { ElMessage } from 'element-plus'

// 后端已对单次对话加总时长保险（默认 100s 内必返回），这里留足余量避免误杀。
const api = axios.create({ baseURL: '/api', timeout: 180000 })

// 这些接口自身不参与 401 自动刷新（登录/注册失败本就是 401，刷新失败也不该再递归刷新）
const AUTH_FREE = ['/auth/login', '/auth/register', '/auth/refresh']

function clearAuth() {
  localStorage.removeItem('token')
  localStorage.removeItem('refreshToken')
  localStorage.removeItem('userInfo')
}

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 单例刷新：并发 401 只触发一次刷新请求
let refreshPromise = null

function refreshAccessToken() {
  if (!refreshPromise) {
    const refreshToken = localStorage.getItem('refreshToken')
    if (!refreshToken) return Promise.reject(new Error('无刷新令牌'))
    refreshPromise = axios
      .post('/api/auth/refresh', { refresh_token: refreshToken })
      .then((resp) => {
        const data = resp.data || {}
        if (data.access_token) localStorage.setItem('token', data.access_token)
        if (data.refresh_token) localStorage.setItem('refreshToken', data.refresh_token)
        if (data.user) localStorage.setItem('userInfo', JSON.stringify(data.user))
        return data.access_token
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

api.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    const response = error?.response
    const config = error?.config || {}
    const url = config.url || ''
    const isAuthFree = AUTH_FREE.some((u) => url.includes(u))

    if (response?.status === 401 && !config._retry && !isAuthFree) {
      config._retry = true
      try {
        const newToken = await refreshAccessToken()
        if (newToken) {
          config.headers = config.headers || {}
          config.headers.Authorization = `Bearer ${newToken}`
          return api(config)
        }
      } catch (e) {
        // 刷新失败：走下方统一清理与跳转
      }
      clearAuth()
      if (!location.pathname.endsWith('/login')) location.href = '/ui/login'
    }

    const message = response?.data?.detail || error.message || '请求失败'
    ElMessage.error(message)
    return Promise.reject(error)
  }
)
export default api
