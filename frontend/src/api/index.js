import axios from 'axios'
import { store } from '@/store'
import { setTokens, clearAuth } from '@/store/slices/authSlice'

const api = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: { 'Content-Type': 'application/json' },
})

const REFRESH_LOCK_KEY = 'auth:refresh-lock'
const REFRESH_LOCK_TTL_MS = 10_000
const authChannel = typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('auth') : null

if (authChannel) {
  authChannel.onmessage = (e) => {
    const msg = e.data || {}
    if (msg.type === 'logout') {
      try { store.dispatch(clearAuth()) } catch {}
      if (window.location.pathname !== '/login') window.location.href = '/login'
    } else if (msg.type === 'tokens' && msg.access) {
      store.dispatch(setTokens({ access: msg.access, refresh: msg.refresh }))
    }
  }
}

export function broadcastLogout() {
  try { authChannel?.postMessage({ type: 'logout' }) } catch {}
}

function acquireRefreshLock() {
  try {
    const now = Date.now()
    const raw = localStorage.getItem(REFRESH_LOCK_KEY)
    if (raw) {
      const ts = parseInt(raw, 10)
      if (!Number.isNaN(ts) && now - ts < REFRESH_LOCK_TTL_MS) return false
    }
    localStorage.setItem(REFRESH_LOCK_KEY, String(now))
    return true
  } catch { return true }
}

function releaseRefreshLock() {
  try { localStorage.removeItem(REFRESH_LOCK_KEY) } catch {}
}

function waitForNewAccessToken(prevAccess, timeoutMs = REFRESH_LOCK_TTL_MS) {
  return new Promise((resolve, reject) => {
    const started = Date.now()
    const tick = () => {
      const current = store.getState().auth?.accessToken
      if (current && current !== prevAccess) return resolve(current)
      if (Date.now() - started > timeoutMs) return reject(new Error('refresh-wait-timeout'))
      setTimeout(tick, 150)
    }
    tick()
  })
}

// Attach JWT token and active tenant
api.interceptors.request.use((config) => {
  try {
    // Prefer live Redux state — keeps in sync with cross-tab BroadcastChannel updates
    const token = store.getState().auth?.accessToken
    if (token) config.headers.Authorization = `Bearer ${token}`
    const tenantUuid = store.getState().tenant?.currentTenant?.tenant_uuid
    const skipTenant = config.params && 'tenant' in config.params && config.params.tenant === null
    if (tenantUuid && !skipTenant) config.params = { tenant: tenantUuid, ...config.params }
  } catch {}
  return config
})

// Auto-refresh on 401 — single in-flight promise within a tab, localStorage lock across tabs
let _refreshPromise = null

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config || {}
    const url = original.url || ''
    const isAuthEndpoint = url.includes('/auth/login/') ||
                           url.includes('/auth/refresh/') ||
                           url.includes('/auth/forgot-password/')
    if (err.response?.status === 401 && !original._retry && !isAuthEndpoint) {
      original._retry = true
      const prevAccess = store.getState().auth?.accessToken
      try {
        if (!_refreshPromise) {
          if (acquireRefreshLock()) {
            const refresh = store.getState().auth?.refreshToken
            _refreshPromise = axios.post('/api/v1/auth/refresh/', { refresh })
              .then(({ data }) => {
                // Persist BOTH access and rotated refresh token through Redux/redux-persist
                store.dispatch(setTokens({ access: data.access, refresh: data.refresh }))
                try { authChannel?.postMessage({ type: 'tokens', access: data.access, refresh: data.refresh }) } catch {}
                return data
              })
              .finally(() => { _refreshPromise = null; releaseRefreshLock() })
          } else {
            // Another tab is refreshing — wait for its broadcast to update our store
            _refreshPromise = waitForNewAccessToken(prevAccess)
              .then((access) => ({ access }))
              .finally(() => { _refreshPromise = null })
          }
        }
        const data = await _refreshPromise
        const newAccess = data?.access || store.getState().auth?.accessToken
        if (!newAccess) throw new Error('no-access-token')
        original.headers = original.headers || {}
        original.headers.Authorization = `Bearer ${newAccess}`
        return api(original)
      } catch {
        releaseRefreshLock()
        store.dispatch(clearAuth())
        broadcastLogout()
        if (window.location.pathname !== '/login') window.location.href = '/login'
      }
    }
    return Promise.reject(err)
  }
)

export default api

