import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'sonner'
import { useSelector } from 'react-redux'
import { selectAuth } from '@/store'
import { canAccessPage } from '@/lib/permissions'
import LiveProvider from '@/providers/LiveProvider'
import AppLayout from '@/components/AppLayout'
import IdleLogout from '@/components/IdleLogout'
import Login from '@/pages/Login'

const Dashboard        = lazy(() => import('@/pages/Dashboard'))
const Extensions       = lazy(() => import('@/pages/Extensions'))
const Cdr              = lazy(() => import('@/pages/Cdr'))
const Voicemails       = lazy(() => import('@/pages/Voicemails'))
const VoicemailInbox   = lazy(() => import('@/pages/VoicemailInbox'))
const Gateways         = lazy(() => import('@/pages/Gateways'))
const RingGroups       = lazy(() => import('@/pages/RingGroups'))
const IvrMenus         = lazy(() => import('@/pages/IvrMenus'))
const CallCenters      = lazy(() => import('@/pages/CallCenters'))
const Conferences      = lazy(() => import('@/pages/Conferences'))
const Fax              = lazy(() => import('@/pages/Fax'))
const Devices          = lazy(() => import('@/pages/Devices'))
const Dialplans        = lazy(() => import('@/pages/Dialplans'))
const ActiveCalls      = lazy(() => import('@/pages/ActiveCalls'))
const FreeSWITCH       = lazy(() => import('@/pages/FreeSWITCH'))
const Domains          = lazy(() => import('@/pages/Domains'))
const Tenants          = lazy(() => import('@/pages/Tenants'))
const TenantList       = lazy(() => import('@/pages/TenantList'))
const Users            = lazy(() => import('@/pages/Users'))
const Destinations     = lazy(() => import('@/pages/Destinations'))
const WorkingHours     = lazy(() => import('@/pages/WorkingHours'))
const CallFlows        = lazy(() => import('@/pages/CallFlows'))
const MediaFiles       = lazy(() => import('@/pages/MediaFiles'))
const CallRecordings   = lazy(() => import('@/pages/CallRecordings'))
const OutboundRoutes   = lazy(() => import('@/pages/OutboundRoutes'))
const CustomDestinations = lazy(() => import('@/pages/CustomDestinations'))
const ApiKeys            = lazy(() => import('@/pages/ApiKeys'))
const Firewall         = lazy(() => import('@/pages/Firewall'))
const FreeSwitchLog    = lazy(() => import('@/pages/FreeSwitchLog'))
const ChangePassword   = lazy(() => import('@/pages/ChangePassword'))
const AuditLog          = lazy(() => import('@/pages/AuditLog'))
const Registrations     = lazy(() => import('@/pages/Registrations'))
const GlobalActiveCalls = lazy(() => import('@/pages/GlobalActiveCalls'))
const CallParking       = lazy(() => import('@/pages/CallParking'))
const SystemLog         = lazy(() => import('@/pages/SystemLog'))
const AdminCdr          = lazy(() => import('@/pages/AdminCdr'))
const AdminInventory    = lazy(() => import('@/pages/AdminInventory'))
const SuperUsers        = lazy(() => import('@/pages/SuperUsers'))
const StatsReport       = lazy(() => import('@/pages/StatsReport'))

function PageLoader() {
  return (
    <div className="flex h-full items-center justify-center py-20">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-primary border-t-transparent" />
    </div>
  )
}

function RequireAuth({ children }) {
  const { isAuthenticated, user } = useSelector(selectAuth)
  if (!isAuthenticated) return <Navigate to="/login" replace />
  if (user?.must_change_password) return <Navigate to="/change-password" replace />
  return children
}

// Guards a route by role tier AND per-user page grants. Blocks direct URL access
// for users who lack access and bounces them back to the dashboard.
function RequirePage({ page, children }) {
  const { user } = useSelector(selectAuth)
  if (!canAccessPage(user, page)) {
    return <Navigate to="/" replace />
  }
  return children
}

// Wrap a lazy page element with a Suspense fallback and a page-access guard.
function page(name, Element) {
  return (
    <RequirePage page={name}>
      <Suspense fallback={<PageLoader />}><Element /></Suspense>
    </RequirePage>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <LiveProvider />
      <IdleLogout />
      <Toaster position="top-right" richColors closeButton />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/change-password" element={
          <Suspense fallback={<PageLoader />}><ChangePassword /></Suspense>
        } />
        <Route
          path="/"
          element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }
        >
          <Route index element={<Suspense fallback={<PageLoader />}><Dashboard /></Suspense>} />
          <Route path="extensions"         element={page('extensions', Extensions)} />
          <Route path="ring-groups"        element={page('ring-groups', RingGroups)} />
          <Route path="ivr-menus"          element={page('ivr-menus', IvrMenus)} />
          <Route path="call-flows"         element={page('call-flows', CallFlows)} />
          <Route path="destinations"       element={page('destinations', Destinations)} />
          <Route path="working-hours"      element={page('working-hours', WorkingHours)} />
          <Route path="custom-destinations" element={page('custom-destinations', CustomDestinations)} />
          <Route path="call-centers"       element={page('call-centers', CallCenters)} />
          <Route path="voicemails"         element={page('voicemails', Voicemails)} />
          <Route path="voicemail-inbox"    element={page('voicemail-inbox', VoicemailInbox)} />
          <Route path="conferences"        element={page('conferences', Conferences)} />
          <Route path="call-parking"       element={page('call-parking', CallParking)} />
          <Route path="fax"                element={page('fax', Fax)} />
          <Route path="gateways"           element={page('gateways', Gateways)} />
          <Route path="outbound-routes"    element={page('outbound-routes', OutboundRoutes)} />
          <Route path="dialplans"          element={page('dialplans', Dialplans)} />
          <Route path="devices"            element={page('devices', Devices)} />
          <Route path="cdr"                element={page('cdr', Cdr)} />
          <Route path="media-files"        element={page('media-files', MediaFiles)} />
          <Route path="call-recordings"    element={page('call-recordings', CallRecordings)} />
          <Route path="active-calls"       element={page('active-calls', ActiveCalls)} />
          <Route path="operator-panel"     element={<Navigate to="/registrations" replace />} />
          <Route path="freeswitch"         element={page('freeswitch', FreeSWITCH)} />
          <Route path="domains"            element={page('domains', Domains)} />
          <Route path="tenants"            element={page('tenants', Tenants)} />
          <Route path="tenant-list"        element={page('tenant-list', TenantList)} />
          <Route path="users"              element={page('users', Users)} />
          <Route path="firewall"           element={page('firewall', Firewall)} />
          <Route path="freeswitch-log"     element={page('freeswitch-log', FreeSwitchLog)} />
          <Route path="api-keys"           element={page('api-keys', ApiKeys)} />
          <Route path="audit-log"          element={page('audit-log', AuditLog)} />
          <Route path="registrations"      element={page('registrations', Registrations)} />
          <Route path="global-active-calls" element={page('global-active-calls', GlobalActiveCalls)} />
          <Route path="system-log"         element={page('system-log', SystemLog)} />
          <Route path="admin-cdr"          element={page('admin-cdr', AdminCdr)} />
          <Route path="admin-inventory"    element={page('admin-inventory', AdminInventory)} />
          <Route path="super-users"        element={page('super-users', SuperUsers)} />
          <Route path="stats-report"       element={page('stats-report', StatsReport)} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
