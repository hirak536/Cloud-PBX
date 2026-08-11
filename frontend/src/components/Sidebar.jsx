import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useSelector, useDispatch } from 'react-redux'
import { selectAuth, selectTenant } from '@/store'
import { canAccessPage, pageKeyOf, hasRole, roleOf } from '@/lib/permissions'
import { setCurrentTenant, fetchTenantsThunk } from '@/store/slices/tenantSlice'
import { useEffect, useRef, useState } from 'react'
import {
  LayoutDashboard, Phone, Users, PhoneCall, GitBranch, MapPin, Clock,
  Headphones, Voicemail, Inbox, Video, Building, Printer, Network,
  GitMerge, Smartphone, BarChart2, Music, Mic, Activity, MonitorPlay,
  Cpu, Globe, UserCog, ChevronDown, Building2, Check,
  PhoneForwarded, PhoneOutgoing, ShieldAlert, ShieldCheck, Bookmark, ScrollText, Key, ClipboardList,
  SquareParking,
} from 'lucide-react'

// Assets
import logoIcon from '@/assests/IH-logo-New.png'
import logoFull from '@/assests/IHS Logo transparent.png'
import logoDark from '@/assests/IHS Logo for Black background.png'
import favicon from '@/assests/favicon.png'

const navGroups = [
  {
    label: 'Overview',
    items: [
      { path: '/', label: 'Dashboard', icon: LayoutDashboard, exact: true },
    ],
  },
  {
    label: 'Call Management',
    items: [
      { path: '/extensions', label: 'Extensions', icon: Phone },
      { path: '/ring-groups', label: 'Ring Groups', icon: Users },
      { path: '/ivr-menus', label: 'IVR Menus', icon: PhoneCall },
      { path: '/call-flows', label: 'Call Flows', icon: GitBranch },
      { path: '/destinations', label: 'DIDs', icon: MapPin },
      { path: '/custom-destinations', label: 'Custom Destinations', icon: Bookmark },
      { path: '/working-hours', label: 'Working Hours', icon: Clock },
      { path: '/call-centers', label: 'Call Centers', icon: Headphones },
    ],
  },
  {
    label: 'Communication',
    items: [
      { path: '/voicemails', label: 'Voicemails', icon: Voicemail },
      { path: '/voicemail-inbox', label: 'Voicemail Inbox', icon: Inbox },
      { path: '/conferences', label: 'Conferences', icon: Video },
      { path: '/call-parking', label: 'Call Parking', icon: SquareParking },
      { path: '/fax', label: 'Fax', icon: Printer },
    ],
  },
  {
    label: 'System',
    items: [
      { path: '/media-files', label: 'Media Files', icon: Music },
      { path: '/dialplans', label: 'Dialplans', icon: GitMerge },
      { path: '/devices', label: 'Devices', icon: Smartphone },
    ],
  },
  {
    label: 'Reports',
    items: [
      { path: '/cdr', label: 'Call Detail Records', icon: BarChart2 },
      { path: '/call-recordings', label: 'Call Recordings', icon: Mic },
    ],
  },
  {
    label: 'Monitoring',
    items: [
      { path: '/active-calls', label: 'Active Calls', icon: Activity },
      { path: '/registrations', label: 'Peer Status', icon: MonitorPlay },
    ],
  },
  {
    label: 'Administration',
    items: [
      { path: '/users', label: 'Users', icon: UserCog },
      { path: '/super-users', label: 'Super Admins', icon: ShieldCheck, role: 'superuser' },
      { path: '/tenants', label: 'Tenant Setting', icon: Building, role: 'admin' },
      { path: '/tenant-list', label: 'Tenant List', icon: Building2, role: 'superuser' },
      { path: '/domains', label: 'Domains', icon: Globe, role: 'superuser' },
      { path: '/gateways', label: 'Gateways', icon: Network, role: 'superuser' },
      { path: '/outbound-routes', label: 'Outbound Routes', icon: PhoneOutgoing, role: 'superuser' },
      { path: '/firewall', label: 'Firewall', icon: ShieldAlert, role: 'superuser' },
      { path: '/global-active-calls', label: 'All Active Calls', icon: PhoneCall, role: 'superuser' },
      { path: '/freeswitch', label: 'FreeSWITCH', icon: Cpu, role: 'superuser' },
      { path: '/freeswitch-log', label: 'FreeSWITCH Log', icon: ScrollText, role: 'superuser' },
      { path: '/api-keys', label: 'API Keys', icon: Key, role: 'superuser' },
      { path: '/system-log', label: 'System Log', icon: Activity, role: 'superuser' },
      { path: '/admin-cdr', label: 'Admin CDR', icon: BarChart2, role: 'superuser' },
      { path: '/admin-inventory', label: 'Admin Inventory', icon: Bookmark, role: 'superuser' },
      { path: '/audit-log', label: 'Audit Log', icon: ClipboardList, role: 'admin' },
    ],
  },
]

