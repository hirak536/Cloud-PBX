import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { selectTenant, selectAuth } from '@/store'
import { roleOf, creatableRoles, GRANTABLE_PAGES, GRANTABLE_PATHS, ACTION_CONTROLLED_PAGES, ACTIONS, ACTION_LABELS } from '@/lib/permissions'
import { users as api, tenants as tenantsApi, auth as authApi, fax as faxApi, organizations as orgApi } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogClose } from '@/components/ui/dialog'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { useInfiniteList } from '@/hooks/useInfiniteList'
import { InfiniteScroll, PageSizeSelector, DEFAULT_PAGE_SIZE } from '@/components/InfiniteScroll'
import ExtensionPicker from '@/components/ExtensionPicker'
import { Plus, Pencil, Trash2, Search, Loader2, ShieldCheck, Shield, User2, KeyRound, Check, Eye, EyeOff, ChevronDown, X, Building2, Phone, MessageSquare, Printer, Power, Lock } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

const ROLES = [
  { value: 'superuser', label: 'Superuser', description: 'Full access to all tenants' },
  { value: 'admin',     label: 'Admin',     description: 'Access to selected tenants only' },
  { value: 'user',      label: 'User',      description: 'Standard user (single tenant)' },
]

function roleFromUser(u) {
  if (u.is_superuser) return 'superuser'
  if (u.is_staff) return 'admin'
  return 'user'
}

// Single-select company filter, keyed on tenant_code. `value` is a tenant code
// or '' (all companies). Used by both the PBX and UC user listings so a
// superadmin can scope to one company (or all) independent of the globally
// selected tenant.
function CompanyFilter({ tenants, value, onChange }) {
  return (
    <Select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      wrapperClassName="w-44 shrink-0"
      className="h-9 text-sm"
    >
      <option value="">All companies</option>
      {tenants.map(t => (
        <option key={t.tenant_uuid} value={t.tenant_code}>
          {t.tenant_code} — {t.tenant_name}
        </option>
      ))}
    </Select>
  )
}

const EMPTY_FORM = {
  first_name: '',
  last_name: '',
  full_name: '',
  username: '',
  user_email: '',
  user_enabled: true,
  role: 'user',
  // Single tenant a standard 'user' is bound to. Required for the user role.
  tenant_uuid: '',
  admin_tenant_uuids: [],
  allowed_pages: [],
  // Per-page action grants for action-controlled pages, e.g.
  // { extensions: ['view','add','edit'] }. Only meaningful for the 'user' role.
  allowed_actions: {},
  // [] = all fax boxes (no restriction); non-empty = only those fax box UUIDs.
  allowed_fax_uuids: [],
}

function buildUsername(first, last) {
  const f = (first || '').trim().replace(/[^a-zA-Z]/g, '')
  const l = (last || '').trim().replace(/[^a-zA-Z]/g, '')
  if (!f && !l) return ''
  return (f.charAt(0) + l).toLowerCase()
}

// ── Organization Settings tab ─────────────────────────────────────────────────
// Superadmin-only. Searchable, paginated list of organizations sourced from the
// external IHS Phone company directory (organizations.list).
const ORG_PAGE_SIZE = 10

