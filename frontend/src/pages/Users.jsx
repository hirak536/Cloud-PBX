import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback } from 'react'
import { useSelector } from 'react-redux'
import { selectTenant, selectAuth } from '@/store'
import { roleOf, creatableRoles, GRANTABLE_PAGES, GRANTABLE_PATHS } from '@/lib/permissions'
import { users as api, tenants as tenantsApi, auth as authApi, ucUsers as ucUsersApi, extensions as extensionsApi, destinations as didsApi, fax as faxApi } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogClose } from '@/components/ui/dialog'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { Plus, Pencil, Trash2, Search, Loader2, ShieldCheck, Shield, User2, KeyRound, ChevronLeft, ChevronRight, Check, Eye, EyeOff, Wand2, Mail } from 'lucide-react'

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

const EMPTY_FORM = {
  first_name: '',
  last_name: '',
  full_name: '',
  username: '',
  user_email: '',
  user_enabled: true,
  role: 'user',
  admin_tenant_uuids: [],
  allowed_pages: [],
  // [] = all fax boxes (no restriction); non-empty = only those fax box UUIDs.
  allowed_fax_uuids: [],
}

function buildUsername(first, last) {
  const f = (first || '').trim().replace(/[^a-zA-Z]/g, '')
  const l = (last || '').trim().replace(/[^a-zA-Z]/g, '')
  if (!f && !l) return ''
  return (f.charAt(0) + l).toLowerCase()
}

// ── UC Users tab ─────────────────────────────────────────────────────────────

const UC_USER_TYPES = [
  { value: 'superadmin', label: 'Super Admin' },
  { value: 'admin',      label: 'Admin' },
  { value: 'user',       label: 'User' },
]

const EMPTY_UC_FORM = {
  firstName: '',
  lastName: '',
  email: '',
  userType: '',
  autoPassword: true,
  password: '',
  extensionId: '',
  extensionPassword: '',
  didIds: [],
  is_active: true,
}

function generatePassword() {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%'
  return Array.from({ length: 12 }, () => chars[Math.floor(Math.random() * chars.length)]).join('')
}

// Which UC user types a PBX role may create. UC types are named differently
// (superadmin/admin/user) from PBX roles (superuser/admin/user).
function creatableUcTypes(role) {
  if (role === 'superuser') return ['superadmin', 'admin', 'user']
  if (role === 'admin') return ['user']
  return []
}

