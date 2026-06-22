import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { outboundRoutes as routesApi, gateways as gatewaysApi } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { Select } from '@/components/ui/select'
import { Plus, Pencil, Trash2, Search, RefreshCw, Loader2, ArrowUpDown } from 'lucide-react'
import { cn } from '@/lib/utils'

const EMPTY = {
  outbound_route_name: '',
  outbound_route_order: 10,
  dialplan_pattern: '',
  prepend: '',
  gateway: '',
  gateway_2: '',
  gateway_3: '',
  outbound_route_enabled: true,
  outbound_route_description: '',
}

const PATTERN_PRESETS = [
  { label: 'Any number',              value: '^(\\d+)$' },
  { label: '4-digit internal',        value: '^(\\d{4})$' },
  { label: 'US/Canada (10-digit)',     value: '^(\\d{10})$' },
  { label: 'US/Canada (1+10-digit)',   value: '^1?(\\d{10})$' },
  { label: '9 + 10-digit (strip 9)',   value: '^9(\\d{10})$' },
  { label: '9 + 11-digit (strip 9)',   value: '^9(1\\d{10})$' },
  { label: 'International (011+)',     value: '^011(\\d+)$' },
  { label: 'UK (0 + 9 digits)',        value: '^0(\\d{9})$' },
]

function Field({ label, required, hint, children }) {
  return (
    <div className="space-y-1.5">
      <Label className="text-xs">
        {label}
        {required && <span className="text-destructive ml-0.5">*</span>}
      </Label>
      {children}
      {hint && <p className="text-[11px] text-muted-foreground leading-tight">{hint}</p>}
    </div>
  )
}

function GatewaySelect({ value, onChange, gateways, placeholder = 'None' }) {
  return (
    <select
      value={value || ''}
      onChange={(e) => onChange(e.target.value || '')}
      className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
    >
      <option value="">{placeholder}</option>
      {gateways.map((gw) => (
        <option key={gw.gateway_uuid} value={gw.gateway_uuid}>
          {gw.gateway} {gw.proxy ? `— ${gw.proxy}` : ''}
        </option>
      ))}
    </select>
  )
}

