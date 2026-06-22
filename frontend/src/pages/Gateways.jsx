import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { gateways as gatewaysApi } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { Plus, Pencil, Trash2, Search, RefreshCw, Loader2, Info } from 'lucide-react'
import { cn } from '@/lib/utils'

// ── Constants ─────────────────────────────────────────────────────────────────

const TRUNK_TYPES = [
  {
    value: 'register',
    label: 'Register',
    badge: 'Register',
    desc: 'PBX registers to provider with username/password. Most common for hosted SIP trunks.',
  },
  {
    value: 'account',
    label: 'Account',
    badge: 'Account',
    desc: 'Digest auth on outbound calls but no REGISTER sent. Provider authenticates each call.',
  },
  {
    value: 'peer',
    label: 'Peer / IP',
    badge: 'Peer',
    desc: 'IP-based trust. No credentials needed — provider allows calls from your IP address.',
  },
]

const EMPTY = {
  trunk_type: 'register',
  gateway: '',
  username: '',
  password: '',
  auth_username: '',
  from_user: '',
  proxy: '',
  from_domain: '',
  realm: '',
  register_transport: 'udp',
  codec_prefs: 'PCMU,PCMA',
  gateway_enabled: true,
  gateway_description: '',
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function statusBadge(state) {
  if (!state)              return <Badge variant="secondary">Unknown</Badge>
  if (state === 'REGED')   return <Badge variant="success">Registered</Badge>
  if (state === 'TRYING')  return <Badge variant="warning">Trying</Badge>
  if (state === 'FAILED')  return <Badge variant="destructive">Failed</Badge>
  if (state === 'UNREGED')   return <Badge variant="outline">Not Registered</Badge>
  if (state === 'NOREG')     return <Badge variant="outline">No Register</Badge>
  if (state === 'FAIL_WAIT') return <Badge variant="destructive">Failed (Retrying)</Badge>
  return <Badge variant="secondary">{state}</Badge>
}

function trunkTypeBadge(type) {
  const t = TRUNK_TYPES.find((x) => x.value === type) || TRUNK_TYPES[0]
  const variants = { register: 'default', account: 'outline', peer: 'secondary' }
  return <Badge variant={variants[t.value] || 'outline'} className="text-xs">{t.badge}</Badge>
}

function Field({ label, hint, children, span2 }) {
  return (
    <div className={cn('space-y-1.5', span2 && 'col-span-2')}>
      <Label className="text-xs">{label}</Label>
      {children}
      {hint && <p className="text-[11px] text-muted-foreground leading-tight">{hint}</p>}
    </div>
  )
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Gateways() {
  const navigate = useNavigate()
  // Route param drives the editor: undefined = list, 'new' = create, else edit by id.
  // The `/new` route has no :id param, so detect create from the path and only
  // use the param for edit.
  const { id: editParamId } = useParams()
  const location = useLocation()
  const isCreate   = location.pathname.endsWith('/gateways/new')
  const routeId    = editParamId
  const editorOpen = isCreate || routeId !== undefined

  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebounce(search, 300)
  const [editId, setEditId] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [deleting, setDeleting] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await gatewaysApi.list(debouncedSearch ? { search: debouncedSearch } : {})
      const list = Array.isArray(data) ? data : data.results || []

      // Fetch all registration states in one ESL call and merge by gateway name
      try {
        const { data: stateMap } = await gatewaysApi.statuses()
        list.forEach((gw) => { gw.state = stateMap[gw.gateway] || null })
      } catch {
        // ESL unavailable — states stay null → shows "Unknown"
      }

      setRows(list)
    } finally { setLoading(false) }
  }, [search])

  useEffect(() => { load() }, [load])

  const set = (key) => (e) => setForm((p) => ({ ...p, [key]: e.target.value }))
  const setVal = (key, val) => setForm((p) => ({ ...p, [key]: val }))

  // When proxy changes, keep from_domain in sync if it was the same or empty
  const setProxy = (e) => {
    const newProxy = e.target.value
    setForm((p) => ({
      ...p,
      proxy: newProxy,
      from_domain: (!p.from_domain || p.from_domain === p.proxy) ? newProxy : p.from_domain,
    }))
  }

  const rowToForm = (r) => ({
    trunk_type:          r.trunk_type || 'register',
    gateway:             r.gateway || '',
    username:            r.username || '',
    password:            '',        // write-only — never returned by API
    auth_username:       r.auth_username || '',
    from_user:           r.from_user || '',
    proxy:               r.proxy || '',
    from_domain:         r.from_domain || '',
    realm:               r.realm || '',
    register_transport:  r.register_transport || 'udp',
    codec_prefs:         r.codec_prefs || 'PCMU,PCMA',
    gateway_enabled:     r.gateway_enabled !== false,
    gateway_description: r.gateway_description || '',
  })

  // Navigate to the full-page editor; the route effect below loads the form.
  const openCreate  = () => navigate('/gateways/new')
  const openEdit    = (r) => navigate(`/gateways/${r.gateway_uuid}/edit`)
  const closeEditor = () => navigate('/gateways')

  // Sync form state to the current route.
  useEffect(() => {
    if (!editorOpen) return
    setFormError('')
    if (isCreate) { setEditId(null); setForm(EMPTY); return }
    setEditId(routeId)
    const row = rows.find(r => r.gateway_uuid === routeId)
    if (row) { setForm(rowToForm(row)); return }
    // Deep-link / refresh: fetch the row if the list isn't loaded yet.
    gatewaysApi.get?.(routeId)
      .then(({ data }) => setForm(rowToForm(data)))
      .catch(() => { setForm(EMPTY) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeId, isCreate, rows])

  const handleSave = async () => {
    if (!form.gateway.trim()) { setFormError('Gateway name is required.'); return }
    if (!form.proxy.trim()) { setFormError('Proxy / SIP host is required.'); return }
    setSaving(true); setFormError('')
    try {
      const payload = { ...form }
      if (editId && !payload.password) delete payload.password
      editId
        ? await gatewaysApi.update(editId, payload)
        : await gatewaysApi.create(payload)
      load(); closeEditor()
    } catch (err) {
      const d = err?.response?.data
      setFormError(typeof d === 'string' ? d : Object.values(d || {}).flat().join(' ') || 'Save failed.')
    } finally { setSaving(false) }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this trunk? Outbound routes using it will lose their gateway.')) return
    setDeleting(id)
    try { await gatewaysApi.delete(id); load() } finally { setDeleting(null) }
  }

  const handleReload = async () => {
    try { await gatewaysApi.reload() } catch {}
  }

  const needsCredentials = form.trunk_type !== 'peer'
  const needsRegisterOptions = form.trunk_type === 'register'

  // ── Full-page editor (routed) ──────────────────────────────────────────────
  if (editorOpen) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={closeEditor} className="-ml-2 gap-1">
            ← Trunks
          </Button>
          <span className="text-muted-foreground">/</span>
          <h1 className="text-lg font-semibold">{isCreate ? 'Add VoIP Trunk' : 'Edit VoIP Trunk'}</h1>
        </div>

        <Card>
          <div className="space-y-5 px-6 py-5">
            {formError && (
              <p className="rounded bg-destructive/10 border border-destructive/30 px-3 py-2 text-xs text-destructive">
                {formError}
              </p>
            )}

            {/* Trunk type selector */}
            <div className="space-y-2">
              <Label className="text-xs">Trunk Type *</Label>
              <div className="grid grid-cols-3 gap-2">
                {TRUNK_TYPES.map((t) => (
                  <button
                    key={t.value}
                    type="button"
                    onClick={() => setVal('trunk_type', t.value)}
                    className={cn(
                      'rounded-lg border p-3 text-left transition-all space-y-0.5',
                      form.trunk_type === t.value
                        ? 'border-primary bg-primary/5 ring-1 ring-primary'
                        : 'border-border hover:border-muted-foreground'
                    )}
                  >
                    <p className="text-xs font-semibold">{t.label}</p>
                    <p className="text-[10px] text-muted-foreground leading-tight">{t.desc}</p>
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Gateway Name *" span2>
                <Input value={form.gateway} onChange={set('gateway')} placeholder="my-trunk" />
              </Field>

              <Field label="Proxy / SIP Host *" span2>
                <Input value={form.proxy} onChange={setProxy} placeholder="sip.provider.com" />
              </Field>

              {needsCredentials && (
                <>
                  <Field label="Username">
                    <Input value={form.username} onChange={set('username')} placeholder="user@provider.com" />
                  </Field>
                  <Field label="Password" hint={editId ? 'Leave blank to keep current.' : ''}>
                    <Input
                      type="password"
                      value={form.password}
                      onChange={set('password')}
                      placeholder={editId ? '••••••••' : ''}
                      autoComplete="new-password"
                    />
                  </Field>
                  <Field label="Auth Username" hint="Override digest auth username. Leave blank to use Username.">
                    <Input value={form.auth_username} onChange={set('auth_username')} placeholder="freesw" />
                  </Field>
                  <Field label="Realm" hint="Leave blank to use proxy host.">
                    <Input value={form.realm} onChange={set('realm')} placeholder="sip.provider.com" />
                  </Field>
                </>
              )}

              {needsCredentials && (
                <Field label="From User" hint="SIP From: header user. Leave blank to use Username.">
                  <Input value={form.from_user} onChange={set('from_user')} placeholder="freesw" />
                </Field>
              )}

              <Field
                label="From Domain"
                hint="SIP From: header domain. Defaults to proxy host."
                span2
              >
                <div className="flex items-center gap-2">
                  <Input
                    value={form.from_domain}
                    onChange={set('from_domain')}
                    placeholder={form.proxy || 'sip.provider.com'}
                    className="flex-1"
                  />
                  {form.from_domain !== form.proxy && form.proxy && (
                    <button
                      type="button"
                      onClick={() => setVal('from_domain', form.proxy)}
                      className="shrink-0 text-xs text-primary hover:underline whitespace-nowrap"
                    >
                      Use proxy
                    </button>
                  )}
                </div>
              </Field>

              {needsRegisterOptions && (
                <>
                  <Field label="Transport">
                    <select
                      value={form.register_transport}
                      onChange={set('register_transport')}
                      className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    >
                      <option value="udp">UDP</option>
                      <option value="tcp">TCP</option>
                      <option value="tls">TLS</option>
                    </select>
                  </Field>
                  <Field label="Codec Preferences">
                    <Input value={form.codec_prefs} onChange={set('codec_prefs')} placeholder="PCMU,PCMA" />
                  </Field>
                </>
              )}

              <Field label="Description" span2>
                <Input
                  value={form.gateway_description}
                  onChange={set('gateway_description')}
                  placeholder="Optional notes"
                />
              </Field>
            </div>

            <label className="flex items-center gap-2 cursor-pointer">
              <input
                type="checkbox"
                checked={form.gateway_enabled}
                onChange={(e) => setVal('gateway_enabled', e.target.checked)}
                className="h-4 w-4 rounded border-input"
              />
              <span className="text-sm">Trunk enabled</span>
            </label>
          </div>

          <div className="flex justify-end gap-2 px-6 py-3 border-t">
            <Button variant="outline" size="sm" onClick={closeEditor}>Cancel</Button>
            <Button size="sm" onClick={handleSave} disabled={saving} className="gap-1.5">
              {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {isCreate ? 'Create Trunk' : 'Save Changes'}
            </Button>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search trunks…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-8 h-9"
          />
        </div>
        <Button variant="outline" size="sm" onClick={load} className="gap-1.5">
          <RefreshCw className="h-3.5 w-3.5" /> Refresh
        </Button>
        <Button variant="outline" size="sm" onClick={handleReload} className="gap-1.5">
          <RefreshCw className="h-3.5 w-3.5" /> Reload FS
        </Button>
        <Button size="sm" onClick={openCreate} className="gap-1.5 ml-auto">
          <Plus className="h-3.5 w-3.5" /> Add Trunk
        </Button>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Proxy / Host</TableHead>
                <TableHead>Username</TableHead>
                <TableHead>Transport</TableHead>
                <TableHead>Registration</TableHead>
                <TableHead className="w-20" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading
                ? Array.from({ length: 4 }).map((_, i) => (
                    <TableRow key={i}>
                      {Array.from({ length: 7 }).map((__, j) => (
                        <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                      ))}
                    </TableRow>
                  ))
                : rows.length === 0
                  ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center py-10 text-muted-foreground text-sm">
                        No VoIP trunks configured. Click <strong>Add Trunk</strong> to get started.
                      </TableCell>
                    </TableRow>
                  )
                  : rows.map((r) => (
                      <TableRow key={r.gateway_uuid} className={cn(!r.gateway_enabled && 'opacity-50')}>
                        <TableCell className="font-medium">{r.gateway}</TableCell>
                        <TableCell>{trunkTypeBadge(r.trunk_type)}</TableCell>
                        <TableCell className="font-mono text-xs text-muted-foreground">
                          {r.proxy || r.from_domain || '—'}
                        </TableCell>
                        <TableCell className="text-sm">{r.username || '—'}</TableCell>
                        <TableCell>
                          <Badge variant="outline" className="text-xs uppercase font-mono">
                            {r.register_transport || 'udp'}
                          </Badge>
                        </TableCell>
                        <TableCell>{statusBadge(r.state)}</TableCell>
                        <TableCell>
                          <div className="flex gap-1 justify-end">
                            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(r)}>
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              variant="ghost" size="icon"
                              className="h-7 w-7 text-destructive hover:text-destructive"
                              onClick={() => handleDelete(r.gateway_uuid)}
                              disabled={deleting === r.gateway_uuid}
                            >
                              {deleting === r.gateway_uuid
                                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                : <Trash2 className="h-3.5 w-3.5" />}
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

    </div>
  )
}
