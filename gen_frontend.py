#!/usr/bin/env python3
"""
gen_frontend.py - Vue 3 + Vite + Pinia + PrimeVue frontend scaffold
"""
import os, textwrap, json

ROOT = os.path.join(os.path.dirname(__file__), 'frontend')

def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(textwrap.dedent(content).lstrip('\n'))
    print(f'  WROTE {os.path.relpath(path, ROOT)}')

# ── package.json ────────────────────────────────────────────────────────────
pkg = {
  "name": "ihspbx-frontend",
  "version": "1.0.0",
  "private": True,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.3.0",
    "pinia": "^2.1.7",
    "axios": "^1.6.0",
    "primevue": "^3.53.0",
    "primeicons": "^6.0.1",
    "@primevue/themes": "^4.0.0",
    "primeflex": "^3.3.1",
    "chart.js": "^4.4.0",
    "vue-chartjs": "^5.3.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^5.0.0"
  }
}
os.makedirs(ROOT, exist_ok=True)
with open(os.path.join(ROOT, 'package.json'), 'w') as f:
    json.dump(pkg, f, indent=2)
print('  WROTE package.json')

# ── vite.config.js ──────────────────────────────────────────────────────────
write(os.path.join(ROOT, 'vite.config.js'), """
    import { defineConfig } from 'vite'
    import vue from '@vitejs/plugin-vue'
    import { fileURLToPath, URL } from 'node:url'

    export default defineConfig({
      plugins: [vue()],
      resolve: {
        alias: {
          '@': fileURLToPath(new URL('./src', import.meta.url))
        }
      },
      server: {
        proxy: {
          '/api': {
            target: 'http://localhost:8000',
            changeOrigin: true
          },
          '/ws': {
            target: 'ws://localhost:8000',
            ws: true,
            changeOrigin: true
          }
        }
      }
    })
""")

# ── index.html ───────────────────────────────────────────────────────────────
write(os.path.join(ROOT, 'index.html'), """
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8" />
      <link rel="icon" type="image/svg+xml" href="/favicon.ico" />
      <meta name="viewport" content="width=device-width, initial-scale=1.0" />
      <title>ihspbx</title>
      <link rel="stylesheet" href="https://unpkg.com/primeflex@3.3.1/primeflex.css" />
      <link rel="stylesheet" href="https://unpkg.com/primeicons/primeicons.css" />
    </head>
    <body>
      <div id="app"></div>
      <script type="module" src="/src/main.js"></script>
    </body>
    </html>
""")

src = os.path.join(ROOT, 'src')

# ── src/main.js ──────────────────────────────────────────────────────────────
write(os.path.join(src, 'main.js'), """
    import { createApp } from 'vue'
    import { createPinia } from 'pinia'
    import PrimeVue from 'primevue/config'
    import Aura from '@primevue/themes/aura'
    import ToastService from 'primevue/toastservice'
    import ConfirmationService from 'primevue/confirmationservice'
    import 'primeicons/primeicons.css'

    import App from './App.vue'
    import router from './router'

    const app = createApp(App)

    app.use(createPinia())
    app.use(router)
    app.use(PrimeVue, {
      theme: {
        preset: Aura,
        options: { darkModeSelector: '.dark-mode' }
      }
    })
    app.use(ToastService)
    app.use(ConfirmationService)

    app.mount('#app')
""")

# ── src/App.vue ───────────────────────────────────────────────────────────────
write(os.path.join(src, 'App.vue'), """
    <template>
      <RouterView />
      <Toast position="top-right" />
      <ConfirmDialog />
    </template>

    <script setup>
    import Toast from 'primevue/toast'
    import ConfirmDialog from 'primevue/confirmdialog'
    </script>

    <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; }
    </style>
""")

