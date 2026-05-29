import { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Toaster } from 'sonner'
import { useSelector } from 'react-redux'
import { selectAuth } from '@/store'
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
          <Route path="extensions"         element={<Suspense fallback={<PageLoader />}><Extensions /></Suspense>} />
          <Route path="ring-groups"        element={<Suspense fallback={<PageLoader />}><RingGroups /></Suspense>} />
          <Route path="ivr-menus"          element={<Suspense fallback={<PageLoader />}><IvrMenus /></Suspense>} />
          <Route path="call-flows"         element={<Suspense fallback={<PageLoader />}><CallFlows /></Suspense>} />
          <Route path="destinations"       element={<Suspense fallback={<PageLoader />}><Destinations /></Suspense>} />
          <Route path="working-hours"      element={<Suspense fallback={<PageLoader />}><WorkingHours /></Suspense>} />
          <Route path="custom-destinations" element={<Suspense fallback={<PageLoader />}><CustomDestinations /></Suspense>} />
          <Route path="call-centers"       element={<Suspense fallback={<PageLoader />}><CallCenters /></Suspense>} />
          <Route path="voicemails"         element={<Suspense fallback={<PageLoader />}><Voicemails /></Suspense>} />
          <Route path="voicemail-inbox"    element={<Suspense fallback={<PageLoader />}><VoicemailInbox /></Suspense>} />
          <Route path="conferences"        element={<Suspense fallback={<PageLoader />}><Conferences /></Suspense>} />
          <Route path="call-parking"       element={<Suspense fallback={<PageLoader />}><CallParking /></Suspense>} />
          <Route path="fax"                element={<Suspense fallback={<PageLoader />}><Fax /></Suspense>} />
          <Route path="gateways"           element={<Suspense fallback={<PageLoader />}><Gateways /></Suspense>} />
          <Route path="outbound-routes"    element={<Suspense fallback={<PageLoader />}><OutboundRoutes /></Suspense>} />
          <Route path="dialplans"          element={<Suspense fallback={<PageLoader />}><Dialplans /></Suspense>} />
          <Route path="devices"            element={<Suspense fallback={<PageLoader />}><Devices /></Suspense>} />
          <Route path="cdr"                element={<Suspense fallback={<PageLoader />}><Cdr /></Suspense>} />
          <Route path="media-files"        element={<Suspense fallback={<PageLoader />}><MediaFiles /></Suspense>} />
          <Route path="call-recordings"    element={<Suspense fallback={<PageLoader />}><CallRecordings /></Suspense>} />
          <Route path="active-calls"       element={<Suspense fallback={<PageLoader />}><ActiveCalls /></Suspense>} />
          <Route path="operator-panel"     element={<Navigate to="/registrations" replace />} />
          <Route path="freeswitch"         element={<Suspense fallback={<PageLoader />}><FreeSWITCH /></Suspense>} />
          <Route path="domains"            element={<Suspense fallback={<PageLoader />}><Domains /></Suspense>} />
          <Route path="tenants"            element={<Suspense fallback={<PageLoader />}><Tenants /></Suspense>} />
          <Route path="tenant-list"        element={<Suspense fallback={<PageLoader />}><TenantList /></Suspense>} />
          <Route path="users"              element={<Suspense fallback={<PageLoader />}><Users /></Suspense>} />
          <Route path="firewall"           element={<Suspense fallback={<PageLoader />}><Firewall /></Suspense>} />
          <Route path="freeswitch-log"     element={<Suspense fallback={<PageLoader />}><FreeSwitchLog /></Suspense>} />
          <Route path="api-keys"           element={<Suspense fallback={<PageLoader />}><ApiKeys /></Suspense>} />
          <Route path="audit-log"          element={<Suspense fallback={<PageLoader />}><AuditLog /></Suspense>} />
          <Route path="registrations"      element={<Suspense fallback={<PageLoader />}><Registrations /></Suspense>} />
          <Route path="global-active-calls" element={<Suspense fallback={<PageLoader />}><GlobalActiveCalls /></Suspense>} />
          <Route path="system-log"         element={<Suspense fallback={<PageLoader />}><SystemLog /></Suspense>} />
          <Route path="admin-cdr"          element={<Suspense fallback={<PageLoader />}><AdminCdr /></Suspense>} />
          <Route path="admin-inventory"    element={<Suspense fallback={<PageLoader />}><AdminInventory /></Suspense>} />
          <Route path="super-users"        element={<Suspense fallback={<PageLoader />}><SuperUsers /></Suspense>} />
          <Route path="stats-report"       element={<Suspense fallback={<PageLoader />}><StatsReport /></Suspense>} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