function UcUsersTab({ tenantCode, tenantUuid, tenantName }) {
  const { user: loggedInUser }      = useSelector(selectAuth)
  const myRole                      = roleOf(loggedInUser)
  const allowedUcTypes              = creatableUcTypes(myRole)
  const [rows, setRows]             = useState([])
  const [loading, setLoading]       = useState(false)
  const [error, setError]           = useState('')
  const [page, setPage]             = useState(1)
  const [pagination, setPagination] = useState(null)

  const [dialogOpen, setDialogOpen] = useState(false)
  const [editUser, setEditUser]     = useState(null)   // null = add mode, object = edit mode
  const [form, setForm]             = useState(EMPTY_UC_FORM)
  const [formError, setFormError]   = useState('')
  const [saving, setSaving]         = useState(false)

  const [extensions, setExtensions]   = useState([])
  const [dids, setDids]               = useState([])
  const [loadingOpts, setLoadingOpts] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [voiceEnabled, setVoiceEnabled] = useState(null) // null = unknown (still loading)
  const [company, setCompany] = useState(null)

  const [resetDialogOpen, setResetDialogOpen] = useState(false)
  const [resetTarget, setResetTarget] = useState(null)
  const [resetPassword, setResetPassword] = useState('')
  const [resetShowPassword, setResetShowPassword] = useState(false)
  const [resetError, setResetError] = useState('')
  const [resetSubmitting, setResetSubmitting] = useState(false)
  const [resetSuccess, setResetSuccess] = useState('')
  const [notifySubmitting, setNotifySubmitting] = useState(false)
  const [resetMethod, setResetMethod] = useState('manual') // 'manual' | 'email'
  const [resetMustChange, setResetMustChange] = useState(false)

  const sendPasswordEmail = async () => {
    if (!resetTarget) return
    setNotifySubmitting(true)
    setResetError('')
    try {
      await ucUsersApi.notify({ userid: resetTarget.id })
      setResetDialogOpen(false)
      setResetSuccess(`Password email sent to ${resetTarget.email}.`)
      setTimeout(() => setResetSuccess(''), 4000)
    } catch (err) {
      const d = err?.response?.data
      setResetError(typeof d === 'string' ? d : d?.message || 'Failed to send password email.')
    } finally {
      setNotifySubmitting(false)
    }
  }

  const openResetPassword = (u) => {
    setResetTarget(u)
    setResetPassword('')
    setResetShowPassword(false)
    setResetError('')
    setResetMethod('manual')
    setResetMustChange(false)
    setResetDialogOpen(true)
  }

  const passwordStrength = (pw) => {
    if (!pw) return { score: 0, label: '', color: '' }
    let score = 0
    if (pw.length >= 8) score++
    if (pw.length >= 12) score++
    if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++
    if (/\d/.test(pw)) score++
    if (/[^A-Za-z0-9]/.test(pw)) score++
    const map = [
      { label: 'Too short', color: 'bg-destructive' },
      { label: 'Weak',      color: 'bg-destructive' },
      { label: 'Fair',      color: 'bg-amber-500' },
      { label: 'Good',      color: 'bg-amber-500' },
      { label: 'Strong',    color: 'bg-emerald-500' },
      { label: 'Very strong', color: 'bg-emerald-500' },
    ]
    return { score, ...map[Math.min(score, 5)] }
  }

  const submitResetPassword = async () => {
    if (!resetPassword.trim()) { setResetError('Password is required.'); return }
    if (!resetMustChange) {
      // Strict policy when user is NOT forced to change at next login
      const pw = resetPassword
      if (pw.length < 8 || !/[A-Z]/.test(pw) || !/[a-z]/.test(pw) || !/\d/.test(pw) || !/[^A-Za-z0-9]/.test(pw)) {
        setResetError('Password must be at least 8 characters and include uppercase, lowercase, number, and symbol.')
        return
      }
    }
    setResetSubmitting(true)
    setResetError('')
    try {
      await ucUsersApi.resetPassword({
        email:        resetTarget.email,
        password:     resetPassword,
        username:     loggedInUser?.user_email || loggedInUser?.username || '',
        newuserlogin: resetMustChange,
      })
      setResetDialogOpen(false)
      setResetSuccess(`Password reset for ${resetTarget.email}.`)
      setTimeout(() => setResetSuccess(''), 4000)
    } catch (err) {
      const d = err?.response?.data
      setResetError(typeof d === 'string' ? d : d?.message || 'Failed to reset password.')
    } finally {
      setResetSubmitting(false)
    }
  }

  useEffect(() => {
    if (!tenantUuid) return
    setVoiceEnabled(null)
    setCompany(null)
    ucUsersApi.listCompanies()
      .then(({ data }) => {
        const c = (data?.success ?? []).find(c => c.tenant_id === tenantUuid)
        setCompany(c || null)
        setVoiceEnabled(c ? !!c.voiceenable : false)
      })
      .catch(() => setVoiceEnabled(false))
  }, [tenantUuid])

  const PAGE_SIZE = 20

  const load = useCallback(async (p = 1) => {
    if (!tenantCode) return
    setLoading(true)
    setError('')
    try {
      const { data } = await ucUsersApi.list(tenantCode, p, PAGE_SIZE)
      const all = data.success ?? []
      setRows(all.filter(u => u.userType !== 'freeswitch'))
      setPagination(data.pagination ?? null)
      setPage(p)
    } catch (e) {
      setError(e?.response?.data?.message || 'Failed to load UC users.')
    } finally {
      setLoading(false)
    }
  }, [tenantCode])

  useEffect(() => { load(1) }, [load])

  const openEditUser = async (u) => {
    setEditUser(u)
    setForm({
      firstName:    u.firstName || '',
      lastName:     u.lastName || '',
      email:        u.email || '',
      userType:     u.userType || '',
      autoPassword: true,
      password:     '',
      extensionId:  '',
      extensionPassword: '',
      didIds:       [],
      is_active:    u.is_active ?? true,
    })
    setFormError('')
    setDialogOpen(true)
    setLoadingOpts(true)
    try {
      const [extRes, didRes] = await Promise.all([
        extensionsApi.list({ page_size: 200 }),
        didsApi.list({ page_size: 200 }),
      ])
      const extList = Array.isArray(extRes.data) ? extRes.data : extRes.data.results || []
      const didList = Array.isArray(didRes.data) ? didRes.data : didRes.data.results || []
      setExtensions(extList)
      setDids(didList)

      // Pre-select extension — match by extname or extension number from user's extension[]
      const userExt = u.extension?.[0]
      if (userExt) {
        const matched = extList.find(e =>
          String(e.id ?? e.extension_uuid) === String(userExt.id) ||
          e.sip_username === userExt.extname ||
          e.extension === userExt.phone
        )
        if (matched) {
          const userPhones = (u.extension || []).flatMap(ex => (ex.phones || []).map(p => p.phone))
          const matchedDids = didList
            .filter(d => userPhones.includes(d.destination_number))
            .map(d => d.destination_uuid)
          setForm(prev => ({
            ...prev,
            extensionId:       String(matched.id ?? matched.extension_uuid),
            extensionPassword: matched.password || userExt.password || '',
            didIds:            matchedDids,
          }))
        }
      }
    } catch {
      // non-fatal
    } finally {
      setLoadingOpts(false)
    }
  }

  const openAddUser = async () => {
    setEditUser(null)
    setForm({ ...EMPTY_UC_FORM, userType: allowedUcTypes.length === 1 ? allowedUcTypes[0] : '' })
    setFormError('')
    setDialogOpen(true)
    setLoadingOpts(true)
    try {
      const [extRes, didRes] = await Promise.all([
        extensionsApi.list({ page_size: 200 }),
        didsApi.list({ page_size: 200 }),
      ])
      setExtensions(Array.isArray(extRes.data) ? extRes.data : extRes.data.results || [])
      setDids(Array.isArray(didRes.data) ? didRes.data : didRes.data.results || [])
    } catch {
      // non-fatal — lists stay empty
    } finally {
      setLoadingOpts(false)
    }
  }

  const toggleDid = (uuid) => {
    setForm(p => ({
      ...p,
      didIds: p.didIds.includes(uuid)
        ? p.didIds.filter(d => d !== uuid)
        : [...p.didIds, uuid],
    }))
  }

  const handleSubmit = async () => {
    if (!form.firstName.trim()) { setFormError('First name is required.'); return }
    if (!form.lastName.trim())  { setFormError('Last name is required.'); return }
    if (!form.email.trim())     { setFormError('Email is required.'); return }
    if (!form.userType)         { setFormError('User type is required.'); return }
    if (!editUser && !form.autoPassword && !form.password.trim()) { setFormError('Password is required.'); return }

    // Build extensions array from selected extension + selected DIDs as phones
    const selectedExt = extensions.find(e => String(e.id ?? e.extension_uuid) === String(form.extensionId))
    const selectedDids = dids.filter(d => form.didIds.includes(d.destination_uuid))

    const phonesPayload = selectedDids.map((d, i) => ({
      phone:      d.destination_number,
      label:      d.destination_name || d.destination_number,
      is_primary: i === 0,
    }))

    let extensionsPayload = []
    // When deactivating a UC user, omit extension + phones entirely
    const deactivating = editUser && form.is_active === false
    if (deactivating) {
      extensionsPayload = []
    } else if (!voiceEnabled) {
      // Voice disabled for this company — send dummy extension carrying the selected DIDs as phones
      extensionsPayload = [{
        extname:  `dummy-${tenantCode}`,
        password: generatePassword(),
        phones:   phonesPayload,
      }]
    } else if (selectedExt) {
      extensionsPayload = [{
        extname:  selectedExt.sip_username || `${selectedExt.extension}-${tenantCode}`,
        password: form.extensionPassword || selectedExt.password || '',
        phones:   phonesPayload,
      }]
    }

    const payload = editUser ? {
      firstName:  form.firstName.trim(),
      lastName:   form.lastName.trim(),
      username:   loggedInUser?.user_email || loggedInUser?.username || '',
      userid:     editUser.uuid,
      userType:   form.userType,
      is_active:  form.is_active,
      ...(extensionsPayload.length > 0 ? { extensions: extensionsPayload } : {}),
    } : {
      email:       form.email.trim(),
      firstName:   form.firstName.trim(),
      lastName:    form.lastName.trim(),
      userType:    form.userType,
      company_id:  tenantUuid,
      companyName: tenantName,
      language:    'en',
      timeZone:    'America/Chicago',
      ...(form.autoPassword ? {} : { password: form.password }),
      ...(extensionsPayload.length > 0 ? { extensions: extensionsPayload } : {}),
    }

    setSaving(true)
    setFormError('')
    try {
      if (editUser) {
        await ucUsersApi.update(payload)
      } else {
        await ucUsersApi.create(payload)
      }
      setDialogOpen(false)
      load(page)
    } catch (err) {
      const d = err?.response?.data
      setFormError(typeof d === 'string' ? d : d?.message || Object.values(d || {}).flat().join(' ') || (editUser ? 'Failed to update user.' : 'Failed to create user.'))
    } finally {
      setSaving(false)
    }
  }

  if (!tenantCode) {
    return (
      <div className="rounded-md border border-muted bg-muted/30 px-4 py-8 text-center text-sm text-muted-foreground">
        Select a tenant to view UC users.
      </div>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        {company ? (
          <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/30 px-3 py-1.5 text-xs">
            <span className="text-muted-foreground">Modules:</span>
            <Badge variant={company.voiceenable ? 'success' : 'secondary'}>
              Voice: {company.voiceenable ? 'Active' : 'Inactive'}
            </Badge>
            <Badge variant={company.smsenable ? 'success' : 'secondary'}>
              SMS: {company.smsenable ? 'Active' : 'Inactive'}
            </Badge>
            <Badge variant={company.faxenable ? 'success' : 'secondary'}>
              Fax: {company.faxenable ? 'Active' : 'Inactive'}
            </Badge>
          </div>
        ) : <div />}
        <Button size="sm" onClick={openAddUser}><Plus className="h-4 w-4" />Add User</Button>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {resetSuccess && (
        <div className="rounded-md border border-primary/30 bg-primary/10 px-3 py-2 text-sm text-primary">
          {resetSuccess}
        </div>
      )}

      <Card><CardContent className="p-0 overflow-x-auto">
        <Table>
          <TableHeader><TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Type</TableHead>
            <TableHead>Extensions</TableHead>
            <TableHead>Assigned DIDs</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="w-16"></TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {loading
              ? [...Array(5)].map((_, i) => (
                  <TableRow key={i}>
                    {[...Array(7)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}
                  </TableRow>
                ))
              : rows.length === 0
                ? <TableRow><TableCell colSpan={7} className="text-center py-10 text-muted-foreground">No UC users found.</TableCell></TableRow>
                : rows.map((u) => (
                    <TableRow key={u.uuid}>
                      <TableCell className="font-medium">
                        {u.firstName} {u.lastName}
                        {u.email && <span className="block text-xs text-muted-foreground">{u.email}</span>}
                      </TableCell>
                      <TableCell className="text-muted-foreground text-sm">{u.email || '—'}</TableCell>
                      <TableCell>
                        {u.userType === 'superadmin'
                          ? <Badge variant="destructive" className="gap-1"><ShieldCheck className="h-3 w-3" />Super Admin</Badge>
                          : u.userType === 'admin'
                            ? <Badge variant="secondary" className="gap-1"><Shield className="h-3 w-3" />Admin</Badge>
                            : <Badge variant="outline" className="gap-1"><User2 className="h-3 w-3" />User</Badge>}
                      </TableCell>
                      <TableCell>
                        {u.extension_numbers?.length > 0
                          ? <div className="flex flex-wrap gap-1">
                              {u.extension_numbers.map(ext => (
                                <Badge key={ext} variant="outline" className="text-xs font-mono">{ext}</Badge>
                              ))}
                            </div>
                          : <span className="text-xs text-muted-foreground">—</span>}
                      </TableCell>
                      <TableCell>
                        {(() => {
                          const dids = (u.extension || []).flatMap(ex => (ex.phones || []).map(p => p.phone)).filter(Boolean)
                          return dids.length > 0
                            ? <div className="flex flex-wrap gap-1">
                                {dids.map(d => (
                                  <Badge key={d} variant="outline" className="text-xs font-mono">{d}</Badge>
                                ))}
                              </div>
                            : <span className="text-xs text-muted-foreground">—</span>
                        })()}
                      </TableCell>
                      <TableCell>
                        <Badge variant={u.is_active ? 'success' : 'secondary'}>
                          {u.is_active ? 'Active' : 'Inactive'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            title="Reset password"
                            onClick={() => openResetPassword(u)}
                          >
                            <KeyRound className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-7 w-7"
                            title="Edit user"
                            onClick={() => openEditUser(u)}
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
          </TableBody>
        </Table>
      </CardContent></Card>

      {pagination && pagination.total_pages > 1 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>
            Showing {((page - 1) * PAGE_SIZE) + 1}–{Math.min(page * PAGE_SIZE, pagination.total)} of {pagination.total}
          </span>
          <div className="flex gap-1">
            <Button variant="outline" size="icon" className="h-7 w-7" disabled={page <= 1} onClick={() => load(page - 1)}>
              <ChevronLeft className="h-3.5 w-3.5" />
            </Button>
            <Button variant="outline" size="icon" className="h-7 w-7" disabled={page >= pagination.total_pages} onClick={() => load(page + 1)}>
              <ChevronRight className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>
      )}

      {/* Add / Edit UC User dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="w-[95vw] max-w-lg p-0 gap-0">
          <DialogHeader className="px-6 py-4 border-b">
            <DialogTitle>{editUser ? 'Edit User' : 'Add User'}</DialogTitle>
            <DialogClose onClose={() => setDialogOpen(false)} />
          </DialogHeader>

          <div className="px-6 py-5 space-y-4 max-h-[70vh] overflow-y-auto">
            {/* Autofill decoys — keep at top, hidden from view */}
            <input type="text" name="username" autoComplete="username" style={{ display: 'none' }} tabIndex={-1} aria-hidden="true" />
            <input type="password" name="password" autoComplete="current-password" style={{ display: 'none' }} tabIndex={-1} aria-hidden="true" />

            {/* Active modules for this company */}
            {company && (
              <div className="flex flex-wrap items-center gap-2 rounded-md border bg-muted/30 px-3 py-2 text-xs">
                <span className="text-muted-foreground">Modules:</span>
                <Badge variant={company.voiceenable ? 'success' : 'secondary'}>
                  Voice: {company.voiceenable ? 'Active' : 'Inactive'}
                </Badge>
                <Badge variant={company.smsenable ? 'success' : 'secondary'}>
                  SMS: {company.smsenable ? 'Active' : 'Inactive'}
                </Badge>
                <Badge variant={company.faxenable ? 'success' : 'secondary'}>
                  Fax: {company.faxenable ? 'Active' : 'Inactive'}
                </Badge>
              </div>
            )}

            {formError && (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {formError}
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>First Name <span className="text-destructive">*</span></Label>
                <Input
                  name="uc-fname"
                  autoComplete="off"
                  placeholder="Enter first name"
                  value={form.firstName}
                  onChange={e => setForm(p => ({ ...p, firstName: e.target.value }))}
                />
              </div>
              <div className="space-y-1.5">
                <Label>Last Name <span className="text-destructive">*</span></Label>
                <Input
                  name="uc-lname"
                  autoComplete="off"
                  placeholder="Enter last name"
                  value={form.lastName}
                  onChange={e => setForm(p => ({ ...p, lastName: e.target.value }))}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label>Email <span className="text-destructive">*</span></Label>
              <Input
                type="email"
                name="uc-email"
                autoComplete="off"
                placeholder="Enter email"
                value={form.email}
                onChange={e => setForm(p => ({ ...p, email: e.target.value }))}
              />
            </div>

            <div className="space-y-1.5">
              <Label>User Type <span className="text-destructive">*</span></Label>
              <Select
                value={form.userType}
                disabled={!editUser && allowedUcTypes.length <= 1}
                onChange={e => setForm(p => ({ ...p, userType: e.target.value }))}
              >
                <option value="">Select user type</option>
                {/* Editing shows all types; creating only those this user may assign. */}
                {(editUser ? UC_USER_TYPES : UC_USER_TYPES.filter(t => allowedUcTypes.includes(t.value))).map(t => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </Select>
              {!editUser && allowedUcTypes.length <= 1 && (
                <p className="text-xs text-muted-foreground">
                  You can only create standard users. Contact a super admin to create admins.
                </p>
              )}
            </div>

            {/* Active/Inactive toggle — only shown when editing */}
            {editUser && (
              <div className="flex items-center justify-between rounded-md border px-3 py-2">
                <div>
                  <Label className="cursor-pointer" htmlFor="uc-user-active">Status</Label>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {form.is_active ? 'User is active' : 'User is inactive'}
                  </p>
                </div>
                <button
                  id="uc-user-active"
                  type="button"
                  role="switch"
                  aria-checked={form.is_active}
                  onClick={() => setForm(p => ({ ...p, is_active: !p.is_active }))}
                  className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2
                    ${form.is_active ? 'bg-primary' : 'bg-muted-foreground/40'}`}
                >
                  <span
                    className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200
                      ${form.is_active ? 'translate-x-5' : 'translate-x-0'}`}
                  />
                </button>
              </div>
            )}

            {/* Password — only shown when adding a new user */}
            {!editUser && <div className="space-y-2.5">
              <div className="flex items-center justify-between">
                <Label>Password <span className="text-destructive">*</span></Label>
                <button
                  type="button"
                  onClick={() => setForm(p => ({ ...p, autoPassword: !p.autoPassword, password: '' }))}
                  className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold border transition-colors duration-150
                    ${form.autoPassword
                      ? 'bg-primary/10 border-primary/20 text-primary hover:bg-primary/20'
                      : 'bg-muted border-border text-muted-foreground hover:bg-muted/70'}`}
                >
                  <Wand2 className="h-3 w-3" />
                  {form.autoPassword ? 'Auto-generate on' : 'Auto-generate off'}
                </button>
              </div>

              {form.autoPassword ? (
                <div className="flex items-start gap-2.5 rounded-lg border border-primary/20 bg-primary/5 px-3.5 py-3">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10">
                    <Mail className="h-3.5 w-3.5 text-primary" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-primary">Password will be auto-generated</p>
                    <p className="text-xs text-muted-foreground mt-0.5">A secure password will be sent to the user's email address.</p>
                  </div>
                </div>
              ) : (
                <div className="relative">
                  <Input
                    type={showPassword ? 'text' : 'password'}
                    name="uc-new-password"
                    autoComplete="new-password"
                    placeholder="Enter password"
                    value={form.password}
                    onChange={e => setForm(p => ({ ...p, password: e.target.value }))}
                    className="pr-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(v => !v)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              )}
            </div>}

            {/* Extension picker — hidden when company has voice disabled */}
            {voiceEnabled === false && (
              <div className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-400">
                Extension selection is unavailable because the Voice module is not active for this company.
              </div>
            )}
            {voiceEnabled && <div className="space-y-1.5">
              <Label>Select Extension</Label>
              {loadingOpts
                ? <Skeleton className="h-9 w-full" />
                : extensions.length === 0
                  ? <p className="text-sm text-muted-foreground">No extensions available for this tenant.</p>
                  : (
                    <Select
                      value={form.extensionId}
                      onChange={e => setForm(p => ({ ...p, extensionId: e.target.value }))}
                    >
                      <option value="">Select extension</option>
                      {extensions.map(ext => (
                        <option key={ext.id ?? ext.extension_uuid} value={ext.id ?? ext.extension_uuid}>
                          {ext.extension}{ext.effective_caller_id_name ? ` — ${ext.effective_caller_id_name}` : ''}
                        </option>
                      ))}
                    </Select>
                  )}
            </div>}

            {/* DID multi-select */}
            <div className="space-y-1.5">
              <Label>Select DIDs</Label>
              {loadingOpts
                ? <Skeleton className="h-24 w-full" />
                : dids.length === 0
                  ? <p className="text-sm text-muted-foreground">No DIDs available for this tenant.</p>
                  : (
                    <div className="border rounded-md max-h-40 overflow-y-auto divide-y">
                      {dids.map(did => {
                        const checked = form.didIds.includes(did.destination_uuid)
                        return (
                          <label
                            key={did.destination_uuid}
                            className="flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-muted/50 select-none"
                          >
                            <input
                              type="checkbox"
                              className="h-4 w-4 shrink-0 rounded border-input accent-primary"
                              checked={checked}
                              onChange={() => toggleDid(did.destination_uuid)}
                            />
                            <span className="text-sm font-mono">{did.destination_number}</span>
                            {did.destination_name && (
                              <span className="text-xs text-muted-foreground truncate">{did.destination_name}</span>
                            )}
                            {checked && <Check className="h-3.5 w-3.5 text-primary ml-auto shrink-0" />}
                          </label>
                        )
                      })}
                    </div>
                  )}
            </div>
          </div>

          <DialogFooter className="px-6 py-3 border-t gap-2">
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSubmit} disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              {editUser ? 'Save Changes' : 'Submit'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Reset password dialog */}
      <Dialog open={resetDialogOpen} onOpenChange={setResetDialogOpen}>
        <DialogContent className="w-[95vw] max-w-md p-0 gap-0">
          <DialogHeader className="px-6 py-4 border-b">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10">
                <KeyRound className="h-4 w-4 text-primary" />
              </div>
              <div className="min-w-0">
                <DialogTitle>Reset Password</DialogTitle>
                {resetTarget && (
                  <p className="text-xs text-muted-foreground truncate mt-0.5">
                    {resetTarget.firstName} {resetTarget.lastName} · {resetTarget.email}
                  </p>
                )}
              </div>
            </div>
            <DialogClose onClose={() => setResetDialogOpen(false)} />
          </DialogHeader>

          <div className="px-6 py-5 space-y-4">
            {resetError && (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {resetError}
              </div>
            )}

            {/* Method picker */}
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => setResetMethod('manual')}
                className={`group flex flex-col items-start gap-1.5 rounded-lg border px-3 py-2.5 text-left transition-colors
                  ${resetMethod === 'manual'
                    ? 'border-primary bg-primary/5 ring-1 ring-primary/30'
                    : 'border-border hover:bg-muted/50'}`}
              >
                <div className="flex w-full items-center justify-between">
                  <KeyRound className={`h-4 w-4 ${resetMethod === 'manual' ? 'text-primary' : 'text-muted-foreground'}`} />
                  {resetMethod === 'manual' && <Check className="h-3.5 w-3.5 text-primary" />}
                </div>
                <span className="text-sm font-medium">Set Manually</span>
                <span className="text-[11px] text-muted-foreground leading-tight">Type a new password yourself.</span>
              </button>
              <button
                type="button"
                onClick={() => setResetMethod('email')}
                className={`group flex flex-col items-start gap-1.5 rounded-lg border px-3 py-2.5 text-left transition-colors
                  ${resetMethod === 'email'
                    ? 'border-primary bg-primary/5 ring-1 ring-primary/30'
                    : 'border-border hover:bg-muted/50'}`}
              >
                <div className="flex w-full items-center justify-between">
                  <Mail className={`h-4 w-4 ${resetMethod === 'email' ? 'text-primary' : 'text-muted-foreground'}`} />
                  {resetMethod === 'email' && <Check className="h-3.5 w-3.5 text-primary" />}
                </div>
                <span className="text-sm font-medium">Send via Email</span>
                <span className="text-[11px] text-muted-foreground leading-tight">Notify the user with a password email.</span>
              </button>
            </div>

            {resetMethod === 'manual' ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label>New Password <span className="text-destructive">*</span></Label>
                  <button
                    type="button"
                    onClick={() => { setResetPassword(generatePassword()); setResetShowPassword(true) }}
                    className="inline-flex items-center gap-1 text-[11px] font-medium text-primary hover:underline"
                  >
                    <Wand2 className="h-3 w-3" /> Generate
                  </button>
                </div>
                <div className="relative">
                  <Input
                    type={resetShowPassword ? 'text' : 'password'}
                    name="uc-reset-password"
                    autoComplete="new-password"
                    placeholder="Enter new password"
                    value={resetPassword}
                    onChange={e => setResetPassword(e.target.value)}
                    className="pr-10 font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => setResetShowPassword(v => !v)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {resetShowPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {resetPassword && (() => {
                  const s = passwordStrength(resetPassword)
                  return (
                    <div className="space-y-1">
                      <div className="flex h-1 gap-1">
                        {[0, 1, 2, 3, 4].map(i => (
                          <div
                            key={i}
                            className={`flex-1 rounded-full transition-colors ${i < s.score ? s.color : 'bg-muted'}`}
                          />
                        ))}
                      </div>
                      <p className="text-[11px] text-muted-foreground">Strength: <span className="font-medium text-foreground">{s.label}</span></p>
                    </div>
                  )
                })()}

                <label className="flex items-start gap-2.5 rounded-md border px-3 py-2 cursor-pointer hover:bg-muted/40 select-none">
                  <input
                    type="checkbox"
                    className="h-4 w-4 mt-0.5 shrink-0 rounded border-input accent-primary"
                    checked={resetMustChange}
                    onChange={e => setResetMustChange(e.target.checked)}
                  />
                  <div className="min-w-0">
                    <p className="text-sm font-medium">User must change password at next login</p>
                    <p className="text-[11px] text-muted-foreground mt-0.5">
                      {resetMustChange
                        ? 'Any password is allowed — the user will be required to set a new one.'
                        : 'Password must be at least 8 characters with uppercase, lowercase, number, and symbol.'}
                    </p>
                  </div>
                </label>
              </div>
            ) : (
              <div className="flex items-start gap-2.5 rounded-lg border border-primary/20 bg-primary/5 px-3.5 py-3">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary/10">
                  <Mail className="h-3.5 w-3.5 text-primary" />
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-medium text-primary">Email the password</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    A password email will be sent to <span className="font-medium text-foreground break-all">{resetTarget?.email}</span>.
                  </p>
                </div>
              </div>
            )}
          </div>

          <DialogFooter className="px-6 py-3 border-t gap-2">
            <Button variant="outline" onClick={() => setResetDialogOpen(false)}>Cancel</Button>
            {resetMethod === 'manual' ? (
              <Button onClick={submitResetPassword} disabled={resetSubmitting || !resetPassword.trim()}>
                {resetSubmitting && <Loader2 className="h-4 w-4 animate-spin" />}
                <KeyRound className="h-4 w-4" />
                Reset Password
              </Button>
            ) : (
              <Button onClick={sendPasswordEmail} disabled={notifySubmitting}>
                {notifySubmitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
                Send Email
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function Users() {
  const { currentTenant } = useSelector(selectTenant)
  const { user: loggedInUser } = useSelector(selectAuth)
  const myRole = roleOf(loggedInUser)
  // Roles the logged-in user is allowed to create (superuser → all; admin → user only).
  const allowedRoles = creatableRoles(myRole)

  const [activeTab, setActiveTab]  = useState('uc')
  const [rows, setRows]            = useState([])
  const [loading, setLoading]      = useState(true)
  const [search, setSearch]        = useState('')
  const [allTenants, setAllTenants] = useState([])
  const [faxBoxes, setFaxBoxes]     = useState([])
  const [faxScope, setFaxScope]     = useState('all')  // 'all' | 'selected'
  const [dialogOpen, setDialogOpen] = useState(false)
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
      const { data } = await api.list(debouncedSearch ? { search: debouncedSearch } : {})
      const all = Array.isArray(data) ? data : data.results || []
      setRows(all.filter(u => !u.is_superuser))
    } finally { setLoading(false) }
  }, [debouncedSearch])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    tenantsApi.list({ page_size: 200 }).then(({ data }) => {
      setAllTenants(Array.isArray(data) ? data : data.results || [])
    }).catch(() => {})
  }, [])

  // Fax boxes for the per-user fax-box picker (tenant-scoped by the backend).
  useEffect(() => {
    faxApi.list({ page_size: 500 }).then(({ data }) => {
      setFaxBoxes(Array.isArray(data) ? data : data.results || [])
    }).catch(() => {})
  }, [currentTenant?.tenant_uuid])

  const f = (key) => (e) => setForm(p => ({ ...p, [key]: e.target.value }))

  const openCreate = () => {
    setEditId(null)
    setForm({ ...EMPTY_FORM, role: allowedRoles[0] || 'user' })
    setFaxScope('all')
    setFormError('')
    setDialogOpen(true)
  }

  const openEdit = (r) => {
    setEditId(r.user_uuid)
    const parts = (r.full_name || '').trim().split(' ')
    const firstName = parts[0] || ''
    const lastName = parts.slice(1).join(' ')
    setForm({
      first_name: firstName,
      last_name: lastName,
      full_name: r.full_name || '',
      username: r.username || '',
      user_email: r.user_email || '',
      user_enabled: r.user_enabled !== false,
      role: roleFromUser(r),
      admin_tenant_uuids: (r.admin_tenants || []).map(t => t.tenant_uuid),
      allowed_pages: Array.isArray(r.allowed_pages) ? r.allowed_pages : [],
      allowed_fax_uuids: Array.isArray(r.allowed_fax_uuids) ? r.allowed_fax_uuids : [],
    })
    setFaxScope((r.allowed_fax_uuids || []).length > 0 ? 'selected' : 'all')
    setFormError('')
    setDialogOpen(true)
  }

  const toggleTenant = (uuid) => {
    setForm(p => ({
      ...p,
      admin_tenant_uuids: p.admin_tenant_uuids.includes(uuid)
        ? p.admin_tenant_uuids.filter(id => id !== uuid)
        : [...p.admin_tenant_uuids, uuid],
    }))
  }

  const togglePage = (path) => {
    setForm(p => ({
      ...p,
      allowed_pages: p.allowed_pages.includes(path)
        ? p.allowed_pages.filter(x => x !== path)
        : [...p.allowed_pages, path],
    }))
  }

  const toggleAllPages = () => {
    setForm(p => ({
      ...p,
      allowed_pages: p.allowed_pages.length === GRANTABLE_PATHS.length ? [] : [...GRANTABLE_PATHS],
    }))
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
      admin_tenant_uuids: form.role === 'admin' ? form.admin_tenant_uuids : [],
      // Per-user page grants only apply to standard users; clear for admin/superuser.
      allowed_pages: form.role === 'user' ? form.allowed_pages : [],
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
      setDialogOpen(false)
      load()
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

  return (
    <div className="space-y-4">
      {/* Tab switcher */}
      <div className="flex items-center gap-1 border-b">
        {[
          { key: 'uc',  label: 'UC Users' },
          { key: 'pbx', label: 'PBX Users' },
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

      {/* ── PBX Users ── */}
      {activeTab === 'pbx' && (
        <>
          <div className="flex items-center gap-3">
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input placeholder="Search users..." className="pl-8" value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
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
                <TableHead>Role</TableHead>
                <TableHead>Tenant Access</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-28" />
              </TableRow></TableHeader>
              <TableBody>
                {loading
                  ? [...Array(5)].map((_, i) => (
                      <TableRow key={i}>
                        {[...Array(6)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}
                      </TableRow>
                    ))
                  : rows.length === 0
                    ? <TableRow><TableCell colSpan={6} className="text-center py-10 text-muted-foreground">No users found.</TableCell></TableRow>
                    : rows.map((r) => {
                        const role = roleFromUser(r)
                        return (
                          <TableRow key={r.user_uuid}>
                            <TableCell className="font-medium">
                              {r.full_name || r.username}
                              {r.full_name && <span className="block text-xs text-muted-foreground">{r.username}</span>}
                            </TableCell>
                            <TableCell className="text-muted-foreground text-sm">{r.user_email || '—'}</TableCell>
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

      {/* ── UC Users ── */}
      {activeTab === 'uc' && (
        <UcUsersTab
          tenantCode={currentTenant?.tenant_code}
          tenantUuid={currentTenant?.tenant_uuid}
          tenantName={currentTenant?.tenant_name}
        />
      )}

      {/* Dialog — only relevant for PBX tab */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="w-[95vw] max-w-lg p-0 gap-0">
          <DialogHeader className="px-6 py-4 border-b">
            <DialogTitle>{editId ? 'Edit User' : 'New User'}</DialogTitle>
            <DialogClose onClose={() => setDialogOpen(false)} />
          </DialogHeader>

          <div className="px-6 py-5 space-y-5 max-h-[70vh] overflow-y-auto">
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
                  Choose which pages this user can see. The Dashboard is always available.
                </p>
                <div className="border rounded-md max-h-60 overflow-y-auto divide-y">
                  {GRANTABLE_PAGES.map(group => (
                    <div key={group.group}>
                      <div className="px-3 py-1.5 bg-muted/40 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">
                        {group.group}
                      </div>
                      {group.items.map(item => {
                        const checked = form.allowed_pages.includes(item.path)
                        return (
                          <label
                            key={item.path}
                            className="flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-muted/50 select-none"
                          >
                            <input
                              type="checkbox"
                              className="h-4 w-4 shrink-0 rounded border-input accent-primary"
                              checked={checked}
                              onChange={() => togglePage(item.path)}
                            />
                            <span className="text-sm">{item.label}</span>
                            {checked && <Check className="h-3.5 w-3.5 text-primary ml-auto shrink-0" />}
                          </label>
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

          <DialogFooter className="px-6 py-3 border-t gap-2">
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              {editId ? 'Save Changes' : 'Create User'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
