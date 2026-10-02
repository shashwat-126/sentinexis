import axios from 'axios'
import { auth } from './firebase'

export const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8081'
export const WS_URL = API_URL.replace(/^http/, 'ws') + '/ws/incidents'

export const api = axios.create({ baseURL: API_URL })

// Every request gets the current Firebase user's ID token attached, if
// they're logged in. This is the ONLY auth path now -- the old hardcoded
// POST /auth/login('admin','admin') is gone. The gateway verifies this
// token and mints its own internal JWT for the backend services; nothing
// else in the frontend needs to know or care about that translation.
api.interceptors.request.use(async (config) => {
  const user = auth.currentUser
  if (user) {
    const token = await user.getIdToken()
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Opens the live incidents WebSocket with the current Firebase ID token
// attached as a query param (browsers can't set custom headers on a native
// WebSocket, so this is the equivalent of the Authorization header above).
export async function connectIncidentsSocket(handlers = {}) {
  const user = auth.currentUser
  if (!user) throw new Error('Not authenticated')
  const token = await user.getIdToken()
  const ws = new WebSocket(`${WS_URL}?token=${encodeURIComponent(token)}`)
  if (handlers.onMessage) ws.onmessage = (evt) => handlers.onMessage(JSON.parse(evt.data))
  if (handlers.onOpen) ws.onopen = handlers.onOpen
  if (handlers.onClose) ws.onclose = handlers.onClose
  if (handlers.onError) ws.onerror = handlers.onError
  return ws
}

// --- Incidents -------------------------------------------------------
export const getIncidents = (params = {}) => api.get('/incidents/', { params }).then(r => r.data)
export const getIncidentStats = () => api.get('/incidents/stats').then(r => r.data)
export const getIncidentTimeline = (id) => api.get(`/incidents/${id}/timeline`).then(r => r.data)
export const getIncidentActions = (id) => api.get(`/incidents/${id}/actions`).then(r => r.data)
export const getMetricsHistory = (serviceName) => api.get(`/metrics-history/${serviceName}`).then(r => r.data)
export const getAuditLogs = () => api.get('/audit-logs').then(r => r.data)

// --- Health ------------------------------------------------------------
export const SERVICES = [
  { key: 'gateway', label: 'API Gateway', path: '/health' },
  { key: 'auth', label: 'Auth Service', path: '/auth/health' },
  { key: 'inference', label: 'Inference Service', path: '/infer/health' },
  { key: 'result', label: 'Result Service', path: '/results/health' },
  { key: 'incident', label: 'Incident Service', path: '/incidents/health' },
  { key: 'remediation', label: 'Remediation Service', path: '/remediation/health' },
  { key: 'notification', label: 'Notification Service', path: '/notifications/health' },
]

export async function checkAllHealth() {
  const results = await Promise.all(
    SERVICES.map(async (s) => {
      try {
        const res = await api.get(s.path, { timeout: 4000 })
        return { ...s, healthy: res.data?.status === 'ok' }
      } catch {
        return { ...s, healthy: false }
      }
    })
  )
  return results
}

// --- Remediation / Chaos -------------------------------------------------
export const triggerChaos = (scenario, payload = {}) => {
  if (scenario === 'container-failure' || scenario === 'database-failure') {
    return api.post(`/remediation/chaos/${scenario}`, payload)
  }
  return api.post(`/infer/chaos/${scenario}`, { duration_seconds: 60, ...payload })
}

export const getChaosStatus = () => api.get('/infer/chaos/status').then(r => r.data)

// --- Inference (existing demo functionality, preserved) ------------------
export const triggerInference = () =>
  api.post('/infer/infer', {
    data_payload: 'Test Payload ' + new Date().toISOString(),
    complexity: Math.floor(Math.random() * 10) + 1,
  })

export const getResults = () => api.get('/results/').then(r => (Array.isArray(r.data) ? r.data : []))