// ── Auth ───────────────────────────────────────────────────────────────────
export const auth = {
  login: (data) => api.post('/auth/login/', data),
  logout: (refresh) => api.post('/auth/logout/', { refresh }),
  me: (config) => api.get('/auth/me/', config),
  resetPassword: (user_uuid) => api.post('/auth/reset-password/', { user_uuid }),
  forgotPassword: (email) => api.post('/auth/forgot-password/', { email }),
  changePassword: (data) => api.post('/auth/change-password/', data),
}

// ── Audit Logs ─────────────────────────────────────────────────────────────
export const auditLogs = {
  list: (p) => api.get('/audit-logs/', { params: p }),
  get: (id) => api.get(`/audit-logs/${id}/`),
}

// ── PBX Resources ──────────────────────────────────────────────────────────
export const extensions = {
  list: (p) => api.get('/extensions/', { params: p }),
  get: (id) => api.get(`/extensions/${id}/`),
  create: (data) => api.post('/extensions/', data),
  update: (id, data) => api.put(`/extensions/${id}/`, data),
  patch: (id, data) => api.patch(`/extensions/${id}/`, data),
  delete: (id) => api.delete(`/extensions/${id}/`),
  bulkDelete: (ids) => api.post('/extensions/bulk_delete/', { ids }),
  reload: () => api.post('/extensions/reload/'),
  checkNumber: (number, excludePk) => api.get('/extensions/check_number/', { params: { number, ...(excludePk ? { exclude_pk: excludePk } : {}) } }),
  exportGrandstream: (p) => api.get('/extensions/export_grandstream/', { params: p, responseType: 'blob' }),
}

export const dialplans = {
  list: (p) => api.get('/dialplans/', { params: p }),
  get: (id) => api.get(`/dialplans/${id}/`),
  create: (data) => api.post('/dialplans/', data),
  update: (id, data) => api.put(`/dialplans/${id}/`, data),
  delete: (id) => api.delete(`/dialplans/${id}/`),
}

export const voicemails = {
  list: (p) => api.get('/voicemails/', { params: p }),
  get: (id) => api.get(`/voicemails/${id}/`),
  create: (data) => api.post('/voicemails/', data),
  update: (id, data) => api.put(`/voicemails/${id}/`, data),
  delete: (id) => api.delete(`/voicemails/${id}/`),
  uploadName: (id, formData) => api.post(`/voicemails/${id}/upload_name/`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  }),
}

export const voicemailMessages = {
  list: (p) => api.get('/voicemail-messages/', { params: p }),
  markRead: (uuid) => api.post(`/voicemail-messages/${uuid}/mark_read/`),
  markUnread: (uuid) => api.post(`/voicemail-messages/${uuid}/mark_unread/`),
  delete: (uuid) => api.delete(`/voicemail-messages/${uuid}/`),
  fetchAudio: (uuid) => api.get(`/voicemail-messages/${uuid}/audio/`, { responseType: 'blob' }),
}

export const systemLog = {
  fetch: (params) => api.get('/client/system-log/', { params }),
}

export const gateways = {
  list: (p) => api.get('/gateways/', { params: p }),
  get: (id) => api.get(`/gateways/${id}/`),
  create: (data) => api.post('/gateways/', data),
  update: (id, data) => api.put(`/gateways/${id}/`, data),
  delete: (id) => api.delete(`/gateways/${id}/`),
  statuses: () => api.get('/gateways/statuses/'),
  status: (id) => api.get(`/gateways/${id}/status/`),
  reload: () => api.post('/gateways/reload/'),
}

export const ringGroups = {
  list: (p) => api.get('/ring-groups/', { params: p }),
  get: (id) => api.get(`/ring-groups/${id}/`),
  create: (data) => api.post('/ring-groups/', data),
  update: (id, data) => api.put(`/ring-groups/${id}/`, data),
  delete: (id) => api.delete(`/ring-groups/${id}/`),
}

export const ivrMenus = {
  list: (p) => api.get('/ivr-menus/', { params: p }),
  get: (id) => api.get(`/ivr-menus/${id}/`),
  create: (data) => api.post('/ivr-menus/', data),
  update: (id, data) => api.put(`/ivr-menus/${id}/`, data),
  delete: (id) => api.delete(`/ivr-menus/${id}/`),
}

export const callCenters = {
  list: (p) => api.get('/call-centers/', { params: p }),
  get: (id) => api.get(`/call-centers/${id}/`),
  create: (data) => api.post('/call-centers/', data),
  update: (id, data) => api.put(`/call-centers/${id}/`, data),
  delete: (id) => api.delete(`/call-centers/${id}/`),
}