# ── src/api/index.js ──────────────────────────────────────────────────────────
os.makedirs(os.path.join(src, 'api'), exist_ok=True)
write(os.path.join(src, 'api', 'index.js'), """
    import axios from 'axios'

    const api = axios.create({
      baseURL: '/api/v1',
      timeout: 15000,
      headers: { 'Content-Type': 'application/json' }
    })

    // Attach JWT token to every request
    api.interceptors.request.use(config => {
      const token = localStorage.getItem('access_token')
      if (token) config.headers.Authorization = `Bearer ${token}`
      return config
    })

    // Auto-refresh on 401
    api.interceptors.response.use(
      res => res,
      async err => {
        const original = err.config
        if (err.response?.status === 401 && !original._retry) {
          original._retry = true
          try {
            const refresh = localStorage.getItem('refresh_token')
            const { data } = await axios.post('/api/v1/auth/refresh/', { refresh })
            localStorage.setItem('access_token', data.access)
            original.headers.Authorization = `Bearer ${data.access}`
            return api(original)
          } catch {
            localStorage.removeItem('access_token')
            localStorage.removeItem('refresh_token')
            window.location.href = '/login'
          }
        }
        return Promise.reject(err)
      }
    )

    export default api

    // ── Resource helpers ──────────────────────────────────────────────────────
    export const auth = {
      login: (data) => api.post('/auth/login/', data),
      logout: (refresh) => api.post('/auth/logout/', { refresh }),
      me: () => api.get('/auth/me/'),
    }

    export const extensions = {
      list: (p) => api.get('/extensions/', { params: p }),
      get: (id) => api.get(`/extensions/${id}/`),
      create: (data) => api.post('/extensions/', data),
      update: (id, data) => api.put(`/extensions/${id}/`, data),
      patch: (id, data) => api.patch(`/extensions/${id}/`, data),
      delete: (id) => api.delete(`/extensions/${id}/`),
      reload: () => api.post('/extensions/reload/'),
    }

    export const dialplans = {
      list: (p) => api.get('/dialplans/', { params: p }),
      get: (id) => api.get(`/dialplans/${id}/`),
      create: (data) => api.post('/dialplans/', data),
      update: (id, data) => api.put(`/dialplans/${id}/`, data),
      delete: (id) => api.delete(`/dialplans/${id}/`),
      reload: () => api.post('/dialplans/reload/'),
    }

    export const voicemails = {
      list: (p) => api.get('/voicemails/', { params: p }),
      get: (id) => api.get(`/voicemails/${id}/`),
      create: (data) => api.post('/voicemails/', data),
      update: (id, data) => api.put(`/voicemails/${id}/`, data),
      delete: (id) => api.delete(`/voicemails/${id}/`),
      messages: (id) => api.get(`/voicemails/${id}/messages/`),
      deleteMessage: (id, msgId) => api.delete(`/voicemails/${id}/delete_message/`, { data: { message_uuid: msgId } }),
    }

    export const gateways = {
      list: (p) => api.get('/gateways/', { params: p }),
      get: (id) => api.get(`/gateways/${id}/`),
      create: (data) => api.post('/gateways/', data),
      update: (id, data) => api.put(`/gateways/${id}/`, data),
      delete: (id) => api.delete(`/gateways/${id}/`),
      status: (id) => api.get(`/gateways/${id}/status/`),
      reload: (id) => api.post(`/gateways/${id}/reload/`),
    }

    export const cdr = {
      list: (p) => api.get('/cdr/', { params: p }),
      summary: (p) => api.get('/cdr/summary/', { params: p }),
    }

    export const freeswitch = {
      status: () => api.get('/freeswitch/status/'),
      calls: () => api.get('/freeswitch/calls/'),
      registrations: () => api.get('/freeswitch/registrations/'),
      originate: (data) => api.post('/freeswitch/originate/', data),
      hangup: (data) => api.post('/freeswitch/hangup/', data),
      transfer: (data) => api.post('/freeswitch/transfer/', data),
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

    export const devices = {
      list: (p) => api.get('/devices/', { params: p }),
      get: (id) => api.get(`/devices/${id}/`),
      create: (data) => api.post('/devices/', data),
      update: (id, data) => api.put(`/devices/${id}/`, data),
      delete: (id) => api.delete(`/devices/${id}/`),
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

    export const domains = {
      list: (p) => api.get('/domains/', { params: p }),
      get: (id) => api.get(`/domains/${id}/`),
      create: (data) => api.post('/domains/', data),
      update: (id, data) => api.put(`/domains/${id}/`, data),
      delete: (id) => api.delete(`/domains/${id}/`),
    }

    export const users = {
      list: (p) => api.get('/users/', { params: p }),
      get: (id) => api.get(`/users/${id}/`),
      create: (data) => api.post('/users/', data),
      update: (id, data) => api.put(`/users/${id}/`, data),
      delete: (id) => api.delete(`/users/${id}/`),
    }
""")

# ── src/stores/auth.js ────────────────────────────────────────────────────────
os.makedirs(os.path.join(src, 'stores'), exist_ok=True)
write(os.path.join(src, 'stores', 'auth.js'), """
    import { defineStore } from 'pinia'
    import { ref, computed } from 'vue'
    import { auth as authApi } from '@/api'

    export const useAuthStore = defineStore('auth', () => {
      const user = ref(null)
      const accessToken = ref(localStorage.getItem('access_token'))
      const refreshToken = ref(localStorage.getItem('refresh_token'))

      const isAuthenticated = computed(() => !!accessToken.value)
      const isAdmin = computed(() => user.value?.is_superuser || false)

      async function login(username, password) {
        const { data } = await authApi.login({ username, password })
        accessToken.value = data.access
        refreshToken.value = data.refresh
        localStorage.setItem('access_token', data.access)
        localStorage.setItem('refresh_token', data.refresh)
        user.value = data.user
        return data
      }

      async function logout() {
        try {
          await authApi.logout(refreshToken.value)
        } catch {}
        accessToken.value = null
        refreshToken.value = null
        user.value = null
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
      }

      async function fetchMe() {
        const { data } = await authApi.me()
        user.value = data
        return data
      }

      return { user, accessToken, refreshToken, isAuthenticated, isAdmin, login, logout, fetchMe }
    })
""")

write(os.path.join(src, 'stores', 'domain.js'), """
    import { defineStore } from 'pinia'
    import { ref } from 'vue'
    import { domains } from '@/api'

    export const useDomainStore = defineStore('domain', () => {
      const currentDomain = ref(null)
      const domainList = ref([])

      async function fetchDomains() {
        const { data } = await domains.list({ page_size: 200 })
        domainList.value = data.results || data
        return domainList.value
      }

      function setDomain(domain) {
        currentDomain.value = domain
      }

      return { currentDomain, domainList, fetchDomains, setDomain }
    })
""")

# ── src/router/index.js ───────────────────────────────────────────────────────
os.makedirs(os.path.join(src, 'router'), exist_ok=True)
write(os.path.join(src, 'router', 'index.js'), """
    import { createRouter, createWebHistory } from 'vue-router'
    import { useAuthStore } from '@/stores/auth'

    const routes = [
      {
        path: '/login',
        name: 'Login',
        component: () => import('@/views/LoginView.vue'),
        meta: { public: true }
      },
      {
        path: '/',
        component: () => import('@/components/AppLayout.vue'),
        meta: { requiresAuth: true },
        children: [
          { path: '', name: 'Dashboard', component: () => import('@/views/DashboardView.vue') },
          { path: 'extensions', name: 'Extensions', component: () => import('@/views/ExtensionsView.vue') },
          { path: 'dialplans', name: 'Dialplans', component: () => import('@/views/DialplansView.vue') },
          { path: 'voicemails', name: 'Voicemails', component: () => import('@/views/VoicemailsView.vue') },
          { path: 'gateways', name: 'Gateways', component: () => import('@/views/GatewaysView.vue') },
          { path: 'ring-groups', name: 'RingGroups', component: () => import('@/views/RingGroupsView.vue') },
          { path: 'ivr-menus', name: 'IvrMenus', component: () => import('@/views/IvrMenusView.vue') },
          { path: 'call-centers', name: 'CallCenters', component: () => import('@/views/CallCentersView.vue') },
          { path: 'conferences', name: 'Conferences', component: () => import('@/views/ConferencesView.vue') },
          { path: 'devices', name: 'Devices', component: () => import('@/views/DevicesView.vue') },
          { path: 'cdr', name: 'CDR', component: () => import('@/views/CdrView.vue') },
          { path: 'active-calls', name: 'ActiveCalls', component: () => import('@/views/ActiveCallsView.vue') },
          { path: 'operator-panel', name: 'OperatorPanel', component: () => import('@/views/OperatorPanelView.vue') },
          { path: 'domains', name: 'Domains', component: () => import('@/views/DomainsView.vue') },
          { path: 'users', name: 'Users', component: () => import('@/views/UsersView.vue') },
          { path: 'freeswitch', name: 'FreeSWITCH', component: () => import('@/views/FreeSwitchView.vue') },
        ]
      },
      { path: '/:pathMatch(.*)*', redirect: '/' }
    ]

    const router = createRouter({
      history: createWebHistory(),
      routes
    })

    router.beforeEach(async (to) => {
      const auth = useAuthStore()
      if (!to.meta.public && !auth.isAuthenticated) {
        return { name: 'Login' }
      }
    })

    export default router
""")

