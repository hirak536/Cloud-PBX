import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { tenants as api, callParking as parkingApi } from '@/api'
import { useDispatch } from 'react-redux'
import { fetchTenantsThunk } from '@/store/slices/tenantSlice'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Select } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { Plus, Pencil, Trash2, Search, Loader2 } from 'lucide-react'

// Common timezones for the dropdown
const TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Phoenix',
  'America/Anchorage',
  'America/Honolulu',
  'America/Toronto',
  'America/Vancouver',
  'America/Mexico_City',
  'America/Bogota',
  'America/Lima',
  'America/Sao_Paulo',
  'America/Argentina/Buenos_Aires',
  'Europe/London',
  'Europe/Dublin',
  'Europe/Lisbon',
  'Europe/Paris',
  'Europe/Berlin',
  'Europe/Amsterdam',
  'Europe/Brussels',
  'Europe/Madrid',
  'Europe/Rome',
  'Europe/Warsaw',
  'Europe/Stockholm',
  'Europe/Helsinki',
  'Europe/Athens',
  'Europe/Istanbul',
  'Europe/Moscow',
  'Africa/Cairo',
  'Africa/Johannesburg',
  'Africa/Lagos',
  'Africa/Nairobi',
  'Asia/Dubai',
  'Asia/Karachi',
  'Asia/Kolkata',
  'Asia/Dhaka',
  'Asia/Bangkok',
  'Asia/Singapore',
  'Asia/Shanghai',
  'Asia/Tokyo',
  'Asia/Seoul',
  'Asia/Hong_Kong',
  'Asia/Jakarta',
  'Asia/Taipei',
  'Australia/Sydney',
  'Australia/Melbourne',
  'Australia/Brisbane',
  'Australia/Perth',
  'Pacific/Auckland',
  'Pacific/Fiji',
]

// Known webhook URL presets
const WEBHOOK_PRESETS = [
  { label: 'IHSPhone', value: 'https://api.ihsphone.com/company/webhook' },
  { label: 'Other (custom URL)', value: '__other__' },
]

const DEFAULT_WEBHOOK_URL = 'https://fsapi.ihsclients.com/company/webhook'

const EMPTY = {
  tenant_name: '',
  tenant_code: '',
  timezone: 'UTC',
  provisioning_webhook_url: '',
  recording_enabled: false,
}

const EMPTY_PARKING = { enabled: false, slot_start: 700, slot_end: 720 }

