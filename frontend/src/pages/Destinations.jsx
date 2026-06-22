import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { destinations as api, fax as faxApi } from '@/api'
import { useDestinationData } from '@/hooks/useDestinationData'
import { useInfiniteList } from '@/hooks/useInfiniteList'
import { InfiniteScroll, PageSizeSelector, DEFAULT_PAGE_SIZE } from '@/components/InfiniteScroll'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Select } from '@/components/ui/select'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import { Plus, Pencil, Trash2, Search, Loader2, X, ChevronDown, PhoneForwarded, PhoneOff, Layers, AlertCircle, CheckCircle2, Sparkles, History, Download } from 'lucide-react'
import { AffinityPanel } from './CustomDestinations'

// ── Constants ──────────────────────────────────────────────────────────────────

const ALWAYS_RECORD_OPTIONS = [
  { value: '',         label: 'No' },
  { value: 'all',      label: 'All' },
  { value: 'local',    label: 'Local' },
  { value: 'outbound', label: 'Outbound' },
  { value: 'inbound',  label: 'Inbound' },
]

const FAX_PROTOCOL_OPTIONS = [
  { value: 't38_only',        label: 'T.38 Only' },
  { value: 't38_preferred',   label: 'T.38 Preferred' },
  { value: 'sdp_passthrough', label: 'SDP Passthrough' },
  { value: 'none',            label: 'None' },
]

const TABS = [
  { id: 'information', label: 'Information' },
  { id: 'voice',       label: 'Voice' },
  { id: 'fax',         label: 'Fax' },
]

const DEST_META = {
  extension:          { label: 'Extension',          color: 'text-blue-500',   bg: 'bg-blue-500/10'   },
  ivr_menu:           { label: 'IVR Menu',           color: 'text-amber-500',  bg: 'bg-amber-500/10'  },
  ring_group:         { label: 'Ring Group',         color: 'text-green-600',  bg: 'bg-green-600/10'  },
  voicemail:          { label: 'Voicemail',          color: 'text-purple-500', bg: 'bg-purple-500/10' },
  conference:         { label: 'Conference',         color: 'text-sky-500',    bg: 'bg-sky-500/10'    },
  working_hours:      { label: 'Working Hours',      color: 'text-teal-500',   bg: 'bg-teal-500/10'   },
  custom_destination: { label: 'Custom Destination', color: 'text-fuchsia-500',bg: 'bg-fuchsia-500/10'},
  external:           { label: 'External',           color: 'text-slate-500',  bg: 'bg-slate-500/10'  },
  fax:                { label: 'Fax',                color: 'text-orange-500', bg: 'bg-orange-500/10' },
  hangup:             { label: 'Hangup',             color: 'text-red-500',    bg: 'bg-red-500/10'    },
}

const EMPTY_ACTION = { type: '', target_uuid: '', external_number: '' }

