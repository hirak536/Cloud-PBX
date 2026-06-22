import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { ivrMenus as api, extensions as extensionsApi } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { Plus, Pencil, Trash2, Search, Loader2 } from 'lucide-react'
import { cn } from '@/lib/utils'
import DestinationPicker, { EMPTY_DEST } from '@/components/DestinationPicker'
import RecordingPicker from '@/components/RecordingPicker'
import { useDestinationData } from '@/hooks/useDestinationData'
import { useRecordingData } from '@/hooks/useRecordingData'

// ─── Constants ────────────────────────────────────────────────────────────────

const OPTION_KEYS = [
  { digit: '1',       label: 'Pressing 1' },
  { digit: '2',       label: 'Pressing 2' },
  { digit: '3',       label: 'Pressing 3' },
  { digit: '4',       label: 'Pressing 4' },
  { digit: '5',       label: 'Pressing 5' },
  { digit: '6',       label: 'Pressing 6' },
  { digit: '7',       label: 'Pressing 7' },
  { digit: '8',       label: 'Pressing 8' },
  { digit: '9',       label: 'Pressing 9' },
  { digit: '0',       label: 'Pressing 0' },
  { digit: '*',       label: 'Pressing STAR' },
  { digit: '#',       label: 'Pressing #' },
  { digit: 'invalid', label: 'On wrong key press/word' },
  { digit: 'timeout', label: 'On timeout' },
  { digit: 'hangup',  label: 'On hangup' },
]

const makeEmptyOptions = () =>
  Object.fromEntries(OPTION_KEYS.map(k => [k.digit, { ...EMPTY_DEST }]))

const EMPTY_FORM = {
  ivr_menu_name: '',
  ivr_menu_extension: '',
  ivr_menu_enabled: true,
  ivr_menu_greet_long: '',
  ivr_menu_greet_short: '',
  ivr_menu_playback_count: 1,
  ivr_menu_timeout: 10,
  ivr_menu_loop_timeout: true,
  ivr_menu_loop_invalid: true,
  ivr_menu_allow_internal_dial: false,
  ivr_menu_allow_custom_codes: false,
  ivr_menu_allow_feature_codes: false,
  ivr_menu_internal_dial_invalid: { ...EMPTY_DEST },
  ivr_menu_description: '',
  options: makeEmptyOptions(),
}

// ─── Main Component ───────────────────────────────────────────────────────────

const TABS = [
  { id: 'settings', label: 'Settings' },
  { id: 'keys',     label: 'Key Options' },
]

