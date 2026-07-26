import axios from 'axios'
import { ElMessage } from 'element-plus'

// 后端已对单次对话加总时长保险（默认 100s 内必返回），这里留足余量避免误杀。
const api = axios.create({ baseURL: '/api', timeout: 180000 })
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error?.response?.data?.detail || error.message || '请求失败'
    ElMessage.error(message)
    return Promise.reject(error)
  }
)
export default api