# ── src/components/AppLayout.vue ──────────────────────────────────────────────
os.makedirs(os.path.join(src, 'components'), exist_ok=True)
write(os.path.join(src, 'components', 'AppLayout.vue'), """
    <template>
      <div class="layout-wrapper">
        <!-- Sidebar -->
        <aside class="layout-sidebar" :class="{ collapsed: sidebarCollapsed }">
          <div class="sidebar-header">
            <img src="/logo.svg" alt="ihspbx" class="logo" v-if="!sidebarCollapsed" />
            <Button icon="pi pi-bars" text rounded @click="toggleSidebar" />
          </div>
          <nav>
            <ul class="nav-menu">
              <li v-for="item in menuItems" :key="item.to">
                <RouterLink :to="item.to" class="nav-link" active-class="nav-link--active">
                  <i :class="item.icon" />
                  <span v-if="!sidebarCollapsed">{{ item.label }}</span>
                </RouterLink>
              </li>
            </ul>
          </nav>
        </aside>

        <!-- Main content -->
        <div class="layout-main">
          <header class="layout-topbar">
            <span class="topbar-title">{{ currentPageTitle }}</span>
            <div class="topbar-actions">
              <DomainSelector />
              <Button icon="pi pi-moon" text rounded @click="toggleDark" />
              <Button :label="auth.user?.username" icon="pi pi-user" text @click="showUserMenu = true" />
              <Button icon="pi pi-sign-out" text rounded severity="secondary" @click="handleLogout" />
            </div>
          </header>
          <main class="layout-content">
            <RouterView />
          </main>
        </div>
      </div>
    </template>

    <script setup>
    import { ref, computed } from 'vue'
    import { useRouter, useRoute } from 'vue-router'
    import { useAuthStore } from '@/stores/auth'
    import Button from 'primevue/button'
    import DomainSelector from './DomainSelector.vue'

    const auth = useAuthStore()
    const router = useRouter()
    const route = useRoute()

    const sidebarCollapsed = ref(false)
    const showUserMenu = ref(false)

    const menuItems = [
      { to: '/', label: 'Dashboard', icon: 'pi pi-home' },
      { to: '/extensions', label: 'Extensions', icon: 'pi pi-phone' },
      { to: '/dialplans', label: 'Dialplans', icon: 'pi pi-sitemap' },
      { to: '/voicemails', label: 'Voicemails', icon: 'pi pi-inbox' },
      { to: '/gateways', label: 'Gateways', icon: 'pi pi-globe' },
      { to: '/ring-groups', label: 'Ring Groups', icon: 'pi pi-users' },
      { to: '/ivr-menus', label: 'IVR Menus', icon: 'pi pi-th-large' },
      { to: '/call-centers', label: 'Call Centers', icon: 'pi pi-headphones' },
      { to: '/conferences', label: 'Conferences', icon: 'pi pi-comments' },
      { to: '/devices', label: 'Devices', icon: 'pi pi-mobile' },
      { to: '/cdr', label: 'Call Records', icon: 'pi pi-list' },
      { to: '/active-calls', label: 'Active Calls', icon: 'pi pi-circle-fill' },
      { to: '/operator-panel', label: 'Operator Panel', icon: 'pi pi-desktop' },
      { to: '/freeswitch', label: 'FreeSWITCH', icon: 'pi pi-server' },
      { to: '/domains', label: 'Domains', icon: 'pi pi-building' },
      { to: '/users', label: 'Users', icon: 'pi pi-user-edit' },
    ]

    const currentPageTitle = computed(() => route.name || 'Dashboard')

    function toggleSidebar() { sidebarCollapsed.value = !sidebarCollapsed.value }
    function toggleDark() { document.body.classList.toggle('dark-mode') }
    async function handleLogout() {
      await auth.logout()
      router.push('/login')
    }
    </script>

    <style scoped>
    .layout-wrapper { display: flex; height: 100vh; overflow: hidden; }
    .layout-sidebar { width: 240px; background: #1e293b; color: #e2e8f0; transition: width 0.2s; display: flex; flex-direction: column; }
    .layout-sidebar.collapsed { width: 60px; }
    .sidebar-header { display: flex; align-items: center; justify-content: space-between; padding: 1rem; border-bottom: 1px solid #334155; }
    .logo { height: 32px; }
    .nav-menu { list-style: none; padding: 0.5rem 0; flex: 1; overflow-y: auto; }
    .nav-link { display: flex; align-items: center; gap: 0.75rem; padding: 0.6rem 1rem; color: #94a3b8; text-decoration: none; border-radius: 6px; margin: 2px 8px; transition: all 0.15s; font-size: 0.9rem; }
    .nav-link:hover { background: #334155; color: #e2e8f0; }
    .nav-link--active { background: #3b82f6; color: #fff; }
    .layout-main { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
    .layout-topbar { height: 60px; background: #fff; border-bottom: 1px solid #e2e8f0; display: flex; align-items: center; justify-content: space-between; padding: 0 1.5rem; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
    .topbar-title { font-weight: 600; font-size: 1.1rem; color: #1e293b; }
    .topbar-actions { display: flex; align-items: center; gap: 0.5rem; }
    .layout-content { flex: 1; overflow-y: auto; padding: 1.5rem; background: #f8fafc; }
    </style>
""")