function OrganizationSettingsTab({ userEmail }) {
  const [search, setSearch]   = useState('')
  const debouncedSearch       = useDebounce(search, 300)
  const [page, setPage]       = useState(1)
  const [rows, setRows]       = useState([])
  const [pagination, setPagination] = useState({ total: 0, page: 1, total_pages: 1 })
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState('')
  const [editOrg, setEditOrg] = useState(null)   // row being edited (null = closed)
  const [reloadKey, setReloadKey] = useState(0)  // bump to refetch after a save
  // is_active filter: 'active' | 'inactive' | 'all'. Defaults to active.
  const [activeFilter, setActiveFilter] = useState('active')

  // Reset to page 1 whenever the search term or filter changes.
  useEffect(() => { setPage(1) }, [debouncedSearch, activeFilter])

  useEffect(() => {
    let alive = true
    setLoading(true); setError('')
    const params = { search: debouncedSearch, page, page_size: ORG_PAGE_SIZE }
    // Only apply the is_active filter when NOT searching, and not for 'all'.
    if (!debouncedSearch && activeFilter !== 'all') {
      params.is_active = activeFilter === 'active'
    }
    orgApi.list(params)
      .then(({ data }) => {
        if (!alive) return
        setRows(data.success || [])
        setPagination(data.pagination || { total: 0, page, total_pages: 1 })
      })
      .catch((e) => {
        if (!alive) return
        setError(e?.response?.data?.message || 'Failed to load organizations.')
        setRows([])
      })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [debouncedSearch, page, reloadKey, activeFilter])

  const totalPages = pagination.total_pages || 1

  const FeatureBadge = ({ on, label }) => (
    <Badge variant={on ? 'success' : 'secondary'} className="text-[10px]">{label}</Badge>
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="relative w-72">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search organizations…"
              className="pl-8"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <Select
            value={activeFilter}
            onChange={(e) => setActiveFilter(e.target.value)}
            disabled={!!debouncedSearch}
            wrapperClassName="w-36"
            title={debouncedSearch ? 'Status filter is ignored while searching' : undefined}
          >
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="all">All statuses</option>
          </Select>
        </div>
        <span className="text-xs text-muted-foreground">
          {pagination.total} organization{pagination.total !== 1 ? 's' : ''}
        </span>
      </div>

      {error && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-2.5 text-sm text-destructive">
          {error}
        </div>
      )}

      <Card><CardContent className="p-0 overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Organization</TableHead>
              <TableHead>Code</TableHead>
              <TableHead>SIP Domain</TableHead>
              <TableHead>Features</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-16" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading
              ? [...Array(6)].map((_, i) => (
                  <TableRow key={i}>
                    {[...Array(6)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}
                  </TableRow>
                ))
              : rows.length === 0
                ? <TableRow><TableCell colSpan={6} className="text-center py-10 text-muted-foreground">No organizations found.</TableCell></TableRow>
                : rows.map((r) => (
                    <TableRow key={r.id}>
                      <TableCell className="font-medium">{r.companyName}</TableCell>
                      <TableCell className="font-mono text-sm">{r.code}</TableCell>
                      <TableCell className="text-sm text-muted-foreground font-mono">{r.sip_domain || '—'}</TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <FeatureBadge on={r.voiceenable} label="Voice" />
                          <FeatureBadge on={r.smsenable} label="SMS" />
                          <FeatureBadge on={r.faxenable} label="Fax" />
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={r.is_active !== false ? 'success' : 'secondary'}>
                          {r.is_active !== false ? 'Active' : 'Disabled'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <Button variant="ghost" size="icon" className="h-7 w-7" title="Edit organization" onClick={() => setEditOrg(r)}>
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
            }
          </TableBody>
        </Table>
      </CardContent></Card>

      {totalPages > 1 && (
        <div className="flex items-center justify-end gap-2">
          <Button variant="outline" size="sm" disabled={page <= 1 || loading} onClick={() => setPage(p => Math.max(1, p - 1))}>
            ← Prev
          </Button>
          <span className="text-xs text-muted-foreground">Page {pagination.page} of {totalPages}</span>
          <Button variant="outline" size="sm" disabled={page >= totalPages || loading} onClick={() => setPage(p => Math.min(totalPages, p + 1))}>
            Next →
          </Button>
        </div>
      )}

      <OrgEditDialog
        org={editOrg}
        userEmail={userEmail}
        onClose={() => setEditOrg(null)}
        onSaved={() => { setEditOrg(null); setReloadKey(k => k + 1) }}
      />
    </div>
  )
}

// Edit dialog for a single organization. The companyEditPBX endpoint only
// updates the feature flags (voice/sms/fax) and active status — name/code/domain
// are read-only here. Requires the logged-in PBX user's email in the payload.
function OrgEditDialog({ org, userEmail, onClose, onSaved }) {
  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  // Password is locked behind an Override toggle — only editable and only sent
  // when override is on.
  const [pwOverride, setPwOverride] = useState(false)
  const [password, setPassword] = useState('')

  useEffect(() => {
    if (!org) { setForm(null); return }
    setError('')
    setPwOverride(false)
    setPassword('')
    setForm({
      voiceenable: !!org.voiceenable,
      smsenable:   !!org.smsenable,
      faxenable:   !!org.faxenable,
      is_active:   org.is_active !== false,
    })
  }, [org])

  const save = async () => {
    if (!userEmail) { setError('Cannot determine the logged-in user email.'); return }
    if (pwOverride && !password.trim()) { setError('Enter a new password or turn off Override.'); return }
    setSaving(true); setError('')
    try {
      await orgApi.update({
        id: String(org.id),
        useremail: userEmail,
        voiceenable: form.voiceenable,
        smsenable:   form.smsenable,
        faxenable:   form.faxenable,
        is_active:   form.is_active,
        // Only include the password when the admin explicitly overrides it.
        ...(pwOverride && password.trim() ? { password } : {}),
      })
      toast.success('Organization updated.')
      onSaved()
    } catch (e) {
      setError(e?.response?.data?.message || 'Failed to update organization.')
    } finally { setSaving(false) }
  }

  // A feature/status row: colored icon + label + on/off toggle switch.
  const ToggleRow = ({ label, hint, k, icon: Icon, tint }) => {
    const on = form[k]
    return (
      <div className="flex items-center gap-3 px-3 py-2.5">
        <div className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-lg', on ? tint : 'bg-muted text-muted-foreground')}>
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium leading-none">{label}</p>
          {hint && <p className="text-[11px] text-muted-foreground mt-0.5">{hint}</p>}
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={on}
          aria-label={label}
          disabled={saving}
          onClick={() => setForm(p => ({ ...p, [k]: !p[k] }))}
          className={cn(
            'relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border-2 border-transparent transition-colors',
            on ? 'bg-primary' : 'bg-input',
            saving && 'opacity-50 cursor-not-allowed',
          )}
        >
          <span className={cn('block h-4 w-4 rounded-full bg-white shadow transition-transform', on ? 'translate-x-4' : 'translate-x-0')} />
        </button>
      </div>
    )
  }

  return (
    <Dialog open={!!org} onOpenChange={(v) => { if (!v && !saving) onClose() }}>
      <DialogContent className="w-[95vw] max-w-lg p-0 gap-0 overflow-hidden">
        {/* Header — org identity */}
        <DialogHeader className="px-6 pt-5 pb-4 border-b">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Building2 className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <DialogTitle className="truncate text-base">{org?.companyName || 'Organization'}</DialogTitle>
              {org && (
                <p className="text-xs text-muted-foreground font-mono mt-0.5">
                  {org.code}{org.sip_domain ? ` · ${org.sip_domain}` : ''}
                </p>
              )}
            </div>
          </div>
        </DialogHeader>

        {org && form && (
          <div className="px-6 py-5 space-y-5 max-h-[70vh] overflow-y-auto">
            {error && (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div>
            )}

            {/* Features */}
            <div className="space-y-1.5">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Features</p>
              <div className="rounded-xl border divide-y">
                <ToggleRow label="Voice" k="voiceenable" icon={Phone}         tint="bg-blue-500/10 text-blue-500" />
                <ToggleRow label="SMS"   k="smsenable"   icon={MessageSquare} tint="bg-green-600/10 text-green-600" />
                <ToggleRow label="Fax"   k="faxenable"   icon={Printer}       tint="bg-orange-500/10 text-orange-500" />
              </div>
            </div>

            {/* Status */}
            <div className="space-y-1.5">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Status</p>
              <div className="rounded-xl border">
                <ToggleRow label="Active" hint="Suspends the organization when disabled." k="is_active" icon={Power} tint="bg-emerald-500/10 text-emerald-500" />
              </div>
            </div>

            {/* Password */}
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Password</p>
                <label className="flex items-center gap-2 cursor-pointer select-none">
                  <span className="text-xs text-muted-foreground">Override</span>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={pwOverride}
                    disabled={saving}
                    onClick={() => {
                      const next = !pwOverride
                      setPwOverride(next)
                      if (!next) setPassword('')  // turning off discards any typed value
                    }}
                    className={cn(
                      'relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border-2 border-transparent transition-colors',
                      pwOverride ? 'bg-primary' : 'bg-input',
                      saving && 'opacity-50 cursor-not-allowed',
                    )}
                  >
                    <span className={cn('block h-4 w-4 rounded-full bg-white shadow transition-transform', pwOverride ? 'translate-x-4' : 'translate-x-0')} />
                  </button>
                </label>
              </div>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />
                <Input
                  type="password"
                  placeholder={pwOverride ? 'Enter new password' : 'Enable Override to change'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  disabled={!pwOverride || saving}
                  autoComplete="new-password"
                  className={cn('pl-9', !pwOverride && 'bg-muted text-muted-foreground')}
                />
              </div>
              <p className="text-[11px] text-muted-foreground">
                {pwOverride
                  ? 'The password will be updated on save.'
                  : 'Leave off to keep the current password unchanged.'}
              </p>
            </div>
          </div>
        )}
        <DialogFooter className="px-6 py-4 border-t bg-muted/30">
          <Button variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
          <Button onClick={save} disabled={saving || !form}>
            {saving && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
            Save Changes
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Users() {
  const navigate = useNavigate()
  // Route param drives the editor: undefined = list, 'new' = create, else edit by id.
  // The `/new` route has no :id param, so detect create from the path.
  const { id: editParamId } = useParams()
  const location = useLocation()
  const isCreate   = location.pathname.endsWith('/users/new')
  const routeId    = editParamId
  const editorOpen = isCreate || routeId !== undefined

  const { currentTenant } = useSelector(selectTenant)
  const { user: loggedInUser } = useSelector(selectAuth)
  const myRole = roleOf(loggedInUser)
  // Roles the logged-in user is allowed to create (superuser → all; admin → user only).
  const allowedRoles = creatableRoles(myRole)

  // Organization Settings tab is superadmin-only; superadmins land there first.
  const isSuperadmin = myRole === 'superuser'
  const [activeTab, setActiveTab] = useState(isSuperadmin ? 'organization' : 'pbx')

  const [rows, setRows]            = useState([])
  const [loading, setLoading]      = useState(true)
  const [search, setSearch]        = useState('')
  const [allTenants, setAllTenants] = useState([])
  // Company (tenant_code) filter shared by both tabs. '' = all companies.
  // Defaults to all so a superadmin sees every user regardless of the globally
  // selected tenant.
  const [companyFilter, setCompanyFilter] = useState('')
  const [faxBoxes, setFaxBoxes]     = useState([])
  const [faxScope, setFaxScope]     = useState('all')  // 'all' | 'selected'
  const [editId, setEditId]        = useState(null)
  const [form, setForm]            = useState(EMPTY_FORM)
  const [saving, setSaving]        = useState(false)
  const [formError, setFormError]  = useState('')
  const [deleting, setDeleting]    = useState(null)
  const [resetting, setResetting]  = useState(null)
  const [resetMsg, setResetMsg]    = useState('')

  const debouncedSearch = useDebounce(search, 300)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      // Scope the PBX user list by the company filter (tenant codes, comma-
      // separated). Empty filter = all companies. The interceptor auto-injects
      // ?tenant=<uuid> for the active tenant, so we explicitly send tenant:null
      // to suppress it and let tenant_code drive scoping.
      const params = { tenant: null }
      if (debouncedSearch) params.search = debouncedSearch
      if (companyFilter) params.tenant_code = companyFilter
      const { data } = await api.list(params)
      const all = Array.isArray(data) ? data : data.results || []
      setRows(all.filter(u => !u.is_superuser))
    } finally { setLoading(false) }
  }, [debouncedSearch, companyFilter])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    tenantsApi.list({ page_size: 200 }).then(({ data }) => {
      setAllTenants(Array.isArray(data) ? data : data.results || [])
    }).catch(() => {})
  }, [])

  // Fax boxes for the per-user fax-box picker. Scoped to the tenant chosen in the
  // dialog's Tenant dropdown (a superuser may target a tenant other than the
  // active one); the backend honors ?tenant= for superusers and otherwise locks
  // to the requester's own tenant. Falls back to the active tenant when no tenant
  // is selected yet (e.g. dialog closed).
  useEffect(() => {
    const tenantUuid = form.tenant_uuid || currentTenant?.tenant_uuid
    if (!tenantUuid) { setFaxBoxes([]); return }
    faxApi.list({ page_size: 500, tenant: tenantUuid }).then(({ data }) => {
      setFaxBoxes(Array.isArray(data) ? data : data.results || [])
    }).catch(() => {})
  }, [form.tenant_uuid, currentTenant?.tenant_uuid])

  const f = (key) => (e) => setForm(p => ({ ...p, [key]: e.target.value }))

  const rowToForm = (r) => {
    const parts = (r.full_name || '').trim().split(' ')
    const firstName = parts[0] || ''
    const lastName = parts.slice(1).join(' ')
    return {
      first_name: firstName,
      last_name: lastName,
      full_name: r.full_name || '',
      username: r.username || '',
      user_email: r.user_email || '',
      user_enabled: r.user_enabled !== false,
      role: roleFromUser(r),
      tenant_uuid: r.tenant || '',
      admin_tenant_uuids: (r.admin_tenants || []).map(t => t.tenant_uuid),
      allowed_pages: Array.isArray(r.allowed_pages) ? r.allowed_pages : [],
      allowed_actions: (r.allowed_actions && typeof r.allowed_actions === 'object') ? r.allowed_actions : {},
      allowed_fax_uuids: Array.isArray(r.allowed_fax_uuids) ? r.allowed_fax_uuids : [],
    }
  }

  // Navigate to the full-page editor; the route effect below loads the form.
  const openCreate  = () => navigate('/users/new')
  const openEdit    = (r) => navigate(`/users/${r.user_uuid}/edit`)
  const closeEditor = () => navigate('/users')

  // Sync form state to the current route. Guarded on the route key so it runs
  // exactly once per editor-open: a re-run (e.g. when the list `rows` refetch
  // in the background) would otherwise overwrite the user's in-progress edits
  // with the freshly-fetched row.
  const lastRouteKeyRef = useRef(null)
  useEffect(() => {
    if (!editorOpen) { lastRouteKeyRef.current = null; return }
    const routeKey = isCreate ? 'new' : routeId
    if (lastRouteKeyRef.current === routeKey) return
    lastRouteKeyRef.current = routeKey
    setFormError('')
    if (isCreate) {
      setEditId(null)
      setForm({
        ...EMPTY_FORM,
        role: allowedRoles[0] || 'user',
        tenant_uuid: currentTenant?.tenant_uuid || '',
      })
      setFaxScope('all')
      return
    }
    setEditId(routeId)
    const row = rows.find(r => r.user_uuid === routeId)
    if (row) {
      setForm(rowToForm(row))
      setFaxScope((row.allowed_fax_uuids || []).length > 0 ? 'selected' : 'all')
      return
    }
    // Deep-link / refresh: fetch the row if the list isn't loaded yet.
    api.get?.(routeId)
      .then(({ data }) => {
        setForm(rowToForm(data))
        setFaxScope((data.allowed_fax_uuids || []).length > 0 ? 'selected' : 'all')
      })
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeId, isCreate, rows])

  const toggleTenant = (uuid) => {
    setForm(p => ({
      ...p,
      admin_tenant_uuids: p.admin_tenant_uuids.includes(uuid)
        ? p.admin_tenant_uuids.filter(id => id !== uuid)
        : [...p.admin_tenant_uuids, uuid],
    }))
  }

  const togglePage = (path) => {
    setForm(p => {
      const has = p.allowed_pages.includes(path)
      const allowed_pages = has
        ? p.allowed_pages.filter(x => x !== path)
        : [...p.allowed_pages, path]
      const allowed_actions = { ...p.allowed_actions }
      if (ACTION_CONTROLLED_PAGES.includes(path)) {
        if (has) {
          // Page removed — drop its action grants.
          delete allowed_actions[path]
        } else if (!allowed_actions[path]) {
          // Page newly granted — default to full actions (admin can pare down).
          allowed_actions[path] = [...ACTIONS]
        }
      }
      return { ...p, allowed_pages, allowed_actions }
    })
  }

  // Toggle a single action for an action-controlled page.
  const toggleAction = (path, action) => {
    setForm(p => {
      const current = p.allowed_actions[path] || []
      const next = current.includes(action)
        ? current.filter(a => a !== action)
        : [...current, action]
      return { ...p, allowed_actions: { ...p.allowed_actions, [path]: next } }
    })
  }

  const toggleAllPages = () => {
    setForm(p => {
      const selectingAll = p.allowed_pages.length !== GRANTABLE_PATHS.length
      const allowed_actions = { ...p.allowed_actions }
      if (selectingAll) {
        // Seed full actions for every action-controlled page.
        for (const path of ACTION_CONTROLLED_PAGES) {
          if (!allowed_actions[path]) allowed_actions[path] = [...ACTIONS]
        }
      } else {
        // Clearing all pages clears all action grants too.
        for (const path of ACTION_CONTROLLED_PAGES) delete allowed_actions[path]
      }
      return {
        ...p,
        allowed_pages: selectingAll ? [...GRANTABLE_PATHS] : [],
        allowed_actions,
      }
    })
  }

  const toggleFaxBox = (uuid) => {
    setForm(p => ({
      ...p,
      allowed_fax_uuids: p.allowed_fax_uuids.includes(uuid)
        ? p.allowed_fax_uuids.filter(x => x !== uuid)
        : [...p.allowed_fax_uuids, uuid],
    }))
  }

  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

  const handleSave = async () => {
    if (!form.username) { setFormError('Username is required.'); return }
    if (!form.user_email) { setFormError('Email is required.'); return }
    if (!EMAIL_RE.test(form.user_email)) { setFormError('Enter a valid email address.'); return }
    if (form.role === 'admin' && form.admin_tenant_uuids.length === 0) {
      setFormError('Select at least one tenant for Admin role.')
      return
    }
    if (form.role === 'user' && !form.tenant_uuid) {
      setFormError('Select a tenant for this user.')
      return
    }
    if (
      form.role === 'user' &&
      form.allowed_pages.includes('fax') &&
      faxScope === 'selected' &&
      form.allowed_fax_uuids.length === 0
    ) {
      setFormError('Select at least one fax box, or choose "All fax boxes".')
      return
    }

    setSaving(true); setFormError('')

    const payload = {
      full_name: form.full_name,
      username: form.username,
      user_email: form.user_email,
      user_enabled: form.user_enabled,
      is_superuser: form.role === 'superuser',
      is_staff: form.role === 'superuser' || form.role === 'admin',
      // A standard user is bound to exactly one tenant. Superusers span all
      // tenants and admins are scoped via admin_tenant_uuids, so both clear it.
      tenant: form.role === 'user' ? form.tenant_uuid : null,
      admin_tenant_uuids: form.role === 'admin' ? form.admin_tenant_uuids : [],
      // Per-user page grants only apply to standard users; clear for admin/superuser.
      allowed_pages: form.role === 'user' ? form.allowed_pages : [],
      // Per-page action grants: only for a standard user, pruned to pages that are
      // both action-controlled and actually granted. Clear for admin/superuser.
      allowed_actions: form.role === 'user'
        ? Object.fromEntries(
            ACTION_CONTROLLED_PAGES
              .filter(p => form.allowed_pages.includes(p) && (form.allowed_actions[p] || []).length > 0)
              .map(p => [p, form.allowed_actions[p]])
          )
        : {},
      // Fax-box scoping only applies to a standard user who has the Fax page granted
      // and explicitly chose to restrict to selected boxes. Otherwise [] = all boxes.
      allowed_fax_uuids:
        form.role === 'user' && form.allowed_pages.includes('fax') && faxScope === 'selected'
          ? form.allowed_fax_uuids
          : [],
    }

    if (!editId) {
      const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%'
      const tempPw = Array.from({ length: 12 }, () => chars[Math.floor(Math.random() * chars.length)]).join('')
      payload.password = tempPw
      payload.password_confirm = tempPw
      payload.must_change_password = true
    }

    try {
      if (editId) {
        await api.update(editId, payload)
      } else {
        await api.create(payload)
      }
      load()
      closeEditor()
    } catch (err) {
      const d = err?.response?.data
      setFormError(typeof d === 'string' ? d : Object.values(d || {}).flat().join(' ') || 'Save failed.')
    } finally { setSaving(false) }
  }

  const handleResetPassword = async (userUuid) => {
    setResetting(userUuid)
    setResetMsg('')
    try {
      await authApi.resetPassword(userUuid)
      setResetMsg('Password reset email sent.')
    } catch (err) {
      const d = err?.response?.data
      setResetMsg(typeof d === 'string' ? d : d?.detail || 'Reset failed.')
    } finally { setResetting(null) }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this user?')) return
    setDeleting(id)
    try { await api.delete(id); load() } finally { setDeleting(null) }
  }

  // ── Full-page editor (routed) ──────────────────────────────────────────────
  if (editorOpen) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={closeEditor} className="-ml-2 gap-1">
            ← Users
          </Button>
          <span className="text-muted-foreground">/</span>
          <h1 className="text-lg font-semibold">{isCreate ? 'New User' : 'Edit User'}</h1>
        </div>

        <Card>
          <div className="px-6 py-5 space-y-5">
          {formError && (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
              {formError}
            </div>
          )}

          <div className="space-y-5">
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>First Name</Label>
                  <Input
                    placeholder="Jane"
                    value={form.first_name}
                    onChange={e => {
                      const first = e.target.value
                      setForm(p => ({
                        ...p,
                        first_name: first,
                        full_name: (first + ' ' + p.last_name).trim(),
                        username: !editId ? buildUsername(first, p.last_name) : p.username,
                      }))
                    }}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label>Last Name</Label>
                  <Input
                    placeholder="Smith"
                    value={form.last_name}
                    onChange={e => {
                      const last = e.target.value
                      setForm(p => ({
                        ...p,
                        last_name: last,
                        full_name: (p.first_name + ' ' + last).trim(),
                        username: !editId ? buildUsername(p.first_name, last) : p.username,
                      }))
                    }}
                  />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <Label>Username <span className="text-destructive">*</span></Label>
                  <Input placeholder="jsmith" value={form.username} onChange={f('username')} />
                </div>
                <div className="space-y-1.5">
                  <Label>Email <span className="text-destructive">*</span></Label>
                  <Input type="email" placeholder="user@example.com" value={form.user_email} onChange={f('user_email')} />
                </div>
              </div>
            </div>

            {!editId && (
              <div className="rounded-md border border-muted bg-muted/40 px-3 py-2 text-sm text-muted-foreground">
                A temporary password will be generated automatically. Use <span className="font-medium text-foreground">Reset Password</span> to email it to the user.
              </div>
            )}

            <div className="space-y-1.5">
              <Label>Role <span className="text-destructive">*</span></Label>
              <Select
                value={form.role}
                disabled={!editId && allowedRoles.length <= 1}
                onChange={(e) => setForm(p => ({ ...p, role: e.target.value, admin_tenant_uuids: [] }))}
              >
                {/* When editing, show every role so the saved value renders.
                    When creating, only show roles this user may assign. */}
                {(editId ? ROLES : ROLES.filter(r => allowedRoles.includes(r.value))).map(r => (
                  <option key={r.value} value={r.value}>{r.label} — {r.description}</option>
                ))}
              </Select>
              {!editId && allowedRoles.length <= 1 && (
                <p className="text-xs text-muted-foreground">
                  You can only create standard users. Contact a super admin to create admins.
                </p>
              )}
            </div>

            {form.role === 'superuser' && (
              <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-400">
                Superusers have unrestricted access to all tenants and system settings.
              </div>
            )}

            {form.role === 'admin' && (
              <div className="space-y-1.5">
                <Label>Tenant Access <span className="text-destructive">*</span></Label>
                {allTenants.length === 0
                  ? <p className="text-sm text-muted-foreground">No tenants available.</p>
                  : (
                    <div className="border rounded-md max-h-44 overflow-y-auto divide-y">
                      {allTenants.map(t => {
                        const checked = form.admin_tenant_uuids.includes(t.tenant_uuid)
                        return (
                          <label
                            key={t.tenant_uuid}
                            className="flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-muted/50 select-none"
                          >
                            <input
                              type="checkbox"
                              className="h-4 w-4 shrink-0 rounded border-input accent-primary"
                              checked={checked}
                              onChange={() => toggleTenant(t.tenant_uuid)}
                            />
                            <span className="text-sm font-medium">{t.tenant_code}</span>
                            <span className="text-sm text-muted-foreground truncate">{t.tenant_name}</span>
                            {t.tenant_enabled === false && (
                              <Badge variant="secondary" className="ml-auto shrink-0 text-xs">Disabled</Badge>
                            )}
                          </label>
                        )
                      })}
                    </div>
                  )}
              </div>
            )}

            {form.role === 'user' && (
              <div className="space-y-1.5">
                <Label>Tenant <span className="text-destructive">*</span></Label>
                {allTenants.length === 0
                  ? <p className="text-sm text-muted-foreground">No tenants available.</p>
                  : (
                    <Select
                      value={form.tenant_uuid}
                      onChange={(e) => {
                        // Switching tenants invalidates any fax boxes picked for
                        // the previous tenant — reset the fax-box scope.
                        setForm(p => ({ ...p, tenant_uuid: e.target.value, allowed_fax_uuids: [] }))
                        setFaxScope('all')
                      }}
                    >
                      <option value="">Select tenant</option>
                      {allTenants.map(t => (
                        <option key={t.tenant_uuid} value={t.tenant_uuid}>
                          {t.tenant_code} — {t.tenant_name}
                        </option>
                      ))}
                    </Select>
                  )}
                <p className="text-xs text-muted-foreground">
                  This user belongs to a single tenant and cannot switch tenants.
                </p>
              </div>
            )}

            {form.role === 'user' && (
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label>Page Access</Label>
                  <button
                    type="button"
                    onClick={toggleAllPages}
                    className="text-[11px] font-medium text-primary hover:underline"
                  >
                    {form.allowed_pages.length === GRANTABLE_PATHS.length ? 'Clear all' : 'Select all'}
                  </button>
                </div>
                <p className="text-xs text-muted-foreground">
                  Choose which pages this user can see, including the Dashboard.
                </p>
                <div className="border rounded-md max-h-60 overflow-y-auto divide-y">
                  {GRANTABLE_PAGES.map(group => (
                    <div key={group.group}>
                      <div className="px-3 py-1.5 bg-muted/40 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                        {group.group}
                      </div>
                      {group.items.map(item => {
                        const checked = form.allowed_pages.includes(item.path)
                        const actionable = ACTION_CONTROLLED_PAGES.includes(item.path)
                        const pageActions = form.allowed_actions[item.path] || []
                        return (
                          <div key={item.path}>
                            <label
                              className="flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-muted/50 select-none"
                            >
                              <input
                                type="checkbox"
                                className="h-4 w-4 shrink-0 rounded border-input accent-primary"
                                checked={checked}
                                onChange={() => togglePage(item.path)}
                              />
                              <span className="text-sm">{item.label}</span>
                              {actionable && checked && (
                                <span className="text-[10px] text-muted-foreground ml-2">
                                  ({pageActions.length ? pageActions.map(a => ACTION_LABELS[a]).join(', ') : 'no actions'})
                                </span>
                              )}
                              {checked && <Check className="h-3.5 w-3.5 text-primary ml-auto shrink-0" />}
                            </label>
                            {actionable && checked && (
                              <div className="flex flex-wrap gap-3 px-3 pb-2 pl-10">
                                {ACTIONS.map(a => (
                                  <label key={a} className="flex items-center gap-1.5 cursor-pointer select-none">
                                    <input
                                      type="checkbox"
                                      className="h-3.5 w-3.5 shrink-0 rounded border-input accent-primary"
                                      checked={pageActions.includes(a)}
                                      onChange={() => toggleAction(item.path, a)}
                                    />
                                    <span className="text-xs text-muted-foreground">{ACTION_LABELS[a]}</span>
                                  </label>
                                ))}
                              </div>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {form.role === 'user' && form.allowed_pages.includes('fax') && (
              <div className="space-y-1.5">
                <Label>Fax Box Access</Label>
                <p className="text-xs text-muted-foreground">
                  Limit which fax boxes this user can see. Leave as <span className="font-medium text-foreground">All fax boxes</span> for no restriction.
                </p>
                <div className="space-y-2">
                  <label className="flex items-center gap-2.5 rounded-md border px-3 py-2 cursor-pointer hover:bg-muted/40 select-none">
                    <input
                      type="radio"
                      name="fax-scope"
                      className="h-4 w-4 accent-primary"
                      checked={faxScope === 'all'}
                      onChange={() => { setFaxScope('all'); setForm(p => ({ ...p, allowed_fax_uuids: [] })) }}
                    />
                    <span className="text-sm font-medium">All fax boxes</span>
                  </label>
                  <label className="flex items-center gap-2.5 rounded-md border px-3 py-2 cursor-pointer hover:bg-muted/40 select-none">
                    <input
                      type="radio"
                      name="fax-scope"
                      className="h-4 w-4 accent-primary"
                      checked={faxScope === 'selected'}
                      onChange={() => setFaxScope('selected')}
                    />
                    <span className="text-sm font-medium">Only selected fax boxes</span>
                  </label>
                </div>
                {faxScope === 'selected' && (
                  faxBoxes.length === 0
                    ? <p className="text-sm text-muted-foreground">No fax boxes available for this tenant.</p>
                    : (
                      <div className="border rounded-md max-h-44 overflow-y-auto divide-y">
                        {faxBoxes.map(b => {
                          const checked = form.allowed_fax_uuids.includes(b.fax_uuid)
                          return (
                            <label
                              key={b.fax_uuid}
                              className="flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-muted/50 select-none"
                            >
                              <input
                                type="checkbox"
                                className="h-4 w-4 shrink-0 rounded border-input accent-primary"
                                checked={checked}
                                onChange={() => toggleFaxBox(b.fax_uuid)}
                              />
                              <span className="text-sm">{b.fax_name}</span>
                              {b.fax_extension && (
                                <span className="text-xs text-muted-foreground font-mono">{b.fax_extension}</span>
                              )}
                              {checked && <Check className="h-3.5 w-3.5 text-primary ml-auto shrink-0" />}
                            </label>
                          )
                        })}
                      </div>
                    )
                )}
              </div>
            )}

            <div className="border-t pt-4">
              <label className="flex items-center gap-2.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-input accent-primary"
                  checked={form.user_enabled}
                  onChange={(e) => setForm(p => ({ ...p, user_enabled: e.target.checked }))}
                />
                <span className="text-sm font-medium">Account enabled</span>
              </label>
            </div>
          </div>
          </div>

          <div className="flex justify-end gap-2 px-6 py-3 border-t">
            <Button variant="outline" size="sm" onClick={closeEditor}>Cancel</Button>
            <Button size="sm" onClick={handleSave} disabled={saving} className="gap-1.5">
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              {isCreate ? 'Create User' : 'Save Changes'}
            </Button>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Tab switcher — Organization Settings is superadmin-only */}
      {isSuperadmin && (
        <div className="flex items-center gap-1 border-b">
          {[
            { key: 'organization', label: 'Organization Settings' },
            { key: 'pbx',          label: 'PBX Users' },
          ].map(tab => (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors duration-150 -mb-px
                ${activeTab === tab.key
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground'}`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      )}

      {/* ── Organization Settings ── */}
      {isSuperadmin && activeTab === 'organization' && (
        <OrganizationSettingsTab userEmail={loggedInUser?.user_email || loggedInUser?.email || ''} />
      )}

      {/* ── PBX Users ── */}
      {activeTab === 'pbx' && (
        <>
          <div className="flex items-center justify-end gap-3">
            <div className="relative w-72">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input placeholder="Search users..." className="pl-8" value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
            {allTenants.length > 1 && (
              <CompanyFilter tenants={allTenants} value={companyFilter} onChange={setCompanyFilter} />
            )}
            <Button size="sm" onClick={openCreate}><Plus className="h-4 w-4" />Add User</Button>
          </div>

          {resetMsg && (
            <div className="rounded-md border border-primary/30 bg-primary/10 px-3 py-2 text-sm text-primary">
              {resetMsg}
            </div>
          )}

          <Card><CardContent className="p-0 overflow-x-auto">
            <Table>
              <TableHeader><TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Company</TableHead>
                <TableHead>Role</TableHead>
                <TableHead>Tenant Access</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-28" />
              </TableRow></TableHeader>
              <TableBody>
                {loading
                  ? [...Array(5)].map((_, i) => (
                      <TableRow key={i}>
                        {[...Array(7)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}
                      </TableRow>
                    ))
                  : rows.length === 0
                    ? <TableRow><TableCell colSpan={7} className="text-center py-10 text-muted-foreground">No users found.</TableCell></TableRow>
                    : rows.map((r) => {
                        const role = roleFromUser(r)
                        return (
                          <TableRow key={r.user_uuid}>
                            <TableCell className="font-medium">
                              {r.full_name || r.username}
                              {r.full_name && <span className="block text-xs text-muted-foreground">{r.username}</span>}
                            </TableCell>
                            <TableCell className="text-muted-foreground text-sm">{r.user_email || '—'}</TableCell>
                            <TableCell className="text-sm">
                              {role === 'superuser'
                                ? <span className="text-xs text-muted-foreground italic">All companies</span>
                                : r.tenant_name || r.tenant_code
                                  ? <span>{r.tenant_name || r.tenant_code}{r.tenant_name && r.tenant_code && <span className="block text-xs text-muted-foreground">{r.tenant_code}</span>}</span>
                                  : r.admin_tenants?.length > 0
                                    ? <div className="flex flex-wrap gap-1">
                                        {r.admin_tenants.map(t => (
                                          <Badge key={t.tenant_uuid} variant="outline" className="text-xs">{t.tenant_name || t.tenant_code}</Badge>
                                        ))}
                                      </div>
                                    : <span className="text-muted-foreground">—</span>}
                            </TableCell>
                            <TableCell>
                              {role === 'superuser'
                                ? <Badge variant="default" className="gap-1"><ShieldCheck className="h-3 w-3" />Superuser</Badge>
                                : role === 'admin'
                                  ? <Badge variant="secondary" className="gap-1"><Shield className="h-3 w-3" />Admin</Badge>
                                  : <Badge variant="outline" className="gap-1"><User2 className="h-3 w-3" />User</Badge>}
                            </TableCell>
                            <TableCell>
                              {role === 'superuser'
                                ? <span className="text-xs text-muted-foreground italic">All tenants</span>
                                : role === 'admin' && r.admin_tenants?.length > 0
                                  ? <div className="flex flex-wrap gap-1">
                                      {r.admin_tenants.map(t => (
                                        <Badge key={t.tenant_uuid} variant="outline" className="text-xs">{t.tenant_code}</Badge>
                                      ))}
                                    </div>
                                  : r.tenant_code
                                    ? <Badge variant="outline" className="text-xs">{r.tenant_code}</Badge>
                                    : <span className="text-xs text-muted-foreground">—</span>}
                            </TableCell>
                            <TableCell>
                              <Badge variant={r.user_enabled !== false ? 'success' : 'secondary'}>
                                {r.user_enabled !== false ? 'Active' : 'Inactive'}
                              </Badge>
                            </TableCell>
                            <TableCell>
                              <div className="flex gap-1">
                                <Button variant="ghost" size="icon" className="h-7 w-7" title="Reset password" onClick={() => handleResetPassword(r.user_uuid)} disabled={resetting === r.user_uuid}>
                                  {resetting === r.user_uuid ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <KeyRound className="h-3.5 w-3.5" />}
                                </Button>
                                <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(r)}>
                                  <Pencil className="h-3.5 w-3.5" />
                                </Button>
                                <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive" onClick={() => handleDelete(r.user_uuid)} disabled={deleting === r.user_uuid}>
                                  {deleting === r.user_uuid ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        )
                      })}
              </TableBody>
            </Table>
          </CardContent></Card>
        </>
      )}

    </div>
  )
}
