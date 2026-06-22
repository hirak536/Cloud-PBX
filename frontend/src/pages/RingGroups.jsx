import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback, useRef } from 'react'
import { createPortal } from 'react-dom'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { ringGroups as api, extensions as extensionsApi } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { Plus, Pencil, Trash2, Search, Loader2, X, GripVertical } from 'lucide-react'
import DestinationPicker, { EMPTY_DEST } from '@/components/DestinationPicker'
import CheckRow from '@/components/CheckRow'
import { useDestinationData } from '@/hooks/useDestinationData'

// ─── Constants ───────────────────────────────────────────────────────────────

const STRATEGIES = [
  { value: 'simultaneous', label: 'Ring All' },
  { value: 'sequence',     label: 'In Order' },
  { value: 'enterprise',   label: 'Enterprise' },
  { value: 'rollover',     label: 'Rollover' },
]

const EMPTY_FORM = {
  ring_group_name: '',
  ring_group_extension: '',
  ring_group_strategy: 'simultaneous',
  ring_group_enabled: true,
  ring_group_description: '',
  ring_group_call_timeout: 60,
  ring_group_dial_timeout: 3600,
  ring_group_skip_busy: false,
  ring_group_skip_offline: false,
  ring_group_fast_dial: false,
  ring_group_moh_sound: false,
  ring_group_allow_redirect: false,
  ring_group_allow_fmfm: false,
  ring_group_allow_additional_destinations: false,
  ring_group_use_custom_destination: false,
  ring_group_confirm_to_answer: false,
  ring_group_confirm_message: '',
  ring_group_use_standard_message: true,
  timeout_dest: { ...EMPTY_DEST },
  destinations: [],
}

// ─── Extension Combobox Input ─────────────────────────────────────────────────

