import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 30000
})

export const articleApi = {
  getList: (params) => api.get('/articles', { params }),
  getById: (id) => api.get(`/articles/${id}`),
  getIssues: () => api.get('/articles/issues'),
  getCategories: () => api.get('/articles/categories'),
  delete: (id) => api.delete(`/articles/${id}`),
  seed: () => api.post('/articles/seed')
}

export const crawlerApi = {
  start: (data) => api.post('/crawler/start', data),
  getStatus: () => api.get('/crawler/status'),
  getSources: () => api.get('/crawler/sources'),
  mock: () => api.post('/crawler/mock')
}

export const settingsApi = {
  get: () => api.get('/settings'),
  update: (data) => api.put('/settings', data),
  addSource: (data) => api.post('/settings/sources', data),
  addMockSource: () => api.post('/settings/sources/mock')
}

export default api