export default function OutboundRoutes() {
  const navigate = useNavigate()
  const { id: editParamId } = useParams()
  const location = useLocation()
  const isCreate   = location.pathname.endsWith('/outbound-routes/new')
  const routeId    = editParamId
  const editorOpen = isCreate || routeId !== undefined

  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebounce(search, 300)
  const [gateways, setGateways] = useState([])
  const [editId, setEditId] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [deleting, setDeleting] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [routeRes, gwRes] = await Promise.all([
        routesApi.list(debouncedSearch ? { search: debouncedSearch } : {}),
        gatewaysApi.list(),
      ])
      setRows(Array.isArray(routeRes.data) ? routeRes.data : routeRes.data.results || [])
      const gwList = Array.isArray(gwRes.data) ? gwRes.data : gwRes.data.results || []
      setGateways(gwList.filter((g) => g.gateway_enabled !== false))
    } finally {
      setLoading(false)
    }
  }, [search])

  useEffect(() => { load() }, [load])

  const set = (key) => (e) => setForm((p) => ({ ...p, [key]: e.target.value }))
  const setVal = (key, val) => setForm((p) => ({ ...p, [key]: val }))

  const rowToForm = (r) => ({
    outbound_route_name: r.outbound_route_name || '',
    outbound_route_order: r.outbound_route_order ?? 10,
    dialplan_pattern: r.dialplan_pattern || '',
    prepend: r.prepend || '',
    gateway: r.gateway || '',
    gateway_2: r.gateway_2 || '',
    gateway_3: r.gateway_3 || '',
    outbound_route_enabled: r.outbound_route_enabled !== false,
    outbound_route_description: r.outbound_route_description || '',
  })

  const openCreate  = () => navigate('/outbound-routes/new')
  const openEdit    = (r) => navigate('/outbound-routes/' + r.outbound_route_uuid + '/edit')
  const closeEditor = () => navigate('/outbound-routes')

  useEffect(() => {
    if (!editorOpen) return
    setFormError('')
    if (isCreate) { setEditId(null); setForm(EMPTY); return }
    setEditId(routeId)
    const row = rows.find(r => r.outbound_route_uuid === routeId)
    if (row) { setForm(rowToForm(row)); return }
    routesApi.get(routeId).then(({ data }) => setForm(rowToForm(data))).catch(() => setForm(EMPTY))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeId, isCreate])

  const handleSave = async () => {
    if (!form.outbound_route_name.trim()) { setFormError('Route name is required.'); return }
    if (!form.dialplan_pattern.trim()) { setFormError('Dialplan pattern is required.'); return }
    if (!form.gateway) { setFormError('At least one gateway is required.'); return }
    setSaving(true); setFormError('')
    try {
      const payload = { ...form }
      if (!payload.gateway_2) delete payload.gateway_2
      if (!payload.gateway_3) delete payload.gateway_3
      editId
        ? await routesApi.update(editId, payload)
        : await routesApi.create(payload)
      load(); closeEditor()
    } catch (err) {
      const d = err?.response?.data
      setFormError(typeof d === 'string' ? d : Object.values(d || {}).flat().join(' ') || 'Save failed.')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this outbound route?')) return
    setDeleting(id)
    try { await routesApi.delete(id); load() } finally { setDeleting(null) }
  }

  const handleReload = async () => {
    try { await routesApi.reload() } catch {}
  }

  const filtered = rows.filter((r) =>
    !search ||
    r.outbound_route_name?.toLowerCase().includes(search.toLowerCase()) ||
    r.dialplan_pattern?.toLowerCase().includes(search.toLowerCase()) ||
    r.gateway_name?.toLowerCase().includes(search.toLowerCase())
  )

  // ── Full-page editor (routed) ──────────────────────────────────────────────
  if (editorOpen) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={closeEditor} className="-ml-2 gap-1">
            ← Outbound Routes
          </Button>
          <span className="text-muted-foreground">/</span>
          <h1 className="text-lg font-semibold">{isCreate ? 'New Outbound Route' : 'Edit Outbound Route'}</h1>
        </div>

        <Card>
          <div className="space-y-5 px-6 py-5">
            {formError && (
              <p className="rounded bg-destructive/10 border border-destructive/30 px-3 py-2 text-xs text-destructive">
                {formError}
              </p>
            )}

            <div className="grid grid-cols-2 gap-4">
              <Field label="Route Name" required>
                <Input value={form.outbound_route_name} onChange={set('outbound_route_name')} placeholder="Local Calls" />
              </Field>
              <Field label="Order" hint="Lower = higher priority">
                <Input
                  type="number" min={0} max={999}
                  value={form.outbound_route_order}
                  onChange={(e) => setVal('outbound_route_order', parseInt(e.target.value) || 0)}
                />
              </Field>
            </div>

            <Field label="Dialplan Pattern" required hint="Regex against destination_number. Capture the digits to send in group 1.">
              <div className="space-y-2">
                <Input
                  value={form.dialplan_pattern}
                  onChange={set('dialplan_pattern')}
                  placeholder="^9(\d{10})$"
                  className="font-mono text-xs"
                />
                <div className="flex flex-wrap gap-1.5">
                  {PATTERN_PRESETS.map((p) => (
                    <button
                      key={p.value}
                      type="button"
                      onClick={() => setVal('dialplan_pattern', p.value)}
                      className={cn(
                        'text-[10px] px-2 py-1 rounded border transition-colors',
                        form.dialplan_pattern === p.value
                          ? 'bg-primary text-primary-foreground border-primary'
                          : 'bg-muted hover:bg-muted/80 border-transparent'
                      )}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>
            </Field>

            <Field label="Prepend" hint="Digits to prepend before $1 when dialing the gateway (e.g. '1' for NANP).">
              <Input
                value={form.prepend}
                onChange={set('prepend')}
                placeholder="1"
                className="font-mono w-32"
              />
            </Field>

            <Field label="Gateway (Primary)" required>
              <GatewaySelect
                value={form.gateway}
                onChange={(v) => setVal('gateway', v)}
                gateways={gateways}
                placeholder="— Select gateway —"
              />
            </Field>

            <div className="grid grid-cols-2 gap-4">
              <Field label="Failover Gateway" hint="Tried if primary fails.">
                <GatewaySelect
                  value={form.gateway_2}
                  onChange={(v) => setVal('gateway_2', v)}
                  gateways={gateways}
                />
              </Field>
              <Field label="2nd Failover" hint="Tried if failover also fails.">
                <GatewaySelect
                  value={form.gateway_3}
                  onChange={(v) => setVal('gateway_3', v)}
                  gateways={gateways}
                />
              </Field>
            </div>

            <Field label="Description">
              <Input value={form.outbound_route_description} onChange={set('outbound_route_description')} placeholder="Optional notes" />
            </Field>

            <div className="flex items-center gap-2 pt-1">
              <input
                id="route-enabled"
                type="checkbox"
                checked={form.outbound_route_enabled}
                onChange={(e) => setVal('outbound_route_enabled', e.target.checked)}
                className="h-4 w-4 rounded border-input"
              />
              <Label htmlFor="route-enabled" className="text-sm cursor-pointer">Enabled</Label>
            </div>
          </div>

          <div className="flex justify-end gap-2 px-6 py-3 border-t">
            <Button variant="outline" size="sm" onClick={closeEditor}>Cancel</Button>
            <Button size="sm" onClick={handleSave} disabled={saving} className="gap-1.5">
              {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {isCreate ? 'Create Route' : 'Save Changes'}
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
            placeholder="Search routes…"
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
          <Plus className="h-3.5 w-3.5" /> Add Route
        </Button>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-10 text-center">#</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Pattern</TableHead>
                <TableHead>Gateway</TableHead>
                <TableHead>Failover</TableHead>
                <TableHead>Prepend</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-20" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading
                ? Array.from({ length: 4 }).map((_, i) => (
                    <TableRow key={i}>
                      {Array.from({ length: 8 }).map((__, j) => (
                        <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                      ))}
                    </TableRow>
                  ))
                : filtered.length === 0
                  ? (
                    <TableRow>
                      <TableCell colSpan={8} className="text-center text-sm text-muted-foreground py-8">
                        No outbound routes found. Click <strong>Add Route</strong> to create one.
                      </TableCell>
                    </TableRow>
                  )
                  : filtered.map((r) => (
                      <TableRow key={r.outbound_route_uuid} className={cn(!r.outbound_route_enabled && 'opacity-50')}>
                        <TableCell className="text-center text-xs text-muted-foreground font-mono">
                          {r.outbound_route_order}
                        </TableCell>
                        <TableCell className="font-medium">{r.outbound_route_name}</TableCell>
                        <TableCell>
                          <code className="text-xs bg-muted px-1.5 py-0.5 rounded">{r.dialplan_pattern}</code>
                        </TableCell>
                        <TableCell className="text-sm">{r.gateway_name || '—'}</TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {[r.gateway_2_name, r.gateway_3_name].filter(Boolean).join(', ') || '—'}
                        </TableCell>
                        <TableCell className="text-xs font-mono">{r.prepend || '—'}</TableCell>
                        <TableCell>
                          {r.outbound_route_enabled
                            ? <Badge variant="success">Enabled</Badge>
                            : <Badge variant="secondary">Disabled</Badge>}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1 justify-end">
                            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(r)}>
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive"
                              onClick={() => handleDelete(r.outbound_route_uuid)}
                              disabled={deleting === r.outbound_route_uuid}
                            >
                              {deleting === r.outbound_route_uuid
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

      {/* Tip */}
      <p className="text-xs text-muted-foreground">
        Routes are evaluated in <strong>order</strong> (ascending). Use capture group <code className="bg-muted px-1 rounded">(\d+)</code> in the pattern — <code className="bg-muted px-1 rounded">$1</code> is sent to the gateway.
      </p>
    </div>
  )
}
