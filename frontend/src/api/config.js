import api from './index'

export const configApi = {
  getRuntimeConfig: () => api.get('/config/runtime'),
  saveRuntimeConfig: (data) => api.post('/config/runtime', data),
}