// ── Tooltip (for collapsed mode) ─────────────────────────────────────────────

function Tooltip({ label, children }) {
  const [visible, setVisible] = useState(false)
  return (
    <div
      className="relative"
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      {children}
      {visible && (
        <div className="pointer-events-none absolute left-full top-1/2 z-[200] ml-3 -translate-y-1/2">
          <div className="whitespace-nowrap rounded-lg bg-foreground px-2.5 py-1.5 text-xs font-medium text-background shadow-lg animate-dropdown-in">
            {label}
            {/* Arrow */}
            <div className="absolute right-full top-1/2 -translate-y-1/2 border-4 border-transparent border-r-foreground" />
          </div>
        </div>
      )}
    </div>
  )
}

// ── Tenant Switcher ───────────────────────────────────────────────────────────

function TenantSwitcher({ collapsed }) {
  const dispatch = useDispatch()
  const { currentTenant, tenantList } = useSelector(selectTenant)
  const fetchTenants = () => dispatch(fetchTenantsThunk())
  const handleSetCurrentTenant = (t) => dispatch(setCurrentTenant(t))
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => { fetchTenants() }, [])
  useEffect(() => {
    const close = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  if (collapsed) {
    return (
      <div className="px-2 py-3 border-b border-[hsl(var(--sidebar-border))]">
        <Tooltip label={currentTenant?.tenant_name || 'Select tenant'}>
          <button className="mx-auto flex h-8 w-8 items-center justify-center rounded-lg bg-[hsl(var(--sidebar-active))]/15 hover:bg-[hsl(var(--sidebar-active))]/25 transition-all duration-150">
            <Building2 className="h-4 w-4 text-[hsl(var(--sidebar-active))]" />
          </button>
        </Tooltip>
      </div>
    )
  }

  return (
    <div className="px-3 py-3 border-b border-[hsl(var(--sidebar-border))]" ref={ref}>
      <p className="mb-2 text-[10px] font-bold uppercase tracking-widest text-[hsl(var(--sidebar-muted))]">
        Active Tenant
      </p>
      <button
        onClick={() => tenantList.length > 1 && setOpen((o) => !o)}
        className={cn(
          'flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition-all duration-150',
          'bg-[hsl(var(--sidebar-hover))] hover:bg-[hsl(var(--sidebar-border))]/60',
          'border border-[hsl(var(--sidebar-border))]/60',
          tenantList.length <= 1 && 'cursor-default'
        )}
      >
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[hsl(var(--sidebar-active))]/15">
          <Building2 className="h-3.5 w-3.5 text-[hsl(var(--sidebar-active))]" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="truncate text-xs font-semibold text-[hsl(var(--sidebar-text))] leading-tight">
            {currentTenant?.tenant_name || 'No tenant selected'}
          </p>
          {tenantList.length > 0 && (
            <p className="text-[10px] text-[hsl(var(--sidebar-muted))] leading-tight mt-0.5">
              {tenantList.length} tenant{tenantList.length !== 1 ? 's' : ''}
            </p>
          )}
        </div>
        {tenantList.length > 1 && (
          <ChevronDown className={cn(
            'h-3.5 w-3.5 shrink-0 text-[hsl(var(--sidebar-muted))] transition-transform duration-200',
            open && 'rotate-180'
          )} />
        )}
      </button>

      {open && (
        <div className="mt-1.5 overflow-hidden rounded-xl border border-[hsl(var(--sidebar-border))] bg-[hsl(var(--sidebar-dropdown))] shadow-2xl animate-dropdown-in">
          <div className="max-h-48 overflow-y-auto scrollbar-thin">
            {tenantList.map((t) => {
              const active = currentTenant?.tenant_uuid === t.tenant_uuid
              return (
                <button
                  key={t.tenant_uuid}
                  onClick={() => { handleSetCurrentTenant(t); setOpen(false) }}
                  className={cn(
                    'flex w-full items-center gap-2.5 px-3 py-2.5 text-xs transition-all duration-100',
                    active
                      ? 'text-[hsl(var(--sidebar-active))] bg-[hsl(var(--sidebar-active))]/10'
                      : 'text-[hsl(var(--sidebar-foreground))] hover:bg-[hsl(var(--sidebar-hover))]'
                  )}
                >
                  <span className="truncate flex-1 text-left">{t.tenant_name}</span>
                  {t.tenant_code && (
                    <span className="ml-auto shrink-0 text-[10px] font-mono opacity-40">{t.tenant_code}</span>
                  )}
                  {active && <Check className="h-3 w-3 shrink-0 text-[hsl(var(--sidebar-active))]" />}
                </button>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Navigation ────────────────────────────────────────────────────────────────

function NavGroup({ group, collapsed }) {
  const [open, setOpen] = useState(true)

  if (collapsed) {
    return (
      <div className="mb-0.5 border-b border-[hsl(var(--sidebar-border))]/40 pb-1 last:border-0">
        {group.items.map((item) => <NavItem key={item.path} item={item} collapsed />)}
      </div>
    )
  }

  return (
    <div className="mb-0.5">
      <button
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between px-3 py-1.5 text-[10px] font-bold uppercase tracking-widest text-[hsl(var(--sidebar-muted))] hover:text-[hsl(var(--sidebar-foreground))] transition-colors duration-150"
      >
        {group.label}
        <ChevronDown className={cn('h-2.5 w-2.5 opacity-50 transition-transform duration-200', !open && '-rotate-90')} />
      </button>
      {open && (
        <div className="space-y-0.5">
          {group.items.map((item) => <NavItem key={item.path} item={item} />)}
        </div>
      )}
    </div>
  )
}

function NavItem({ item, collapsed }) {
  const Icon = item.icon

  const linkContent = ({ isActive }) => (
    <span className={cn(
      'relative flex items-center rounded-lg transition-all duration-150',
      collapsed
        ? 'mx-auto h-9 w-9 justify-center'
        : 'mx-2 gap-2.5 px-3 py-2 w-[calc(100%-1rem)]',
      isActive
        ? 'text-[hsl(var(--sidebar-active))]'
        : 'text-[hsl(var(--sidebar-foreground))] hover:bg-[hsl(var(--sidebar-hover))] hover:text-[hsl(var(--sidebar-text))]'
    )}>
      {/* Left pill indicator for active item */}
      {isActive && !collapsed && (
        <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-0.5 rounded-full bg-[hsl(var(--sidebar-active))]" />
      )}
      {/* Active background — subtle, not full gradient */}
      {isActive && (
        <span className={cn(
          'absolute inset-0 rounded-lg bg-[hsl(var(--sidebar-active))]/10',
          collapsed && 'rounded-xl'
        )} />
      )}
      <Icon className="relative h-4 w-4 shrink-0" />
      {!collapsed && (
        <span className="relative truncate text-sm font-medium">{item.label}</span>
      )}
    </span>
  )

  // External links (e.g. the HOMER admin UI proxied at /homer/) open in a new
  // tab via a plain anchor rather than a client-side route.
  if (item.external) {
    const anchor = (
      <a href={item.path} target="_blank" rel="noopener noreferrer"
         className="block py-0.5">
        {linkContent({ isActive: false })}
      </a>
    )
    return collapsed ? <Tooltip label={item.label}>{anchor}</Tooltip> : anchor
  }

  if (collapsed) {
    return (
      <Tooltip label={item.label}>
        <NavLink to={item.path} end={item.exact} className="block py-0.5">
          {linkContent}
        </NavLink>
      </Tooltip>
    )
  }

  return (
    <NavLink to={item.path} end={item.exact}>
      {linkContent}
    </NavLink>
  )
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

export default function Sidebar({ collapsed }) {
  const { user } = useSelector(selectAuth)

  // A nav item is visible if the user can access its page (role tier + per-user
  // grants). The Dashboard ('/') maps to the 'dashboard' grant key. External
  // items (e.g. HOMER) aren't routes, so gate them by their explicit `role`.
  const canSeeItem = (item) =>
    item.external
      ? hasRole(roleOf(user), item.role)
      : canAccessPage(user, pageKeyOf(item.path))

  return (
    <aside
      className={cn(
        'flex h-screen md:h-full flex-col bg-[hsl(var(--sidebar))] md:rounded-2xl shadow-sm',
        'border border-[hsl(var(--sidebar-border))]',
        'transition-[width] duration-300 ease-[cubic-bezier(0.4,0,0.2,1)] shrink-0 overflow-hidden',
        'w-60 md:w-auto',
        collapsed ? 'md:w-14' : 'md:w-60'
      )}
    >
      {/* Brand */}
      <div className={cn(
        'flex h-14 shrink-0 items-center border-b border-[hsl(var(--sidebar-border))] rounded-t-2xl px-4',
        collapsed ? 'justify-center px-0' : 'justify-start'
      )}>
        {collapsed ? (
          <img src={favicon} alt="IHS" className="h-8 w-8 object-contain animate-in fade-in zoom-in duration-300" />
        ) : (
          <div className="flex flex-row items-center gap-2.5 animate-in fade-in slide-in-from-left-4 duration-300">
            <img src={favicon} alt="IHS" className="h-8 w-8 object-contain shrink-0" />
            <div className="flex flex-col leading-tight">
              <span className="text-sm font-bold tracking-wide text-foreground">IHS PBX</span>
              <span className="text-[10px] font-medium tracking-wider text-[hsl(var(--sidebar-muted))] whitespace-nowrap">Unified Communication</span>
            </div>
          </div>
        )}
      </div>

      {/* Tenant switcher */}
      <TenantSwitcher collapsed={collapsed} />

      {/* Nav */}
      <nav className={cn(
        'flex-1 overflow-y-auto overflow-x-hidden scrollbar-thin py-3',
        collapsed ? 'space-y-0' : 'space-y-4'
      )}>
        {navGroups.map((group) => {
          const items = group.items.filter(canSeeItem)
          if (!items.length) return null
          return <NavGroup key={group.label} group={{ ...group, items }} collapsed={collapsed} />
        })}
      </nav>

      {/* Footer */}
      <div className={cn(
        'shrink-0 border-t border-[hsl(var(--sidebar-border))] transition-all duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]',
        collapsed ? 'px-0 py-2.5' : 'px-4 py-2.5'
      )}>
        {collapsed ? (
          <Tooltip label="IHS PBX v2.0 · Online">
            <div className="flex justify-center">
              <div className="h-2 w-2 rounded-full bg-emerald-400 animate-live-pulse" />
            </div>
          </Tooltip>
        ) : (
          <div className="flex items-center gap-2 overflow-hidden">
            <div className="h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400 animate-live-pulse" />
            <p className="whitespace-nowrap text-[10px] text-[hsl(var(--sidebar-muted))]">IHS PBX v2.0 · Online</p>
          </div>
        )}
      </div>
    </aside>
  )
}