write(os.path.join(src, 'components', 'DomainSelector.vue'), """
    <template>
      <Select v-model="selected" :options="store.domainList" optionLabel="domain_name"
              optionValue="domain_uuid" placeholder="Select Domain" class="w-13rem"
              @change="store.setDomain(selected)" />
    </template>

    <script setup>
    import { ref, onMounted } from 'vue'
    import Select from 'primevue/select'
    import { useDomainStore } from '@/stores/domain'

    const store = useDomainStore()
    const selected = ref(null)

    onMounted(() => store.fetchDomains())
    </script>
""")

# ── Views ────────────────────────────────────────────────────────────────────
views = os.path.join(src, 'views')
os.makedirs(views, exist_ok=True)

# Login
write(os.path.join(views, 'LoginView.vue'), """
    <template>
      <div class="login-page">
        <Card class="login-card">
          <template #header>
            <div class="login-header">
              <h2>ihspbx</h2>
              <p>Sign in to your account</p>
            </div>
          </template>
          <template #content>
            <form @submit.prevent="handleLogin">
              <div class="field">
                <label for="username">Username</label>
                <InputText id="username" v-model="form.username" autofocus class="w-full" />
              </div>
              <div class="field mt-3">
                <label for="password">Password</label>
                <Password id="password" v-model="form.password" :feedback="false" toggleMask class="w-full" inputClass="w-full" />
              </div>
              <div v-if="error" class="mt-3">
                <Message severity="error">{{ error }}</Message>
              </div>
              <Button type="submit" label="Sign In" icon="pi pi-sign-in" class="w-full mt-4" :loading="loading" />
            </form>
          </template>
        </Card>
      </div>
    </template>

    <script setup>
    import { ref } from 'vue'
    import { useRouter } from 'vue-router'
    import { useAuthStore } from '@/stores/auth'
    import Card from 'primevue/card'
    import InputText from 'primevue/inputtext'
    import Password from 'primevue/password'
    import Button from 'primevue/button'
    import Message from 'primevue/message'

    const auth = useAuthStore()
    const router = useRouter()

    const form = ref({ username: '', password: '' })
    const loading = ref(false)
    const error = ref('')

    async function handleLogin() {
      loading.value = true
      error.value = ''
      try {
        await auth.login(form.value.username, form.value.password)
        router.push('/')
      } catch (e) {
        error.value = e.response?.data?.message || 'Invalid credentials'
      } finally {
        loading.value = false
      }
    }
    </script>

    <style scoped>
    .login-page { min-height: 100vh; display: flex; align-items: center; justify-content: center; background: #f0f4f8; }
    .login-card { width: 400px; }
    .login-header { text-align: center; padding: 1.5rem 1.5rem 0; }
    .login-header h2 { font-size: 1.8rem; color: #1e293b; margin-bottom: 0.25rem; }
    .login-header p { color: #64748b; margin: 0; }
    .field label { display: block; font-weight: 500; margin-bottom: 0.4rem; color: #374151; }
    </style>
""")

# Dashboard
write(os.path.join(views, 'DashboardView.vue'), """
    <template>
      <div>
        <h1 class="page-title">Dashboard</h1>

        <!-- Stats row -->
        <div class="grid">
          <div class="col-12 md:col-3" v-for="stat in stats" :key="stat.label">
            <Card class="stat-card">
              <template #content>
                <div class="stat-content">
                  <div class="stat-icon" :style="{ background: stat.color }">
                    <i :class="stat.icon" />
                  </div>
                  <div>
                    <div class="stat-value">{{ stat.value }}</div>
                    <div class="stat-label">{{ stat.label }}</div>
                  </div>
                </div>
              </template>
            </Card>
          </div>
        </div>

        <!-- Active calls table -->
        <Card class="mt-4">
          <template #title>Active Calls</template>
          <template #content>
            <DataTable :value="activeCalls" :loading="loading" size="small"
                       scrollable scrollHeight="300px">
              <Column field="caller_id_number" header="Caller" />
              <Column field="destination_number" header="Destination" />
              <Column field="state" header="State" />
              <Column field="duration" header="Duration" />
              <Column header="Actions">
                <template #body="{ data }">
                  <Button icon="pi pi-times" severity="danger" text rounded size="small"
                          @click="hangup(data.uuid)" title="Hangup" />
                </template>
              </Column>
            </DataTable>
          </template>
        </Card>
      </div>
    </template>

    <script setup>
    import { ref, onMounted, onUnmounted } from 'vue'
    import Card from 'primevue/card'
    import DataTable from 'primevue/datatable'
    import Column from 'primevue/column'
    import Button from 'primevue/button'
    import { useToast } from 'primevue/usetoast'
    import { freeswitch } from '@/api'

    const toast = useToast()
    const loading = ref(false)
    const activeCalls = ref([])
    const stats = ref([
      { label: 'Active Calls', value: 0, icon: 'pi pi-phone', color: '#3b82f6' },
      { label: 'Registrations', value: 0, icon: 'pi pi-users', color: '#10b981' },
      { label: 'Extensions', value: 0, icon: 'pi pi-th-large', color: '#8b5cf6' },
      { label: 'Gateways Up', value: 0, icon: 'pi pi-globe', color: '#f59e0b' },
    ])

    let ws = null
    let interval = null

    async function fetchCalls() {
      loading.value = true
      try {
        const { data } = await freeswitch.calls()
        activeCalls.value = data
        stats.value[0].value = data.length
      } catch {}
      loading.value = false
    }

    async function hangup(uuid) {
      try {
        await freeswitch.hangup({ uuid })
        toast.add({ severity: 'success', summary: 'Call hung up', life: 2000 })
        fetchCalls()
      } catch (e) {
        toast.add({ severity: 'error', summary: 'Hangup failed', detail: e.message, life: 3000 })
      }
    }

    function connectWebSocket() {
      const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${protocol}://${location.host}/ws/active-calls/`)
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data)
        if (msg.type === 'active_calls_update') {
          activeCalls.value = msg.calls
          stats.value[0].value = msg.calls.length
        }
      }
      ws.onclose = () => { setTimeout(connectWebSocket, 3000) }
    }

    onMounted(() => {
      fetchCalls()
      connectWebSocket()
      interval = setInterval(fetchCalls, 30000)
    })

    onUnmounted(() => {
      ws?.close()
      clearInterval(interval)
    })
    </script>

    <style scoped>
    .page-title { font-size: 1.5rem; font-weight: 600; color: #1e293b; margin-bottom: 1.5rem; }
    .stat-card { border-radius: 12px; }
    .stat-content { display: flex; align-items: center; gap: 1rem; }
    .stat-icon { width: 52px; height: 52px; border-radius: 12px; display: flex; align-items: center; justify-content: center; }
    .stat-icon i { font-size: 1.4rem; color: white; }
    .stat-value { font-size: 1.8rem; font-weight: 700; color: #1e293b; }
    .stat-label { font-size: 0.85rem; color: #64748b; }
    </style>
""")