const EMPTY = {
  destination_number: '+1',
  destination_number_regex: '',
  destination_name: '',
  actions: [],
  max_channels: '',
  notify_over_limit: false,
  use_cnam_service: false,
  hide_callerid: false,
  use_as_emergency_callerid: false,
  inbound_call_rate: '',
  destination_cid_number_prefix: '',
  destination_cid_name_prefix: '',
  destination_ringback: '',
  destination_hold_music: '',
  destination_accountcode: '',
  destination_enabled: true,
  destination_description: '',
  unconditional_forward: false,
  callback_to_last_caller: false,
  always_record: '',
  email_recording_to: '',
  transcript_recorded: false,
  summarize_recorded: false,
  sentiment_analysis: false,
  fax_id: '',
  fax_receive: false,
  fax_station_id: '',
  fax_header: '',
  fax_protocol: 't38_only',
  fax_store: false,
  fax_on_receive: '',
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function rowToForm(r) {
  return {
    destination_number:        r.destination_number || '',
    destination_number_regex:  r.destination_number_regex || '',
    destination_name:          r.destination_name || '',
    actions: (r.actions || []).map(a => ({
      type:           a.dest_type || '',
      target_uuid:    a.dest_target_uuid || '',
      external_number: a.dest_external_number || '',
    })),
    max_channels:              r.max_channels ?? '',
    notify_over_limit:         !!r.notify_over_limit,
    use_cnam_service:          !!r.use_cnam_service,
    hide_callerid:             !!r.hide_callerid,
    use_as_emergency_callerid: !!r.use_as_emergency_callerid,
    inbound_call_rate:         r.inbound_call_rate || '',
    destination_cid_number_prefix: r.destination_cid_number_prefix || '',
    destination_cid_name_prefix:   r.destination_cid_name_prefix || '',
    destination_ringback:      r.destination_ringback || '',
    destination_hold_music:    r.destination_hold_music || '',
    destination_accountcode:   r.destination_accountcode || '',
    destination_enabled:       r.destination_enabled !== false,
    destination_description:   r.destination_description || '',
    unconditional_forward:     !!r.unconditional_forward,
    callback_to_last_caller:   !!r.callback_to_last_caller,
    always_record:             r.always_record || '',
    email_recording_to:        r.email_recording_to || '',
    transcript_recorded:       !!r.transcript_recorded,
    summarize_recorded:        !!r.summarize_recorded,
    sentiment_analysis:        !!r.sentiment_analysis,
    fax_id:                    r.fax_id || '',
    fax_receive:               !!r.fax_receive,
    fax_station_id:            r.fax_station_id || '',
    fax_header:                r.fax_header || '',
    fax_protocol:              r.fax_protocol || 't38_only',
    fax_store:                 !!r.fax_store,
    fax_on_receive:            r.fax_on_receive || '',
  }
}

// ── Destination Picker ─────────────────────────────────────────────────────────

function actionLabel(type, targetUuid, extNumber, data) {
  if (!type) return null
  if (type === 'hangup')        return 'Hangup'
  if (type === 'external')      return extNumber || 'External Number'
  if (type === 'fax')           return 'Direct Fax Receive'
  if (type === 'extension') {
    const e = data.extensions.find(x => x.extension_uuid === targetUuid)
    return e ? `${e.extension}${e.effective_caller_id_name ? ` — ${e.effective_caller_id_name}` : ''}` : (targetUuid ? `Ext ${targetUuid.slice(0, 8)}…` : null)
  }
  if (type === 'voicemail') {
    const v = data.voicemails.find(x => (x.voicemail_uuid || x.id) === targetUuid)
    return v ? `Voicemail ${v.voicemail_id}` : (targetUuid ? `VM ${targetUuid.slice(0, 8)}…` : null)
  }
  if (type === 'ivr_menu') {
    const i = data.ivr_menus.find(x => x.ivr_menu_uuid === targetUuid)
    return i ? i.ivr_menu_name : (targetUuid ? `IVR ${targetUuid.slice(0, 8)}…` : null)
  }
  if (type === 'ring_group') {
    const r = data.ring_groups.find(x => x.ring_group_uuid === targetUuid)
    return r ? r.ring_group_name : (targetUuid ? `RG ${targetUuid.slice(0, 8)}…` : null)
  }
  if (type === 'conference') {
    const c = data.conferences.find(x => x.conference_uuid === targetUuid)
    return c ? c.conference_name : (targetUuid ? `Conf ${targetUuid.slice(0, 8)}…` : null)
  }
  if (type === 'working_hours') {
    const w = data.working_hours.find(x => x.working_hours_uuid === targetUuid)
    return w ? w.working_hours_name : (targetUuid ? `WH ${targetUuid.slice(0, 8)}…` : null)
  }
  if (type === 'custom_destination') {
    const c = (data.custom_destinations || []).find(x => x.custom_destination_uuid === targetUuid)
    return c ? c.name : (targetUuid ? `CD ${targetUuid.slice(0, 8)}…` : null)
  }
  return null
}

function DestinationPicker({ action, onChange, data, loading, searchLoading, onSearch }) {
  const [open, setOpen]     = useState(false)
  const [dropUp, setDropUp] = useState(false)
  const [query, setQuery]   = useState('')
  const debouncedQuery      = useDebounce(query, 300)
  const containerRef        = useRef(null)
  const inputRef            = useRef(null)

  const toggleOpen = () => {
    if (!open && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect()
      setDropUp(rect.bottom + 320 > window.innerHeight)
    }
    setOpen(o => !o)
  }

  useEffect(() => {
    if (!open) return
    const h = (e) => { if (!containerRef.current?.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [open])

  useEffect(() => {
    if (open) requestAnimationFrame(() => inputRef.current?.focus())
  }, [open])

  // Fire API search whenever the debounced query changes
  useEffect(() => {
    if (!open) return
    onSearch(debouncedQuery)
  }, [debouncedQuery, open])

  // When closed, reset to unfiltered list
  useEffect(() => {
    if (!open && query) { setQuery(''); onSearch('') }
  }, [open])

  const exts  = data.extensions    || []
  const vms   = data.voicemails    || []
  const ivrs  = data.ivr_menus     || []
  const rgs   = data.ring_groups   || []
  const confs = data.conferences   || []
  const whs   = data.working_hours || []
  const cds   = data.custom_destinations || []
  const q = query.trim()
  const showNumber = q.length >= 2 && /^[\d+\s().-]+$/.test(q)
  const hasAny = exts.length || vms.length || ivrs.length || rgs.length || confs.length || whs.length || cds.length || showNumber

  const select = (type, target_uuid = '', external_number = '') => {
    onChange({ type, target_uuid, external_number })
    setOpen(false); setQuery('')
  }

  const label = actionLabel(action.type, action.target_uuid, action.external_number, data)
  const meta  = action.type ? DEST_META[action.type] : null

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={toggleOpen}
        className={cn(
          'flex h-9 w-full items-center justify-between gap-2 rounded-md border border-input bg-background px-3 text-sm shadow-sm',
          'hover:border-ring/60 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring transition-colors',
        )}
      >
        {loading ? (
          <span className="flex items-center gap-2 text-muted-foreground text-xs">
            <Loader2 className="h-3 w-3 animate-spin" /> Loading…
          </span>
        ) : label ? (
          <span className="flex items-center gap-2 min-w-0">
            <span className={cn('shrink-0 text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded', meta?.color, meta?.bg)}>
              {meta?.label}
            </span>
            <span className="truncate text-sm">{label}</span>
          </span>
        ) : (
          <span className="text-muted-foreground text-sm">Select destination…</span>
        )}
        <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
      </button>

      {open && (
        <div className={cn("absolute z-50 w-full min-w-[300px] rounded-xl border border-border/60 bg-card shadow-2xl shadow-black/10 animate-dropdown-in", dropUp ? "bottom-full mb-1" : "mt-1")}>
          <div className="flex items-center gap-2 border-b px-3 py-1.5">
            {searchLoading
              ? <Loader2 className="h-3.5 w-3.5 shrink-0 text-muted-foreground animate-spin" />
              : <Search className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />}
            <input
              ref={inputRef}
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search extensions, ring groups, voicemail…"
              className="flex-1 text-sm bg-transparent outline-none placeholder:text-muted-foreground"
            />
            {query && <button type="button" onClick={() => setQuery('')}><X className="h-3 w-3 text-muted-foreground" /></button>}
          </div>

          <div className="max-h-60 overflow-y-auto py-1">
            {loading ? (
              <div className="flex items-center justify-center py-4 gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading…
              </div>
            ) : (
              <>
                {exts.length > 0 && (
                  <div>
                    <p className="px-3 pt-2 pb-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Extensions</p>
                    {exts.map(e => (
                      <button key={e.extension_uuid} type="button" onClick={() => select('extension', e.extension_uuid)}
                        className="w-full flex items-center gap-3 mx-1 px-3 py-1.5 rounded-lg hover:bg-muted text-left transition-colors text-sm">
                        <span className="font-mono font-bold text-blue-500 w-10 shrink-0">{e.extension}</span>
                        <span className="text-sm truncate text-muted-foreground">{e.effective_caller_id_name || e.description || ''}</span>
                      </button>
                    ))}
                  </div>
                )}
                {rgs.length > 0 && (
                  <div>
                    <p className="px-3 pt-2 pb-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Ring Groups</p>
                    {rgs.map(r => (
                      <button key={r.ring_group_uuid} type="button" onClick={() => select('ring_group', r.ring_group_uuid)}
                        className="w-full flex items-center gap-3 mx-1 px-3 py-1.5 rounded-lg hover:bg-muted text-left transition-colors text-sm">
                        <span className="font-mono font-bold text-green-600 w-10 shrink-0">{r.ring_group_extension || '—'}</span>
                        <span className="text-sm truncate">{r.ring_group_name}</span>
                      </button>
                    ))}
                  </div>
                )}
                {ivrs.length > 0 && (
                  <div>
                    <p className="px-3 pt-2 pb-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">IVR Menus</p>
                    {ivrs.map(i => (
                      <button key={i.ivr_menu_uuid} type="button" onClick={() => select('ivr_menu', i.ivr_menu_uuid)}
                        className="w-full flex items-center gap-3 mx-1 px-3 py-1.5 rounded-lg hover:bg-muted text-left transition-colors text-sm">
                        <span className="font-mono font-bold text-amber-500 w-10 shrink-0">{i.ivr_menu_extension || '—'}</span>
                        <span className="text-sm truncate">{i.ivr_menu_name}</span>
                      </button>
                    ))}
                  </div>
                )}
                {vms.length > 0 && (
                  <div>
                    <p className="px-3 pt-2 pb-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Voicemail</p>
                    {vms.map(v => (
                      <button key={v.voicemail_uuid || v.id} type="button" onClick={() => select('voicemail', v.voicemail_uuid || v.id)}
                        className="w-full flex items-center gap-3 mx-1 px-3 py-1.5 rounded-lg hover:bg-muted text-left transition-colors text-sm">
                        <span className="font-mono font-bold text-purple-500 w-10 shrink-0">{v.voicemail_id}</span>
                        <span className="text-sm truncate text-muted-foreground">{v.voicemail_name || ''}</span>
                      </button>
                    ))}
                  </div>
                )}
                {confs.length > 0 && (
                  <div>
                    <p className="px-3 pt-2 pb-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Conferences</p>
                    {confs.map(c => (
                      <button key={c.conference_uuid} type="button" onClick={() => select('conference', c.conference_uuid)}
                        className="w-full flex items-center gap-3 mx-1 px-3 py-1.5 rounded-lg hover:bg-muted text-left transition-colors text-sm">
                        <span className="font-mono font-bold text-sky-500 w-10 shrink-0">{c.conference_extension || '—'}</span>
                        <span className="text-sm truncate">{c.conference_name}</span>
                      </button>
                    ))}
                  </div>
                )}
                {whs.length > 0 && (
                  <div>
                    <p className="px-3 pt-2 pb-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Working Hours</p>
                    {whs.map(w => (
                      <button key={w.working_hours_uuid} type="button" onClick={() => select('working_hours', w.working_hours_uuid)}
                        className="w-full flex items-center gap-3 mx-1 px-3 py-1.5 rounded-lg hover:bg-muted text-left transition-colors text-sm">
                        <span className="font-mono font-bold text-teal-500 w-10 shrink-0">WH</span>
                        <span className="text-sm truncate">{w.working_hours_name}</span>
                      </button>
                    ))}
                  </div>
                )}
                {cds.length > 0 && (
                  <div>
                    <p className="px-3 pt-2 pb-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">Custom Destinations</p>
                    {cds.map(c => (
                      <button key={c.custom_destination_uuid} type="button" onClick={() => select('custom_destination', c.custom_destination_uuid)}
                        className="w-full flex items-center gap-3 mx-1 px-3 py-1.5 rounded-lg hover:bg-muted text-left transition-colors text-sm">
                        <span className="font-mono font-bold text-fuchsia-500 w-10 shrink-0">CD</span>
                        <span className="text-sm truncate">{c.name}</span>
                        {c.callback_to_last_caller && <span className="text-[10px] text-amber-600 ml-auto shrink-0">sticky</span>}
                      </button>
                    ))}
                  </div>
                )}
                {showNumber && (
                  <div>
                    <p className="px-3 pt-2 pb-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">External Number</p>
                    <button type="button" onClick={() => select('external', '', query)}
                      className="w-full flex items-center gap-3 mx-1 px-3 py-1.5 rounded-lg hover:bg-muted text-left transition-colors text-sm">
                      <PhoneForwarded className="h-4 w-4 text-slate-500 shrink-0" />
                      <span className="text-sm">Forward to <span className="font-mono font-semibold">{query}</span></span>
                    </button>
                  </div>
                )}
                {q && !hasAny && !searchLoading && (
                  <p className="px-3 py-4 text-sm text-muted-foreground text-center">No results for &ldquo;{query}&rdquo;</p>
                )}
                <div className="border-t mt-1 pt-1">
                  <button type="button" onClick={() => select('fax')}
                    className="w-full flex items-center gap-3 mx-1 px-3 py-1.5 rounded-lg hover:bg-muted text-left transition-colors text-sm">
                    <span className={cn('text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded shrink-0', DEST_META.fax.color, DEST_META.fax.bg)}>Fax</span>
                    <span className="text-sm text-orange-500 font-medium">Direct Fax Receive</span>
                  </button>
                  <button type="button" onClick={() => select('hangup')}
                    className="w-full flex items-center gap-3 mx-1 px-3 py-1.5 rounded-lg hover:bg-muted text-left transition-colors text-sm">
                    <PhoneOff className="h-4 w-4 text-red-500 shrink-0" />
                    <span className="text-sm text-red-500 font-medium">Hangup</span>
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ── UI helpers ─────────────────────────────────────────────────────────────────

function Field({ label, hint, children, className }) {
  return (
    <div className={cn('space-y-1.5', className)}>
      <Label className="text-sm font-medium">{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}

function Row({ children }) {
  return <div className="grid grid-cols-2 gap-4">{children}</div>
}

function Toggle({ checked, onChange }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        checked ? 'bg-primary' : 'bg-input',
      )}
    >
      <span className={cn('pointer-events-none block h-4 w-4 rounded-full bg-background shadow-lg transition-transform', checked ? 'translate-x-4' : 'translate-x-0')} />
    </button>
  )
}

function ToggleRow({ label, hint, checked, onChange }) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <div>
        <p className="text-sm font-medium leading-none">{label}</p>
        {hint && <p className="text-xs text-muted-foreground mt-0.5">{hint}</p>}
      </div>
      <Toggle checked={checked} onChange={onChange} />
    </div>
  )
}

function SectionTitle({ children }) {
  return <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mt-5 mb-2 first:mt-0">{children}</p>
}

// ── Inline Fax Box form ──────────────────────────────────────────────────────
// Lets a fax box be created or edited directly from the DID dialog's Fax tab.
// Mirrors the (simplified) Fax page box form: the single Name drives both
// fax_name and fax_caller_id_name; no forward number.

const FAX_BOX_EMPTY = {
  fax_name: '', fax_extension: '', fax_email: '',
  fax_caller_id_number: '', fax_description: '', fax_enabled: true,
  fax_delivery_mode: 'email',
  fax_ftp_host: '', fax_ftp_port: 21, fax_ftp_username: '',
  fax_ftp_password: '', fax_ftp_path: '', fax_ftp_use_tls: false,
}

function FaxBoxFormDialog({ open, editBox, didNumber, dids, onClose }) {
  const [form, setForm] = useState(FAX_BOX_EMPTY)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!open) return
    setError('')
    if (editBox) {
      setForm({
        fax_name:             editBox.fax_name || editBox.fax_caller_id_name || '',
        // One box per number: extension is the DID number.
        fax_extension:        didNumber || editBox.fax_extension || '',
        fax_email:            editBox.fax_email || '',
        fax_caller_id_number: editBox.fax_caller_id_number || '',
        fax_description:      editBox.fax_description || '',
        fax_enabled:          editBox.fax_enabled !== false,
        fax_delivery_mode:    editBox.fax_delivery_mode || 'email',
        fax_ftp_host:         editBox.fax_ftp_host || '',
        fax_ftp_port:         editBox.fax_ftp_port ?? 21,
        fax_ftp_username:     editBox.fax_ftp_username || '',
        // Password is write-only on the backend, so it never comes back — leave blank.
        fax_ftp_password:     '',
        fax_ftp_path:         editBox.fax_ftp_path || '',
        fax_ftp_use_tls:      editBox.fax_ftp_use_tls === true,
      })
    } else {
      setForm({ ...FAX_BOX_EMPTY, fax_extension: didNumber || '' })
    }
  }, [open, editBox, didNumber])

  const sf = (key) => (e) => setForm(p => ({ ...p, [key]: e.target.value }))

  const handleSave = async () => {
    if (!form.fax_name.trim())      { setError('Name is required.');      return }
    if (!form.fax_extension.trim()) { setError('Enter the DID number first — the fax box is tied to it.'); return }
    const wantsFtp = form.fax_delivery_mode === 'ftp' || form.fax_delivery_mode === 'both'
    if (wantsFtp && !form.fax_ftp_host.trim()) { setError('FTP host is required for the selected delivery mode.'); return }
    setSaving(true); setError('')
    // Single Name drives both fax_name and fax_caller_id_name on the backend.
    const payload = { ...form, fax_caller_id_name: form.fax_name.trim() }
    // Blank password means "leave unchanged" — don't overwrite the stored one.
    if (!payload.fax_ftp_password) delete payload.fax_ftp_password
    try {
      let saved
      if (editBox) {
        const { data } = await faxApi.update(editBox.fax_uuid, payload)
        saved = data
        toast.success('Fax box updated.')
      } else {
        const { data } = await faxApi.create(payload)
        saved = data
        toast.success('Fax box created.')
      }
      onClose(saved || true)
    } catch (err) {
      const d = err?.response?.data
      setError(typeof d === 'string' ? d : Object.values(d || {}).flat().join(' ') || 'Save failed.')
    } finally { setSaving(false) }
  }

  return (
    <Dialog open={open} onOpenChange={() => { if (!saving) onClose(false) }}>
      <DialogContent className="w-[95vw] max-w-lg flex flex-col p-0 gap-0">
        <DialogHeader className="px-6 py-4 border-b shrink-0">
          <DialogTitle>{editBox ? 'Edit Fax Box' : 'New Fax Box'}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 px-6 py-5 overflow-y-auto">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <Field label="Name *" hint="Also used as the outbound caller ID name.">
              <Input placeholder="Main Fax" value={form.fax_name} onChange={sf('fax_name')} disabled={saving} />
            </Field>
            <Field label="Extension" hint="Tied to this DID number — one fax box per number.">
              <Input value={form.fax_extension} readOnly disabled className="font-mono" />
            </Field>
            <Field label="Received Fax Delivery" hint="What to do with inbound faxes." className="sm:col-span-2">
              <Select value={form.fax_delivery_mode} onChange={sf('fax_delivery_mode')} disabled={saving}>
                <option value="email">Email</option>
                <option value="ftp">FTP server</option>
                <option value="both">Email + FTP</option>
              </Select>
            </Field>
            {(form.fax_delivery_mode === 'email' || form.fax_delivery_mode === 'both') && (
              <Field label="Notification Email" hint="Inbound faxes are emailed here. Separate multiple addresses with commas." className="sm:col-span-2">
                <Input type="text" placeholder="fax@company.com, alerts@company.com" value={form.fax_email} onChange={sf('fax_email')} disabled={saving} />
              </Field>
            )}
            {(form.fax_delivery_mode === 'ftp' || form.fax_delivery_mode === 'both') && (
              <div className="sm:col-span-2 rounded-md border bg-muted/30 p-4">
                <p className="text-sm font-medium mb-3">FTP Server</p>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <Field label="FTP Host *" className="sm:col-span-2">
                    <Input placeholder="ftp.example.com" value={form.fax_ftp_host} onChange={sf('fax_ftp_host')} disabled={saving} />
                  </Field>
                  <Field label="Port">
                    <Input type="number" value={form.fax_ftp_port}
                      onChange={(e) => setForm(p => ({ ...p, fax_ftp_port: e.target.value === '' ? '' : Number(e.target.value) }))}
                      disabled={saving} />
                  </Field>
                  <Field label="Use FTPS (TLS)">
                    <Select value={String(form.fax_ftp_use_tls)} onChange={(e) => setForm(p => ({ ...p, fax_ftp_use_tls: e.target.value === 'true' }))} disabled={saving}>
                      <option value="false">No</option>
                      <option value="true">Yes</option>
                    </Select>
                  </Field>
                  <Field label="Username">
                    <Input placeholder="anonymous" value={form.fax_ftp_username} onChange={sf('fax_ftp_username')} disabled={saving} autoComplete="off" />
                  </Field>
                  <Field label="Password" hint={editBox ? 'Leave blank to keep the current password.' : undefined}>
                    <Input type="password" value={form.fax_ftp_password} onChange={sf('fax_ftp_password')} disabled={saving} autoComplete="new-password" />
                  </Field>
                  <Field label="Remote Path" hint="Directory to store faxes in (created if missing)." className="sm:col-span-2">
                    <Input placeholder="/incoming-faxes" value={form.fax_ftp_path} onChange={sf('fax_ftp_path')} disabled={saving} />
                  </Field>
                </div>
              </div>
            )}
            <Field label="Status">
              <Select value={String(form.fax_enabled)} onChange={(e) => setForm(p => ({ ...p, fax_enabled: e.target.value === 'true' }))} disabled={saving}>
                <option value="true">Enabled</option>
                <option value="false">Disabled</option>
              </Select>
            </Field>
            <Field label="Caller ID Number">
              <Select value={form.fax_caller_id_number} onChange={sf('fax_caller_id_number')} disabled={saving}>
                <option value="">— Select DID —</option>
                {/* Keep the current value selectable even if its DID isn't in the
                    list yet (e.g. an unsaved DID auto-created this box). */}
                {form.fax_caller_id_number &&
                  !dids.some(d => d.destination_number === form.fax_caller_id_number) && (
                    <option value={form.fax_caller_id_number}>{form.fax_caller_id_number}</option>
                  )}
                {dids.map(d => (
                  <option key={d.destination_uuid} value={d.destination_number}>
                    {d.destination_number}{d.destination_name ? ` — ${d.destination_name}` : ''}
                  </option>
                ))}
              </Select>
            </Field>
            <Field label="Description" className="sm:col-span-2">
              <Input placeholder="Optional description" value={form.fax_description} onChange={sf('fax_description')} disabled={saving} />
            </Field>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <div className="flex justify-end gap-2 px-6 py-3 border-t shrink-0">
          <Button variant="outline" onClick={() => onClose(false)} disabled={saving}>Cancel</Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? <><Loader2 className="h-4 w-4 animate-spin" />Saving…</> : 'Save'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ── Tab body ───────────────────────────────────────────────────────────────────

// Inline notification-email editor shown under a linked fax box. Saves on blur
// (only when the value actually changed) so admins can set the inbound-fax email
// without opening the full box form.
function FaxBoxEmailField({ box, onSave }) {
  const [value, setValue] = useState(box.fax_email || '')
  const [saving, setSaving] = useState(false)
  useEffect(() => { setValue(box.fax_email || '') }, [box.fax_uuid, box.fax_email])

  const commit = async () => {
    if (value === (box.fax_email || '')) return
    setSaving(true)
    try { await onSave(box, value) } finally { setSaving(false) }
  }

  return (
    <Field label="Notification Email" hint="Incoming faxes are emailed here as a PDF. Separate multiple addresses with commas.">
      <div className="relative">
        <Input
          type="text"
          placeholder="fax@company.com, alerts@company.com"
          value={value}
          onChange={e => setValue(e.target.value)}
          onBlur={commit}
          disabled={saving}
        />
        {saving && <Loader2 className="absolute right-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 animate-spin text-muted-foreground" />}
      </div>
    </Field>
  )
}

function DIDFormBody({ tab, form, set, setForm, destData, destLoading, destSearchLoading, onSearch, onNewFaxBox, onEditFaxBox, onAutoCreateFaxBox, autoCreatingFax, onUpdateFaxBoxEmail }) {
  const addAction    = () => setForm(p => ({ ...p, actions: [...p.actions, { ...EMPTY_ACTION }] }))
  const removeAction = (idx) => setForm(p => ({ ...p, actions: p.actions.filter((_, i) => i !== idx) }))
  const updateAction = (idx, v) => setForm(p => ({
    ...p,
    actions: p.actions.map((a, i) => i === idx ? { type: v.type, target_uuid: v.target_uuid, external_number: v.external_number } : a),
  }))

  if (tab === 'information') return (
    <div className="space-y-3">
      <Row>
        <Field label="DID / Phone Number *">
          <Input placeholder="+12025551234" value={form.destination_number} onChange={set('destination_number')} />
        </Field>
        <Field label="Friendly Name">
          <Input placeholder="e.g. IHS Main" value={form.destination_name} onChange={set('destination_name')} />
        </Field>
      </Row>
      <Field label="Match Regex" hint="Override carrier number matching (e.g. ^\+?1?2025551234$). Leave blank to match exactly.">
        <Input placeholder="^\+?1?2025551234$" value={form.destination_number_regex} onChange={set('destination_number_regex')} />
      </Field>

      <SectionTitle>Priority Routing</SectionTitle>
      <p className="text-xs text-muted-foreground -mt-1">
        Routes are tried in order. Add multiple for failover (e.g. Extension → Ring Group → Voicemail).
      </p>

      <div className="space-y-2">
        {form.actions.length === 0 && (
          <p className="text-sm text-muted-foreground text-center py-3 border border-dashed rounded-xl">
            No routing defined — add a route below.
          </p>
        )}
        {form.actions.map((action, idx) => (
          <div key={idx} className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground w-4 shrink-0 text-right font-mono">{idx + 1}</span>
            <div className="flex-1">
              <DestinationPicker
                action={action}
                onChange={(v) => updateAction(idx, v)}
                data={destData}
                loading={destLoading}
                searchLoading={destSearchLoading}
                onSearch={onSearch}
              />
            </div>
            <button
              type="button"
              onClick={() => removeAction(idx)}
              className="shrink-0 h-7 w-7 flex items-center justify-center rounded text-muted-foreground hover:text-destructive hover:bg-muted transition-colors"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        ))}
        <Button type="button" variant="outline" size="sm" onClick={addAction} className="w-full mt-1">
          <Plus className="h-3.5 w-3.5 mr-1" /> Add Route
        </Button>
      </div>

      <SectionTitle>Capacity &amp; Caller ID</SectionTitle>
      <Row>
        <Field label="Max Channels" hint="Null = unlimited">
          <Input type="number" min="0" placeholder="Unlimited" value={form.max_channels} onChange={set('max_channels')} />
        </Field>
        <Field label="Inbound Call Rate" hint="Per-minute rate (blank = not applied)">
          <Input placeholder="0.0050" value={form.inbound_call_rate} onChange={set('inbound_call_rate')} />
        </Field>
      </Row>
      <div className="space-y-1">
        <ToggleRow label="Notify when over channel limit" checked={form.notify_over_limit} onChange={v => setForm(p => ({ ...p, notify_over_limit: v }))} />
        <ToggleRow label="Use CNAM service" checked={form.use_cnam_service} onChange={v => setForm(p => ({ ...p, use_cnam_service: v }))} />
        <ToggleRow label="Hide caller ID" checked={form.hide_callerid} onChange={v => setForm(p => ({ ...p, hide_callerid: v }))} />
        <ToggleRow label="Use as emergency caller ID" checked={form.use_as_emergency_callerid} onChange={v => setForm(p => ({ ...p, use_as_emergency_callerid: v }))} />
      </div>

      <SectionTitle>Caller ID Manipulation</SectionTitle>
      <Row>
        <Field label="CID Number Prefix">
          <Input placeholder="IHS-" value={form.destination_cid_number_prefix} onChange={set('destination_cid_number_prefix')} />
        </Field>
        <Field label="CID Name Prefix">
          <Input placeholder="Sales: " value={form.destination_cid_name_prefix} onChange={set('destination_cid_name_prefix')} />
        </Field>
      </Row>
      <Row>
        <Field label="Ringback" hint="Tone URI or leave blank">
          <Input placeholder="us-ring" value={form.destination_ringback} onChange={set('destination_ringback')} />
        </Field>
        <Field label="Hold Music URI">
          <Input placeholder="local_stream://default" value={form.destination_hold_music} onChange={set('destination_hold_music')} />
        </Field>
      </Row>
      <Field label="Account Code" hint="Billing code for CDR">
        <Input value={form.destination_accountcode} onChange={set('destination_accountcode')} />
      </Field>

      <SectionTitle>Status</SectionTitle>
      <ToggleRow label="Enabled" checked={form.destination_enabled} onChange={v => setForm(p => ({ ...p, destination_enabled: v }))} />
      <Field label="Description">
        <textarea
          className="flex min-h-[64px] w-full rounded-xl border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:border-primary/60 hover:border-primary/40 transition-all duration-150"
          placeholder="Optional notes"
          value={form.destination_description}
          onChange={set('destination_description')}
        />
      </Field>
    </div>
  )

  if (tab === 'voice') return (
    <div className="space-y-3">
      <SectionTitle>Forwarding</SectionTitle>
      <ToggleRow label="Unconditional Forward" hint="Forward all calls immediately, bypassing routing" checked={form.unconditional_forward} onChange={v => setForm(p => ({ ...p, unconditional_forward: v }))} />
      <div className={cn('rounded-xl border px-4 py-3 transition-colors', form.callback_to_last_caller ? 'border-amber-200 bg-amber-500/5' : 'border-border/60')}>
        <ToggleRow
          label="Route to last agent"
          hint="If the caller has been dialed before, send them to that same extension. Falls through to the routing above when no match."
          checked={form.callback_to_last_caller}
          onChange={v => setForm(p => ({ ...p, callback_to_last_caller: v }))}
        />
        {form.callback_to_last_caller && (
          <div className="flex items-start gap-2 text-xs text-amber-700 mt-1">
            <Sparkles className="h-3.5 w-3.5 shrink-0 mt-0.5" />
            <span>
              Mappings update automatically from outbound calls.{' '}
              <button type="button" onClick={() => window.dispatchEvent(new CustomEvent('open-affinity'))} className="underline font-medium">
                View current mappings
              </button>.
            </span>
          </div>
        )}
      </div>

      <SectionTitle>Recording</SectionTitle>
      <Field label="Always Record">
        <Select value={form.always_record} onChange={set('always_record')}>
          {ALWAYS_RECORD_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </Select>
      </Field>
      <Field label="Email Recording To">
        <Input type="email" placeholder="recordings@example.com" value={form.email_recording_to} onChange={set('email_recording_to')} />
      </Field>

      <SectionTitle>AI Features</SectionTitle>
      <div className="space-y-1">
        <ToggleRow label="Transcribe Recordings" checked={form.transcript_recorded} onChange={v => setForm(p => ({ ...p, transcript_recorded: v }))} />
        <ToggleRow label="Summarize Recordings" checked={form.summarize_recorded} onChange={v => setForm(p => ({ ...p, summarize_recorded: v }))} />
        <ToggleRow label="Sentiment Analysis" checked={form.sentiment_analysis} onChange={v => setForm(p => ({ ...p, sentiment_analysis: v }))} />
      </div>
    </div>
  )

  if (tab === 'fax') {
    const selectedBox = (destData.fax_boxes || []).find(b => b.fax_uuid === form.fax_id)
    return (
    <div className="space-y-3">
      <Field label="Fax Box" hint="Each number has a single fax box. Create one to enable fax receive on this DID.">
        {selectedBox ? (
          <div className="space-y-2">
            <div className="flex items-center gap-3 rounded-xl border px-4 py-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-orange-500/10">
                <PhoneForwarded className="h-4 w-4 text-orange-500" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium truncate">{selectedBox.fax_name}</p>
                <p className="text-xs text-muted-foreground font-mono">
                  {selectedBox.fax_extension}
                  {selectedBox.fax_caller_id_number ? ` · CID ${selectedBox.fax_caller_id_number}` : ''}
                </p>
              </div>
              <Button type="button" variant="outline" size="sm" className="shrink-0" onClick={() => onEditFaxBox(selectedBox)}>
                <Pencil className="h-3.5 w-3.5 mr-1" />Edit
              </Button>
              <Button
                type="button" variant="ghost" size="sm"
                className="shrink-0 text-muted-foreground hover:text-destructive"
                onClick={() => setForm(p => ({ ...p, fax_id: '' }))}
              >
                <X className="h-3.5 w-3.5 mr-1" />Unlink
              </Button>
            </div>
            <FaxBoxEmailField box={selectedBox} onSave={onUpdateFaxBoxEmail} />
          </div>
        ) : (
          <div className="flex items-center justify-between rounded-xl border border-dashed px-4 py-3">
            <span className="text-sm text-muted-foreground">No fax box for this number.</span>
            <Button type="button" variant="outline" size="sm" onClick={onNewFaxBox}>
              <Plus className="h-3.5 w-3.5 mr-1" />Create Fax Box
            </Button>
          </div>
        )}
      </Field>
      <ToggleRow
        label="Enable Fax Receive"
        hint="Accept incoming faxes on this DID. Turning this on creates a fax box automatically if none exists."
        checked={form.fax_receive}
        onChange={v => {
          if (v && !form.fax_id) {
            // Auto-create + link a fax box, then enable receive.
            onAutoCreateFaxBox()
          } else {
            setForm(p => ({ ...p, fax_receive: v }))
          }
        }}
      />
      {autoCreatingFax && (
        <p className="text-xs text-muted-foreground flex items-center gap-1.5">
          <Loader2 className="h-3 w-3 animate-spin" /> Creating fax box…
        </p>
      )}

      <SectionTitle>Protocol</SectionTitle>
      <Field label="Fax Protocol">
        <Select value={form.fax_protocol} onChange={set('fax_protocol')}>
          {FAX_PROTOCOL_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
        </Select>
      </Field>

      <SectionTitle>Delivery</SectionTitle>
      <p className="text-xs text-muted-foreground -mt-1">
        Email notifications and caller ID are configured on the <span className="font-medium">Fax Box</span> above
        (Create / Edit).
      </p>
      <ToggleRow label="Store Received Faxes" checked={form.fax_store} onChange={v => setForm(p => ({ ...p, fax_store: v }))} />
    </div>
    )
  }

  return null
}

// ── Table routing cell ─────────────────────────────────────────────────────────

function RoutingCell({ row }) {
  const actions = row.actions || []
  if (actions.length === 0) return <span className="text-muted-foreground text-sm">—</span>
  return (
    <div className="flex flex-wrap items-center gap-1">
      {actions.map((a, i) => {
        const meta = DEST_META[a.dest_type]
        const name = a.dest_label || null
        return (
          <span key={i} className="flex items-center gap-1">
            {i > 0 && <span className="text-muted-foreground text-xs">→</span>}
            <span className={cn('text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded', meta?.color, meta?.bg)}>
              {meta?.label || a.dest_type}
            </span>
            {name && <span className="text-xs text-muted-foreground">{name}</span>}
          </span>
        )
      })}
    </div>
  )
}

// ── Bulk Add DIDs Dialog ────────────────────────────────────────────────────────────────

function normalizePhone(raw) {
  const digits = raw.replace(/\D/g, '')
  if (digits.length === 10) return `+1${digits}`
  if (digits.length === 11 && digits[0] === '1') return `+${digits}`
  return null
}

function BulkAddDIDsDialog({ open, onClose, onDone }) {
  const [text, setText] = useState('')
  const [preview, setPreview] = useState([])
  const [step, setStep] = useState('input')
  const [progress, setProgress] = useState(0)
  const [results, setResults] = useState([])
  const [error, setError] = useState('')

  const reset = () => {
    setText(''); setPreview([]); setStep('input'); setProgress(0); setResults([]); setError('')
  }

  useEffect(() => { if (!open) reset() }, [open])

  const buildPreview = () => {
    setError('')
    const lines = text.split('\n').map(s => s.trim()).filter(Boolean)
    if (!lines.length) { setError('Enter at least one phone number.'); return }
    if (lines.length > 200) { setError('Maximum 200 DIDs per bulk add.'); return }
    const items = lines.map(raw => ({ original: raw, normalized: normalizePhone(raw) }))
    const bad = items.filter(i => !i.normalized)
    if (bad.length) {
      setError(`Cannot normalize (expected 10 or 11 digit US numbers): ${bad.map(b => b.original).slice(0, 4).join(', ')}`)
      return
    }
    setPreview(items)
    setStep('preview')
  }

  const handleCreate = async () => {
    setStep('creating'); setProgress(0)
    const res = []
    for (let i = 0; i < preview.length; i++) {
      const { original, normalized } = preview[i]
      try {
        await api.create({ destination_number: normalized, destination_enabled: true, actions: [] })
        res.push({ original, normalized, status: 'ok' })
      } catch (err) {
        const d = err?.response?.data
        const msg = d?.destination_number?.[0] || d?.message || Object.values(d || {}).flat()[0] || 'Failed'
        res.push({ original, normalized, status: 'error', error: String(msg) })
      }
      setProgress(i + 1)
      setResults([...res])
    }
    setStep('done')
  }

  const ok  = results.filter(r => r.status === 'ok').length
  const bad = results.filter(r => r.status === 'error').length

  return (
    <Dialog open={open} onOpenChange={v => { if (!v) onClose() }}>
      <DialogContent className="w-[95vw] max-w-lg h-[540px] max-h-[90vh] flex flex-col p-0 overflow-hidden">
        <DialogHeader className="px-6 pt-5 pb-4 border-b">
          <DialogTitle className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-primary" /> Bulk Add DIDs
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">

          {step === 'input' && (
            <>
              <div className="space-y-1.5">
                <Label className="text-xs">Phone Numbers — one per line</Label>
                <p className="text-xs text-muted-foreground">Accepts any US format: (346) 571-1216 · 3465711216 · +13465711216</p>
                <textarea
                  className="flex min-h-[160px] w-full rounded-xl border border-input bg-background px-3 py-2 text-sm font-mono placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 transition-all"
                  placeholder={"(346) 571-1216\n(346) 831-0764\n3468310765"}
                  value={text}
                  onChange={e => setText(e.target.value)}
                />
              </div>
              {error && (
                <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />{error}
                </div>
              )}
            </>
          )}

          {step === 'preview' && (
            <>
              <p className="text-sm text-muted-foreground">
                {preview.length} DID{preview.length !== 1 ? 's' : ''} will be added (unrouted — configure routing in the Destinations page after creation).
              </p>
              <div className="rounded-xl border overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="border-b bg-muted/40">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-semibold text-muted-foreground">Original</th>
                      <th className="px-3 py-2 text-left text-xs font-semibold text-muted-foreground">E.164 (stored as)</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {preview.map(({ original, normalized }) => (
                      <tr key={normalized}>
                        <td className="px-3 py-1.5 text-sm text-muted-foreground">{original}</td>
                        <td className="px-3 py-1.5 font-mono font-bold text-blue-500">{normalized}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          {step === 'creating' && (
            <div className="space-y-3">
              <p className="text-sm text-muted-foreground">Creating {progress} / {preview.length}…</p>
              <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
                <div className="h-2 bg-primary transition-all duration-300 rounded-full"
                  style={{ width: `${(progress / preview.length) * 100}%` }} />
              </div>
              <div className="max-h-48 overflow-y-auto space-y-1">
                {results.map(r => (
                  <div key={r.normalized} className={cn('flex items-center gap-2 text-xs px-2 py-1 rounded',
                    r.status === 'ok' ? 'text-emerald-600' : 'text-destructive bg-destructive/5')}>
                    {r.status === 'ok'
                      ? <CheckCircle2 className="h-3 w-3 shrink-0" />
                      : <AlertCircle className="h-3 w-3 shrink-0" />}
                    <span className="font-mono font-bold">{r.normalized}</span>
                    <span>{r.status === 'ok' ? 'Created' : r.error}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {step === 'done' && (
            <div className="space-y-3">
              <div className={cn('flex items-center gap-2 rounded-lg px-4 py-3 text-sm font-medium',
                bad === 0 ? 'bg-emerald-500/10 text-emerald-700 border border-emerald-200' : 'bg-amber-500/10 text-amber-700 border border-amber-200')}>
                <CheckCircle2 className="h-4 w-4" />
                {ok} DID{ok !== 1 ? 's' : ''} added{bad > 0 ? `, ${bad} failed` : ' — all done!'}
              </div>
              {bad > 0 && (
                <div className="max-h-40 overflow-y-auto space-y-1">
                  {results.filter(r => r.status === 'error').map(r => (
                    <div key={r.normalized} className="flex items-start gap-2 text-xs text-destructive">
                      <AlertCircle className="h-3 w-3 shrink-0 mt-0.5" />
                      <span><span className="font-mono font-bold">{r.normalized}</span>: {r.error}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

        </div>

        <div className="flex justify-between gap-2 px-6 py-4 border-t">
          <Button variant="ghost" onClick={() => { onClose(); if (step === 'done') onDone() }}>
            {step === 'done' ? 'Close' : 'Cancel'}
          </Button>
          <div className="flex gap-2">
            {step === 'preview' && <Button variant="outline" onClick={() => setStep('input')}>Back</Button>}
            {step === 'input' && <Button onClick={buildPreview}>Preview →</Button>}
            {step === 'preview' && (
              <Button onClick={handleCreate}>Add {preview.length} DID{preview.length !== 1 ? 's' : ''}</Button>
            )}
            {step === 'done' && ok > 0 && <Button onClick={() => { onClose(); onDone() }}>Done</Button>}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────────


export default function Destinations() {
  const navigate = useNavigate()
  // Route param drives the editor: undefined = list, 'new' = create, else edit by id.
  // We use a route segment (/destinations/new, /destinations/:id/edit) so the
  // editor is a full page with the app sidebar still visible, and browser
  // back / deep-linking work.
  // The `/new` route has no :id param, so detect create from the path and only
  // use the param for edit. editorOpen is true for either editor route.
  const { id: editParamId } = useParams()
  const location = useLocation()
  const isCreate   = location.pathname.endsWith('/destinations/new')
  const routeId    = editParamId
  const editorOpen = isCreate || routeId !== undefined

  const [pageSize, setPageSize]   = useState(DEFAULT_PAGE_SIZE)
  const [search, setSearch]       = useState('')
  const debouncedSearch           = useDebounce(search, 300)
  const [bulkOpen, setBulkOpen]   = useState(false)
  const [editId, setEditId]       = useState(null)
  const [form, setForm]           = useState(EMPTY)
  const [tab, setTab]             = useState('information')
  const [saving, setSaving]       = useState(false)
  const [formError, setFormError] = useState('')
  const [deleting, setDeleting]   = useState(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [affinityOpen, setAffinityOpen] = useState(false)
  const [exporting, setExporting] = useState(false)
  // Inline fax box management (from the DID dialog's Fax tab).
  const [faxBoxDialogOpen, setFaxBoxDialogOpen] = useState(false)
  const [editFaxBox, setEditFaxBox] = useState(null)

  useEffect(() => {
    const h = () => setAffinityOpen(true)
    window.addEventListener('open-affinity', h)
    return () => window.removeEventListener('open-affinity', h)
  }, [])

  const { destData, destLoading, destSearchLoading, loadDestData, searchDestData, reloadFaxBoxes } = useDestinationData({ withConferences: true, withFaxBoxes: true })

  const openNewFaxBox  = () => { setEditFaxBox(null); setFaxBoxDialogOpen(true) }
  const openEditFaxBox = (box) => { if (box) { setEditFaxBox(box); setFaxBoxDialogOpen(true) } }
  const [autoCreatingFax, setAutoCreatingFax] = useState(false)

  // Auto-create a fax box for this DID (no form). Extension = DID number, name =
  // friendly name or the number. Used when Enable Fax Receive is toggled on.
  const autoCreateFaxBox = useCallback(async () => {
    const number = (form.destination_number || '').trim()
    if (!number) { setFormError('Enter the DID number before enabling fax receive.'); setTab('information'); return null }
    setAutoCreatingFax(true)
    try {
      const name = (form.destination_name || '').trim() || number
      const { data } = await faxApi.create({
        fax_name:             name,
        fax_caller_id_name:   name,
        // Default the caller ID number to this DID — it's the number faxes go out on.
        fax_caller_id_number: number,
        fax_extension:        number,
        fax_enabled:          true,
      })
      await reloadFaxBoxes()
      setForm(p => ({ ...p, fax_id: data.fax_uuid, fax_receive: true }))
      toast.success('Fax box created.')
      return data
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : Object.values(d || {}).flat().join(' ') || 'Could not create fax box.')
      return null
    } finally { setAutoCreatingFax(false) }
  }, [form.destination_number, form.destination_name, reloadFaxBoxes])

  // Called when the inline fax box dialog closes. `result` is the saved box
  // object (create/update) or false on cancel. After a create, auto-link the
  // new box to the DID being edited.
  const handleFaxBoxClose = async (result) => {
    setFaxBoxDialogOpen(false)
    if (!result) { setEditFaxBox(null); return }
    await reloadFaxBoxes()
    if (!editFaxBox && result?.fax_uuid) {
      setForm(p => ({ ...p, fax_id: result.fax_uuid }))
    }
    setEditFaxBox(null)
  }

  // Patch just the notification email on a linked fax box (inline edit).
  const updateFaxBoxEmail = useCallback(async (box, email) => {
    try {
      await faxApi.patch(box.fax_uuid, { fax_email: email })
      await reloadFaxBoxes()
      toast.success('Notification email saved.')
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : Object.values(d || {}).flat().join(' ') || 'Could not save email.')
    }
  }, [reloadFaxBoxes])

  const listParams = useMemo(
    () => (debouncedSearch ? { search: debouncedSearch } : {}),
    [debouncedSearch],
  )
  const {
    rows, total, loading, loadingMore, hasMore, loadMore, reload: load,
  } = useInfiniteList(api.list, { params: listParams, pageSize })

  const set = (key) => (e) => setForm(p => ({ ...p, [key]: e.target.value }))

  // Navigate to the full-page editor; the route effect below loads the form.
  const openCreate = () => navigate('/destinations/new')
  const openEdit   = (r) => navigate(`/destinations/${r.destination_uuid}/edit`)
  const closeEditor = () => navigate('/destinations')

  // Sync form state to the current route. Runs whenever the editor route changes.
  useEffect(() => {
    if (!editorOpen) return
    setTab('information'); setFormError('')
    loadDestData()
    if (isCreate) {
      setEditId(null); setForm(EMPTY)
      return
    }
    // Edit: seed from the list row if we have it (instant render), then fetch
    // the full detail. If the row isn't loaded yet, fetch is the only source.
    setEditId(routeId)
    const row = rows.find(r => r.destination_uuid === routeId)
    if (row) setForm(rowToForm(row))
    setDetailLoading(true)
    api.get(routeId)
      .then(({ data }) => setForm(rowToForm(data)))
      .catch(() => { if (!row) { toast.error('DID not found.'); closeEditor() } })
      .finally(() => setDetailLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeId, isCreate])

  const handleSave = async () => {
    if (!form.destination_number.trim()) {
      setFormError('DID / Phone Number is required.'); setTab('information'); return
    }
    setSaving(true); setFormError('')
    try {
      const payload = {
        destination_number:        form.destination_number,
        destination_number_regex:  form.destination_number_regex,
        destination_name:          form.destination_name,
        actions: form.actions.map((a, i) => ({
          dest_type:            a.type,
          dest_target_uuid:     a.target_uuid || null,
          dest_external_number: a.external_number || '',
          order:                i,
        })),
        max_channels:              form.max_channels !== '' ? parseInt(form.max_channels, 10) : null,
        notify_over_limit:         form.notify_over_limit,
        use_cnam_service:          form.use_cnam_service,
        hide_callerid:             form.hide_callerid,
        use_as_emergency_callerid: form.use_as_emergency_callerid,
        inbound_call_rate:         form.inbound_call_rate,
        destination_cid_number_prefix: form.destination_cid_number_prefix,
        destination_cid_name_prefix:   form.destination_cid_name_prefix,
        destination_ringback:      form.destination_ringback,
        destination_hold_music:    form.destination_hold_music,
        destination_accountcode:   form.destination_accountcode,
        destination_enabled:       form.destination_enabled,
        destination_description:   form.destination_description,
        unconditional_forward:     form.unconditional_forward,
        callback_to_last_caller:   form.callback_to_last_caller,
        always_record:             form.always_record,
        email_recording_to:        form.email_recording_to,
        transcript_recorded:       form.transcript_recorded,
        summarize_recorded:        form.summarize_recorded,
        sentiment_analysis:        form.sentiment_analysis,
        fax_id:                    form.fax_id || null,
        fax_receive:               form.fax_receive,
        fax_station_id:            form.fax_station_id,
        fax_header:                form.fax_header,
        fax_protocol:              form.fax_protocol,
        fax_store:                 form.fax_store,
        fax_on_receive:            form.fax_on_receive,
      }
      editId ? await api.update(editId, payload) : await api.create(payload)
      load(); closeEditor()
    } catch (err) {
      const d = err?.response?.data
      if (d && typeof d === 'object') {
        const msgs = Object.entries(d).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`).join(' | ')
        setFormError(msgs || 'Save failed.')
      } else {
        setFormError(typeof d === 'string' ? d : 'Save failed.')
      }
    } finally { setSaving(false) }
  }

  const handleExport = async () => {
    setExporting(true)
    try {
      // Lazy-load the heavy xlsx lib so it stays out of the main bundle.
      const XLSX = await import('xlsx')
      // Page through the API until every row is collected — the backend's default
      // pagination caps page_size at 25 and ignores larger values, so we must loop.
      const list = []
      let pageNum = 1
      for (;;) {
        const params = { page: pageNum, page_size: 100 }
        if (debouncedSearch) params.search = debouncedSearch
        const { data } = await api.list(params)
        if (Array.isArray(data)) { list.push(...data); break }
        list.push(...(data.results || []))
        if (!data.next) break
        pageNum += 1
      }
      const routingString = (actions) => (actions || [])
        .map(a => {
          const label = DEST_META[a.dest_type]?.label || a.dest_type || ''
          return a.dest_label ? `${label}: ${a.dest_label}` : label
        })
        .filter(Boolean)
        .join(' → ')
      const sheetRows = list.map(r => ({
        Number:      r.destination_number || '',
        Name:        r.destination_name || '',
        Routing:     routingString(r.actions),
        Status:      r.destination_enabled !== false ? 'Active' : 'Disabled',
        Description: r.destination_description || '',
      }))
      const ws = XLSX.utils.json_to_sheet(sheetRows)
      const wb = XLSX.utils.book_new()
      XLSX.utils.book_append_sheet(wb, ws, 'DIDs')
      XLSX.writeFile(wb, `dids-${new Date().toISOString().slice(0, 10)}.xlsx`)
    } finally {
      setExporting(false)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this DID?')) return
    setDeleting(id)
    try { await api.delete(id); load() } finally { setDeleting(null) }
  }

  // ── Full-page editor (routed) ──────────────────────────────────────────────
  // Rendered in place of the list when on /destinations/new or /:id/edit. The
  // app sidebar stays visible because it lives in AppLayout, outside this page.
  if (editorOpen) {
    const tabIndex = TABS.findIndex(t => t.id === tab)
    return (
      <div className="space-y-4">
        {/* Header with breadcrumb-style back */}
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={closeEditor} className="-ml-2">
            <X className="h-4 w-4 mr-1" />Destinations
          </Button>
          <span className="text-muted-foreground">/</span>
          <h1 className="text-lg font-semibold">{isCreate ? 'Define DID' : 'Edit DID'}</h1>
          {detailLoading && <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />}
        </div>

        <Card>
          {/* Tab bar */}
          <div className="flex items-center gap-1 px-4 pt-3 border-b border-border/60">
            {TABS.map(t => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={cn(
                  'px-4 py-2 text-sm font-medium rounded-t-lg border-b-2 transition-all duration-150',
                  tab === t.id
                    ? 'border-primary text-primary bg-primary/5'
                    : 'border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/50',
                )}
              >
                {t.label}
              </button>
            ))}
          </div>

          {/* Body */}
          <CardContent className="px-6 py-5 space-y-1">
            {formError && (
              <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-2.5 text-sm text-destructive mb-3">
                {formError}
              </div>
            )}
            <DIDFormBody
              tab={tab} form={form} set={set} setForm={setForm}
              destData={destData} destLoading={destLoading}
              destSearchLoading={destSearchLoading} onSearch={searchDestData}
              onNewFaxBox={openNewFaxBox} onEditFaxBox={openEditFaxBox}
              onAutoCreateFaxBox={autoCreateFaxBox} autoCreatingFax={autoCreatingFax}
              onUpdateFaxBoxEmail={updateFaxBoxEmail}
            />
          </CardContent>

          {/* Footer */}
          <div className="flex items-center justify-between px-6 py-4 border-t border-border/60 bg-muted/30">
            <span className="text-xs text-muted-foreground">
              Step {tabIndex + 1} of {TABS.length}
            </span>
            <div className="flex gap-2">
              <Button variant="outline" onClick={closeEditor}>Cancel</Button>
              {tabIndex > 0 && (
                <Button variant="outline" onClick={() => setTab(TABS[tabIndex - 1].id)}>← Back</Button>
              )}
              {tabIndex < TABS.length - 1 ? (
                <Button onClick={() => setTab(TABS[tabIndex + 1].id)}>Next →</Button>
              ) : (
                <Button onClick={handleSave} disabled={saving}>
                  {saving && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
                  {isCreate ? 'Create DID' : 'Save Changes'}
                </Button>
              )}
            </div>
          </div>
        </Card>

        {/* Inline fax box create/edit, opened from the DID editor's Fax tab */}
        <FaxBoxFormDialog
          open={faxBoxDialogOpen}
          editBox={editFaxBox}
          didNumber={form.destination_number}
          dids={rows}
          onClose={handleFaxBoxClose}
        />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* toolbar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Search DIDs…" className="pl-8" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <PageSizeSelector value={pageSize} onChange={setPageSize} />
        <Button variant="outline" size="sm" onClick={() => setBulkOpen(true)}>
          <Layers className="h-4 w-4 mr-1" />Bulk Add
        </Button>
        <Button variant="outline" size="sm" onClick={handleExport} disabled={exporting} title="Export DIDs to Excel">
          {exporting ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : <Download className="h-4 w-4 mr-1" />}
          {exporting ? 'Exporting…' : 'Export'}
        </Button>
        <Button size="sm" onClick={openCreate}><Plus className="h-4 w-4 mr-1" />Define DID</Button>
      </div>

      <BulkAddDIDsDialog
        open={bulkOpen}
        onClose={() => setBulkOpen(false)}
        onDone={() => { setBulkOpen(false); load() }}
      />

      <AffinityPanel open={affinityOpen} onClose={() => setAffinityOpen(false)} />

      {/* table */}
      <Card><CardContent className="p-0 overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Number</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Routing</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="w-20" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {loading
              ? [...Array(4)].map((_, i) => (
                  <TableRow key={i}>
                    {[...Array(5)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}
                  </TableRow>
                ))
              : rows.length === 0
                ? <TableRow><TableCell colSpan={5} className="text-center py-10 text-muted-foreground">No DIDs defined.</TableCell></TableRow>
                : rows.map((r) => (
                    <TableRow key={r.destination_uuid}>
                      <TableCell className="font-mono font-medium">{r.destination_number}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">{r.destination_name || '—'}</TableCell>
                      <TableCell><RoutingCell row={r} /></TableCell>
                      <TableCell>
                        <Badge variant={r.destination_enabled !== false ? 'success' : 'secondary'}>
                          {r.destination_enabled !== false ? 'Active' : 'Disabled'}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(r)}>
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive"
                            onClick={() => handleDelete(r.destination_uuid)}
                            disabled={deleting === r.destination_uuid}
                          >
                            {deleting === r.destination_uuid
                              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              : <Trash2 className="h-3.5 w-3.5" />}
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
            }
          </TableBody>
        </Table>
        {!loading && rows.length > 0 && (
          <InfiniteScroll
            hasMore={hasMore}
            loadingMore={loadingMore}
            onLoadMore={loadMore}
            loaded={rows.length}
            total={total}
          />
        )}
      </CardContent></Card>

    </div>
  )
}
