import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { clientApiKeys, tenants } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogClose } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { Plus, Pencil, Trash2, Loader2, Key, Eye, EyeOff, Copy, Check, X } from 'lucide-react'

const EMPTY = {
  tenant: '',
  label: '',
  expires_at: '',
  webhook_url: '',
  webhook_secret: '',
}

function urlsToList(csv) {
  const urls = (csv || '').split(',').map(u => u.trim()).filter(Boolean)
  return urls.length ? urls : ['']
}

export default function ApiKeys() {
  const navigate = useNavigate()
  // Route param drives the editor: undefined = list, /new = create, else edit by id.
  // The `/new` route has no :id param, so detect create from the path and only
  // use the param for edit.
  const { id: editParamId } = useParams()
  const location = useLocation()
  const isCreate   = location.pathname.endsWith('/api-keys/new')
  const routeId    = editParamId
  const editorOpen = isCreate || routeId !== undefined

  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [tenantList, setTenantList] = useState([])
  const [editId, setEditId] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [deleting, setDeleting] = useState(null)
  // Shown once after creation
  const [newKey, setNewKey] = useState(null)
  const [copied, setCopied] = useState(false)
  const [showSecret, setShowSecret] = useState(false)
  const [webhookUrls, setWebhookUrls] = useState([''])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await clientApiKeys.list()
      setRows(Array.isArray(data) ? data : data.results || [])
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    tenants.list({ page_size: 200 }).then(({ data }) => {
      setTenantList(Array.isArray(data) ? data : data.results || [])
    }).catch(() => {})
  }, [])

  const f = (key) => (e) => setForm(p => ({ ...p, [key]: e.target.value }))

  const rowToForm = (r) => ({
    tenant: r.tenant || '',
    label: r.label || '',
    expires_at: r.expires_at || '',
    webhook_url: r.webhook_url || '',
    webhook_secret: '',
    is_active: r.is_active,
  })

  // Navigate to the full-page editor; the route effect below loads the form.
  const openCreate  = () => navigate('/api-keys/new')
  const openEdit    = (r) => navigate('/api-keys/' + r.id + '/edit')
  const closeEditor = () => navigate('/api-keys')

  // Sync form state to the current route.
  useEffect(() => {
    if (!editorOpen) return
    setFormError('')
    setShowSecret(false)
    if (isCreate) { setEditId(null); setForm(EMPTY); setWebhookUrls(['']); return }
    setEditId(routeId)
    const row = rows.find(r => r.id === routeId)
    if (row) { setForm(rowToForm(row)); setWebhookUrls(urlsToList(row.webhook_url)); return }
    // Deep-link / refresh: fetch the row if the list isn't loaded yet.
    clientApiKeys.get?.(routeId)
      .then(({ data }) => { setForm(rowToForm(data)); setWebhookUrls(urlsToList(data.webhook_url)) })
      .catch(() => { setForm(EMPTY); setWebhookUrls(['']) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeId, isCreate])

  const handleSave = async () => {
    if (!form.tenant && !editId) { setFormError('Tenant is required.'); return }
    if (!form.label) { setFormError('Label is required.'); return }
    const joinedUrls = webhookUrls.map(u => u.trim()).filter(Boolean).join(',')
    setSaving(true); setFormError('')
    try {
      if (editId) {
        const payload = { label: form.label, expires_at: form.expires_at || null, webhook_url: joinedUrls }
        if (form.webhook_secret) payload.webhook_secret = form.webhook_secret
        await clientApiKeys.update(editId, payload)
        load()
        closeEditor()
      } else {
        const payload = { ...form, webhook_url: joinedUrls, expires_at: form.expires_at || null }
        const { data } = await clientApiKeys.create(payload)
        load()
        // Navigate back to the list FIRST, then open the secret-reveal dialog
        // so the user sees the one-time secret on the list page.
        closeEditor()
        if (data.api_key) setNewKey(data.api_key)
      }
    } catch (err) {
      const d = err?.response?.data
      setFormError(typeof d === 'string' ? d : Object.values(d || {}).flat().join(' ') || 'Save failed.')
    } finally { setSaving(false) }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this API key? This cannot be undone and will revoke access immediately.')) return
    setDeleting(id)
    try { await clientApiKeys.delete(id); load() } finally { setDeleting(null) }
  }

  const handleToggle = async (row) => {
    try {
      await clientApiKeys.update(row.id, { is_active: !row.is_active })
      load()
    } catch {}
  }

  const copyKey = () => {
    if (!newKey) return
    navigator.clipboard.writeText(newKey)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // ── Full-page editor (routed) ──────────────────────────────────────────────
  if (editorOpen) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={closeEditor} className="-ml-2 gap-1">
            ← API Keys
          </Button>
          <span className="text-muted-foreground">/</span>
          <h1 className="text-lg font-semibold">{isCreate ? 'New API Key' : 'Edit API Key'}</h1>
        </div>

        <Card>
          <div className="px-6 py-5 space-y-4">
            {formError && (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {formError}
              </div>
            )}
            {!editId && (
              <div className="space-y-1.5">
                <Label>Tenant *</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                  value={form.tenant}
                  onChange={(e) => setForm(p => ({ ...p, tenant: e.target.value }))}
                >
                  <option value="">Select tenant…</option>
                  {tenantList.map(t => (
                    <option key={t.tenant_uuid} value={t.tenant_uuid}>
                      {t.tenant_code} — {t.tenant_name}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div className="space-y-1.5">
              <Label>Label *</Label>
              <Input placeholder="e.g. Phone App Server" value={form.label} onChange={f('label')} />
            </div>
            <div className="space-y-1.5">
              <Label>Expires (optional)</Label>
              <Input type="date" value={form.expires_at} onChange={f('expires_at')} />
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label>Webhook URLs</Label>
                <button
                  type="button"
                  className="text-xs text-primary hover:underline flex items-center gap-1"
                  onClick={() => setWebhookUrls(u => [...u, ''])}
                >
                  <Plus className="h-3 w-3" /> Add URL
                </button>
              </div>
              <div className="space-y-2">
                {webhookUrls.map((url, i) => (
                  <div key={i} className="flex gap-1.5">
                    <Input
                      placeholder="https://yourserver.com/webhook"
                      value={url}
                      onChange={e => setWebhookUrls(u => u.map((v, j) => j === i ? e.target.value : v))}
                    />
                    {webhookUrls.length > 1 && (
                      <button
                        type="button"
                        className="text-muted-foreground hover:text-destructive shrink-0"
                        onClick={() => setWebhookUrls(u => u.filter((_, j) => j !== i))}
                      >
                        <X className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>{editId ? 'Webhook Secret (leave blank to keep unchanged)' : 'Webhook Secret'}</Label>
              <div className="relative">
                <Input
                  type={showSecret ? 'text' : 'password'}
                  placeholder={editId ? '••••••••' : 'Secret for HMAC signing'}
                  value={form.webhook_secret}
                  onChange={f('webhook_secret')}
                  className="pr-9"
                />
                <button
                  type="button"
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  onClick={() => setShowSecret(s => !s)}
                >
                  {showSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
          </div>

          <div className="flex justify-end gap-2 px-6 py-3 border-t">
            <Button variant="outline" onClick={closeEditor}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              {isCreate ? 'Generate Key' : 'Save'}
            </Button>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Client API Keys</h2>
          <p className="text-sm text-muted-foreground">Manage server-to-server API keys for tenant integrations</p>
        </div>
        <Button size="sm" onClick={openCreate}><Plus className="h-4 w-4" />New API Key</Button>
      </div>

      <Card><CardContent className="p-0 overflow-x-auto">
        <Table>
          <TableHeader><TableRow>
            <TableHead>Label</TableHead>
            <TableHead>Tenant</TableHead>
            <TableHead>Webhook URL</TableHead>
            <TableHead>Expires</TableHead>
            <TableHead>Created</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="w-24" />
          </TableRow></TableHeader>
          <TableBody>
            {loading
              ? [...Array(4)].map((_, i) => (
                  <TableRow key={i}>
                    {[...Array(7)].map((_, j) => (
                      <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                    ))}
                  </TableRow>
                ))
              : rows.length === 0
              ? <TableRow><TableCell colSpan={7} className="text-center py-10 text-muted-foreground">No API keys yet.</TableCell></TableRow>
              : rows.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-medium">
                      <div className="flex items-center gap-1.5">
                        <Key className="h-3.5 w-3.5 text-muted-foreground" />
                        {r.label}
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="font-mono text-xs">{r.tenant_code}</span>
                      <span className="ml-1 text-muted-foreground text-xs">{r.tenant_name}</span>
                    </TableCell>
                    <TableCell className="max-w-[180px] truncate text-xs text-muted-foreground">
                      {r.webhook_url || '—'}
                    </TableCell>
                    <TableCell className="text-xs">{r.expires_at || '—'}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {r.created_at ? new Date(r.created_at).toLocaleDateString() : '—'}
                      {r.created_by_username && <span className="block">{r.created_by_username}</span>}
                    </TableCell>
                    <TableCell>
                      <button onClick={() => handleToggle(r)} className="cursor-pointer">
                        <Badge variant={r.is_active ? 'success' : 'secondary'}>
                          {r.is_active ? 'Active' : 'Disabled'}
                        </Badge>
                      </button>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(r)}>
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost" size="icon"
                          className="h-7 w-7 text-destructive hover:text-destructive"
                          onClick={() => handleDelete(r.id)}
                          disabled={deleting === r.id}
                        >
                          {deleting === r.id
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

      {/* Create / Edit dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="w-[95vw] max-w-md p-0 gap-0">
          <DialogHeader className="px-6 py-4 border-b">
            <DialogTitle>{editId ? 'Edit API Key' : 'New API Key'}</DialogTitle>
            <DialogClose onClose={() => setDialogOpen(false)} />
          </DialogHeader>
          <div className="px-6 py-5 space-y-4">
            {formError && (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {formError}
              </div>
            )}
            {!editId && (
              <div className="space-y-1.5">
                <Label>Tenant *</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm"
                  value={form.tenant}
                  onChange={(e) => setForm(p => ({ ...p, tenant: e.target.value }))}
                >
                  <option value="">Select tenant…</option>
                  {tenantList.map(t => (
                    <option key={t.tenant_uuid} value={t.tenant_uuid}>
                      {t.tenant_code} — {t.tenant_name}
                    </option>
                  ))}
                </select>
              </div>
            )}
            <div className="space-y-1.5">
              <Label>Label *</Label>
              <Input placeholder="e.g. Phone App Server" value={form.label} onChange={f('label')} />
            </div>
            <div className="space-y-1.5">
              <Label>Expires (optional)</Label>
              <Input type="date" value={form.expires_at} onChange={f('expires_at')} />
            </div>
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <Label>Webhook URLs</Label>
                <button
                  type="button"
                  className="text-xs text-primary hover:underline flex items-center gap-1"
                  onClick={() => setWebhookUrls(u => [...u, ''])}
                >
                  <Plus className="h-3 w-3" /> Add URL
                </button>
              </div>
              <div className="space-y-2">
                {webhookUrls.map((url, i) => (
                  <div key={i} className="flex gap-1.5">
                    <Input
                      placeholder="https://yourserver.com/webhook"
                      value={url}
                      onChange={e => setWebhookUrls(u => u.map((v, j) => j === i ? e.target.value : v))}
                    />
                    {webhookUrls.length > 1 && (
                      <button
                        type="button"
                        className="text-muted-foreground hover:text-destructive shrink-0"
                        onClick={() => setWebhookUrls(u => u.filter((_, j) => j !== i))}
                      >
                        <X className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
            <div className="space-y-1.5">
              <Label>{editId ? 'Webhook Secret (leave blank to keep unchanged)' : 'Webhook Secret'}</Label>
              <div className="relative">
                <Input
                  type={showSecret ? 'text' : 'password'}
                  placeholder={editId ? '••••••••' : 'Secret for HMAC signing'}
                  value={form.webhook_secret}
                  onChange={f('webhook_secret')}
                  className="pr-9"
                />
                <button
                  type="button"
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  onClick={() => setShowSecret(s => !s)}
                >
                  {showSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
          </div>
          <DialogFooter className="px-6 py-3 border-t gap-2">
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              {editId ? 'Save' : 'Generate Key'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* New key reveal dialog — shown once */}
      <Dialog open={!!newKey} onOpenChange={() => { setNewKey(null); setCopied(false) }}>
        <DialogContent className="w-[95vw] max-w-md p-0 gap-0">
          <DialogHeader className="px-6 py-4 border-b">
            <DialogTitle>API Key Generated</DialogTitle>
            <DialogClose onClose={() => { setNewKey(null); setCopied(false) }} />
          </DialogHeader>
          <div className="px-6 py-5 space-y-3">
            <p className="text-sm text-muted-foreground">
              Copy this key now — it will <strong>not</strong> be shown again.
            </p>
            <div className="flex items-center gap-2">
              <code className="flex-1 rounded-md bg-muted px-3 py-2 text-xs font-mono break-all select-all">
                {newKey}
              </code>
              <Button variant="outline" size="icon" className="shrink-0" onClick={copyKey}>
                {copied ? <Check className="h-4 w-4 text-green-600" /> : <Copy className="h-4 w-4" />}
              </Button>
            </div>
          </div>
          <DialogFooter className="px-6 py-3 border-t">
            <Button onClick={() => { setNewKey(null); setCopied(false) }}>Done</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