# Generic CRUD view factory
def make_crud_view(name, title, apiModule, columns, formFields):
    col_defs = '\n              '.join([f'<Column field="{c[0]}" header="{c[1]}" />' for c in columns])
    field_defs = '\n              '.join([f'<div class="field"><label>{f[1]}</label><InputText v-model="form.{f[0]}" class="w-full" /></div>' for f in formFields])
    return f"""
    <template>
      <div>
        <div class="page-header">
          <h1 class="page-title">{title}</h1>
          <Button label="Add" icon="pi pi-plus" @click="openNew" />
        </div>

        <Card>
          <template #content>
            <Toolbar class="mb-3">
              <template #start>
                <InputText v-model="searchQuery" placeholder="Search..." @input="onSearch" class="mr-2" />
                <Button icon="pi pi-refresh" text @click="fetchData" />
              </template>
            </Toolbar>
            <DataTable :value="items" :loading="loading" paginator :rows="25"
                       lazy :totalRecords="totalRecords" @page="onPage"
                       size="small" stripedRows>
              {col_defs}
              <Column header="Actions" style="width:120px">
                <template #body="{{ data }}">
                  <Button icon="pi pi-pencil" text rounded size="small" @click="editItem(data)" />
                  <Button icon="pi pi-trash" text rounded severity="danger" size="small" @click="confirmDelete(data)" />
                </template>
              </Column>
            </DataTable>
          </template>
        </Card>

        <Dialog v-model:visible="dialogVisible" :header="editing ? 'Edit {title}' : 'New {title}'"
                modal :style="{{width:'520px'}}">
          <form @submit.prevent="saveItem">
            {field_defs}
            <div class="flex justify-content-end gap-2 mt-4">
              <Button label="Cancel" text @click="dialogVisible=false" />
              <Button type="submit" label="Save" icon="pi pi-check" :loading="saving" />
            </div>
          </form>
        </Dialog>

        <ConfirmDialog />
      </div>
    </template>

    <script setup>
    import {{ ref, onMounted }} from 'vue'
    import {{ useConfirm }} from 'primevue/useconfirm'
    import {{ useToast }} from 'primevue/usetoast'
    import Card from 'primevue/card'
    import DataTable from 'primevue/datatable'
    import Column from 'primevue/column'
    import Button from 'primevue/button'
    import Dialog from 'primevue/dialog'
    import InputText from 'primevue/inputtext'
    import Toolbar from 'primevue/toolbar'
    import ConfirmDialog from 'primevue/confirmdialog'
    import {{ {apiModule} }} from '@/api'

    const confirm = useConfirm()
    const toast = useToast()

    const items = ref([])
    const loading = ref(false)
    const saving = ref(false)
    const dialogVisible = ref(false)
    const editing = ref(false)
    const form = ref({{}})
    const searchQuery = ref('')
    const totalRecords = ref(0)
    const page = ref(1)

    async function fetchData() {{
      loading.value = true
      try {{
        const {{ data }} = await {apiModule}.list({{ page: page.value, search: searchQuery.value }})
        items.value = data.results || data
        totalRecords.value = data.count || items.value.length
      }} catch (e) {{
        toast.add({{ severity: 'error', summary: 'Load failed', detail: e.message, life: 3000 }})
      }}
      loading.value = false
    }}

    function openNew() {{
      form.value = {{}}
      editing.value = false
      dialogVisible.value = true
    }}

    function editItem(item) {{
      form.value = {{ ...item }}
      editing.value = true
      dialogVisible.value = true
    }}

    async function saveItem() {{
      saving.value = true
      try {{
        if (editing.value) {{
          const id = form.value[Object.keys(form.value)[0]]
          await {apiModule}.update(id, form.value)
        }} else {{
          await {apiModule}.create(form.value)
        }}
        toast.add({{ severity: 'success', summary: 'Saved', life: 2000 }})
        dialogVisible.value = false
        fetchData()
      }} catch (e) {{
        toast.add({{ severity: 'error', summary: 'Save failed', detail: e.message, life: 3000 }})
      }}
      saving.value = false
    }}

    function confirmDelete(item) {{
      confirm.require({{
        message: 'Delete this item?',
        header: 'Confirm',
        icon: 'pi pi-exclamation-triangle',
        rejectProps: {{ label: 'Cancel', severity: 'secondary', text: true }},
        acceptProps: {{ label: 'Delete', severity: 'danger' }},
        accept: async () => {{
          try {{
            const id = item[Object.keys(item)[0]]
            await {apiModule}.delete(id)
            toast.add({{ severity: 'success', summary: 'Deleted', life: 2000 }})
            fetchData()
          }} catch (e) {{
            toast.add({{ severity: 'error', summary: 'Delete failed', detail: e.message, life: 3000 }})
          }}
        }}
      }})
    }}

    function onSearch() {{ page.value = 1; fetchData() }}
    function onPage(e) {{ page.value = e.page + 1; fetchData() }}
    onMounted(fetchData)
    </script>

    <style scoped>
    .page-header {{ display: flex; align-items: center; justify-content: space-between; margin-bottom: 1.5rem; }}
    .page-title {{ font-size: 1.5rem; font-weight: 600; color: #1e293b; }}
    .field {{ margin-bottom: 1rem; }}
    .field label {{ display: block; font-weight: 500; margin-bottom: 0.4rem; color: #374151; }}
    </style>
"""

