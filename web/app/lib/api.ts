import axios from 'axios'

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1'
const client = axios.create({ baseURL: BASE_URL })

client.interceptors.request.use((config) => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('tms_token') : null
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})
client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('tms_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export const api = {
  auth: {
    login: (email: string, password: string) =>
      client.post('/auth/login', { email, password }).then((r) => r.data),
  },
  shipments: {
    list: (params?: Record<string, string>) => client.get('/shipments/', { params }).then((r) => r.data),
    get: (id: string) => client.get(`/shipments/${id}`).then((r) => r.data),
    update: (id: string, data: Record<string, unknown>) => client.patch(`/shipments/${id}`, data).then((r) => r.data),
    listStatuses: () => client.get('/shipments/statuses').then((r) => r.data),
  },
  purchaseOrders: {
    list: (params?: Record<string, string>) => client.get('/purchase-orders/', { params }).then((r) => r.data),
    get: (id: string) => client.get(`/purchase-orders/${id}`).then((r) => r.data),
    update: (id: string, data: Record<string, unknown>) => client.patch(`/purchase-orders/${id}`, data).then((r) => r.data),
  },
  orderReleases: {
    list: (params?: Record<string, string>) => client.get('/order-releases/', { params }).then((r) => r.data),
    get: (id: string) => client.get(`/order-releases/${id}`).then((r) => r.data),
  },
  organizations: {
    list: () => client.get('/organizations/').then((r) => r.data),
    create: (data: Record<string, unknown>) => client.post('/organizations/', data).then((r) => r.data),
    update: (id: string, data: Record<string, unknown>) => client.patch(`/organizations/${id}`, data).then((r) => r.data),
    delete: (id: string) => client.delete(`/organizations/${id}`).then((r) => r.data),
    listBUs: (orgId: string) => client.get(`/organizations/${orgId}/business-units`).then((r) => r.data),
    createBU: (orgId: string, data: Record<string, unknown>) => client.post(`/organizations/${orgId}/business-units`, data).then((r) => r.data),
    updateBU: (orgId: string, buId: string, data: Record<string, unknown>) => client.patch(`/organizations/${orgId}/business-units/${buId}`, data).then((r) => r.data),
    deleteBU: (orgId: string, buId: string) => client.delete(`/organizations/${orgId}/business-units/${buId}`).then((r) => r.data),
  },
  workflows: {
    listRules: (params?: Record<string, string>) => client.get('/workflows/rules', { params }).then((r) => r.data),
    createRule: (data: Record<string, unknown>) => client.post('/workflows/rules', data).then((r) => r.data),
    updateRule: (id: string, data: Record<string, unknown>) => client.patch(`/workflows/rules/${id}`, data).then((r) => r.data),
    deleteRule: (id: string) => client.delete(`/workflows/rules/${id}`).then((r) => r.data),
    trigger: (data: Record<string, unknown>) => client.post('/workflows/trigger', data).then((r) => r.data),
    listNotifications: (params?: Record<string, string>) => client.get('/workflows/notifications', { params }).then((r) => r.data),
    markRead: (id: string) => client.patch(`/workflows/notifications/${id}/read`, {}).then((r) => r.data),
    markAllRead: () => client.patch('/workflows/notifications/read-all', {}).then((r) => r.data),
  },
  statusModels: {
    list: (params?: Record<string, string>) => client.get('/status-models/', { params }).then((r) => r.data),
    update: (id: string, data: Record<string, unknown>) => client.patch(`/status-models/values/${id}`, data).then((r) => r.data),
    listTransitions: (params?: Record<string, string>) => client.get('/status-models/transitions', { params }).then((r) => r.data),
    updateTransition: (id: string, data: Record<string, unknown>) => client.patch(`/status-models/transitions/${id}`, data).then((r) => r.data),
    validate: (data: Record<string, unknown>) => client.post('/status-models/validate', data).then((r) => r.data),
  },
  numbering: {
    list: () => client.get('/numbering/').then((r) => r.data),
    generate: (entityType: string) => client.post(`/numbering/generate/${entityType}`).then((r) => r.data),
    preview: (entityType: string) => client.get(`/numbering/preview/${entityType}`).then((r) => r.data),
    update: (entityType: string, data: Record<string, unknown>) => client.patch(`/numbering/${entityType}`, data).then((r) => r.data),
    reset: (entityType: string, data: Record<string, unknown>) => client.post(`/numbering/${entityType}/reset`, data).then((r) => r.data),
  },
  carriers: {
    list: (params?: Record<string, string>) => client.get('/carriers/', { params }).then((r) => r.data),
  },
  dispatches: {
    list: () => client.get('/dispatches/').then((r) => r.data),
  },
  globalSettings: {
    currencies:          () => client.get('/global/currencies').then((r) => r.data),
    updateCurrency:      (code: string, data: Record<string, unknown>) => client.patch(`/global/currencies/${code}`, data).then((r) => r.data),
    languages:           () => client.get('/global/languages').then((r) => r.data),
    updateLanguage:      (code: string, data: Record<string, unknown>) => client.patch(`/global/languages/${code}`, data).then((r) => r.data),
    dateFormats:         () => client.get('/global/date-formats').then((r) => r.data),
    updateDateFormat:    (code: string, data: Record<string, unknown>) => client.patch(`/global/date-formats/${code}`, data).then((r) => r.data),
    timeZones:           (params?: Record<string, string>) => client.get('/global/time-zones', { params }).then((r) => r.data),
    updateTimeZone:      (code: string, data: Record<string, unknown>) => client.patch(`/global/time-zones/${code}`, data).then((r) => r.data),
    taxJurisdictions:    (params?: Record<string, string>) => client.get('/global/tax-jurisdictions', { params }).then((r) => r.data),
    updateTaxJurisdiction: (code: string, data: Record<string, unknown>) => client.patch(`/global/tax-jurisdictions/${code}`, data).then((r) => r.data),
    uoms:                (params?: Record<string, string>) => client.get('/global/uoms', { params }).then((r) => r.data),
    updateUOM:           (code: string, data: Record<string, unknown>) => client.patch(`/global/uoms/${code}`, data).then((r) => r.data),
  },
  omsEvents: {
    poll: () => client.get('/oms-events/').then((r) => r.data),
  },
}