export default function TenantList() {
  const dispatch = useDispatch()
  const fetchTenants = () => dispatch(fetchTenantsThunk())
  const navigate = useNavigate()
  // Route param drives the editor: undefined = list, /new = create, else edit by id.
  // The `/new` route has no :id param, so detect create from the path and only
  // use the param for edit.
  const { id: editParamId } = useParams()
  const location = useLocation()
  const isCreate   = location.pathname.endsWith('/tenant-list/new')
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

  // Webhook URL state
  const [webhookPreset, setWebhookPreset] = useState(DEFAULT_WEBHOOK_URL)
  const [webhookCustom, setWebhookCustom] = useState('http://')
  const [extraWebhookEnabled, setExtraWebhookEnabled] = useState(false)
  const [extraWebhookUrl, setExtraWebhookUrl] = useState('')

  // Parking lots state (create only)
  const [parking, setParking] = useState(EMPTY_PARKING)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.list(debouncedSearch ? { search: debouncedSearch } : {})
      setRows(Array.isArray(data) ? data : data.results || [])
    } finally { setLoading(false) }
  }, [search])

  useEffect(() => { load() }, [load])

  const f = (key) => (e) => setForm(p => ({ ...p, [key]: e.target.value }))

  const rowToForm = (r) => ({
    tenant_name: r.tenant_name || '',
    tenant_code: r.tenant_code || '',
    timezone: r.timezone || 'UTC',
  })

  // Navigate to the full-page editor; the route effect below loads the form.
  const openCreate  = () => navigate('/tenant-list/new')
  const openEdit    = (r) => navigate('/tenant-list/' + r.tenant_uuid + '/edit')
  const closeEditor = () => navigate('/tenant-list')

  // Sync form state to the current route.
  useEffect(() => {
    if (!editorOpen) return
    setFormError('')
    // Reset auxiliary create-only state whenever the editor opens.
    setWebhookCustom('http://')
    setExtraWebhookEnabled(false)
    setExtraWebhookUrl('')
    setParking(EMPTY_PARKING)
    if (isCreate) {
      setEditId(null)
      setForm(EMPTY)
      setWebhookPreset(DEFAULT_WEBHOOK_URL)
      return
    }
    setWebhookPreset('')
    setEditId(routeId)
    const row = rows.find(r => r.tenant_uuid === routeId)
    if (row) { setForm(rowToForm(row)); return }
    // Deep-link / refresh: fetch the row if the list isn't loaded yet.
    api.get(routeId).then(({ data }) => setForm(rowToForm(data))).catch(() => setForm(EMPTY))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeId, isCreate])

  // Resolve the actual webhook URL from preset + custom input
  const resolvedWebhookUrl = () => {
    const primary = (!webhookPreset || webhookPreset === '__other__')
      ? (webhookCustom.trim() === 'http://' ? '' : webhookCustom.trim())
      : webhookPreset
    const extra = extraWebhookEnabled ? extraWebhookUrl.trim() : ''
    return [primary, extra].filter(Boolean).join(',')
  }

  const handleSave = async () => {
    if (!form.tenant_name.trim()) { setFormError('Tenant name is required.'); return }
    if (!form.tenant_code.trim()) { setFormError('Tenant code is required.'); return }
    if (!editId && parking.enabled) {
      const s = parseInt(parking.slot_start, 10)
      const e = parseInt(parking.slot_end, 10)
      if (isNaN(s) || isNaN(e) || s < 1 || e < s) {
        setFormError('Parking lot: start must be ≥ 1 and end must be ≥ start.')
        return
      }
      if (e - s > 99) {
        setFormError('Parking lot range cannot exceed 100 slots.')
        return
      }
    }
    setSaving(true); setFormError('')
    try {
      const payload = { ...form }
      if (!editId) payload.provisioning_webhook_url = resolvedWebhookUrl()
      if (!editId) payload.recording_enabled = form.recording_enabled

      let newTenantUuid = editId
      if (editId) {
        await api.update(editId, payload)
      } else {
        const { data: created } = await api.create(payload)
        newTenantUuid = created.tenant_uuid
      }

      // Bulk-create parking slots for new tenants if requested
      if (!editId && parking.enabled && newTenantUuid) {
        try {
          await parkingApi.bulkCreate({
            slot_start: parseInt(parking.slot_start, 10),
            slot_end: parseInt(parking.slot_end, 10),
            parking_timeout: 60,
            timeout_action: 'hangup',
            timeout_voicemail_extension: '',
            music_on_hold: '',
            slot_enabled: true,
          }, newTenantUuid)
        } catch {
          // Non-fatal: tenant was created, parking failed silently
        }
      }

      load()
      closeEditor()
      fetchTenants()
    } catch (err) {
      const d = err?.response?.data
      setFormError(typeof d === 'string' ? d : Object.values(d || {}).flat().join(' ') || 'Save failed.')
    } finally { setSaving(false) }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this tenant? This cannot be undone.')) return
    setDeleting(id)
    try { await api.delete(id); load(); fetchTenants() } finally { setDeleting(null) }
  }

  const filtered = rows.filter(r =>
    !search ||
    r.tenant_name?.toLowerCase().includes(search.toLowerCase()) ||
    r.tenant_code?.toLowerCase().includes(search.toLowerCase())
  )

  // ── Full-page editor (routed) ──────────────────────────────────────────────
  if (editorOpen) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={closeEditor} className="-ml-2 gap-1">
            ← Tenants
          </Button>
          <span className="text-muted-foreground">/</span>
          <h1 className="text-lg font-semibold">{isCreate ? 'New Tenant' : 'Edit Tenant'}</h1>
        </div>

        <Card>
          <div className="px-6 py-5 space-y-4">
            {formError && (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {formError}
              </div>
            )}

            {/* ── Basic Info ── */}
            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2 space-y-1.5">
                <Label>Tenant Name <span className="text-destructive">*</span></Label>
                <Input placeholder="Acme Corp" value={form.tenant_name} onChange={f('tenant_name')} />
              </div>
              <div className="space-y-1.5">
                <Label>Tenant Code <span className="text-destructive">*</span></Label>
                <Input
                  placeholder="ACME"
                  value={form.tenant_code}
                  onChange={e => setForm(p => ({ ...p, tenant_code: e.target.value.toUpperCase() }))}
                  className="font-mono"
                />
                <p className="text-xs text-muted-foreground">Used in SIP usernames.</p>
              </div>

              {/* ── Timezone dropdown ── */}
              <div className="space-y-1.5">
                <Label>Timezone</Label>
                <Select
                  value={form.timezone}
                  onChange={e => setForm(p => ({ ...p, timezone: e.target.value }))}
                >
                  {TIMEZONES.map(tz => (
                    <option key={tz} value={tz}>{tz}</option>
                  ))}
                </Select>
              </div>
            </div>

            {/* ── Create-only fields ── */}
            {isCreate && (
              <>
                {/* ── Webhook URL ── */}
                <div className="space-y-1.5">
                  <Label>Provisioning Webhook URL</Label>
                  <Select
                    value={webhookPreset}
                    onChange={e => {
                      setWebhookPreset(e.target.value)
                      if (e.target.value !== '__other__') setWebhookCustom('http://')
                    }}
                  >
                    <option value="">— None —</option>
                    {WEBHOOK_PRESETS.map(p => (
                      <option key={p.value} value={p.value}>{p.label}</option>
                    ))}
                  </Select>
                  {webhookPreset === '__other__' && (
                    <Input
                      value={webhookCustom}
                      onChange={e => setWebhookCustom(e.target.value)}
                      placeholder="https://server-a.com/webhook, https://server-b.com/webhook"
                      className="mt-1.5"
                    />
                  )}
                  {extraWebhookEnabled ? (
                    <div className="mt-1.5 flex gap-1.5">
                      <Input
                        value={extraWebhookUrl}
                        onChange={e => setExtraWebhookUrl(e.target.value)}
                        placeholder="https://another-server.com/webhook"
                      />
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => { setExtraWebhookEnabled(false); setExtraWebhookUrl('') }}
                      >
                        Remove
                      </Button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setExtraWebhookEnabled(true)}
                      className="mt-1.5 text-xs font-medium text-primary hover:underline"
                    >
                      + Add another URL
                    </button>
                  )}
                  <p className="text-xs text-muted-foreground">
                    An API key will be auto-generated and POSTed here when the tenant is created. Separate multiple URLs with commas to fan out to all of them.
                  </p>
                </div>

                {/* ── Parking Lots ── */}
                <div className="space-y-3 rounded-md border px-4 py-3">
                  <div className="flex items-center justify-between">
                    <Label className="text-sm font-medium">Parking Lots</Label>
                    <button
                      type="button"
                      role="switch"
                      aria-checked={parking.enabled}
                      onClick={() => setParking(p => ({ ...p, enabled: !p.enabled }))}
                      className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors ${
                        parking.enabled ? 'bg-primary' : 'bg-muted-foreground/30'
                      }`}
                    >
                      <span className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition-transform ${
                        parking.enabled ? 'translate-x-4' : 'translate-x-0'
                      }`} />
                    </button>
                  </div>
                  {parking.enabled && (
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1.5">
                        <Label className="text-xs">Parking lot start number</Label>
                        <Input
                          type="number"
                          min={1}
                          value={parking.slot_start}
                          onChange={e => setParking(p => ({ ...p, slot_start: e.target.value }))}
                        />
                      </div>
                      <div className="space-y-1.5">
                        <Label className="text-xs">Parking lot end number</Label>
                        <Input
                          type="number"
                          min={1}
                          value={parking.slot_end}
                          onChange={e => setParking(p => ({ ...p, slot_end: e.target.value }))}
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* ── Recording ── */}
                <div className="flex items-center justify-between rounded-md border px-4 py-3">
                  <Label className="text-sm font-medium">Recording</Label>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setForm(p => ({ ...p, recording_enabled: false }))}
                      className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                        !form.recording_enabled
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted text-muted-foreground hover:bg-muted/80'
                      }`}
                    >
                      No
                    </button>
                    <button
                      type="button"
                      onClick={() => setForm(p => ({ ...p, recording_enabled: true }))}
                      className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                        form.recording_enabled
                          ? 'bg-primary text-primary-foreground'
                          : 'bg-muted text-muted-foreground hover:bg-muted/80'
                      }`}
                    >
                      Yes
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>

          <div className="flex justify-end gap-2 px-6 py-3 border-t">
            <Button variant="outline" onClick={closeEditor}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              {isCreate ? 'Create Tenant' : 'Save Changes'}
            </Button>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search tenants..."
            className="pl-8"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <Button size="sm" onClick={openCreate}>
          <Plus className="h-4 w-4" /> Add Tenant
        </Button>
      </div>

      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Code</TableHead>
                <TableHead>Timezone</TableHead>
                <TableHead>Domains</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-20" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading
                ? [...Array(4)].map((_, i) => (
                    <TableRow key={i}>
                      {[...Array(6)].map((_, j) => (
                        <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                      ))}
                    </TableRow>
                  ))
                : filtered.length === 0
                ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center py-10 text-muted-foreground">
                        No tenants found.
                      </TableCell>
                    </TableRow>
                  )
                : filtered.map((r) => (
                    <TableRow key={r.tenant_uuid}>
                      <TableCell className="font-medium">{r.tenant_name}</TableCell>
                      <TableCell className="font-mono text-sm">{r.tenant_code}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">{r.timezone || '—'}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">{r.domain_count ?? '—'}</TableCell>
                      <TableCell>
                        <Badge variant={r.tenant_enabled !== false ? 'success' : 'secondary'}>
                          {r.tenant_enabled !== false ? 'Active' : 'Disabled'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button
                            variant="ghost" size="icon" className="h-7 w-7"
                            onClick={() => openEdit(r)}
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost" size="icon"
                            className="h-7 w-7 text-destructive hover:text-destructive"
                            onClick={() => handleDelete(r.tenant_uuid)}
                            disabled={deleting === r.tenant_uuid}
                          >
                            {deleting === r.tenant_uuid
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