# Write each CRUD view
crud_views = [
    ('ExtensionsView.vue', 'Extensions', 'extensions',
     [('extension', 'Extension'), ('effective_caller_id_name', 'Name'), ('effective_caller_id_number', 'Caller ID')],
     [('extension', 'Extension Number'), ('password', 'SIP Password'), ('effective_caller_id_name', 'Display Name'), ('effective_caller_id_number', 'Caller ID Number')]),
    ('DialplansView.vue', 'Dialplans', 'dialplans',
     [('dialplan_name', 'Name'), ('dialplan_number', 'Number'), ('dialplan_context', 'Context')],
     [('dialplan_name', 'Name'), ('dialplan_number', 'Number'), ('dialplan_context', 'Context'), ('dialplan_order', 'Order')]),
    ('VoicemailsView.vue', 'Voicemails', 'voicemails',
     [('voicemail_id', 'Voicemail ID'), ('voicemail_mail_to', 'Email'), ('voicemail_enabled', 'Enabled')],
     [('voicemail_id', 'Voicemail ID'), ('voicemail_password', 'Password'), ('voicemail_mail_to', 'Email')]),
    ('GatewaysView.vue', 'Gateways', 'gateways',
     [('gateway', 'Gateway'), ('username', 'Username'), ('proxy', 'Proxy'), ('register', 'Register')],
     [('gateway', 'Name'), ('username', 'Username'), ('password', 'Password'), ('proxy', 'Proxy Server'), ('register', 'Register')]),
    ('RingGroupsView.vue', 'Ring Groups', 'ringGroups',
     [('ring_group_name', 'Name'), ('ring_group_extension', 'Extension'), ('ring_group_strategy', 'Strategy')],
     [('ring_group_name', 'Name'), ('ring_group_extension', 'Extension'), ('ring_group_timeout_action', 'Timeout Action')]),
    ('IvrMenusView.vue', 'IVR Menus', 'ivrMenus',
     [('ivr_menu_name', 'Name'), ('ivr_menu_extension', 'Extension'), ('ivr_menu_language', 'Language')],
     [('ivr_menu_name', 'Name'), ('ivr_menu_extension', 'Extension'), ('ivr_menu_timeout', 'Timeout (ms)')]),
    ('CallCentersView.vue', 'Call Centers', 'callCenters',
     [('call_center_queue_name', 'Queue Name'), ('call_center_queue_strategy', 'Strategy')],
     [('call_center_queue_name', 'Name'), ('call_center_queue_timeout', 'Timeout')]),
    ('ConferencesView.vue', 'Conferences', 'conferences',
     [('conference_name', 'Name'), ('conference_extension', 'Extension'), ('conference_max_members', 'Max Members')],
     [('conference_name', 'Name'), ('conference_extension', 'Extension'), ('conference_max_members', 'Max Members')]),
    ('DevicesView.vue', 'Devices', 'devices',
     [('device_mac_address', 'MAC'), ('device_vendor', 'Vendor'), ('device_model', 'Model'), ('device_label', 'Label')],
     [('device_mac_address', 'MAC Address'), ('device_vendor', 'Vendor'), ('device_model', 'Model'), ('device_label', 'Label')]),
    ('DomainsView.vue', 'Domains', 'domains',
     [('domain_name', 'Domain'), ('domain_enabled', 'Enabled'), ('insert_date', 'Created')],
     [('domain_name', 'Domain Name'), ('domain_description', 'Description')]),
    ('UsersView.vue', 'Users', 'users',
     [('username', 'Username'), ('user_email', 'Email'), ('user_enabled', 'Enabled')],
     [('username', 'Username'), ('user_email', 'Email'), ('user_first_name', 'First Name'), ('user_last_name', 'Last Name')]),
]

for fname, title, api_mod, cols, fields in crud_views:
    write(os.path.join(views, fname), make_crud_view(fname.replace('.vue',''), title, api_mod, cols, fields))

# CDR view
write(os.path.join(views, 'CdrView.vue'), """
    <template>
      <div>
        <div class="page-header">
          <h1 class="page-title">Call Detail Records</h1>
          <Button label="Export CSV" icon="pi pi-download" outlined @click="exportCsv" />
        </div>

        <Card>
          <template #content>
            <div class="filter-row mb-3">
              <InputText v-model="filters.caller" placeholder="Caller ID" />
              <InputText v-model="filters.destination" placeholder="Destination" />
              <DatePicker v-model="filters.start" placeholder="Start Date" showIcon />
              <DatePicker v-model="filters.end" placeholder="End Date" showIcon />
              <Button label="Filter" icon="pi pi-search" @click="fetchData" />
              <Button label="Reset" icon="pi pi-refresh" text @click="resetFilters" />
            </div>
            <DataTable :value="records" :loading="loading" paginator :rows="50"
                       lazy :totalRecords="total" @page="onPage" size="small" stripedRows>
              <Column field="caller_id_number" header="Caller" sortable />
              <Column field="destination_number" header="Destination" sortable />
              <Column field="start_stamp" header="Start" sortable />
              <Column field="duration" header="Duration" sortable />
              <Column field="billsec" header="Billsec" sortable />
              <Column field="hangup_cause" header="Result" />
              <Column field="direction" header="Direction" />
            </DataTable>
          </template>
        </Card>
      </div>
    </template>

    <script setup>
    import { ref, onMounted } from 'vue'
    import Card from 'primevue/card'
    import DataTable from 'primevue/datatable'
    import Column from 'primevue/column'
    import Button from 'primevue/button'
    import InputText from 'primevue/inputtext'
    import DatePicker from 'primevue/datepicker'
    import { cdr } from '@/api'

    const records = ref([])
    const loading = ref(false)
    const total = ref(0)
    const page = ref(1)
    const filters = ref({ caller: '', destination: '', start: null, end: null })

    async function fetchData() {
      loading.value = true
      try {
        const params = { page: page.value, page_size: 50 }
        if (filters.value.caller) params.caller_id_number = filters.value.caller
        if (filters.value.destination) params.destination_number = filters.value.destination
        if (filters.value.start) params.start = filters.value.start.toISOString()
        if (filters.value.end) params.end = filters.value.end.toISOString()
        const { data } = await cdr.list(params)
        records.value = data.results || data
        total.value = data.count || records.value.length
      } catch {}
      loading.value = false
    }

    function resetFilters() { filters.value = { caller: '', destination: '', start: null, end: null }; fetchData() }
    function onPage(e) { page.value = e.page + 1; fetchData() }
    function exportCsv() { window.open('/api/v1/cdr/export/', '_blank') }
    onMounted(fetchData)
    </script>

    <style scoped>
    .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
    .page-title { font-size: 1.5rem; font-weight: 600; color: #1e293b; }
    .filter-row { display: flex; gap: 0.75rem; flex-wrap: wrap; align-items: center; }
    </style>
""")