export const conferences = {
  list: (p) => api.get('/conferences/', { params: p }),
  get: (id) => api.get(`/conferences/${id}/`),
  create: (data) => api.post('/conferences/', data),
  update: (id, data) => api.put(`/conferences/${id}/`, data),
  delete: (id) => api.delete(`/conferences/${id}/`),
}

export const musicOnHold = {
  list: (p) => api.get('/music-on-hold/', { params: p }),
}

export const callParking = {
  list: (p) => api.get('/call-parking/', { params: p }),
  get: (id) => api.get(`/call-parking/${id}/`),
  create: (data) => api.post('/call-parking/', data),
  update: (id, data) => api.put(`/call-parking/${id}/`, data),
  delete: (id) => api.delete(`/call-parking/${id}/`),
  bulkCreate: (data, tenantUuid) => api.post('/call-parking/bulk_create/', data, tenantUuid ? { params: { tenant: tenantUuid } } : {}),
}

export const fax = {
  list: (p) => api.get('/fax/', { params: p }),
  get: (id) => api.get(`/fax/${id}/`),
  create: (data) => api.post('/fax/', data),
  update: (id, data) => api.put(`/fax/${id}/`, data),
  patch: (id, data) => api.patch(`/fax/${id}/`, data),
  delete: (id) => api.delete(`/fax/${id}/`),
  send: (id, formData) => api.post(`/fax/${id}/send/`, formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  quickSend: (formData) => api.post('/fax/quick-send/', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  files: (p) => api.get('/fax/files/', { params: p }),
  cancelFile: (fileId) => api.post(`/fax/files/${fileId}/cancel/`),
}

export const devices = {
  list: (p) => api.get('/devices/', { params: p }),
  get: (id) => api.get(`/devices/${id}/`),
  create: (data) => api.post('/devices/', data),
  update: (id, data) => api.put(`/devices/${id}/`, data),
  delete: (id) => api.delete(`/devices/${id}/`),
}

export const cdr = {
  list: (p) => api.get('/cdr/', { params: p }),
  summary: (p) => api.get('/cdr/summary/', { params: p }),
  export: (p) => api.get('/cdr/export/', { params: p, responseType: 'blob' }),
  legs: (id) => api.get(`/cdr/${id}/legs/`),
  pcap: (id) => api.get(`/cdr/${id}/pcap/`),
  pcapDownload: (id, legUuid) =>
    api.get(`/cdr/${id}/pcap/${legUuid}/download/`, { responseType: 'blob' }),
  // HOMER-backed SIP search (tenant-scoped). Params: number, extension, call_id,
  // from/to (date or datetime), date, date_from/date_to, page, page_size, tenant (superadmin).
  homerSearch: (p) => api.get('/cdr/homer-search/', { params: p }),
  // Decoded SIP ladder (frames) for one Call-ID from a HOMER search result.
  homerLadder: (p) => api.get('/cdr/homer-ladder/', { params: p }),
}

export const statsReport = {
  get: (p) => api.get('/client/stats-report/', { params: p }),
}

export const freeswitch = {
  status: () => api.get('/freeswitch/status/'),
  calls: () => api.get('/freeswitch/calls/'),
  callsByTenant: () => api.get('/freeswitch/calls-by-tenant/'),
  registrations: () => api.get('/freeswitch/registrations/'),
  allRegistrations: () => api.get('/freeswitch/registrations/', { params: { tenant: null } }),
  extensionStatus: () => api.get('/freeswitch/extension-status/'),
  deregister: (call_id, profile = 'internal', tenant_code = '') => api.post('/freeswitch/deregister/', { call_id, profile, tenant_code }),
  reboot: (call_id, profile = 'internal', tenant_code = '') => api.post('/freeswitch/reboot/', { call_id, profile, tenant_code }),
  peerHistory: (user, days = 5) => api.get('/freeswitch/peer-history/', { params: { user, days } }),
  sofia: () => api.get('/freeswitch/sofia/'),
  dbStats: () => api.get('/freeswitch/db-stats/'),
  log: (params) => api.get('/freeswitch/log/', { params }),
  serverHealth: () => api.get('/freeswitch/server-health/'),
  originate: (data) => api.post('/freeswitch/originate/', data),
  hangup: (data) => api.post('/freeswitch/hangup/', data),
  transfer: (data) => api.post('/freeswitch/transfer/', data),
  eavesdrop: (data) => api.post('/freeswitch/eavesdrop/', data),
}

export const domains = {
  list: (p) => api.get('/domains/', { params: p }),
  get: (id) => api.get(`/domains/${id}/`),
  create: (data) => api.post('/domains/', data),
  update: (id, data) => api.put(`/domains/${id}/`, data),
  delete: (id) => api.delete(`/domains/${id}/`),
}

export const tenants = {
  list: (p) => api.get('/tenants/', { params: p }),
  get: (id) => api.get(`/tenants/${id}/`),
  create: (data) => api.post('/tenants/', data),
  update: (id, data) => api.put(`/tenants/${id}/`, data),
  patch: (id, data) => api.patch(`/tenants/${id}/`, data),
  delete: (id) => api.delete(`/tenants/${id}/`),
  applyRecording: (id) => api.post(`/tenants/${id}/apply-recording/`),
  applyPushNotifications: (id) => api.post(`/tenants/${id}/apply-push-notifications/`),
}

export const users = {
  list: (p) => api.get('/users/', { params: p }),
  get: (id) => api.get(`/users/${id}/`, { params: { tenant: null } }),
  create: (data) => api.post('/users/', data, { params: { tenant: null } }),
  update: (id, data) => api.put(`/users/${id}/`, data, { params: { tenant: null } }),
  delete: (id) => api.delete(`/users/${id}/`, { params: { tenant: null } }),
}

const ORG_API_BASE_URL = import.meta.env.VITE_ORG_API_BASE_URL || 'https://api.ihsphone.com'
const ORG_API_TOKEN = 'django-secure-p=bnajkpqq2_(l3)1$$vaf($jq#uw7qdysxi3$one3p$=55_'

const orgAxios = axios.create({
  baseURL: ORG_API_BASE_URL,
  headers: { Authorization: `Bearer ${ORG_API_TOKEN}` },
})

export const organizations = {
  list: ({ search = '', page = 1, page_size = 10, is_active } = {}) => {
    const params = { search, page, page_size }
    if (is_active !== undefined) params.is_active = is_active
    return orgAxios.get('/company/listPBXCompany', { params })
  },
  // Full unpaginated company list — used to populate the company filter dropdown.
  listAll: () => orgAxios.get('/company/listPBXCompany', { params: { data_all: true } }),
  // POST /company/companyEditPBX
  // Payload: { id, useremail (logged-in PBX user), voiceenable, smsenable, faxenable, is_active }
  update: (data) => orgAxios.post('/company/companyEditPBX', data),
}

// ── UC Users (external IHS Phone user directory) ──────────────────────────────
export const ucUsers = {
  // GET /user/listpbx?search=&page=&page_size=&is_active=&code=
  // `code` scopes to a company; omit it (undefined) for all companies.
  // Returns { success: [...users], pagination: {...} }.
  list: ({ search = '', page = 1, page_size = 20, is_active, code, usertype } = {}) => {
    const params = { search, page, page_size }
    if (is_active !== undefined) params.is_active = is_active
    if (code) params.code = code
    // usertype may be a comma-joined list of selected types (omit when empty).
    if (usertype) params.usertype = usertype
    return orgAxios.get('/user/listpbx', { params })
  },
  // POST /user/editTokenpbx — send `userid` plus only the changed fields.
  update: (data) => orgAxios.post('/user/editTokenpbx', data),
  // DELETE /user/deletepbx/{uuid} — hard delete. Body carries the acting user's email.
  delete: (uuid, useremail) => orgAxios.delete(`/user/deletepbx/${uuid}`, { data: { useremail } }),
  // POST /user/userNotify — send a password-reset notification. `userid` is the numeric id.
  notify: (userid) => orgAxios.post('/user/userNotify', { userid }),
  // POST /user/useraddpbx — create a UC user.
  create: (data) => orgAxios.post('/user/useraddpbx', data),
}

export const firewall = {
  fail2banStatus: () => api.get('/firewall/fail2ban/'),
  ban: (data) => api.post('/firewall/fail2ban/ban/', data),
  unban: (data) => api.post('/firewall/fail2ban/unban/', data),
  whitelist: (data) => api.post('/firewall/fail2ban/whitelist/', data),
  ufwStatus: () => api.get('/firewall/ufw/'),
  checkIp: (ip) => api.get('/firewall/iptables/', { params: { ip } }),
  unblockIp: (data) => api.delete('/firewall/iptables/', { data }),
}

export const outboundRoutes = {
  list: (p) => api.get('/outbound-routes/', { params: p }),
  get: (id) => api.get(`/outbound-routes/${id}/`),
  create: (data) => api.post('/outbound-routes/', data),
  update: (id, data) => api.put(`/outbound-routes/${id}/`, data),
  delete: (id) => api.delete(`/outbound-routes/${id}/`),
  reload: () => api.post('/outbound-routes/reload/'),
}

export const workingHours = {
  list: (p) => api.get('/working-hours/', { params: p }),
  get: (id) => api.get(`/working-hours/${id}/`),
  create: (data) => api.post('/working-hours/', data),
  update: (id, data) => api.put(`/working-hours/${id}/`, data),
  delete: (id) => api.delete(`/working-hours/${id}/`),
  days: {
    list: (p) => api.get('/working-hours/days/', { params: p }),
    create: (data) => api.post('/working-hours/days/', data),
    update: (id, data) => api.put(`/working-hours/days/${id}/`, data),
    delete: (id) => api.delete(`/working-hours/days/${id}/`),
  },
  holidays: {
    list: (p) => api.get('/working-hours/holidays/', { params: p }),
    create: (data) => api.post('/working-hours/holidays/', data),
    delete: (id) => api.delete(`/working-hours/holidays/${id}/`),
  },
}

export const customDestinations = {
  list: (p) => api.get('/custom-destinations/', { params: p }),
  get: (id) => api.get(`/custom-destinations/${id}/`),
  create: (data) => api.post('/custom-destinations/', data),
  update: (id, data) => api.put(`/custom-destinations/${id}/`, data),
  delete: (id) => api.delete(`/custom-destinations/${id}/`),
  affinityStats: (params) => api.get('/custom-destinations/affinity-stats/', { params }),
  affinityCreate: (data) => api.post('/custom-destinations/affinity/', data),
  affinityUpdate: (id, data) => api.patch(`/custom-destinations/affinity/${id}/`, data),
  affinityDelete: (id) => api.delete(`/custom-destinations/affinity/${id}/`),
  toggleState: (id) => api.get(`/custom-destinations/${id}/toggle-state/`),
  setToggleState: (id, state) => api.post(`/custom-destinations/${id}/set-state/`, { state }),
  resyncToggles: () => api.post('/custom-destinations/resync-toggles/'),
}

export const recordings = {
  list: (p) => api.get('/recordings/', { params: p }),
  get: (id) => api.get(`/recordings/${id}/`),
  create: (data) => api.post('/recordings/', data),
  update: (id, data) => api.put(`/recordings/${id}/`, data),
  delete: (id) => api.delete(`/recordings/${id}/`),
  recordCall: (data) => api.post('/recordings/record_call/', data),
  streamMediaFile: (id) => api.get(`/recordings/${id}/stream/`, { responseType: 'blob' }),
  callRecordings: (p) => api.get('/recordings/call-recordings/', { params: p }),
  syncCallRecordings: () => api.post('/recordings/call-recordings/sync/'),
  streamRecording: (id) => api.get(`/recordings/call-recordings/${id}/stream/`, { responseType: 'blob' }),
  downloadRecording: (id) => api.get(`/recordings/call-recordings/${id}/stream/`, { params: { download: 1 }, responseType: 'blob' }),
}

export const callFlows = {
  list: (p) => api.get('/call-flows/', { params: p }),
  get: (id) => api.get(`/call-flows/${id}/`),
  create: (data) => api.post('/call-flows/', data),
  update: (id, data) => api.put(`/call-flows/${id}/`, data),
  delete: (id) => api.delete(`/call-flows/${id}/`),
  toggle: (id) => api.post(`/call-flows/${id}/toggle/`),
}

export const destinations = {
  list: (p) => api.get('/destinations/', { params: p }),
  get: (id) => api.get(`/destinations/${id}/`),
  create: (data) => api.post('/destinations/', data),
  update: (id, data) => api.put(`/destinations/${id}/`, data),
  delete: (id) => api.delete(`/destinations/${id}/`),
}

export const clientApiKeys = {
  list: (p) => api.get('/client/api-keys/', { params: p }),
  get: (id) => api.get(`/client/api-keys/${id}/`),
  create: (data) => api.post('/client/api-keys/', data),
  update: (id, data) => api.patch(`/client/api-keys/${id}/`, data),
  delete: (id) => api.delete(`/client/api-keys/${id}/`),
}

export const freeswitchCache = {
  // /xml-curl/ is outside /api/v1/ — use root-relative URL with the shared intercepted instance
  flush: () => api.post('/xml-curl/cache/flush/', {}, { baseURL: '' }),
}
