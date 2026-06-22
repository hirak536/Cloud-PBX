import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { users as api, tenants as tenantsApi, auth as authApi } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { Plus, Pencil, Trash2, Search, Loader2, ShieldCheck, KeyRound, Eye, EyeOff } from 'lucide-react'

const EMPTY_FORM = {
  first_name: '',
  last_name: '',
  full_name: '',
  username: '',
  user_email: '',
  user_enabled: true,
  password: '',
}

function buildUsername(first, last) {
  const f = (first || '').trim().replace(/[^a-zA-Z]/g, '')
  const l = (last || '').trim().replace(/[^a-zA-Z]/g, '')
  if (!f && !l) return ''
  return (f.charAt(0) + l).toLowerCase()
}

export default function SuperUsers() {
  const navigate = useNavigate()
  const { id: editParamId } = useParams()
  const location = useLocation()
  const isCreate   = location.pathname.endsWith('/super-users/new')
  const routeId    = editParamId
  const editorOpen = isCreate || routeId !== undefined

  const [rows, setRows]          = useState([])
  const [loading, setLoading]    = useState(true)
  const [search, setSearch]      = useState('')
  const [editId, setEditId]      = useState(null)
  const [form, setForm]          = useState(EMPTY_FORM)
  const [saving, setSaving]      = useState(false)
  const [formError, setFormError] = useState('')
  const [deleting, setDeleting]  = useState(null)
  const [resetting, setResetting] = useState(null)
  const [resetMsg, setResetMsg]  = useState('')
  const [showPassword, setShowPassword] = useState(false)

  const debouncedSearch = useDebounce(search, 300)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.list(debouncedSearch ? { search: debouncedSearch } : {})
      const all = Array.isArray(data) ? data : data.results || []
      setRows(all.filter(u => u.is_superuser))
    } finally { setLoading(false) }
  }, [debouncedSearch])

  useEffect(() => { load() }, [load])

  const f = (key) => (e) => setForm(p => ({ ...p, [key]: e.target.value }))

  const rowToForm = (r) => {
    const parts = (r.full_name || '').trim().split(' ')
    const firstName = parts[0] || ''
    const lastName = parts.slice(1).join(' ')
    return {
      first_name:   firstName,
      last_name:    lastName,
      full_name:    r.full_name || '',
      username:     r.username || '',
      user_email:   r.user_email || '',
      user_enabled: r.user_enabled !== false,
      password:     '',
    }
  }

  const openCreate  = () => navigate('/super-users/new')
  const openEdit    = (r) => navigate('/super-users/' + r.user_uuid + '/edit')
  const closeEditor = () => navigate('/super-users')

  useEffect(() => {
    if (!editorOpen) return
    setFormError('')
    setShowPassword(false)
    if (isCreate) { setEditId(null); setForm(EMPTY_FORM); return }
    setEditId(routeId)
    const row = rows.find(r => r.user_uuid === routeId)
    if (row) { setForm(rowToForm(row)); return }
    api.get?.(routeId).then(({ data }) => setForm(rowToForm(data))).catch(() => setForm(EMPTY_FORM))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeId, isCreate, rows])

  const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

  const handleSave = async () => {
    if (!form.username.trim())   { setFormError('Username is required.'); return }
    if (!form.user_email.trim()) { setFormError('Email is required.'); return }
    if (!EMAIL_RE.test(form.user_email)) { setFormError('Enter a valid email address.'); return }
    if (!editId && !form.password.trim()) { setFormError('Password is required for new superusers.'); return }

    setSaving(true)
    setFormError('')

    const payload = {
      full_name:    form.full_name,
      username:     form.username,
      user_email:   form.user_email,
      user_enabled: form.user_enabled,
      is_superuser: true,
      is_staff:     true,
      admin_tenant_uuids: [],
    }

    if (!editId) {
      payload.password         = form.password
      payload.password_confirm = form.password
    }

    try {
      if (editId) {
        await api.update(editId, payload)
      } else {
        await api.create(payload)
      }
      load(); closeEditor()
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
    if (!confirm('Delete this superuser?')) return
    setDeleting(id)
    try { await api.delete(id); load() } finally { setDeleting(null) }
  }

  if (editorOpen) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={closeEditor} className="-ml-2 gap-1">
            ← Super Users
          </Button>
          <span className="text-muted-foreground">/</span>
          <h1 className="text-lg font-semibold">{isCreate ? 'New Super User' : 'Edit Super User'}</h1>
        </div>

        <Card>
          <div className="px-6 py-5 space-y-4">
            {formError && (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {formError}
              </div>
            )}

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
                      username: buildUsername(first, p.last_name),
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
                      username: buildUsername(p.first_name, last),
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

            {!editId && (
              <div className="space-y-1.5">
                <Label>Password <span className="text-destructive">*</span></Label>
                <div className="relative">
                  <Input
                    type={showPassword ? 'text' : 'password'}
                    placeholder="Enter password"
                    value={form.password}
                    onChange={f('password')}
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
              </div>
            )}

            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-400">
              Superusers have unrestricted access to all tenants and system settings.
            </div>

            <div className="border-t pt-4">
              <label className="flex items-center gap-2.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  className="h-4 w-4 rounded border-input accent-primary"
                  checked={form.user_enabled}
                  onChange={e => setForm(p => ({ ...p, user_enabled: e.target.checked }))}
                />
                <span className="text-sm font-medium">Account enabled</span>
              </label>
            </div>
          </div>

          <div className="flex justify-end gap-2 px-6 py-3 border-t">
            <Button variant="outline" size="sm" onClick={closeEditor}>Cancel</Button>
            <Button size="sm" onClick={handleSave} disabled={saving} className="gap-1.5">
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              {isCreate ? 'Create Superuser' : 'Save Changes'}
            </Button>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold">Super Admins</h2>
          <p className="text-xs text-muted-foreground mt-0.5">PBX superusers with full system access across all tenants.</p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search superusers..."
            className="pl-8"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <Button size="sm" onClick={openCreate}><Plus className="h-4 w-4" />Add Superuser</Button>
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
            <TableHead>Username</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="w-28" />
          </TableRow></TableHeader>
          <TableBody>
            {loading
              ? [...Array(4)].map((_, i) => (
                  <TableRow key={i}>
                    {[...Array(5)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}
                  </TableRow>
                ))
              : rows.length === 0
                ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-10 text-muted-foreground">
                      No superusers found.
                    </TableCell>
                  </TableRow>
                )
                : rows.map(r => (
                    <TableRow key={r.user_uuid}>
                      <TableCell>
                        <div className="flex items-center gap-2.5">
                          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-[hsl(217,91%,55%)] text-white text-xs font-bold shadow-sm shadow-primary/30">
                            {(r.full_name || r.username).split(' ').map(n => n[0]).slice(0, 2).join('').toUpperCase()}
                          </div>
                          <div>
                            <p className="font-medium text-sm">{r.full_name || r.username}</p>
                            <Badge variant="default" className="gap-1 text-[10px] mt-0.5 h-4 px-1.5">
                              <ShieldCheck className="h-2.5 w-2.5" />Superuser
                            </Badge>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">{r.username}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">{r.user_email || '—'}</TableCell>
                      <TableCell>
                        <Badge variant={r.user_enabled !== false ? 'success' : 'secondary'}>
                          {r.user_enabled !== false ? 'Active' : 'Inactive'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost" size="icon" className="h-7 w-7"
                            title="Reset password"
                            onClick={() => handleResetPassword(r.user_uuid)}
                            disabled={resetting === r.user_uuid}
                          >
                            {resetting === r.user_uuid
                              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              : <KeyRound className="h-3.5 w-3.5" />}
                          </Button>
                          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(r)}>
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive"
                            onClick={() => handleDelete(r.user_uuid)}
                            disabled={deleting === r.user_uuid}
                          >
                            {deleting === r.user_uuid
                              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              : <Trash2 className="h-3.5 w-3.5" />}
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
          </TableBody>
        </Table>
      </CardContent></Card>
    </div>
  )
}