function ExtensionInput({ value, onChange, extensions = [], className }) {
  const [open, setOpen] = useState(false)
  const [dropStyle, setDropStyle] = useState({})
  const containerRef = useRef(null)
  const inputRef = useRef(null)

  const filtered = extensions
    .filter(ext =>
      !value ||
      ext.extension.includes(value) ||
      (ext.effective_caller_id_name || '').toLowerCase().includes(value.toLowerCase())
    )
    .slice(0, 20)

  const reposition = () => {
    if (!inputRef.current) return
    const r = inputRef.current.getBoundingClientRect()
    setDropStyle({ top: r.bottom + 2, left: r.left, width: Math.max(r.width, 200) })
  }

  return (
    <div ref={containerRef} onBlur={e => {
      if (!containerRef.current?.contains(e.relatedTarget)) setOpen(false)
    }}>
      <input
        ref={inputRef}
        className={`flex h-7 w-full rounded-md border border-input bg-background px-3 py-1 text-sm font-mono shadow-sm transition-colors placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring${className ? ' ' + className : ''}`}
        placeholder="1001"
        value={value}
        onChange={e => { onChange(e.target.value); reposition(); setOpen(true) }}
        onFocus={() => { reposition(); setOpen(true) }}
      />
      {open && filtered.length > 0 && createPortal(
        <div
          style={{ position: 'fixed', zIndex: 9999, ...dropStyle }}
          className="rounded-md border bg-card shadow-md max-h-48 overflow-y-auto"
        >
          {filtered.map(ext => (
            <button
              key={ext.extension_uuid}
              type="button"
              className="flex w-full items-center gap-2 px-3 py-1.5 text-sm hover:bg-accent text-left"
              onMouseDown={e => { e.preventDefault(); onChange(ext.extension); setOpen(false) }}
            >
              <span className="font-mono font-medium">{ext.extension}</span>
              {ext.effective_caller_id_name && (
                <span className="text-muted-foreground truncate">{ext.effective_caller_id_name}</span>
              )}
            </button>
          ))}
        </div>,
        document.body
      )}
    </div>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function RingGroups() {
  const navigate = useNavigate()
  // Route param drives the editor: undefined = list, 'new' = create, else edit by id.
  // The `/new` route has no :id param, so detect create from the path.
  const { id: editParamId } = useParams()
  const location = useLocation()
  const isCreate   = location.pathname.endsWith('/ring-groups/new')
  const routeId    = editParamId
  const editorOpen = isCreate || routeId !== undefined

  const [rows, setRows]           = useState([])
  const [loading, setLoading]     = useState(true)
  const [search, setSearch]         = useState('')
  const debouncedSearch             = useDebounce(search, 300)
  const [editId, setEditId]       = useState(null)
  const [form, setForm]           = useState(EMPTY_FORM)
  const [saving, setSaving]       = useState(false)
  const [formError, setFormError] = useState('')
  const [deleting, setDeleting]   = useState(null)
  const [numStatus, setNumStatus] = useState(null)
  const [numConflict, setNumConflict] = useState('')
  const debouncedExt = useDebounce(form.ring_group_extension, 600)
  const { destData, destLoading, destSearchLoading, loadDestData, searchDestData } = useDestinationData()

  useEffect(() => {
    const val = debouncedExt.trim()
    if (!val || !/^\d{3,5}$/.test(val)) { setNumStatus(null); return }
    setNumStatus('checking')
    extensionsApi.checkNumber(val, editId || undefined)
      .then(({ data }) => {
        setNumStatus(data.available ? 'ok' : 'taken')
        setNumConflict(data.conflicts?.[0] || '')
      })
      .catch(() => setNumStatus(null))
  }, [debouncedExt, editId])

  // ── Load ring groups list ──────────────────────────────────────────────────

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.list(debouncedSearch ? { search: debouncedSearch } : {})
      setRows(Array.isArray(data) ? data : data.results || [])
    } finally { setLoading(false) }
  }, [search])

  useEffect(() => { load() }, [load])

  // ── Form helpers ───────────────────────────────────────────────────────────

  const f = (key) => (e) => setForm(p => ({ ...p, [key]: e.target.value }))
  const fNum = (key) => (e) => setForm(p => ({ ...p, [key]: Number(e.target.value) }))
  const fBool = (key) => (val) => setForm(p => ({ ...p, [key]: val }))
  const fCheck = (key) => (e) => setForm(p => ({ ...p, [key]: e.target.checked }))

  // ── Destinations drag-and-drop ────────────────────────────────────────────

  const dragIdx = useRef(null)
  const [dragOverIdx, setDragOverIdx] = useState(null)

  const moveDest = (from, to) => setForm(p => {
    const arr = [...p.destinations]
    arr.splice(to, 0, arr.splice(from, 1)[0])
    return { ...p, destinations: arr }
  })

  // ── Destinations list helpers ──────────────────────────────────────────────

  const addDest = () => setForm(p => ({
    ...p,
    destinations: [...p.destinations, { destination_number: '', destination_delay: 0, destination_timeout: 30 }],
  }))

  const removeDest = (idx) => setForm(p => ({
    ...p,
    destinations: p.destinations.filter((_, i) => i !== idx),
  }))

  const updateDest = (idx, key, val) => setForm(p => ({
    ...p,
    destinations: p.destinations.map((d, i) => i === idx ? { ...d, [key]: val } : d),
  }))

  // ── Form seeding ────────────────────────────────────────────────────────────

  const rowToForm = (d) => ({
    ring_group_name:      d.ring_group_name || '',
    ring_group_extension: d.ring_group_extension || '',
    ring_group_strategy:  d.ring_group_strategy || 'simultaneous',
    ring_group_enabled:   d.ring_group_enabled !== false,
    ring_group_description: d.ring_group_description || '',
    ring_group_call_timeout: d.ring_group_call_timeout ?? 60,
    ring_group_dial_timeout: d.ring_group_dial_timeout ?? 3600,
    ring_group_skip_busy:   d.ring_group_skip_busy || false,
    ring_group_skip_offline: d.ring_group_skip_offline || false,
    ring_group_fast_dial:   d.ring_group_fast_dial || false,
    ring_group_moh_sound:   d.ring_group_moh_sound || false,
    ring_group_allow_redirect: d.ring_group_allow_redirect || false,
    ring_group_allow_fmfm:  d.ring_group_allow_fmfm || false,
    ring_group_allow_additional_destinations: d.ring_group_allow_additional_destinations || false,
    ring_group_use_custom_destination: d.ring_group_use_custom_destination || false,
    ring_group_confirm_to_answer: d.ring_group_confirm_to_answer || false,
    ring_group_confirm_message: d.ring_group_confirm_message || '',
    ring_group_use_standard_message: d.ring_group_use_standard_message !== false,
    timeout_dest: {
      type:            d.ring_group_timeout_type || '',
      target_uuid:     d.ring_group_timeout_target_uuid || '',
      external_number: d.ring_group_timeout_external_number || '',
    },
    destinations: (d.destinations || []).map(dest => ({
      destination_number:  dest.destination_number || '',
      destination_delay:   dest.destination_delay ?? 0,
      destination_timeout: dest.destination_timeout ?? 30,
    })),
  })

  // ── Editor navigation ─────────────────────────────────────────────────────

  const openCreate  = () => navigate('/ring-groups/new')
  const openEdit    = (r) => navigate(`/ring-groups/${r.ring_group_uuid}/edit`)
  const closeEditor = () => navigate('/ring-groups')

  // Sync form state to the current route.
  useEffect(() => {
    if (!editorOpen) return
    setFormError('')
    loadDestData()
    if (isCreate) {
      setEditId(null)
      setForm({ ...EMPTY_FORM, timeout_dest: { ...EMPTY_DEST }, destinations: [] })
      return
    }
    setEditId(routeId)
    setForm({ ...EMPTY_FORM, timeout_dest: { ...EMPTY_DEST }, destinations: [] })
    api.get(routeId)
      .then(({ data }) => setForm(rowToForm(data)))
      .catch(() => { /* keep empty form if fetch fails */ })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeId, isCreate])

  // ── Save ───────────────────────────────────────────────────────────────────

  const handleSave = async () => {
    if (!form.ring_group_name)      { setFormError('Name is required.'); return }
    setSaving(true)
    setFormError('')
    try {
      const payload = {
        ring_group_name:      form.ring_group_name,
        ring_group_extension: form.ring_group_extension,
        ring_group_strategy:  form.ring_group_strategy,
        ring_group_enabled:   form.ring_group_enabled,
        ring_group_description: form.ring_group_description,
        ring_group_call_timeout: Number(form.ring_group_call_timeout),
        ring_group_dial_timeout: Number(form.ring_group_dial_timeout),
        ring_group_skip_busy:   form.ring_group_skip_busy,
        ring_group_skip_offline: form.ring_group_skip_offline,
        ring_group_fast_dial:   form.ring_group_fast_dial,
        ring_group_moh_sound:   form.ring_group_moh_sound,
        ring_group_allow_redirect: form.ring_group_allow_redirect,
        ring_group_allow_fmfm:  form.ring_group_allow_fmfm,
        ring_group_allow_additional_destinations: form.ring_group_allow_additional_destinations,
        ring_group_use_custom_destination: form.ring_group_use_custom_destination,
        ring_group_confirm_to_answer: form.ring_group_confirm_to_answer,
        ring_group_confirm_message: form.ring_group_confirm_message,
        ring_group_use_standard_message: form.ring_group_use_standard_message,
        ring_group_timeout_type:            form.timeout_dest.type || '',
        ring_group_timeout_target_uuid:     form.timeout_dest.target_uuid || null,
        ring_group_timeout_external_number: form.timeout_dest.external_number || '',
        destinations: form.destinations.filter(d => d.destination_number.trim()).map(d => ({
          destination_number:  d.destination_number.trim(),
          destination_delay:   Number(d.destination_delay),
          destination_timeout: Number(d.destination_timeout),
        })),
      }
      editId ? await api.update(editId, payload) : await api.create(payload)
      load()
      closeEditor()
    } catch (err) {
      const d = err?.response?.data
      setFormError(typeof d === 'string' ? d : Object.values(d || {}).flat().join(' ') || 'Save failed.')
    } finally { setSaving(false) }
  }

  // ── Delete ─────────────────────────────────────────────────────────────────

  const handleDelete = async (id) => {
    if (!confirm('Delete this ring group?')) return
    setDeleting(id)
    try { await api.delete(id); load() } finally { setDeleting(null) }
  }

  // ── Full-page editor (routed) ──────────────────────────────────────────────

  if (editorOpen) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={closeEditor} className="-ml-2 gap-1">
            ← Ring Groups
          </Button>
          <span className="text-muted-foreground">/</span>
          <h1 className="text-lg font-semibold">{isCreate ? 'New Ring Group' : 'Edit Ring Group'}</h1>
        </div>

        <Card>
          <div className="px-6 py-5 space-y-5">
            {formError && (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {formError}
              </div>
            )}

            {/* ── Name & Number ── */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Name <span className="text-destructive">*</span></Label>
                <Input placeholder="Sales Team" value={form.ring_group_name} onChange={f('ring_group_name')} />
              </div>
              <div className="space-y-1.5">
                <Label>Number</Label>
                <Input placeholder="2000 (auto-generated if blank)" value={form.ring_group_extension} onChange={f('ring_group_extension')} />
                {numStatus === 'checking' && <p className="text-xs text-muted-foreground">Checking availability…</p>}
                {numStatus === 'taken'    && <p className="text-xs text-destructive">{numConflict || 'Already in use on this tenant'}</p>}
                {numStatus === 'ok'       && <p className="text-xs text-green-600">Available</p>}
                {!form.ring_group_extension && !numStatus && <p className="text-xs text-muted-foreground">Leave blank to auto-generate (e.g. rg_a1b2c3d4)</p>}
              </div>
            </div>

            {/* ── Type / Strategy ── */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Type</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  value={form.ring_group_strategy}
                  onChange={f('ring_group_strategy')}
                >
                  {STRATEGIES.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                </select>
              </div>
              <div className="space-y-1.5">
                <Label>Status</Label>
                <select
                  className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                  value={form.ring_group_enabled ? 'true' : 'false'}
                  onChange={e => setForm(p => ({ ...p, ring_group_enabled: e.target.value === 'true' }))}
                >
                  <option value="true">Active</option>
                  <option value="false">Disabled</option>
                </select>
              </div>
            </div>

            {/* ── Extensions / Destinations ── */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>Extensions</Label>
                <Button type="button" variant="outline" size="sm" className="h-7 text-xs" onClick={addDest}>
                  <Plus className="h-3.5 w-3.5" /> Add
                </Button>
              </div>

              {form.destinations.length === 0 ? (
                <p className="text-sm text-muted-foreground py-2 text-center border rounded-md">
                  No extensions — click Add to add destinations
                </p>
              ) : (
                <div className="rounded-md border overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-muted/50">
                      <tr>
                        <th className="w-6" />
                        <th className="text-left px-3 py-1.5 font-medium text-xs text-muted-foreground">Extension / Number</th>
                        <th className="text-left px-3 py-1.5 font-medium text-xs text-muted-foreground w-24">Delay (s)</th>
                        <th className="text-left px-3 py-1.5 font-medium text-xs text-muted-foreground w-24">Timeout (s)</th>
                        <th className="w-8" />
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {form.destinations.map((dest, idx) => (
                        <tr
                          key={idx}
                          draggable
                          onDragStart={() => { dragIdx.current = idx }}
                          onDragOver={e => { e.preventDefault(); setDragOverIdx(idx) }}
                          onDragLeave={() => setDragOverIdx(null)}
                          onDrop={e => {
                            e.preventDefault()
                            if (dragIdx.current !== null && dragIdx.current !== idx) moveDest(dragIdx.current, idx)
                            dragIdx.current = null; setDragOverIdx(null)
                          }}
                          onDragEnd={() => { dragIdx.current = null; setDragOverIdx(null) }}
                          className={dragOverIdx === idx ? 'bg-accent/60' : undefined}
                        >
                          <td className="pl-2 py-1.5 cursor-grab active:cursor-grabbing text-muted-foreground">
                            <GripVertical className="h-3.5 w-3.5" />
                          </td>
                          <td className="px-3 py-1.5">
                            <ExtensionInput
                              value={dest.destination_number}
                              onChange={val => updateDest(idx, 'destination_number', val)}
                              extensions={destData.extensions}
                            />
                          </td>
                          <td className="px-3 py-1.5">
                            <Input
                              type="number" min="0"
                              value={dest.destination_delay}
                              onChange={e => updateDest(idx, 'destination_delay', Number(e.target.value))}
                              className="h-7 text-sm"
                            />
                          </td>
                          <td className="px-3 py-1.5">
                            <Input
                              type="number" min="1"
                              value={dest.destination_timeout}
                              onChange={e => updateDest(idx, 'destination_timeout', Number(e.target.value))}
                              className="h-7 text-sm"
                            />
                          </td>
                          <td className="px-2 py-1.5">
                            <button
                              type="button"
                              onClick={() => removeDest(idx)}
                              className="p-1 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors"
                            >
                              <X className="h-3.5 w-3.5" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>

            {/* ── Behavior checkboxes ── */}
            <div className="space-y-1">
              <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Behavior</Label>
              <div className="grid grid-cols-2 gap-x-6">
                <CheckRow checked={form.ring_group_fast_dial}                    onChange={fBool('ring_group_fast_dial')}                    label="Use fast dialing" />
                <CheckRow checked={form.ring_group_moh_sound}                    onChange={fBool('ring_group_moh_sound')}                    label="Use Default Music On Hold instead of ringing" />
                <CheckRow checked={form.ring_group_skip_busy}                    onChange={fBool('ring_group_skip_busy')}                    label="Skip if exten is in use" />
                <CheckRow checked={form.ring_group_skip_offline}                 onChange={fBool('ring_group_skip_offline')}                 label="Skip if exten is offline" />
                <CheckRow checked={form.ring_group_allow_redirect}               onChange={fBool('ring_group_allow_redirect')}               label="Allow extension redirect" />
                <CheckRow checked={form.ring_group_allow_fmfm}                   onChange={fBool('ring_group_allow_fmfm')}                   label="Allow FMFM" />
                <CheckRow checked={form.ring_group_allow_additional_destinations} onChange={fBool('ring_group_allow_additional_destinations')} label="Allow additional destinations" />
                <CheckRow checked={form.ring_group_use_custom_destination}       onChange={fBool('ring_group_use_custom_destination')}       label="Use Custom Destination details" />
                <CheckRow checked={form.ring_group_confirm_to_answer}            onChange={fBool('ring_group_confirm_to_answer')}            label="Request confirm to answer" />
              </div>
            </div>

            {/* ── Confirm message ── */}
            {form.ring_group_confirm_to_answer && (
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <Label>Confirm message</Label>
                  <label className="flex items-center gap-2 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={form.ring_group_use_standard_message}
                      onChange={fCheck('ring_group_use_standard_message')}
                      className="h-4 w-4 rounded border-input accent-primary cursor-pointer"
                    />
                    <span className="text-xs text-muted-foreground">Use standard message</span>
                  </label>
                </div>
                {!form.ring_group_use_standard_message && (
                  <Input
                    placeholder="Custom confirm message…"
                    value={form.ring_group_confirm_message}
                    onChange={f('ring_group_confirm_message')}
                  />
                )}
              </div>
            )}

            {/* ── Timing ── */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Ring time (s)</Label>
                <Input type="number" min="1" value={form.ring_group_call_timeout} onChange={fNum('ring_group_call_timeout')} />
              </div>
              <div className="space-y-1.5">
                <Label>Dial timeout (s)</Label>
                <Input type="number" min="1" value={form.ring_group_dial_timeout} onChange={fNum('ring_group_dial_timeout')} />
              </div>
            </div>

            {/* ── On timeout destination ── */}
            <div className="space-y-1.5">
              <Label>On timeout</Label>
              <DestinationPicker
                value={form.timeout_dest}
                onChange={val => setForm(p => ({ ...p, timeout_dest: val }))}
                data={destData}
                loading={destLoading}
                searchLoading={destSearchLoading}
                onSearch={searchDestData}
                placeholder="Set destination…"
              />
            </div>

            {/* ── Description ── */}
            <div className="space-y-1.5">
              <Label>Description</Label>
              <Input placeholder="Optional notes…" value={form.ring_group_description} onChange={f('ring_group_description')} />
            </div>
          </div>

          <div className="flex justify-end gap-2 px-6 py-3 border-t">
            <Button variant="outline" onClick={closeEditor}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              {isCreate ? 'Create Ring Group' : 'Save Changes'}
            </Button>
          </div>
        </Card>
      </div>
    )
  }

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search ring groups…"
            className="pl-8"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        <Button size="sm" onClick={openCreate}>
          <Plus className="h-4 w-4" /> Add Ring Group
        </Button>
      </div>

      {/* Table */}
      <Card><CardContent className="p-0 overflow-x-auto">
        <Table>
          <TableHeader><TableRow>
            <TableHead>Number</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Strategy</TableHead>
            <TableHead>Ring Time</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="w-20" />
          </TableRow></TableHeader>
          <TableBody>
            {loading
              ? [...Array(4)].map((_, i) => (
                  <TableRow key={i}>
                    {[...Array(6)].map((_, j) => (
                      <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                    ))}
                  </TableRow>
                ))
              : rows.length === 0
                ? <TableRow><TableCell colSpan={6} className="text-center py-10 text-muted-foreground">No ring groups found.</TableCell></TableRow>
                : rows.map(r => {
                    const id = r.ring_group_uuid
                    const strategy = STRATEGIES.find(s => s.value === r.ring_group_strategy)
                    return (
                      <TableRow key={id}>
                        <TableCell className="font-mono font-medium">{r.ring_group_extension || '—'}</TableCell>
                        <TableCell>{r.ring_group_name}</TableCell>
                        <TableCell>
                          <Badge variant="secondary">{strategy?.label || r.ring_group_strategy}</Badge>
                        </TableCell>
                        <TableCell className="text-muted-foreground">{r.ring_group_call_timeout}s</TableCell>
                        <TableCell>
                          <Badge variant={r.ring_group_enabled !== false ? 'success' : 'secondary'}>
                            {r.ring_group_enabled !== false ? 'Active' : 'Disabled'}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(r)}>
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive"
                              onClick={() => handleDelete(id)} disabled={deleting === id}
                            >
                              {deleting === id
                                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                : <Trash2 className="h-3.5 w-3.5" />}
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
    </div>
  )
}
