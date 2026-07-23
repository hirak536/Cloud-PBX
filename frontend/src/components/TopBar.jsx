import { useLocation } from 'react-router-dom'
import { useSelector, useDispatch } from 'react-redux'
import { selectAuth, selectTheme, selectTenant } from '@/store'
import { logoutThunk } from '@/store/slices/authSlice'
import { setTheme } from '@/store/slices/themeSlice'
import { setCurrentTenant } from '@/store/slices/tenantSlice'
import { Button } from '@/components/ui/button'
import { PanelLeftClose, PanelLeftOpen, LogOut, ChevronRight, Sun, Moon, Monitor, Check, Building2, ChevronDown, Search, Menu } from 'lucide-react'
import { useState, useRef, useEffect } from 'react'

const routeMeta = {
  '/':               { title: 'Dashboard',          group: null },
  '/extensions':     { title: 'Extensions',          group: 'Call Management' },
  '/ring-groups':    { title: 'Ring Groups',          group: 'Call Management' },
  '/ivr-menus':      { title: 'IVR Menus',            group: 'Call Management' },
  '/call-flows':     { title: 'Call Flows',           group: 'Call Management' },
  '/destinations':   { title: 'Destinations',         group: 'Call Management' },
  '/working-hours':  { title: 'Working Hours',        group: 'Call Management' },
  '/call-centers':   { title: 'Call Centers',         group: 'Call Management' },
  '/voicemails':     { title: 'Voicemails',           group: 'Communication' },
  '/conferences':    { title: 'Conferences',          group: 'Communication' },
  '/gateways':       { title: 'Gateways',             group: 'System' },
  '/dialplans':      { title: 'Dialplans',            group: 'System' },
  '/devices':        { title: 'Devices',              group: 'System' },
  '/cdr':            { title: 'Call Detail Records',  group: 'Reports' },
  '/recordings':     { title: 'Recordings',           group: 'Reports' },
  '/active-calls':   { title: 'Active Calls',         group: 'Monitoring' },
  '/operator-panel': { title: 'Operator Panel',       group: 'Monitoring' },
  '/freeswitch':     { title: 'FreeSWITCH',           group: 'Monitoring' },
  '/domains':        { title: 'Domains',              group: 'Administration' },
  '/users':          { title: 'Users',                group: 'Administration' },
  '/super-users':    { title: 'Super Admins',         group: 'Administration' },
  '/audit-log':      { title: 'Audit Log',            group: 'Administration' },
}

