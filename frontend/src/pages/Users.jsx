import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { selectTenant, selectAuth } from '@/store'
import { roleOf, creatableRoles, GRANTABLE_PAGES, GRANTABLE_PATHS, ACTION_CONTROLLED_PAGES, ACTIONS, ACTION_LABELS } from '@/lib/permissions'
import { users as api, tenants as tenantsApi, auth as authApi, fax as faxApi, organizations as orgApi, ucUsers as ucUsersApi, extensions as extensionsApi, destinations as destinationsApi, voicemails as voicemailsApi } from '@/api'
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
import { Plus, Pencil, Trash2, Search, Loader2, ShieldCheck, Shield, User2, KeyRound, Check, Eye, EyeOff, ChevronDown, X, Building2, Phone, MessageSquare, Printer, Power, Lock, AlertTriangle, Mail, Wand2 } from 'lucide-react'
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
// external company directory (organizations.list).
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
        setError(apiErrorMessage(e, 'Failed to load organizations.'))
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

// ── UC Users tab ──────────────────────────────────────────────────────────────
// Superadmin-only. Searchable, filterable (status + company), paginated list of
// UC users sourced from the external directory (ucUsers.list).
const UC_PAGE_SIZE = 20
const UC_USER_TYPE_OPTIONS = [
  { value: 'superadmin', label: 'Super Admin' },
  { value: 'admin',      label: 'Admin' },
  { value: 'user',       label: 'User' },
]

// Small multi-select dropdown (checkbox list) for the userType filter.
// Shape check only — deliberately permissive (no TLD allowlist), matching the
// PBX-user form and Login. Deliverability is the backend's call.
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

// Coerce a grant field (fax_id / voicemail_id) to an array. The API is
// inconsistent: it may return a native array, a JSON-encoded string ("[905]" —
// the same shape it accepts on write), or a single bare value. Anything
// unparseable degrades to an empty list rather than throwing.
function asGrantArray(v) {
  if (Array.isArray(v)) return v
  if (v === null || v === undefined || v === '') return []
  if (typeof v === 'string') {
    const s = v.trim()
    if (s.startsWith('[')) {
      try {
        const parsed = JSON.parse(s)
        return Array.isArray(parsed) ? parsed : [parsed]
      } catch { return [] }
    }
    return [s]
  }
  return [v]
}