# Active Calls view
write(os.path.join(views, 'ActiveCallsView.vue'), """
    <template>
      <div>
        <div class="page-header">
          <h1 class="page-title">Active Calls <Tag :value="`${calls.length} calls`" /></h1>
          <div class="flex gap-2">
            <Button icon="pi pi-refresh" outlined @click="fetchCalls" :loading="loading" />
            <span :class="['ws-status', wsConnected ? 'connected' : 'disconnected']">
              <i :class="wsConnected ? 'pi pi-circle-fill' : 'pi pi-circle'" />
              {{ wsConnected ? 'Live' : 'Polling' }}
            </span>
          </div>
        </div>

        <Card>
          <template #content>
            <DataTable :value="calls" :loading="loading" size="small" stripedRows sortField="duration" :sortOrder="-1">
              <Column field="caller_id_number" header="Caller" sortable />
              <Column field="caller_id_name" header="Caller Name" />
              <Column field="destination_number" header="Destination" sortable />
              <Column field="state" header="State" sortable>
                <template #body="{ data }">
                  <Tag :value="data.state" :severity="data.state === 'CS_EXECUTE' ? 'success' : 'info'" />
                </template>
              </Column>
              <Column field="duration" header="Duration" sortable>
                <template #body="{ data }">{{ formatDuration(data.duration) }}</template>
              </Column>
              <Column header="Actions">
                <template #body="{ data }">
                  <Button icon="pi pi-times" severity="danger" text rounded size="small" title="Hangup"
                          @click="hangup(data.uuid)" />
                </template>
              </Column>
            </DataTable>
          </template>
        </Card>
      </div>
    </template>

    <script setup>
    import { ref, onMounted, onUnmounted } from 'vue'
    import { useToast } from 'primevue/usetoast'
    import Card from 'primevue/card'
    import DataTable from 'primevue/datatable'
    import Column from 'primevue/column'
    import Button from 'primevue/button'
    import Tag from 'primevue/tag'
    import { freeswitch } from '@/api'

    const toast = useToast()
    const calls = ref([])
    const loading = ref(false)
    const wsConnected = ref(false)
    let ws = null, interval = null

    async function fetchCalls() {
      loading.value = true
      try {
        const { data } = await freeswitch.calls()
        calls.value = data
      } catch {}
      loading.value = false
    }

    async function hangup(uuid) {
      try {
        await freeswitch.hangup({ uuid })
        toast.add({ severity: 'success', summary: 'Hung up', life: 2000 })
        fetchCalls()
      } catch (e) {
        toast.add({ severity: 'error', summary: 'Failed', detail: e.message, life: 3000 })
      }
    }

    function formatDuration(secs) {
      if (!secs) return '0:00'
      const m = Math.floor(secs / 60), s = secs % 60
      return `${m}:${String(s).padStart(2,'0')}`
    }

    function connect() {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/ws/active-calls/`)
      ws.onopen = () => { wsConnected.value = true }
      ws.onmessage = e => {
        const msg = JSON.parse(e.data)
        if (msg.type === 'active_calls_update') calls.value = msg.calls
      }
      ws.onclose = () => { wsConnected.value = false; setTimeout(connect, 3000) }
    }

    onMounted(() => { fetchCalls(); connect(); interval = setInterval(fetchCalls, 15000) })
    onUnmounted(() => { ws?.close(); clearInterval(interval) })
    </script>

    <style scoped>
    .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
    .page-title { font-size: 1.5rem; font-weight: 600; color: #1e293b; display: flex; align-items: center; gap: 0.5rem; }
    .ws-status { display: flex; align-items: center; gap: 0.4rem; font-size: 0.85rem; padding: 0.3rem 0.75rem; border-radius: 20px; }
    .ws-status.connected { background: #d1fae5; color: #065f46; }
    .ws-status.disconnected { background: #fee2e2; color: #991b1b; }
    </style>
""")