export default function IvrMenus() {
  const navigate = useNavigate()
  const { id: editParamId } = useParams()
  const location = useLocation()
  const isCreate   = location.pathname.endsWith('/ivr-menus/new')
  const routeId    = editParamId
  const editorOpen = isCreate || routeId !== undefined

  const [rows, setRows]             = useState([])
  const [loading, setLoading]       = useState(true)
  const [search, setSearch]         = useState('')
  const debouncedSearch             = useDebounce(search, 300)
  const [editId, setEditId]         = useState(null)
  const [form, setForm]             = useState(EMPTY_FORM)
  const [saving, setSaving]         = useState(false)
  const [formError, setFormError]   = useState('')
  const [deleting, setDeleting]     = useState(null)
  const [tab, setTab]               = useState('settings')
  const [numStatus, setNumStatus]   = useState(null)
  const [numConflict, setNumConflict] = useState('')
  const debouncedExt = useDebounce(form.ivr_menu_extension, 600)

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

  const { destData, destLoading, loadDestData } = useDestinationData()
  const { recordings, recLoading, loadRecordings } = useRecordingData()

  // ── List ──────────────────────────────────────────────────────────────────

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.list(debouncedSearch ? { search: debouncedSearch } : {})
      setRows(Array.isArray(data) ? data : data.results || [])
    } finally { setLoading(false) }
  }, [search])

  useEffect(() => { load() }, [load])

  // ── Form helpers ──────────────────────────────────────────────────────────

  const f  = (key) => (e) => setForm(p => ({ ...p, [key]: e.target.value }))
  const fN = (key) => (e) => setForm(p => ({ ...p, [key]: Number(e.target.value) }))
  const fB = (key) => (val) => setForm(p => ({ ...p, [key]: val }))

  const setOption = (digit, dest) =>
    setForm(p => ({ ...p, options: { ...p.options, [digit]: dest } }))

  // ── Dialog open helpers ───────────────────────────────────────────────────

  const detailToForm = (d) => {
    const optionsMap = makeEmptyOptions()
    for (const opt of d.options || []) {
      const dig = opt.ivr_menu_option_digits
      if (Object.hasOwn(optionsMap, dig)) {
        optionsMap[dig] = {
          type:            opt.ivr_menu_option_dest_type || '',
          target_uuid:     opt.ivr_menu_option_dest_target_uuid || '',
          external_number: opt.ivr_menu_option_dest_external_number || '',
        }
      }
    }
    return {
      ivr_menu_name:             d.ivr_menu_name || '',
      ivr_menu_extension:        d.ivr_menu_extension || '',
      ivr_menu_enabled:          d.ivr_menu_enabled !== false,
      ivr_menu_greet_long:       d.ivr_menu_greet_long || '',
      ivr_menu_greet_short:      d.ivr_menu_greet_short || '',
      ivr_menu_playback_count:   d.ivr_menu_playback_count ?? 1,
      ivr_menu_timeout:          Math.round((d.ivr_menu_timeout ?? 10000) / 1000),
      ivr_menu_loop_timeout:     d.ivr_menu_loop_timeout !== false,
      ivr_menu_loop_invalid:     d.ivr_menu_loop_invalid !== false,
      ivr_menu_allow_internal_dial: d.ivr_menu_allow_internal_dial || false,
      ivr_menu_allow_custom_codes:  d.ivr_menu_allow_custom_codes  || false,
      ivr_menu_allow_feature_codes: d.ivr_menu_allow_feature_codes || false,
      ivr_menu_internal_dial_invalid: {
        type:            d.ivr_menu_internal_dial_invalid_type || '',
        target_uuid:     d.ivr_menu_internal_dial_invalid_target_uuid || '',
        external_number: d.ivr_menu_internal_dial_invalid_external_number || '',
      },
      ivr_menu_description:      d.ivr_menu_description || '',
      options: optionsMap,
    }
  }

  const openCreate  = () => navigate('/ivr-menus/new')
  const openEdit    = (r) => navigate('/ivr-menus/' + r.ivr_menu_uuid + '/edit')
  const closeEditor = () => navigate('/ivr-menus')

  // Sync form state to the current route.
  useEffect(() => {
    if (!editorOpen) return
    setFormError('')
    setTab('settings')
    loadDestData()
    loadRecordings()
    if (isCreate) {
      setEditId(null)
      setForm({ ...EMPTY_FORM, options: makeEmptyOptions() })
      return
    }
    setEditId(routeId)
    setForm({ ...EMPTY_FORM, options: makeEmptyOptions() })
    api.get(routeId)
      .then(({ data: d }) => setForm(detailToForm(d)))
      .catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeId, isCreate])

  // ── Save ──────────────────────────────────────────────────────────────────

  const handleSave = async () => {
    if (!form.ivr_menu_name)      { setFormError('Name is required.'); setTab('settings'); return }
    setSaving(true); setFormError('')
    try {
      const optionsPayload = OPTION_KEYS
        .filter(({ digit }) => form.options[digit]?.type)
        .map(({ digit }, i) => ({
          ivr_menu_option_digits:               digit,
          ivr_menu_option_dest_type:            form.options[digit].type,
          ivr_menu_option_dest_target_uuid:     form.options[digit].target_uuid || null,
          ivr_menu_option_dest_external_number: form.options[digit].external_number || '',
          ivr_menu_option_order:                (i + 1) * 10,
        }))

      const payload = {
        ivr_menu_name:             form.ivr_menu_name,
        ivr_menu_extension:        form.ivr_menu_extension,
        ivr_menu_enabled:          form.ivr_menu_enabled,
        ivr_menu_greet_long:       form.ivr_menu_greet_long,
        ivr_menu_greet_short:      form.ivr_menu_greet_short,
        ivr_menu_playback_count:   Number(form.ivr_menu_playback_count),
        ivr_menu_timeout:          Number(form.ivr_menu_timeout) * 1000,
        ivr_menu_loop_timeout:     form.ivr_menu_loop_timeout,
        ivr_menu_loop_invalid:     form.ivr_menu_loop_invalid,
        ivr_menu_allow_internal_dial: form.ivr_menu_allow_internal_dial,
        ivr_menu_allow_custom_codes:  form.ivr_menu_allow_custom_codes,
        ivr_menu_allow_feature_codes: form.ivr_menu_allow_feature_codes,
        ivr_menu_internal_dial_invalid_type:            form.ivr_menu_internal_dial_invalid?.type || '',
        ivr_menu_internal_dial_invalid_target_uuid:     form.ivr_menu_internal_dial_invalid?.target_uuid || null,
        ivr_menu_internal_dial_invalid_external_number: form.ivr_menu_internal_dial_invalid?.external_number || '',
        ivr_menu_description:      form.ivr_menu_description,
        options:                   optionsPayload,
      }
      editId ? await api.update(editId, payload) : await api.create(payload)
      load(); closeEditor()
    } catch (err) {
      const d = err?.response?.data
      setFormError(typeof d === 'string' ? d : Object.values(d || {}).flat().join(' ') || 'Save failed.')
    } finally { setSaving(false) }
  }

  // ── Delete ────────────────────────────────────────────────────────────────

  const handleDelete = async (id) => {
    if (!confirm('Delete this IVR menu?')) return
    setDeleting(id)
    try { await api.delete(id); load() } finally { setDeleting(null) }
  }

  // ── Render ────────────────────────────────────────────────────────────────

  // Full-page editor (routed)
  if (editorOpen) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={closeEditor} className="-ml-2 gap-1">
            ← IVR Menus
          </Button>
          <span className="text-muted-foreground">/</span>
          <h1 className="text-lg font-semibold">{isCreate ? 'New IVR Menu' : 'Edit IVR Menu'}</h1>
        </div>

        <Card>
          {/* Tabs */}
          <div className="px-6 pt-3 border-b shrink-0">
            <div className="flex">
              {TABS.map(t => (
                <button key={t.id} type="button" onClick={() => setTab(t.id)}
                  className={cn(
                    'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
                    tab === t.id
                      ? 'border-primary text-primary'
                      : 'border-transparent text-muted-foreground hover:text-foreground',
                  )}>
                  {t.label}
                </button>
              ))}
            </div>
          </div>

          {/* Body */}
          <div className="px-6 py-5 space-y-5">
            {formError && (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {formError}
              </div>
            )}

            {/* ══ SETTINGS TAB ═══════════════════════════════════════════════ */}
            {tab === 'settings' && (
              <>
                {/* Name / Type / Status */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5 col-span-2">
                    <Label>Name <span className="text-destructive">*</span></Label>
                    <Input placeholder="Main Menu" value={form.ivr_menu_name} onChange={f('ivr_menu_name')} />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Type</Label>
                    <select
                      className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm"
                      value="dtmf" disabled
                    >
                      <option value="dtmf">DTMF</option>
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <Label>Status</Label>
                    <select
                      className="flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                      value={form.ivr_menu_enabled ? 'true' : 'false'}
                      onChange={e => setForm(p => ({ ...p, ivr_menu_enabled: e.target.value === 'true' }))}
                    >
                      <option value="true">Active</option>
                      <option value="false">Disabled</option>
                    </select>
                  </div>
                </div>

                {/* Welcome Message */}
                <div className="space-y-1.5">
                  <Label>Welcome Message</Label>
                  <RecordingPicker
                    value={form.ivr_menu_greet_long}
                    onChange={val => setForm(p => ({ ...p, ivr_menu_greet_long: val }))}
                    recordings={recordings}
                    loading={recLoading}
                  />
                  <p className="text-xs text-muted-foreground">Played once when the caller first enters this menu</p>
                </div>

                {/* Options Message */}
                <div className="space-y-1.5">
                  <Label>Options Message</Label>
                  <RecordingPicker
                    value={form.ivr_menu_greet_short}
                    onChange={val => setForm(p => ({ ...p, ivr_menu_greet_short: val }))}
                    recordings={recordings}
                    loading={recLoading}
                  />
                  <p className="text-xs text-muted-foreground">Played on each loop ("Press 1 for Sales, Press 2 for…")</p>
                </div>

                {/* Messages playback + Timeout */}
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label>Messages playback</Label>
                    <Input type="number" min="1" value={form.ivr_menu_playback_count} onChange={fN('ivr_menu_playback_count')} />
                  </div>
                  <div className="space-y-1.5">
                    <Label>Menu selection timeout (s)</Label>
                    <Input type="number" min="1" value={form.ivr_menu_timeout} onChange={fN('ivr_menu_timeout')} />
                  </div>
                </div>

                {/* Checkboxes */}
                <div className="space-y-1">
                  <Label className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">Options</Label>
                  <div className="grid grid-cols-2 gap-x-8">
                    {[
                      { key: 'ivr_menu_loop_timeout',        label: 'Loop on timeout' },
                      { key: 'ivr_menu_loop_invalid',        label: 'Loop on wrong key press/word' },
                      { key: 'ivr_menu_allow_internal_dial', label: 'Allow dialing internal numbers' },
                      { key: 'ivr_menu_allow_custom_codes',  label: 'Allow Custom Codes' },
                      { key: 'ivr_menu_allow_feature_codes', label: 'Allow Dialing Feature Codes' },
                    ].map(({ key, label }) => (
                      <label key={key} className="flex items-center gap-2.5 py-1 cursor-pointer select-none group">
                        <input
                          type="checkbox"
                          checked={!!form[key]}
                          onChange={e => fB(key)(e.target.checked)}
                          className="h-4 w-4 rounded border-input accent-primary cursor-pointer"
                        />
                        <span className="text-sm text-muted-foreground group-hover:text-foreground transition-colors">{label}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Direct-dial fallback (only when internal dial is allowed) */}
                {form.ivr_menu_allow_internal_dial && (
                  <div className="space-y-1.5">
                    <Label>If dialed extension doesn't exist</Label>
                    <p className="text-xs text-muted-foreground">
                      Caller types &lt;ext&gt;# inside the IVR. If the extension isn't found in this tenant, route the call here.
                    </p>
                    <DestinationPicker
                      value={form.ivr_menu_internal_dial_invalid}
                      onChange={dest => setForm(p => ({ ...p, ivr_menu_internal_dial_invalid: dest }))}
                      data={destData}
                      loading={destLoading}
                    />
                  </div>
                )}

                {/* Description */}
                <div className="space-y-1.5">
                  <Label>Description</Label>
                  <Input placeholder="Optional notes…" value={form.ivr_menu_description} onChange={f('ivr_menu_description')} />
                </div>
              </>
            )}

            {/* ══ KEY OPTIONS TAB ════════════════════════════════════════════ */}
            {tab === 'keys' && (
              <div className="space-y-0.5">
                <p className="text-xs text-muted-foreground pb-3">
                  Set the destination for each key press. Leave blank to use default behavior.
                </p>

                {/* Digit keys */}
                {OPTION_KEYS.filter(k => !['invalid','timeout','hangup'].includes(k.digit)).map(({ digit, label }) => (
                  <div key={digit} className="flex items-center gap-3 py-1">
                    <span className="text-sm w-36 shrink-0 font-medium">{label}</span>
                    <div className="flex-1">
                      <DestinationPicker
                        value={form.options[digit]}
                        onChange={dest => setOption(digit, dest)}
                        data={destData}
                        loading={destLoading}
                      />
                    </div>
                  </div>
                ))}

                {/* Separator */}
                <div className="border-t my-4" />

                {/* Special keys */}
                {OPTION_KEYS.filter(k => ['invalid','timeout','hangup'].includes(k.digit)).map(({ digit, label }) => (
                  <div key={digit} className="flex items-center gap-3 py-1">
                    <span className="text-sm w-36 shrink-0 text-muted-foreground font-medium">{label}</span>
                    <div className="flex-1">
                      <DestinationPicker
                        value={form.options[digit]}
                        onChange={dest => setOption(digit, dest)}
                        data={destData}
                        loading={destLoading}
                      />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-6 py-3 border-t shrink-0">
            <div className="flex items-center justify-between w-full">
              <span className="text-xs text-muted-foreground">
                Step {TABS.findIndex(t => t.id === tab) + 1} of {TABS.length}
              </span>
              <div className="flex gap-2">
                <Button variant="outline" onClick={closeEditor}>Cancel</Button>
                {TABS.findIndex(t => t.id === tab) > 0 && (
                  <Button variant="outline" onClick={() => setTab(TABS[TABS.findIndex(t => t.id === tab) - 1].id)}>
                    ← Back
                  </Button>
                )}
                {TABS.findIndex(t => t.id === tab) < TABS.length - 1 ? (
                  <Button onClick={() => setTab(TABS[TABS.findIndex(t => t.id === tab) + 1].id)}>
                    Next →
                  </Button>
                ) : (
                  <Button onClick={handleSave} disabled={saving}>
                    {saving && <Loader2 className="h-4 w-4 animate-spin" />}
                    {isCreate ? 'Create IVR Menu' : 'Save Changes'}
                  </Button>
                )}
              </div>
            </div>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Search IVR menus…" className="pl-8" value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <Button size="sm" onClick={openCreate}><Plus className="h-4 w-4" /> Add IVR Menu</Button>
      </div>

      {/* Table */}
      <Card><CardContent className="p-0 overflow-x-auto">
        <Table>
          <TableHeader><TableRow>
            <TableHead>Extension</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Timeout</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="w-20" />
          </TableRow></TableHeader>
          <TableBody>
            {loading
              ? [...Array(4)].map((_, i) => (
                  <TableRow key={i}>{[...Array(5)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}</TableRow>
                ))
              : rows.length === 0
                ? <TableRow><TableCell colSpan={5} className="text-center py-10 text-muted-foreground">No IVR menus found.</TableCell></TableRow>
                : rows.map(r => {
                    const id = r.ivr_menu_uuid
                    return (
                      <TableRow key={id}>
                        <TableCell className="font-mono font-medium">{r.ivr_menu_extension || '—'}</TableCell>
                        <TableCell>{r.ivr_menu_name}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {r.ivr_menu_timeout ? `${Math.round(r.ivr_menu_timeout / 1000)}s` : '—'}
                        </TableCell>
                        <TableCell>
                          <Badge variant={r.ivr_menu_enabled !== false ? 'success' : 'secondary'}>
                            {r.ivr_menu_enabled !== false ? 'Active' : 'Disabled'}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(r)}>
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive"
                              onClick={() => handleDelete(id)} disabled={deleting === id}>
                              {deleting === id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
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