// `searchable` adds a filter box at the top of the menu — worth it for the long
// fax/voicemail listings, needless for the short userType filter.
function MultiSelectDropdown({ options, selected, onChange, placeholder = 'Any type', summaryNoun = 'selected', className, searchable = false, searchPlaceholder = 'Search…' }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [rect, setRect] = useState(null)
  const [dropUp, setDropUp] = useState(false)
  const ref = useRef(null)
  const menuRef = useRef(null)

  // Close on outside click (menu is portalled, so check both trigger and menu).
  useEffect(() => {
    if (!open) return
    const h = (e) => {
      if (ref.current?.contains(e.target)) return
      if (menuRef.current?.contains(e.target)) return
      setOpen(false)
    }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [open])

  // Track the trigger position so the portalled menu aligns to it; flip up when
  // there isn't room below (e.g. near the bottom of a modal).
  useEffect(() => {
    if (!open) return
    const measure = () => {
      if (!ref.current) return
      const r = ref.current.getBoundingClientRect()
      setRect(r)
      // Menu is the 240px list plus the search row when one is shown.
      const h = searchable ? 300 : 260
      setDropUp(r.bottom + h > window.innerHeight && r.top > h)
    }
    measure()
    window.addEventListener('scroll', measure, true)
    window.addEventListener('resize', measure)
    return () => {
      window.removeEventListener('scroll', measure, true)
      window.removeEventListener('resize', measure)
    }
  }, [open, searchable])

  // Start each opening from an unfiltered list.
  useEffect(() => { if (!open) setQuery('') }, [open])

  const toggle = (v) => onChange(selected.includes(v) ? selected.filter(x => x !== v) : [...selected, v])
  const labels = options.filter(o => selected.includes(o.value)).map(o => o.label)
  const q = query.trim().toLowerCase()
  const visible = q ? options.filter(o => String(o.label).toLowerCase().includes(q)) : options
  return (
    <div className={cn('relative', className)} ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="flex h-9 w-full items-center justify-between gap-2 rounded-xl border border-input bg-background px-3 text-sm shadow-sm hover:border-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
      >
        <span className={cn('truncate', labels.length === 0 && 'text-muted-foreground')}>
          {labels.length === 0 ? placeholder : labels.length <= 2 ? labels.join(', ') : `${labels.length} ${summaryNoun}`}
        </span>
        <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
      </button>
      {open && rect && createPortal(
        <div
          ref={menuRef}
          style={{
            position: 'fixed',
            left: rect.left,
            width: rect.width,
            ...(dropUp
              ? { bottom: window.innerHeight - rect.top + 4 }
              : { top: rect.bottom + 4 }),
          }}
          className="z-[60] rounded-xl border border-border/60 bg-card shadow-2xl shadow-black/10 animate-dropdown-in py-1"
        >
          {searchable && (
            <div className="px-2 pb-1">
              <div className="relative">
                <Search className="absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
                <Input
                  autoFocus
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder={searchPlaceholder}
                  className="h-8 pl-7 text-sm"
                />
              </div>
            </div>
          )}
          <div className="max-h-60 overflow-auto">
          {visible.length === 0 && (
            <div className="px-3 py-2 text-sm text-muted-foreground">No matches</div>
          )}
          {visible.map(opt => (
            <div
              key={opt.value}
              onClick={() => toggle(opt.value)}
              className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-accent cursor-pointer"
            >
              <div className={cn('flex h-4 w-4 items-center justify-center rounded border shrink-0', selected.includes(opt.value) ? 'bg-primary border-primary' : 'border-input')}>
                {selected.includes(opt.value) && <Check className="h-3 w-3 text-primary-foreground" />}
              </div>
              <span>{opt.label}</span>
            </div>
          ))}
          </div>
        </div>,
        document.body
      )}
    </div>
  )
}

function UcUsersTab({ userEmail }) {
  const [search, setSearch]   = useState('')
  const debouncedSearch       = useDebounce(search, 300)
  const [activeFilter, setActiveFilter] = useState('active')  // active | inactive | all
  const [companyCode, setCompanyCode]   = useState('')        // '' = all companies
  const [userTypes, setUserTypes]       = useState([])        // [] = any type
  const [companies, setCompanies] = useState([])

  // Load the full company list once for the filter dropdown.
  useEffect(() => {
    let alive = true
    orgApi.listAll()
      .then(({ data }) => { if (alive) setCompanies(data.success || []) })
      .catch(() => { if (alive) setCompanies([]) })
    return () => { alive = false }
  }, [])

  // Build the query params. Memoized so useInfiniteList only resets on real change.
  const listParams = useMemo(() => {
    const p = {}
    if (debouncedSearch) p.search = debouncedSearch
    // is_active filter is skipped while searching (search spans all statuses).
    if (!debouncedSearch && activeFilter !== 'all') p.is_active = activeFilter === 'active'
    if (companyCode) p.code = companyCode              // omit for "All companies"
    if (userTypes.length) p.usertype = userTypes.join(',')
    return p
  }, [debouncedSearch, activeFilter, companyCode, userTypes])

  const { rows, total, loading, loadingMore, hasMore, error, loadMore, reload } = useInfiniteList(
    ucUsersApi.list,
    {
      params: listParams,
      pageSize: UC_PAGE_SIZE,
      selectResults: (d) => d.success || [],
      selectCount:   (d) => d.pagination?.total ?? (d.success?.length || 0),
    },
  )

  const [editUser, setEditUser] = useState(null)      // row being edited (null = closed)
  const [deleteUser, setDeleteUser] = useState(null)  // row pending delete confirmation
  const [deleting, setDeleting] = useState(false)
  const [resetUser, setResetUser] = useState(null)    // row pending password reset
  const [addOpen, setAddOpen] = useState(false)

  const confirmDelete = async () => {
    if (!deleteUser) return
    if (!userEmail) { toast.error('Cannot determine the logged-in user email.'); return }
    setDeleting(true)
    try {
      await ucUsersApi.delete(deleteUser.uuid, userEmail)
      toast.success('User deleted.')
      setDeleteUser(null)
      reload()
    } catch (e) {
      toast.error(apiErrorMessage(e, 'Failed to delete user.'))
    } finally { setDeleting(false) }
  }

  // Prefetch a second page on initial load (when more is available), so two
  // pages are shown by default before the user scrolls.
  const prefetchedRef = useRef(false)
  useEffect(() => { prefetchedRef.current = false }, [listParams])
  useEffect(() => {
    if (!loading && !loadingMore && hasMore && !prefetchedRef.current) {
      prefetchedRef.current = true
      loadMore()
    }
  }, [loading, loadingMore, hasMore, loadMore])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative w-64">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input placeholder="Search users…" className="pl-8" value={search} onChange={(e) => setSearch(e.target.value)} />
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
          <MultiSelectDropdown
            options={UC_USER_TYPE_OPTIONS}
            selected={userTypes}
            onChange={setUserTypes}
            placeholder="Any type"
            summaryNoun="types"
            className="w-44"
          />
          <Select value={companyCode} onChange={(e) => setCompanyCode(e.target.value)} wrapperClassName="w-56">
            <option value="">All companies</option>
            {companies.map(c => (
              <option key={c.id} value={c.code}>{c.companyName}</option>
            ))}
          </Select>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs text-muted-foreground">
            {total} user{total !== 1 ? 's' : ''}
          </span>
          <Button size="sm" onClick={() => setAddOpen(true)}><Plus className="h-4 w-4" />Add User</Button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-2.5 text-sm text-destructive">
          {apiErrorMessage(error, 'Failed to load users.')}
        </div>
      )}

      <Card><CardContent className="p-0 overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Email</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Extensions</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-16" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading
              ? [...Array(8)].map((_, i) => (
                  <TableRow key={i}>
                    {[...Array(7)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}
                  </TableRow>
                ))
              : rows.length === 0
                ? <TableRow><TableCell colSpan={7} className="text-center py-10 text-muted-foreground">No users found.</TableCell></TableRow>
                : rows.map((u) => {
                    const name = [u.firstName, u.lastName].filter(Boolean).join(' ') || '—'
                    const exts = u.extension_numbers || []
                    return (
                      <TableRow key={u.id}>
                        <TableCell className="font-medium">{name}</TableCell>
                        <TableCell className="text-sm text-muted-foreground">{u.email || '—'}</TableCell>
                        <TableCell><Badge variant="secondary" className="capitalize">{u.userType || '—'}</Badge></TableCell>
                        <TableCell className="text-sm">{u.company?.companyName || '—'}</TableCell>
                        <TableCell>
                          {exts.length === 0
                            ? <span className="text-muted-foreground text-sm">—</span>
                            : <div className="flex flex-wrap gap-1">
                                {exts.map((e, i) => <Badge key={i} variant="outline" className="font-mono text-[10px]">{e}</Badge>)}
                              </div>}
                        </TableCell>
                        <TableCell>
                          <Badge variant={u.is_active !== false ? 'success' : 'secondary'}>
                            {u.is_active !== false ? 'Active' : 'Inactive'}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Button variant="ghost" size="icon" className="h-7 w-7" title="Edit user" onClick={() => setEditUser(u)}>
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-7 w-7" title="Reset password" onClick={() => setResetUser(u)}>
                              <KeyRound className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              variant="ghost" size="icon"
                              className="h-7 w-7 text-destructive hover:text-destructive"
                              title="Delete user"
                              onClick={() => setDeleteUser(u)}
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })
            }
          </TableBody>
        </Table>
      </CardContent></Card>

      {!loading && rows.length > 0 && (
        <InfiniteScroll
          hasMore={hasMore}
          loadingMore={loadingMore}
          onLoadMore={loadMore}
          loaded={rows.length}
          total={total}
        />
      )}

      <UcUserEditDialog
        user={editUser}
        onClose={() => setEditUser(null)}
        onSaved={() => { setEditUser(null); reload() }}
      />

      {/* Hard-delete warning */}
      <Dialog open={!!deleteUser} onOpenChange={(v) => { if (!v && !deleting) setDeleteUser(null) }}>
        <DialogContent className="w-[95vw] max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="h-5 w-5" />
              Delete user permanently?
            </DialogTitle>
          </DialogHeader>
          {deleteUser && (
            <div className="space-y-3 py-1">
              <p className="text-sm">
                You are about to delete{' '}
                <span className="font-semibold">
                  {[deleteUser.firstName, deleteUser.lastName].filter(Boolean).join(' ') || deleteUser.email || 'this user'}
                </span>.
              </p>
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2.5 text-sm text-destructive space-y-1">
                <p className="font-medium">This is an irreversible action.</p>
                <p>
                  Once deleted, all data related to this user will be permanently removed —
                  including their <span className="font-medium">Chat Rooms, Contacts, and Messages</span>.
                </p>
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteUser(null)} disabled={deleting}>Cancel</Button>
            <Button variant="destructive" onClick={confirmDelete} disabled={deleting}>
              {deleting && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
              Delete Permanently
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <UcPasswordResetDialog
        user={resetUser}
        onClose={() => setResetUser(null)}
        onDone={() => setResetUser(null)}
      />

      <UcUserAddDialog
        open={addOpen}
        companies={companies}
        userEmail={userEmail}
        defaultCompanyCode={companyCode}
        onClose={() => setAddOpen(false)}
        onCreated={() => { setAddOpen(false); reload() }}
      />
    </div>
  )
}

// Add dialog for a new UC user. Fields: email (new user, lowercased),
// firstName, lastName, userType, company (dropdown → numeric id), one extension
// (from the company's tenant) + multiple DIDs, and a password mode toggle
// (email → omit password; manual → send it). `useremail` = acting admin.
function UcUserAddDialog({ open, companies, userEmail, defaultCompanyCode, onClose, onCreated }) {
  const EMPTY = {
    email: '', firstName: '', lastName: '',
    userType: 'user', companyId: '', extname: '', dids: [],
    faxUuids: [], voicemailIds: [],
    pwMode: 'email', password: '',   // pwMode: 'email' | 'manual'
  }
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [showPw, setShowPw] = useState(false)
  // Inline email error waits for blur so it doesn't fire while still typing.
  const [emailBlurred, setEmailBlurred] = useState(false)
  const [pbxExtensions, setPbxExtensions] = useState([])
  const [pbxDids, setPbxDids] = useState([])
  const [pbxFaxes, setPbxFaxes] = useState([])
  const [pbxVoicemails, setPbxVoicemails] = useState([])
  // True once the user has hand-edited the voicemail selection, which stops the
  // extension-follows-voicemail default below from overwriting their choice.
  const vmTouchedRef = useRef(false)

  // Only flag a non-empty value — emptiness is the "required" error's job.
  const emailInvalid = emailBlurred && form.email.trim() !== '' && !EMAIL_RE.test(form.email.trim().toLowerCase())

  const selectedCompany = companies.find(c => String(c.id) === String(form.companyId)) || null
  const tenantId = selectedCompany?.tenant_id
  const voiceEnabled = selectedCompany ? selectedCompany.voiceenable !== false : true
  const smsEnabled   = selectedCompany ? selectedCompany.smsenable === true : false

  // Reset on open; default the company to the tab's current filter if any.
  useEffect(() => {
    if (!open) return
    const preset = companies.find(c => c.code === defaultCompanyCode)
    setForm({ ...EMPTY, companyId: preset ? String(preset.id) : '' })
    setError(''); setShowPw(false); setSaving(false); setEmailBlurred(false)
    vmTouchedRef.current = false
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  // Load the chosen company's PBX extensions, DIDs, fax boxes and voicemail boxes.
  useEffect(() => {
    if (!open || !tenantId) {
      setPbxExtensions([]); setPbxDids([]); setPbxFaxes([]); setPbxVoicemails([])
      return
    }
    let alive = true
    const params = { page_size: 500, tenant: tenantId }
    extensionsApi.list(params)
      .then(({ data }) => { if (alive) setPbxExtensions(Array.isArray(data) ? data : data.results || []) })
      .catch(() => { if (alive) setPbxExtensions([]) })
    destinationsApi.list({ ...params, destination_enabled: true })
      .then(({ data }) => { if (alive) setPbxDids(Array.isArray(data) ? data : data.results || []) })
      .catch(() => { if (alive) setPbxDids([]) })
    faxApi.list(params)
      .then(({ data }) => { if (alive) setPbxFaxes(Array.isArray(data) ? data : data.results || []) })
      .catch(() => { if (alive) setPbxFaxes([]) })
    voicemailsApi.list(params)
      .then(({ data }) => { if (alive) setPbxVoicemails(Array.isArray(data) ? data : data.results || []) })
      .catch(() => { if (alive) setPbxVoicemails([]) })
    return () => { alive = false }
  }, [open, tenantId])

  // Default the voicemail selection to the mailbox belonging to the chosen
  // extension. There is no FK: an Extension names its mailbox via
  // Extension.voicemail_id, falling back to the extension number when blank —
  // the same rule the auto_create_voicemail signal uses to create the box, so
  // resolving it this way stays in step with whatever the Extensions page set.
  // An extension with voicemail disabled has no mailbox to select.
  // Skipped once the admin has touched the voicemail dropdown themselves.
  useEffect(() => {
    if (!open || vmTouchedRef.current) return
    const ext = form.extname
      ? pbxExtensions.find(x => (x.sip_username || x.extension) === form.extname)
      : null
    const mailboxId = ext && ext.voicemail_enabled !== false
      ? (ext.voicemail_id || ext.extension)
      : null
    const vm = mailboxId
      ? pbxVoicemails.find(v => String(v.voicemail_id) === String(mailboxId))
      : null
    setForm(p => ({ ...p, voicemailIds: vm ? [String(vm.voicemail_id)] : [] }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, form.extname, pbxExtensions, pbxVoicemails])

  const sf = (k) => (e) => setForm(p => ({ ...p, [k]: e.target.value }))

  const save = async () => {
    setError('')
    if (!userEmail)            { setError('Cannot determine the logged-in user email.'); return }
    if (!form.email.trim())    { setError('Email is required.'); return }
    // Same normalised value that goes in the payload below.
    if (!EMAIL_RE.test(form.email.trim().toLowerCase())) { setError('Enter a valid email address.'); return }
    if (!form.firstName.trim()){ setError('First name is required.'); return }
    if (!form.lastName.trim()) { setError('Last name is required.'); return }
    if (!form.companyId)       { setError('Select a company.'); return }
    if (form.pwMode === 'manual' && !form.password) { setError('Enter a password or switch to email delivery.'); return }

    if (voiceEnabled && !form.extname) { setError('Select an extension.'); return }
    // SMS-enabled companies require at least one DID (SMS needs a number).
    if (smsEnabled && form.dids.length === 0) { setError('Select at least one DID — SMS is enabled for this company.'); return }

    // Build one extension. Extension password is always required — use the
    // selected PBX extension's own password, falling back to a random one.
    // Phone label = the DID's destination_name from the PBX DID list. When voice
    // is off, extname/password are random; DIDs are still attached (for SMS).
    const selectedExt = pbxExtensions.find(x => (x.sip_username || x.extension) === form.extname)
    const phones = form.dids.map((num, i) => {
      const did = pbxDids.find(d => d.destination_number === num)
      return { phone: num, label: did?.destination_name || '', is_primary: i === 0 }
    })
    const extension = voiceEnabled
      ? { extname: form.extname, password: selectedExt?.password || randomToken(16), phones }
      : { extname: randomToken(6), password: randomToken(16), phones }

    const payload = {
      email:     form.email.trim().toLowerCase(),   // always lowercase
      useremail: userEmail,                          // acting admin
      firstName: form.firstName.trim(),
      lastName:  form.lastName.trim(),
      userType:  form.userType,
      company:   Number(form.companyId),
      extensions: [extension],
      // Fax / voicemail box grants, both JSON-encoded strings rather than
      // native arrays (e.g. voicemail_id: "[905]"). Voicemail carries numeric
      // mailbox ids; fax carries objects with the box's caller ID. Both are
      // omitted entirely when nothing is selected.
      ...(form.voicemailIds.length
        ? { voicemail_id: JSON.stringify(form.voicemailIds.map(Number)) }
        : {}),
      ...(form.faxUuids.length ? {
        fax_id: JSON.stringify(form.faxUuids.map(uuid => {
          const f = pbxFaxes.find(x => x.fax_uuid === uuid)
          return {
            fax_uuid:              uuid,
            fax_caller_id_name:    f?.fax_caller_id_name || '',
            fax_caller_id_number:  f?.fax_caller_id_number || '',
          }
        })),
      } : {}),
      // Manual mode sends the top-level password; email mode omits it.
      ...(form.pwMode === 'manual' ? { password: form.password } : {}),
    }

    setSaving(true)
    try {
      await ucUsersApi.create(payload)
      toast.success('User created.')
      onCreated()
    } catch (e) {
      setError(apiErrorMessage(e, 'Failed to create user.'))
    } finally { setSaving(false) }
  }

  const didOptions = (() => {
    const opts = pbxDids.map(d => ({
      value: d.destination_number,
      label: `${d.destination_number}${d.destination_name ? ` — ${d.destination_name}` : ''}`,
    }))
    for (const num of form.dids) if (num && !opts.some(o => o.value === num)) opts.unshift({ value: num, label: num })
    return opts
  })()

  const faxOptions = pbxFaxes.map(f => ({
    value: f.fax_uuid,
    label: `${f.fax_extension || ''}${f.fax_extension && f.fax_name ? ' — ' : ''}${f.fax_name || ''}` || f.fax_uuid,
  }))

  // Voicemail boxes are selected (and sent) by voicemail_id — the mailbox
  // number, not the UUID. Values are strings here; they are cast to numbers
  // when the payload is built.
  const voicemailOptions = pbxVoicemails.map(v => ({
    value: String(v.voicemail_id),
    label: `${v.voicemail_id}${v.voicemail_name ? ` — ${v.voicemail_name}` : ''}`,
  }))

  return (
    <Dialog open={open} onOpenChange={(v) => { if (!v && !saving) onClose() }}>
      <DialogContent className="w-[95vw] max-w-xl p-0 gap-0 overflow-hidden">
        <DialogHeader className="px-6 pt-5 pb-4 border-b">
          <DialogTitle>Add User</DialogTitle>
        </DialogHeader>

        <div className="px-6 py-5 space-y-5 max-h-[70vh] overflow-y-auto">
          {error && (
            <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label>First Name <span className="text-destructive">*</span></Label>
              <Input value={form.firstName} onChange={sf('firstName')} disabled={saving} />
            </div>
            <div className="space-y-1.5">
              <Label>Last Name <span className="text-destructive">*</span></Label>
              <Input value={form.lastName} onChange={sf('lastName')} disabled={saving} />
            </div>
            <div className="space-y-1.5">
              <Label>Email <span className="text-destructive">*</span></Label>
              <Input
                type="email"
                value={form.email}
                onChange={sf('email')}
                onBlur={() => setEmailBlurred(true)}
                disabled={saving}
                placeholder="user@example.com"
                aria-invalid={emailInvalid || undefined}
                className={cn(emailInvalid && 'border-destructive focus-visible:ring-destructive/40')}
              />
              {emailInvalid && (
                <p className="text-[11px] text-destructive">Enter a valid email address.</p>
              )}
            </div>
            <div className="space-y-1.5">
              <Label>User Type</Label>
              <Select value={form.userType} onChange={sf('userType')} disabled={saving}>
                {UC_USER_TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Company <span className="text-destructive">*</span></Label>
              <Select value={form.companyId} onChange={sf('companyId')} disabled={saving}>
                <option value="">— Select company —</option>
                {companies.map(c => <option key={c.id} value={c.id}>{c.companyName}</option>)}
              </Select>
            </div>
          </div>

          {/* Password mode */}
          <div className="space-y-2">
            <Label>Password</Label>
            <div className="grid grid-cols-2 gap-2">
              <button type="button" disabled={saving} onClick={() => setForm(p => ({ ...p, pwMode: 'email' }))}
                className={cn('rounded-lg border px-3 py-2 text-sm text-left transition-colors', form.pwMode === 'email' ? 'border-primary bg-primary/5 text-primary' : 'border-input hover:border-primary/40')}>
                <p className="font-medium">Email to user</p>
                <p className="text-[11px] text-muted-foreground">User sets it via emailed link.</p>
              </button>
              <button type="button" disabled={saving} onClick={() => setForm(p => ({ ...p, pwMode: 'manual' }))}
                className={cn('rounded-lg border px-3 py-2 text-sm text-left transition-colors', form.pwMode === 'manual' ? 'border-primary bg-primary/5 text-primary' : 'border-input hover:border-primary/40')}>
                <p className="font-medium">Set manually</p>
                <p className="text-[11px] text-muted-foreground">Enter a password now.</p>
              </button>
            </div>
            {form.pwMode === 'manual' && (
              <div className="relative">
                <Input type={showPw ? 'text' : 'password'} value={form.password} onChange={sf('password')} disabled={saving} autoComplete="new-password" placeholder="Enter password" className="pr-20 font-mono" />
                <div className="absolute right-1.5 top-1/2 -translate-y-1/2 flex items-center gap-0.5">
                  <button type="button" title="Generate" disabled={saving} onClick={() => { setForm(p => ({ ...p, password: randomToken(14) })); setShowPw(true) }}
                    className="p-1.5 rounded text-muted-foreground hover:text-foreground hover:bg-muted"><Wand2 className="h-3.5 w-3.5" /></button>
                  <button type="button" title={showPw ? 'Hide' : 'Show'} disabled={saving} onClick={() => setShowPw(s => !s)}
                    className="p-1.5 rounded text-muted-foreground hover:text-foreground hover:bg-muted">{showPw ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}</button>
                </div>
              </div>
            )}
          </div>

          {/* Extension (voice only) + DIDs (always shown). */}
          <div className="rounded-xl border p-3 space-y-3">
            {voiceEnabled && (
              <div className="space-y-1.5">
                <Label className="text-xs">Extension <span className="text-destructive">*</span></Label>
                <Select value={form.extname} onChange={sf('extname')} disabled={saving || !tenantId}>
                  <option value="">{tenantId ? '— Select extension —' : 'Select a company first'}</option>
                  {pbxExtensions.map(x => {
                    const val = x.sip_username || x.extension
                    return <option key={x.extension_uuid || x.id} value={val}>{x.extension}{x.effective_caller_id_name ? ` — ${x.effective_caller_id_name}` : ''}</option>
                  })}
                </Select>
              </div>
            )}
            <div className="space-y-1.5">
              <Label className="text-xs">
                Phones (DIDs){smsEnabled && <span className="text-destructive"> *</span>}
              </Label>
              <MultiSelectDropdown
                options={didOptions}
                selected={form.dids}
                onChange={(nums) => setForm(p => ({ ...p, dids: nums }))}
                placeholder={tenantId ? 'Select DIDs…' : 'Select a company first'}
                summaryNoun="DIDs"
                searchable
                searchPlaceholder="Search DIDs…"
                className="w-full"
              />
              {smsEnabled && <p className="text-[11px] text-muted-foreground">Required — SMS is enabled for this company.</p>}
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs">Fax Boxes</Label>
              <MultiSelectDropdown
                options={faxOptions}
                selected={form.faxUuids}
                onChange={(ids) => setForm(p => ({ ...p, faxUuids: ids }))}
                placeholder={tenantId ? 'Select fax boxes…' : 'Select a company first'}
                summaryNoun="fax boxes"
                searchable
                searchPlaceholder="Search fax boxes…"
                className="w-full"
              />
            </div>

            <div className="space-y-1.5">
              <Label className="text-xs">Voicemail Boxes</Label>
              <MultiSelectDropdown
                options={voicemailOptions}
                selected={form.voicemailIds}
                onChange={(ids) => { vmTouchedRef.current = true; setForm(p => ({ ...p, voicemailIds: ids })) }}
                placeholder={tenantId ? 'Select voicemail boxes…' : 'Select a company first'}
                summaryNoun="voicemail boxes"
                searchable
                searchPlaceholder="Search voicemail boxes…"
                className="w-full"
              />
              <p className="text-[11px] text-muted-foreground">Defaults to the selected extension's own mailbox.</p>
            </div>
          </div>
        </div>

        <DialogFooter className="px-6 py-4 border-t bg-muted/30">
          <Button variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
          <Button onClick={save} disabled={saving}>
            {saving && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
            Create User
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// Password reset for a UC user. Two options:
//   1. Send a reset notification (POST /user/userNotify with numeric id).
//   2. Set a custom password (edit API /user/editTokenpbx with { userid: uuid, password }),
//      asking for the new password once.
function UcPasswordResetDialog({ user, onClose, onDone }) {
  const [mode, setMode] = useState('notify')   // 'notify' | 'custom'
  const [pw, setPw] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!user) return
    setMode('notify'); setPw(''); setShowPw(false); setError(''); setSaving(false)
  }, [user])

  const submit = async () => {
    setError('')
    try {
      if (mode === 'notify') {
        setSaving(true)
        await ucUsersApi.notify(user.id)
        toast.success('Password reset email sent.')
      } else {
        if (!pw) { setError('Enter a new password.'); return }
        setSaving(true)
        await ucUsersApi.update({ userid: user.uuid, password: pw, other: '0' })
        toast.success('Password updated.')
      }
      onDone()
    } catch (e) {
      setError(apiErrorMessage(e, 'Failed to reset password.'))
    } finally { setSaving(false) }
  }

  const name = user ? ([user.firstName, user.lastName].filter(Boolean).join(' ') || user.email || 'this user') : ''

  const ModeCard = ({ value, icon: Icon, title, desc }) => {
    const active = mode === value
    return (
      <button
        type="button"
        onClick={() => setMode(value)}
        disabled={saving}
        className={cn(
          'relative flex items-start gap-3 rounded-xl border p-3 text-left transition-colors',
          active ? 'border-primary bg-primary/5' : 'border-input hover:border-primary/40',
        )}
      >
        <div className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-lg', active ? 'bg-primary/15 text-primary' : 'bg-muted text-muted-foreground')}>
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <p className={cn('text-sm font-medium', active && 'text-primary')}>{title}</p>
          <p className="text-[11px] text-muted-foreground mt-0.5 leading-snug">{desc}</p>
        </div>
        {active && (
          <span className="absolute right-2 top-2 flex h-4 w-4 items-center justify-center rounded-full bg-primary text-primary-foreground">
            <Check className="h-3 w-3" />
          </span>
        )}
      </button>
    )
  }

  return (
    <Dialog open={!!user} onOpenChange={(v) => { if (!v && !saving) onClose() }}>
      <DialogContent className="w-[95vw] max-w-md p-0 gap-0 overflow-hidden">
        <DialogHeader className="px-6 pt-5 pb-4 border-b">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <KeyRound className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <DialogTitle className="text-base">Reset Password</DialogTitle>
              {user && <p className="text-xs text-muted-foreground mt-0.5 truncate">for {name}</p>}
            </div>
          </div>
        </DialogHeader>

        {user && (
          <div className="px-6 py-5 space-y-4">
            {error && (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div>
            )}

            {/* Mode selector */}
            <div className="grid grid-cols-2 gap-2 items-stretch">
              <ModeCard value="notify" icon={Mail}     title="Send reset email"    desc="Email a reset link to the user." />
              <ModeCard value="custom" icon={KeyRound}  title="Set custom password" desc="Set a new password directly." />
            </div>

            {mode === 'custom' && (
              <div className="space-y-1.5">
                <Label>New Password <span className="text-destructive">*</span></Label>
                <div className="relative">
                  <Lock className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground pointer-events-none" />
                  <Input
                    type={showPw ? 'text' : 'password'}
                    value={pw}
                    onChange={(e) => setPw(e.target.value)}
                    disabled={saving}
                    autoComplete="new-password"
                    placeholder="Enter new password"
                    className="pl-9 pr-20 font-mono"
                  />
                  <div className="absolute right-1.5 top-1/2 -translate-y-1/2 flex items-center gap-0.5">
                    <button type="button" title="Generate" disabled={saving} onClick={() => { setPw(randomToken(14)); setShowPw(true) }}
                      className="p-1.5 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
                      <Wand2 className="h-3.5 w-3.5" />
                    </button>
                    <button type="button" title={showPw ? 'Hide' : 'Show'} disabled={saving} onClick={() => setShowPw(s => !s)}
                      className="p-1.5 rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors">
                      {showPw ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                    </button>
                  </div>
                </div>
                <p className="text-[11px] text-muted-foreground">The user's password will be changed immediately.</p>
              </div>
            )}
          </div>
        )}

        <DialogFooter className="px-6 py-4 border-t bg-muted/30">
          <Button variant="outline" onClick={onClose} disabled={saving}>Cancel</Button>
          <Button onClick={submit} disabled={saving}>
            {saving && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
            {mode === 'notify' ? 'Send Reset Email' : 'Update Password'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// Pull the most useful human-readable message out of an axios error from the
// external directory API, whose error shape varies (message / error / detail /
// field-keyed arrays / plain string).
function apiErrorMessage(e, fallback = 'Request failed.') {
  const d = e?.response?.data
  if (!d) return e?.message || fallback
  if (typeof d === 'string') return d
  if (d.message) return d.message
  if (d.error)   return typeof d.error === 'string' ? d.error : JSON.stringify(d.error)
  if (d.detail)  return d.detail
  // Field-level errors: { field: ["msg", ...] } or { field: "msg" }
  const parts = Object.entries(d)
    .filter(([, v]) => v != null)
    .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
  if (parts.length) return parts.join(' | ')
  return fallback
}

// Random alphanumeric string generator (used to fill ext/password when voice
// is disabled, so the payload still carries plausible values).
function randomToken(len = 16) {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
  let out = ''
  for (let i = 0; i < len; i++) out += chars[Math.floor(Math.random() * chars.length)]
  return out
}

// Edit dialog for a UC user. Editable: firstName, lastName, userType, and each
// extension's DID/extname + phones. Email is read-only. The save sends `userid`
// plus only the fields that changed; if ANY extension field changed, the whole
// extensions array is sent (in the /user/editTokenpbx shape).
function UcUserEditDialog({ user, onClose, onSaved }) {
  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const originalRef = useRef(null)
  // PBX extensions + DIDs for this user's tenant, populating the dropdowns.
  const [pbxExtensions, setPbxExtensions] = useState([])
  const [pbxDids, setPbxDids] = useState([])
  const [pbxFaxes, setPbxFaxes] = useState([])
  const [pbxVoicemails, setPbxVoicemails] = useState([])
  const tenantId = user?.company?.tenant_id
  // Voice off → the extension/DID selection is meaningless; hide it and send a
  // random ext + password on save instead.
  const voiceEnabled = user?.company?.voiceenable !== false

  // Fetch the tenant's PBX extensions, DIDs, fax boxes and voicemail boxes.
  useEffect(() => {
    if (!user || !tenantId) {
      setPbxExtensions([]); setPbxDids([]); setPbxFaxes([]); setPbxVoicemails([])
      return
    }
    let alive = true
    const params = { page_size: 500, tenant: tenantId }
    extensionsApi.list(params)
      .then(({ data }) => { if (alive) setPbxExtensions(Array.isArray(data) ? data : data.results || []) })
      .catch(() => { if (alive) setPbxExtensions([]) })
    destinationsApi.list({ ...params, destination_enabled: true })
      .then(({ data }) => { if (alive) setPbxDids(Array.isArray(data) ? data : data.results || []) })
      .catch(() => { if (alive) setPbxDids([]) })
    faxApi.list(params)
      .then(({ data }) => { if (alive) setPbxFaxes(Array.isArray(data) ? data : data.results || []) })
      .catch(() => { if (alive) setPbxFaxes([]) })
    voicemailsApi.list(params)
      .then(({ data }) => { if (alive) setPbxVoicemails(Array.isArray(data) ? data : data.results || []) })
      .catch(() => { if (alive) setPbxVoicemails([]) })
    return () => { alive = false }
  }, [user, tenantId])

  useEffect(() => {
    if (!user) { setForm(null); return }
    setError('')
    // Map each extension to the editable shape (extname, password, phones).
    const initial = {
      firstName: user.firstName || '',
      lastName:  user.lastName || '',
      userType:  user.userType || 'user',
      is_active: user.is_active !== false,
      // Existing grants, normalised to the same shapes the dropdowns use:
      // fax as a list of UUIDs, voicemail as a list of mailbox-id strings.
      // The API returns fax_id as objects; tolerate bare UUIDs too.
      faxUuids: asGrantArray(user.fax_id).map(f => (typeof f === 'string' ? f : f?.fax_uuid)).filter(Boolean),
      voicemailIds: asGrantArray(user.voicemail_id)
        .map(v => (v && typeof v === 'object' ? v.voicemail_id : v))
        .filter(v => v !== null && v !== undefined && v !== '')
        .map(String),
      extensions: (user.extension || []).map(ext => ({
        extname:  ext.extname || ext.username || '',
        password: ext.password || '',
        // DIDs are edited as a set of numbers; keep original phone objects to
        // preserve label/is_primary metadata when rebuilding on save.
        phoneNumbers: (ext.phones || []).map(p => p.phone).filter(Boolean),
        _origPhones: (ext.phones || []).map(p => ({
          phone:      p.phone || '',
          label:      p.label || '',
          is_primary: !!p.is_primary,
        })),
      })),
    }
    setForm(initial)
    // Snapshot for change detection (deep clone).
    originalRef.current = JSON.parse(JSON.stringify(initial))
  }, [user])

  const setField = (k) => (e) => setForm(p => ({ ...p, [k]: e.target.value }))
  const setExt = (i, k, v) => setForm(p => ({
    ...p,
    extensions: p.extensions.map((ex, idx) => idx === i ? { ...ex, [k]: v } : ex),
  }))
  const setExtDids = (i, nums) => setForm(p => ({
    ...p,
    extensions: p.extensions.map((ex, idx) => idx === i ? { ...ex, phoneNumbers: nums } : ex),
  }))

  const save = async () => {
    if (!form.firstName.trim()) { setError('First name is required.'); return }
    if (!form.lastName.trim())  { setError('Last name is required.'); return }
    const orig = originalRef.current
    const payload = { userid: user.uuid }   // always sent
    if (form.firstName !== orig.firstName) payload.firstName = form.firstName
    if (form.lastName  !== orig.lastName)  payload.lastName  = form.lastName
    if (form.userType  !== orig.userType)  payload.userType  = form.userType
    if (form.is_active !== orig.is_active) payload.is_active = form.is_active
    // Fax / voicemail grants, sent only when the set actually changed —
    // compared order-insensitively so merely reordering isn't a "change".
    // Sent whole (the full desired set), including [] to clear all grants.
    const sameSet = (a, b) => JSON.stringify([...a].sort()) === JSON.stringify([...b].sort())
    // Both grant fields go as JSON-encoded strings, not native arrays —
    // /user/editTokenpbx expects e.g. voicemail_id: "[905]".
    if (!sameSet(form.voicemailIds, orig.voicemailIds)) {
      payload.voicemail_id = JSON.stringify(form.voicemailIds.map(Number))
    }
    if (!sameSet(form.faxUuids, orig.faxUuids)) {
      payload.fax_id = JSON.stringify(form.faxUuids.map(uuid => {
        const f = pbxFaxes.find(x => x.fax_uuid === uuid)
        // Fall back to the caller ID already on the user's grant when the box
        // isn't in the fetched list (e.g. out of tenant scope).
        const prev = asGrantArray(user.fax_id).find(x => x && typeof x === 'object' && x.fax_uuid === uuid)
        return {
          fax_uuid:             uuid,
          fax_caller_id_name:   f?.fax_caller_id_name   ?? prev?.fax_caller_id_name   ?? '',
          fax_caller_id_number: f?.fax_caller_id_number ?? prev?.fax_caller_id_number ?? '',
        }
      }))
    }
    if (!voiceEnabled) {
      // Voice disabled: no extension UI. Always send a single random ext +
      // password so the payload carries plausible values (no phones/DIDs).
      payload.extensions = [{ extname: randomToken(6), password: randomToken(16), phones: [] }]
    } else if (JSON.stringify(form.extensions) !== JSON.stringify(orig.extensions)) {
      // If anything in extensions changed, send the whole array in the API shape:
      // { extname, password, phones:[{phone,label,is_primary}] }. Rebuild phones
      // from the selected DID numbers, preserving label/primary metadata where the
      // number existed before; the first selected DID is primary.
      payload.extensions = form.extensions.map(ex => ({
        extname:  ex.extname,
        password: ex.password,
        phones: (ex.phoneNumbers || []).map((num, i) => {
          const prev = (ex._origPhones || []).find(p => p.phone === num)
          return { phone: num, label: prev?.label || '', is_primary: i === 0 }
        }),
      }))
    }
    // Nothing but userid → nothing to save. (When voice is off, extensions is
    // always present, so this only triggers for voice-enabled users.)
    if (Object.keys(payload).length === 1) {
      setError('No changes to save.'); return
    }
    setSaving(true); setError('')
    try {
      await ucUsersApi.update(payload)
      toast.success('User updated.')
      onSaved()
    } catch (e) {
      setError(apiErrorMessage(e, 'Failed to update user.'))
    } finally { setSaving(false) }
  }

  return (
    <Dialog open={!!user} onOpenChange={(v) => { if (!v && !saving) onClose() }}>
      <DialogContent className="w-[95vw] max-w-xl p-0 gap-0 overflow-hidden">
        <DialogHeader className="px-6 pt-5 pb-4 border-b">
          <DialogTitle>Edit User</DialogTitle>
        </DialogHeader>
        {user && form && (
          <div className="px-6 py-5 space-y-5 max-h-[70vh] overflow-y-auto">
            {error && (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>First Name <span className="text-destructive">*</span></Label>
                <Input value={form.firstName} onChange={setField('firstName')} disabled={saving} />
              </div>
              <div className="space-y-1.5">
                <Label>Last Name <span className="text-destructive">*</span></Label>
                <Input value={form.lastName} onChange={setField('lastName')} disabled={saving} />
              </div>
              <div className="space-y-1.5">
                <Label>Email</Label>
                <Input value={user.email || ''} readOnly disabled className="bg-muted text-muted-foreground" />
              </div>
              <div className="space-y-1.5">
                <Label>User Type</Label>
                <Select value={form.userType} onChange={setField('userType')} disabled={saving}>
                  {UC_USER_TYPE_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
                </Select>
              </div>
            </div>

            <div className="flex items-center justify-between rounded-xl border px-4 py-3">
              <div>
                <p className="text-sm font-medium leading-none">Active</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">Disable to suspend this user's access.</p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={form.is_active}
                aria-label="Active"
                disabled={saving}
                onClick={() => setForm(p => ({ ...p, is_active: !p.is_active }))}
                className={cn(
                  'relative inline-flex h-5 w-9 shrink-0 items-center rounded-full border-2 border-transparent transition-colors',
                  form.is_active ? 'bg-primary' : 'bg-input',
                  saving && 'opacity-50 cursor-not-allowed',
                )}
              >
                <span className={cn('block h-4 w-4 rounded-full bg-white shadow transition-transform', form.is_active ? 'translate-x-4' : 'translate-x-0')} />
              </button>
            </div>

            {voiceEnabled && (
            <div className="space-y-2">
              <Label>Extensions</Label>
              {form.extensions.length === 0 && (
                <p className="text-sm text-muted-foreground">No extensions on this user.</p>
              )}
              {form.extensions.map((ext, ei) => (
                <div key={ei} className="rounded-xl border p-3 space-y-3">
                  <div className="space-y-1.5">
                    <Label className="text-xs">Extension</Label>
                    <Select value={ext.extname} onChange={(e) => setExt(ei, 'extname', e.target.value)} disabled={saving}>
                      <option value="">— Select extension —</option>
                      {/* Keep the current value selectable even if it's not in the fetched list. */}
                      {ext.extname && !pbxExtensions.some(x => (x.sip_username || x.extension) === ext.extname) && (
                        <option value={ext.extname}>{ext.extname}</option>
                      )}
                      {pbxExtensions.map(x => {
                        const val = x.sip_username || x.extension
                        return (
                          <option key={x.extension_uuid || x.id} value={val}>
                            {x.extension}{x.effective_caller_id_name ? ` — ${x.effective_caller_id_name}` : ''}
                          </option>
                        )
                      })}
                    </Select>
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs">Phones (DIDs)</Label>
                    <MultiSelectDropdown
                      options={(() => {
                        const opts = pbxDids.map(d => ({
                          value: d.destination_number,
                          label: `${d.destination_number}${d.destination_name ? ` — ${d.destination_name}` : ''}`,
                        }))
                        // Keep any already-assigned DID selectable even if it's not in the fetched list.
                        for (const num of ext.phoneNumbers || []) {
                          if (num && !opts.some(o => o.value === num)) opts.unshift({ value: num, label: num })
                        }
                        return opts
                      })()}
                      selected={ext.phoneNumbers || []}
                      onChange={(nums) => setExtDids(ei, nums)}
                      placeholder="Select DIDs…"
                      summaryNoun="DIDs"
                      searchable
                      searchPlaceholder="Search DIDs…"
                      className="w-full"
                    />
                  </div>
                </div>
              ))}
            </div>
            )}

            <div className="rounded-xl border p-3 space-y-3">
              <div className="space-y-1.5">
                <Label className="text-xs">Fax Boxes</Label>
                <MultiSelectDropdown
                  options={(() => {
                    const opts = pbxFaxes.map(f => ({
                      value: f.fax_uuid,
                      label: `${f.fax_extension || ''}${f.fax_extension && f.fax_name ? ' — ' : ''}${f.fax_name || ''}` || f.fax_uuid,
                    }))
                    // Keep an already-granted box selectable even if it's not in the fetched list.
                    for (const id of form.faxUuids) {
                      if (id && !opts.some(o => o.value === id)) {
                        const prev = asGrantArray(user.fax_id).find(x => x && typeof x === 'object' && x.fax_uuid === id)
                        opts.unshift({ value: id, label: prev?.fax_caller_id_name || id })
                      }
                    }
                    return opts
                  })()}
                  selected={form.faxUuids}
                  onChange={(ids) => setForm(p => ({ ...p, faxUuids: ids }))}
                  placeholder="Select fax boxes…"
                  summaryNoun="fax boxes"
                  searchable
                  searchPlaceholder="Search fax boxes…"
                  className="w-full"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Voicemail Boxes</Label>
                <MultiSelectDropdown
                  options={(() => {
                    const opts = pbxVoicemails.map(v => ({
                      value: String(v.voicemail_id),
                      label: `${v.voicemail_id}${v.voicemail_name ? ` — ${v.voicemail_name}` : ''}`,
                    }))
                    for (const id of form.voicemailIds) {
                      if (id && !opts.some(o => o.value === id)) opts.unshift({ value: id, label: id })
                    }
                    return opts
                  })()}
                  selected={form.voicemailIds}
                  onChange={(ids) => setForm(p => ({ ...p, voicemailIds: ids }))}
                  placeholder="Select voicemail boxes…"
                  summaryNoun="voicemail boxes"
                  searchable
                  searchPlaceholder="Search voicemail boxes…"
                  className="w-full"
                />
              </div>
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
      setError(apiErrorMessage(e, 'Failed to update organization.'))
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
            { key: 'uc',           label: 'Directory Users' },
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

      {/* ── UC Users ── */}
      {isSuperadmin && activeTab === 'uc' && (
        <UcUsersTab userEmail={loggedInUser?.user_email || loggedInUser?.email || ''} />
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