# Operator Panel
write(os.path.join(views, 'OperatorPanelView.vue'), """
    <template>
      <div>
        <div class="page-header">
          <h1 class="page-title">Operator Panel</h1>
          <span :class="['ws-badge', wsConnected ? 'live' : 'offline']">
            {{ wsConnected ? '● LIVE' : '○ OFFLINE' }}
          </span>
        </div>

        <div class="op-grid">
          <!-- Active calls -->
          <Card>
            <template #title>Active Calls ({{ calls.length }})</template>
            <template #content>
              <div class="call-list">
                <div v-for="c in calls" :key="c.uuid" class="call-item">
                  <div class="call-info">
                    <strong>{{ c.caller_id_number }}</strong>
                    <span class="arrow">→</span>
                    <span>{{ c.destination_number }}</span>
                  </div>
                  <Tag :value="c.state" size="small" />
                  <Button icon="pi pi-times" text rounded severity="danger" size="small" @click="hangup(c.uuid)" />
                </div>
              </div>
            </template>
          </Card>

          <!-- Click-to-call -->
          <Card>
            <template #title>Click to Call</template>
            <template #content>
              <div class="field">
                <label>From Extension</label>
                <InputText v-model="ctc.from" placeholder="1001" class="w-full" />
              </div>
              <div class="field">
                <label>To Number</label>
                <InputText v-model="ctc.to" placeholder="15551234567" class="w-full" />
              </div>
              <Button label="Call" icon="pi pi-phone" class="w-full" @click="originate" :loading="calling" />
            </template>
          </Card>
        </div>
      </div>
    </template>

    <script setup>
    import { ref, onMounted, onUnmounted } from 'vue'
    import { useToast } from 'primevue/usetoast'
    import Card from 'primevue/card'
    import Button from 'primevue/button'
    import InputText from 'primevue/inputtext'
    import Tag from 'primevue/tag'
    import { freeswitch } from '@/api'

    const toast = useToast()
    const calls = ref([])
    const wsConnected = ref(false)
    const calling = ref(false)
    const ctc = ref({ from: '', to: '' })
    let ws = null

    async function hangup(uuid) {
      try { await freeswitch.hangup({ uuid }); toast.add({ severity: 'success', summary: 'Hung up', life: 2000 }) }
      catch (e) { toast.add({ severity: 'error', summary: 'Failed', detail: e.message, life: 3000 }) }
    }

    async function originate() {
      calling.value = true
      try {
        await freeswitch.originate({ src: ctc.value.from, dst: ctc.value.to })
        toast.add({ severity: 'success', summary: 'Call initiated', life: 2000 })
      } catch (e) {
        toast.add({ severity: 'error', summary: 'Call failed', detail: e.message, life: 3000 })
      }
      calling.value = false
    }

    function connect() {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      ws = new WebSocket(`${proto}://${location.host}/ws/operator-panel/`)
      ws.onopen = () => { wsConnected.value = true }
      ws.onmessage = e => {
        const msg = JSON.parse(e.data)
        if (msg.type === 'active_calls_update') calls.value = msg.calls
      }
      ws.onclose = () => { wsConnected.value = false; setTimeout(connect, 3000) }
    }

    onMounted(() => { connect(); freeswitch.calls().then(r => { calls.value = r.data }) })
    onUnmounted(() => ws?.close())
    </script>

    <style scoped>
    .page-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; }
    .page-title { font-size: 1.5rem; font-weight: 600; }
    .ws-badge { font-size: 0.8rem; font-weight: 600; padding: 0.3rem 0.75rem; border-radius: 12px; }
    .ws-badge.live { background: #d1fae5; color: #065f46; }
    .ws-badge.offline { background: #fee2e2; color: #991b1b; }
    .op-grid { display: grid; grid-template-columns: 2fr 1fr; gap: 1.5rem; }
    .call-list { display: flex; flex-direction: column; gap: 0.5rem; max-height: 400px; overflow-y: auto; }
    .call-item { display: flex; align-items: center; justify-content: space-between; padding: 0.5rem; border-radius: 6px; background: #f8fafc; }
    .call-info { display: flex; align-items: center; gap: 0.5rem; font-size: 0.9rem; }
    .arrow { color: #94a3b8; }
    .field { margin-bottom: 1rem; }
    .field label { display: block; font-weight: 500; margin-bottom: 0.4rem; color: #374151; }
    </style>
""")

# FreeSWITCH status view
write(os.path.join(views, 'FreeSwitchView.vue'), """
    <template>
      <div>
        <h1 class="page-title">FreeSWITCH Status</h1>

        <div class="grid">
          <div class="col-12 md:col-6">
            <Card>
              <template #title>System Status</template>
              <template #content>
                <pre v-if="status" class="status-pre">{{ status }}</pre>
                <ProgressSpinner v-else />
              </template>
            </Card>
          </div>
          <div class="col-12 md:col-6">
            <Card>
              <template #title>Registrations ({{ registrations.length }})</template>
              <template #content>
                <DataTable :value="registrations" size="small" scrollable scrollHeight="300px">
                  <Column field="reg_user" header="User" />
                  <Column field="realm" header="Realm" />
                  <Column field="network_addr" header="Network" />
                  <Column field="status" header="Status" />
                </DataTable>
              </template>
            </Card>
          </div>
        </div>

        <Card class="mt-4">
          <template #title>API Console</template>
          <template #content>
            <div class="console-row">
              <InputText v-model="cmd" placeholder="e.g. sofia status" class="flex-1" @keyup.enter="runCmd" />
              <Button label="Run" icon="pi pi-play" @click="runCmd" :loading="cmdLoading" />
            </div>
            <pre v-if="cmdResult" class="console-output mt-3">{{ cmdResult }}</pre>
          </template>
        </Card>
      </div>
    </template>

    <script setup>
    import { ref, onMounted } from 'vue'
    import Card from 'primevue/card'
    import DataTable from 'primevue/datatable'
    import Column from 'primevue/column'
    import Button from 'primevue/button'
    import InputText from 'primevue/inputtext'
    import ProgressSpinner from 'primevue/progressspinner'
    import { freeswitch } from '@/api'
    import api from '@/api'

    const status = ref(null)
    const registrations = ref([])
    const cmd = ref('')
    const cmdResult = ref('')
    const cmdLoading = ref(false)

    async function fetchStatus() {
      try { const { data } = await freeswitch.status(); status.value = JSON.stringify(data, null, 2) } catch (e) { status.value = `Error: ${e.message}` }
    }
    async function fetchRegs() {
      try { const { data } = await freeswitch.registrations(); registrations.value = data } catch {}
    }
    async function runCmd() {
      if (!cmd.value) return
      cmdLoading.value = true
      try {
        const { data } = await api.post('/freeswitch/api/', { command: cmd.value })
        cmdResult.value = data.result || JSON.stringify(data)
      } catch (e) { cmdResult.value = `Error: ${e.message}` }
      cmdLoading.value = false
    }

    onMounted(() => { fetchStatus(); fetchRegs() })
    </script>

    <style scoped>
    .page-title { font-size: 1.5rem; font-weight: 600; color: #1e293b; margin-bottom: 1.5rem; }
    .status-pre, .console-output { background: #1e293b; color: #e2e8f0; padding: 1rem; border-radius: 8px; font-size: 0.8rem; white-space: pre-wrap; max-height: 300px; overflow-y: auto; }
    .console-row { display: flex; gap: 0.75rem; }
    </style>
""")

print('\nFrontend scaffold done!')
print(f'Directory: {ROOT}')
print('Run:  cd frontend && npm install && npm run dev')