export default function TopBar({ collapsed, onToggle, onMobileToggle }) {
  const { pathname } = useLocation()
  const meta = routeMeta[pathname] || { title: 'IHS PBX', group: null }
  const dispatch = useDispatch()
  const { user } = useSelector(selectAuth)
  const theme = useSelector(selectTheme)
  const { currentTenant, tenantList } = useSelector(selectTenant)
  const logout = () => dispatch(logoutThunk())
  const handleSetCurrentTenant = (t) => dispatch(setCurrentTenant(t))
  const [menuOpen, setMenuOpen] = useState(false)
  const [themeOpen, setThemeOpen] = useState(false)
  const [tenantOpen, setTenantOpen] = useState(false)
  const [tenantSearch, setTenantSearch] = useState('')
  const menuRef = useRef(null)
  const themeRef = useRef(null)
  const tenantRef = useRef(null)

  const themeOptions = [
    { value: 'light', label: 'Light', icon: Sun },
    { value: 'dark',  label: 'Dark',  icon: Moon },
    { value: 'system', label: 'System', icon: Monitor },
  ]
  const activeThemeOption = themeOptions.find((o) => o.value === theme) || themeOptions[2]
  const ThemeIcon = activeThemeOption.icon

  useEffect(() => {
    const close = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false)
      if (themeRef.current && !themeRef.current.contains(e.target)) setThemeOpen(false)
      if (tenantRef.current && !tenantRef.current.contains(e.target)) { setTenantOpen(false); setTenantSearch('') }
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  const displayName = user
    ? (user.first_name ? `${user.first_name} ${user.last_name}`.trim() : user.username)
    : 'User'
  const initials = displayName.split(' ').map((n) => n[0]).slice(0, 2).join('').toUpperCase()

  return (
    <header className="relative z-30 flex h-14 shrink-0 items-center gap-2 sm:gap-3 md:rounded-2xl border border-border/60 bg-card/90 backdrop-blur-md px-3 sm:px-4 shadow-sm overflow-visible">
      {/* Mobile hamburger — visible only on mobile */}
      <Button variant="ghost" size="icon" onClick={onMobileToggle} className="shrink-0 text-muted-foreground hover:text-foreground md:hidden">
        <Menu className="h-4 w-4" />
      </Button>
      {/* Sidebar collapse toggle — visible only on desktop */}
      <Button variant="ghost" size="icon" onClick={onToggle} className="shrink-0 text-muted-foreground hover:text-foreground hidden md:inline-flex">
        {collapsed
          ? <PanelLeftOpen className="h-4 w-4" />
          : <PanelLeftClose className="h-4 w-4" />}
      </Button>

      {/* Breadcrumb */}
      <div className="flex flex-1 items-center gap-1.5 text-sm min-w-0">
        {meta.group && (
          <>
            <span className="text-muted-foreground/70 truncate hidden sm:block text-xs">{meta.group}</span>
            <ChevronRight className="h-3 w-3 text-muted-foreground/40 shrink-0 hidden sm:block" />
          </>
        )}
        <span className="font-semibold truncate">{meta.title}</span>

        {/* Tenant switcher badge — only interactive when the user has more than
            one tenant. A single-tenant user (e.g. standard PBX user) sees a
            static label with no switch option. */}
        {currentTenant && tenantList.length <= 1 && (
          <span className="hidden md:inline-flex items-center gap-1.5 rounded-full bg-primary/10 border border-primary/20 px-2.5 py-0.5 text-[11px] font-semibold text-primary ml-2">
            <Building2 className="h-3 w-3 shrink-0" />
            {currentTenant.tenant_name}
          </span>
        )}
        {currentTenant && tenantList.length > 1 && (
          <div className="relative hidden md:block ml-2" ref={tenantRef}>
            <button
              onClick={() => setTenantOpen((o) => !o)}
              className="inline-flex items-center gap-1.5 rounded-full bg-primary/10 border border-primary/20 px-2.5 py-0.5 text-[11px] font-semibold text-primary hover:bg-primary/20 transition-colors duration-150"
            >
              <Building2 className="h-3 w-3 shrink-0" />
              {currentTenant.tenant_name}
              <ChevronDown className={`h-3 w-3 shrink-0 transition-transform duration-200 ${tenantOpen ? 'rotate-180' : ''}`} />
            </button>

            {tenantOpen && tenantList.length > 0 && (
              <div className="absolute left-0 top-8 z-50 min-w-56 rounded-xl border border-border/60 bg-card shadow-2xl shadow-black/15 overflow-hidden animate-dropdown-in">
                <div className="px-3 py-2 border-b border-border/60 bg-muted/30">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">Switch Tenant</p>
                  <div className="relative">
                    <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground pointer-events-none" />
                    <input
                      autoFocus
                      value={tenantSearch}
                      onChange={(e) => setTenantSearch(e.target.value)}
                      placeholder="Search tenants..."
                      className="w-full rounded-md bg-background border border-border/60 pl-7 pr-2.5 py-1.5 text-xs outline-none focus:ring-1 focus:ring-primary/40 placeholder:text-muted-foreground/60"
                    />
                  </div>
                </div>
                <div className="p-1 max-h-52 overflow-y-auto">
                  {tenantList.filter(t => t.tenant_name.toLowerCase().includes(tenantSearch.toLowerCase())).length === 0 ? (
                    <p className="px-3 py-4 text-xs text-center text-muted-foreground">No tenants found</p>
                  ) : (
                    tenantList
                      .filter(t => t.tenant_name.toLowerCase().includes(tenantSearch.toLowerCase()))
                      .map((t) => (
                        <button
                          key={t.tenant_uuid}
                          onClick={() => { handleSetCurrentTenant(t); setTenantOpen(false); setTenantSearch('') }}
                          className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm hover:bg-accent transition-colors duration-100"
                        >
                          <div className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                            <Building2 className="h-3.5 w-3.5" />
                          </div>
                          <span className="flex-1 text-left truncate font-medium">{t.tenant_name}</span>
                          {t.tenant_uuid === currentTenant.tenant_uuid && (
                            <Check className="h-3.5 w-3.5 text-primary shrink-0" />
                          )}
                        </button>
                      ))
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Theme selector */}
      <div className="relative shrink-0" ref={themeRef}>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setThemeOpen((o) => !o)}
          className="shrink-0 text-muted-foreground hover:text-foreground transition-all duration-200"
          title="Change theme"
        >
          <ThemeIcon className="h-4 w-4" />
        </Button>
        {themeOpen && (
          <div className="absolute right-0 top-10 z-50 w-36 rounded-xl border border-border/60 bg-card shadow-2xl shadow-black/15 overflow-hidden animate-dropdown-in">
            <div className="p-1">
              {themeOptions.map(({ value, label, icon: Icon }) => (
                <button
                  key={value}
                  onClick={() => { dispatch(setTheme(value)); setThemeOpen(false) }}
                  className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm hover:bg-accent transition-colors duration-100"
                >
                  <Icon className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                  <span className="flex-1 text-left">{label}</span>
                  {theme === value && <Check className="h-3.5 w-3.5 text-primary shrink-0" />}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* User menu */}
      <div className="relative shrink-0" ref={menuRef}>
        <button
          onClick={() => setMenuOpen((o) => !o)}
          className="flex items-center gap-2 rounded-xl px-2 py-1.5 hover:bg-accent transition-all duration-150 group"
        >
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-gradient-to-br from-primary to-[hsl(217,91%,55%)] text-white text-xs font-bold shadow-md shadow-primary/30">
            {initials}
          </div>
          <div className="hidden sm:block text-left">
            <p className="text-xs font-semibold leading-tight">{displayName}</p>
            {user?.email && (
              <p className="text-[10px] text-muted-foreground leading-tight truncate max-w-28">
                {user.email}
              </p>
            )}
          </div>
          <ChevronRight className={`h-3.5 w-3.5 text-muted-foreground/60 transition-transform duration-200 hidden sm:block ${menuOpen ? 'rotate-90' : ''}`} />
        </button>

        {menuOpen && (
          <div className="absolute right-0 top-12 z-50 w-56 rounded-xl border border-border/60 bg-card shadow-2xl shadow-black/15 overflow-hidden animate-dropdown-in">
            <div className="px-4 py-3.5 border-b border-border/60 bg-muted/30">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-primary to-[hsl(217,91%,55%)] text-white text-sm font-bold shadow">
                  {initials}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold truncate">{displayName}</p>
                  <p className="text-xs text-muted-foreground truncate">{user?.email || user?.username}</p>
                  {currentTenant && (
                    <p className="text-xs text-primary mt-0.5 truncate font-medium">{currentTenant.tenant_name}</p>
                  )}
                </div>
              </div>
            </div>
            <div className="p-1.5">
              <button
                onClick={() => logout()}
                className="flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-sm text-destructive hover:bg-destructive/8 transition-all duration-150 font-medium"
              >
                <LogOut className="h-4 w-4" />
                Sign out
              </button>
            </div>
          </div>
        )}
      </div>
    </header>
  )
}
