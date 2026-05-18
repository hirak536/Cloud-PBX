import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback, useRef } from 'react'
import { useSelector } from 'react-redux'
import { selectLive, selectTenant } from '@/store'
import { extensions as extensionsApi, voicemails as voicemailsApi, gateways as gatewaysApi, ringGroups as ringGroupsApi, destinations as destinationsApi, freeswitchCache } from '@/api'
import DestinationPicker, { EMPTY_DEST } from '@/components/DestinationPicker'
import { useDestinationData } from '@/hooks/useDestinationData'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Select } from '@/components/ui/select'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogClose } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import {
  Plus, Pencil, Trash2, Search, RefreshCw, Loader2,
  RotateCcw, AlertCircle, CheckCircle2, ChevronDown, Check, Copy, Layers,
} from 'lucide-react'

// ── Constants ─────────────────────────────────────────────────────────────────

const CODEC_OPTIONS = [
  { value: 'OPUS',    label: 'OPUS',    desc: 'Wideband' },
  { value: 'PCMU',    label: 'PCMU',    desc: 'G.711 u-law' },
  { value: 'PCMA',    label: 'PCMA',    desc: 'G.711 a-law' },
  { value: 'G722',    label: 'G.722',   desc: 'HD Voice' },
  { value: 'G726-32', label: 'G.726',   desc: '32k ADPCM' },
  { value: 'GSM',     label: 'GSM',     desc: '' },
  { value: 'H264',    label: 'H.264',   desc: 'Video' },
  { value: 'VP8',     label: 'VP8',     desc: 'Video' },
]
const DEFAULT_CODECS = 'OPUS,PCMU,PCMA'

const TABS = [
  { id: 'general',       label: 'General' },
  { id: 'configuration', label: 'Configuration' },
  { id: 'voicemail',     label: 'Voicemail' },
  { id: 'outbound',      label: 'Outbound' },
  { id: 'forwarding',    label: 'Forwarding' },
]

const EMPTY_FORM = {
  // General
  extension: '',
  effective_caller_id_name: '',
  description: '',
  password: '',
  // Directory
  directory_full_name: '',
  directory_visible: true,
  directory_exten_visible: true,
  // Configuration
  codec_preference: DEFAULT_CODECS,
  absolute_codec_string: '',
  sip_bypass_media: '',
  call_group: '',
  ring_group_ids: [],
  hold_music: '',
  language: '',
  call_screen_enabled: false,
  user_record: '',
  // Recording
  call_recording: 'inherit',
  // Voicemail
  reject_to_voicemail: false,
  voicemail_enabled: true,
  voicemail_id: '',
  voicemail_password: '',
  voicemail_mail_to: '',
  voicemail_file: 'attach',
  voicemail_local_after_email: true,
  mwi_account: '',
  // Outbound
  outbound_did: '',
  outbound_caller_id_number: '',
  outbound_caller_id_name: '',
  outbound_route: '',
  // Forwarding
  call_forward_active: false,
  forward_all_enabled: false,
  forward_all_destination: '',
  forward_no_answer_enabled: false,
  forward_no_answer_destination: '',
  forward_busy_enabled: false,
  forward_busy_destination: '',
  forward_user_not_registered_enabled: false,
  forward_user_not_registered_destination: '',
  forward_on_condition_enabled: false,
  forward_on_condition: '',
  forward_on_condition_destination: '',
  enabled: true,
}

// ── Utility ───────────────────────────────────────────────────────────────────

function generatePassword() {
  const u = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'
  const l = 'abcdefghijklmnopqrstuvwxyz'
  const d = '0123456789'
  const all = u + l + d
  const pwd = [
    u[Math.floor(Math.random() * u.length)],
    l[Math.floor(Math.random() * l.length)],
    d[Math.floor(Math.random() * d.length)],
    ...Array.from({ length: 13 }, () => all[Math.floor(Math.random() * all.length)]),
  ]
  for (let i = pwd.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [pwd[i], pwd[j]] = [pwd[j], pwd[i]]
  }
  return pwd.join('')
}


// ── Primitives ────────────────────────────────────────────────────────────────

function Field({ label, required, hint, span2, children }) {
  return (
    <div className={cn('space-y-1.5', span2 && 'col-span-2')}>
      <Label className="text-xs">
        {label}
        {required && <span className="text-destructive ml-0.5">*</span>}
      </Label>
      {children}
      {hint && <p className="text-[11px] text-muted-foreground leading-tight">{hint}</p>}
    </div>
  )
}

function Toggle({ checked, onChange, disabled }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => !disabled && onChange(!checked)}
      className={cn(
        'relative inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent transition-colors focus-visible:outline-none',
        checked ? 'bg-primary' : 'bg-input',
        disabled && 'opacity-40 cursor-not-allowed',
      )}
    >
      <span className={cn(
        'pointer-events-none block h-4 w-4 rounded-full bg-white shadow-lg transition-transform',
        checked ? 'translate-x-4' : 'translate-x-0',
      )} />
    </button>
  )
}

function TabBar({ tabs, active, onChange }) {
  return (
    <div className="flex border-b shrink-0 overflow-x-auto scrollbar-none">
      {tabs.map(t => (
        <button
          key={t.id}
          type="button"
          onClick={() => onChange(t.id)}
          className={cn(
            'px-4 py-2.5 text-xs font-medium whitespace-nowrap border-b-2 transition-colors',
            active === t.id
              ? 'border-primary text-primary'
              : 'border-transparent text-muted-foreground hover:text-foreground hover:border-muted-foreground/30',
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  )
}

function SectionTitle({ children }) {
  return (
    <div className="col-span-2 pb-1 border-b">
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">{children}</p>
    </div>
  )
}

// ── Codec picker ──────────────────────────────────────────────────────────────

function CodecPicker({ value, onChange, bypassMedia, bypassMediaWebrtc }) {
  // Any UDP bypass or proxy mode forces PCMU — FS cannot transcode when out of the media path.
  const udpBypassed = bypassMedia === 'true' || bypassMedia === 'proxy'
  const selected = udpBypassed ? ['PCMU'] : (value ? value.split(',').filter(Boolean) : [])

  const toggle = (codec) => {
    if (udpBypassed) return
    const next = selected.includes(codec)
      ? selected.filter(c => c !== codec)
      : [...selected, codec]
    onChange(next.join(','))
  }

  return (
    <div className="space-y-2">
      {udpBypassed && (
        <p className="text-xs text-amber-600 dark:text-amber-400">
          PCMU forced — codec selection is locked while UDP bypass or proxy media is enabled.
        </p>
      )}
      <div className="grid grid-cols-5 gap-1.5">
        {CODEC_OPTIONS.map(c => {
          const active = selected.includes(c.value)
          const disabled = udpBypassed && c.value !== 'PCMU'
          return (
            <button
              key={c.value}
              type="button"
              onClick={() => toggle(c.value)}
              disabled={disabled}
              title={c.desc || c.label}
              className={cn(
                'flex flex-col items-center gap-0.5 rounded-md border px-2 py-1.5 text-[11px] font-medium transition-colors',
                disabled
                  ? 'border-input bg-muted text-muted-foreground/40 cursor-not-allowed opacity-40'
                  : active
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-input bg-background text-muted-foreground hover:border-primary/40 hover:text-foreground',
              )}
            >
              <span>{c.label}</span>
              {c.desc && (
                <span className={cn('text-[10px] font-normal truncate w-full text-center', active ? 'text-primary/70' : 'text-muted-foreground/60')}>
                  {c.desc}
                </span>
              )}
            </button>
          )
        })}
      </div>
      {selected.length > 0 && (
        <p className="text-[11px] text-muted-foreground">
          Priority order: <span className="font-mono">{selected.join(', ')}</span>
        </p>
      )}
    </div>
  )
}

// ── MultiSelect ───────────────────────────────────────────────────────────────

function MultiSelect({ options, selected, onChange, loading, placeholder }) {
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  const toggle = (value) => {
    onChange(selected.includes(value)
      ? selected.filter(v => v !== value)
      : [...selected, value])
  }

  const selectedLabels = options.filter(o => selected.includes(o.value)).map(o => o.label)

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="flex h-9 w-full items-center justify-between rounded-xl border border-input bg-background px-3 py-2 text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
      >
        <span className={cn('truncate text-left', selectedLabels.length === 0 && 'text-muted-foreground')}>
          {loading ? 'Loading…' : selectedLabels.length > 0 ? selectedLabels.join(', ') : (placeholder || 'Select…')}
        </span>
        <ChevronDown className="h-4 w-4 shrink-0 opacity-50 ml-2" />
      </button>
      {open && (
        <div className="absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-xl border border-border/60 bg-card shadow-2xl shadow-black/10 animate-dropdown-in">
          {loading ? (
            <div className="px-3 py-2 text-sm text-muted-foreground">Loading…</div>
          ) : options.length === 0 ? (
            <div className="px-3 py-2 text-sm text-muted-foreground">No ring groups available</div>
          ) : (
            options.map(opt => (
              <div
                key={opt.value}
                className="flex items-center gap-2 px-3 py-2 text-sm hover:bg-accent cursor-pointer"
                onClick={() => toggle(opt.value)}
              >
                <div className={cn(
                  'h-4 w-4 rounded border flex items-center justify-center shrink-0',
                  selected.includes(opt.value) ? 'bg-primary border-primary' : 'border-input',
                )}>
                  {selected.includes(opt.value) && <Check className="h-3 w-3 text-primary-foreground" />}
                </div>
                <span className="flex-1">{opt.label}</span>
                {opt.sub && <span className="text-xs text-muted-foreground">{opt.sub}</span>}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}

// ── Forwarding helpers ────────────────────────────────────────────────────────

function destToString(dest, destData) {
  if (!dest?.type) return ''
  const { type, target_uuid, external_number } = dest
  if (type === 'number') return external_number || ''
  if (type === 'hangup') return 'hangup'
  if (type === 'extension') {
    const e = (destData.extensions || []).find(x => x.extension_uuid === target_uuid)
    return e?.extension || ''
  }
  if (type === 'voicemail') {
    const v = (destData.voicemails || []).find(x => (x.voicemail_uuid || x.id) === target_uuid)
    return v?.voicemail_id ? `voicemail:${v.voicemail_id}` : ''
  }
  if (type === 'ivr_menu') {
    const i = (destData.ivr_menus || []).find(x => x.ivr_menu_uuid === target_uuid)
    return i?.ivr_menu_extension || ''
  }
  if (type === 'ring_group') {
    const r = (destData.ring_groups || []).find(x => x.ring_group_uuid === target_uuid)
    return r?.ring_group_extension || ''
  }
  if (type === 'working_hours') {
    const wh = (destData.working_hours || []).find(x => x.working_hours_uuid === target_uuid)
    return wh?.dialplan_extension || ''
  }
  if (type === 'custom_destination') {
    const cd = (destData.custom_destinations || []).find(x => x.custom_destination_uuid === target_uuid)
    return cd?.dialplan_extension || ''
  }
  return ''
}

function stringToDest(str, destData) {
  if (!str) return EMPTY_DEST
  if (str.startsWith('voicemail:')) {
    const vmId = str.slice('voicemail:'.length)
    const vm = (destData.voicemails || []).find(v => v.voicemail_id === vmId)
    return { type: 'voicemail', target_uuid: vm ? (vm.voicemail_uuid || vm.id) : '', external_number: vmId }
  }
  const ext = (destData.extensions || []).find(e => e.extension === str)
  if (ext) return { type: 'extension', target_uuid: ext.extension_uuid, external_number: '' }
  const vm = (destData.voicemails || []).find(v => v.voicemail_id === str)
  if (vm) return { type: 'voicemail', target_uuid: vm.voicemail_uuid || vm.id, external_number: '' }
  const ivr = (destData.ivr_menus || []).find(i => i.ivr_menu_extension === str)
  if (ivr) return { type: 'ivr_menu', target_uuid: ivr.ivr_menu_uuid, external_number: '' }
  const rg = (destData.ring_groups || []).find(r => r.ring_group_extension === str)
  if (rg) return { type: 'ring_group', target_uuid: rg.ring_group_uuid, external_number: '' }
  const wh = (destData.working_hours || []).find(w => w.dialplan_extension === str)
  if (wh) return { type: 'working_hours', target_uuid: wh.working_hours_uuid, external_number: '' }
  return { type: 'number', target_uuid: '', external_number: str }
}

// ── Forwarding row ────────────────────────────────────────────────────────────

function ForwardRow({ label, enabled, onToggle, destination, onDestChange, disabled, destData, destLoading, extensionNumber }) {
  const destValue   = stringToDest(destination, destData)
  const handleChange = (dest) => onDestChange(destToString(dest, destData))
  const isVoicemailSelf = extensionNumber && destination === `voicemail:${extensionNumber}`
  return (
    <div className="grid grid-cols-[160px_1fr] gap-3 items-center px-3 py-2.5">
      <div className="flex items-center gap-2">
        <Toggle checked={enabled} onChange={onToggle} disabled={disabled} />
        <span className="text-xs text-muted-foreground">{label}</span>
      </div>
      <div className={cn('flex items-center gap-2', disabled || !enabled ? 'pointer-events-none opacity-40' : '')}>
        <div className="flex-1">
          <DestinationPicker
            value={destValue}
            onChange={handleChange}
            data={destData}
            loading={destLoading}
            compact
            placeholder="Select destination…"
          />
        </div>
        {extensionNumber && (
          <button
            type="button"
            title="Set to voicemail of this extension"
            onClick={() => onDestChange(`voicemail:${extensionNumber}`)}
            className={cn(
              'shrink-0 text-xs px-2 py-1 rounded border transition-colors',
              isVoicemailSelf
                ? 'bg-primary text-primary-foreground border-primary'
                : 'border-border text-muted-foreground hover:text-foreground hover:border-foreground'
            )}
          >
            Voicemail
          </button>
        )}
      </div>
    </div>
  )
}

// ── Form body (tabbed) ────────────────────────────────────────────────────────

function ExtensionFormBody({ form, setForm, editId, currentTenant, formError, ringGroupList, rgLoading, activeTab, setActiveTab }) {
  const { destData, destLoading, loadDestData } = useDestinationData()

  useEffect(() => {
    if (activeTab === 'forwarding' || activeTab === 'configuration') loadDestData()
  }, [activeTab, loadDestData])
  const [extStatus, setExtStatus] = useState(null)
  const [extConflict, setExtConflict] = useState('')
  const [extTouched, setExtTouched] = useState(false)
  const [voicemailBoxes, setVoicemailBoxes] = useState([])
  const [vmLoading, setVmLoading] = useState(false)
  const [gatewayList, setGatewayList] = useState([])
  const [gwLoading, setGwLoading] = useState(false)
  const [didList, setDidList] = useState([])
  const [didLoading, setDidLoading] = useState(false)

  const debouncedExt = useDebounce(form.extension, 600)

  // Reset touched flag when the dialog switches between create/edit modes
  useEffect(() => { setExtTouched(false); setExtStatus(null) }, [editId])

  // Live duplicate check — only runs after the field has been manually changed
  useEffect(() => {
    if (!extTouched) return
    const val = debouncedExt.trim()
    if (!val || !/^\d{3,5}$/.test(val)) { setExtStatus(null); return }
    setExtStatus('checking')
    extensionsApi.checkNumber(val, editId || undefined)
      .then(({ data }) => {
        setExtStatus(data.available ? 'ok' : 'taken')
        setExtConflict(data.conflicts?.[0] || '')
      })
      .catch(() => setExtStatus(null))
  }, [debouncedExt, editId, extTouched])

  // Fetch voicemail boxes when voicemail tab opens
  useEffect(() => {
    if (activeTab !== 'voicemail' || voicemailBoxes.length > 0) return
    setVmLoading(true)
    voicemailsApi.list({ page_size: 200 })
      .then(({ data }) => {
        const list = Array.isArray(data) ? data : data.results || []
        setVoicemailBoxes(list)
      })
      .catch(() => {})
      .finally(() => setVmLoading(false))
  }, [activeTab, voicemailBoxes.length])

  // Find the voicemail box for the current extension (by voicemail_id, or extension number).
  const matchedVoicemailBox = (() => {
    const mailboxKey = form.voicemail_id || form.extension
    if (!mailboxKey) return null
    return voicemailBoxes.find(vm => vm.voicemail_id === mailboxKey) || null
  })()

  // When the matched box is found, mirror its email + PIN into the form.
  // Edits on these fields flow to both sides on save.
  useEffect(() => {
    if (!matchedVoicemailBox) return
    const boxEmail = matchedVoicemailBox.voicemail_mail_to || ''
    const boxPin = matchedVoicemailBox.voicemail_password || ''
    setForm(f => ({
      ...f,
      voicemail_mail_to: f.voicemail_mail_to === boxEmail ? f.voicemail_mail_to : boxEmail,
      voicemail_password: f.voicemail_password === boxPin ? f.voicemail_password : boxPin,
    }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [matchedVoicemailBox?.voicemail_uuid])

  // Fetch gateways and DIDs when outbound tab opens
  useEffect(() => {
    if (activeTab !== 'outbound') return
    if (gatewayList.length === 0) {
      setGwLoading(true)
      gatewaysApi.list({ page_size: 200 })
        .then(({ data }) => {
          const list = Array.isArray(data) ? data : data.results || []
          setGatewayList(list)
          if (!editId && list.length > 0) {
            setForm(f => {
              if (f.outbound_route) return f
              // Prefer tenant default gateway, fall back to first in list
              const defaultUuid = currentTenant?.default_gateway
              const match = defaultUuid
                ? list.find(gw => (gw.gateway_uuid || gw.id) === defaultUuid)
                : null
              const selected = match ?? list[0]
              return { ...f, outbound_route: selected.gateway_uuid || selected.id }
            })
          }
        })
        .catch(() => {})
        .finally(() => setGwLoading(false))
    }
    if (didList.length === 0) {
      setDidLoading(true)
      destinationsApi.list({ page_size: 200, destination_enabled: true })
        .then(({ data }) => {
          const list = Array.isArray(data) ? data : data.results || []
          setDidList(list)
          // Auto-select first DID when creating a new extension and none chosen yet
          if (!editId && list.length > 0) {
            const first = list[0]
            const uuid = first.destination_uuid || first.id
            setForm(f => f.outbound_did ? f : {
              ...f,
              outbound_did: uuid,
              outbound_caller_id_number: first.destination_number || f.outbound_caller_id_number,
              outbound_caller_id_name: first.destination_name || first.destination_number || f.outbound_caller_id_name,
            })
          }
        })
        .catch(() => {})
        .finally(() => setDidLoading(false))
    }
  }, [activeTab, gatewayList.length, didList.length])

  const set = (key) => (e) => setForm(f => ({ ...f, [key]: e?.target ? e.target.value : e }))
  const setToggle = (key) => (val) => setForm(f => ({ ...f, [key]: val }))

  const sipUsername = form.extension && currentTenant?.tenant_code
    ? `${form.extension}-${currentTenant.tenant_code}`
    : form.extension || ''

  const extHint = () => {
    const v = form.extension
    if (!v) return null
    if (!/^\d+$/.test(v))  return { msg: 'Digits only', type: 'error' }
    if (v.length < 3)      return { msg: 'Minimum 3 digits', type: 'error' }
    if (v.length > 5)      return { msg: 'Maximum 5 digits', type: 'error' }
    if (extStatus === 'checking') return { msg: 'Checking availability…', type: 'info' }
    if (extStatus === 'taken')    return { msg: extConflict || 'Already in use on this tenant', type: 'error' }
    if (extStatus === 'ok')       return { msg: 'Available', type: 'ok' }
    return null
  }
  const hint = extHint()

  return (
    <div className="flex flex-col h-full">
      <TabBar tabs={TABS} active={activeTab} onChange={setActiveTab} />

      <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
        {formError && (
          <div className="flex items-start gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <span>{formError}</span>
          </div>
        )}

        {/* ── General ── */}
        {activeTab === 'general' && (
          <div className="grid grid-cols-2 gap-x-4 gap-y-4">

            <SectionTitle>Credentials</SectionTitle>

            <Field label="Extension Number" required>
              <div className="relative">
                <Input
                  placeholder="e.g. 1001"
                  value={form.extension}
                  maxLength={5}
                  onChange={e => { setExtTouched(true); set('extension')(e) }}
                  className={cn(
                    'pr-8',
                    hint?.type === 'error' && 'border-destructive focus-visible:ring-destructive',
                    hint?.type === 'ok'    && 'border-emerald-500 focus-visible:ring-emerald-500',
                  )}
                />
                <div className="absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none">
                  {hint?.type === 'info'  && <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />}
                  {hint?.type === 'error' && <AlertCircle className="h-3.5 w-3.5 text-destructive" />}
                  {hint?.type === 'ok'    && <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />}
                </div>
              </div>
              {hint && (
                <p className={cn('text-[11px]',
                  hint.type === 'error' && 'text-destructive',
                  hint.type === 'ok'    && 'text-emerald-600',
                  hint.type === 'info'  && 'text-muted-foreground',
                )}>{hint.msg}</p>
              )}
            </Field>

            <Field label="Extension Name" hint="Display name shown in caller ID and listings">
              <Input placeholder="e.g. John Doe" value={form.effective_caller_id_name} onChange={set('effective_caller_id_name')} />
            </Field>

            <Field label="SIP Username" hint="Auto-generated · read-only">
              <Input value={sipUsername} readOnly className="bg-muted/50 text-muted-foreground font-mono text-xs" />
            </Field>

            <Field label="SIP Password" required>
              <div className="flex gap-1.5">
                <Input
                  type="text"
                  placeholder="Password"
                  value={form.password}
                  onChange={set('password')}
                  className="font-mono text-xs"
                />
                <Button
                  type="button" variant="outline" size="icon" className="shrink-0"
                  title="Regenerate password"
                  onClick={() => setForm(f => ({ ...f, password: generatePassword() }))}
                >
                  <RotateCcw className="h-3.5 w-3.5" />
                </Button>
              </div>
              <p className="text-[11px] text-muted-foreground">
                Auto-generated 16-char password. Click <RotateCcw className="inline h-2.5 w-2.5" /> to regenerate or type your own.
              </p>
            </Field>

            <Field label="Description" span2>
              <Input placeholder="Optional description" value={form.description} onChange={set('description')} />
            </Field>

            {/* Directory section — commented out
            <SectionTitle>Directory</SectionTitle>

            <Field label="Directory Full Name" hint="Name shown in the company directory">
              <Input placeholder="e.g. John Doe" value={form.directory_full_name} onChange={set('directory_full_name')} />
            </Field>

            <Field label="Visible in Directory">
              <div className="flex h-9 items-center gap-3">
                <Toggle checked={form.directory_visible} onChange={setToggle('directory_visible')} />
                <span className="text-sm text-muted-foreground">{form.directory_visible ? 'Yes' : 'No'}</span>
              </div>
            </Field>

            <Field label="Extension Visible in Directory">
              <div className="flex h-9 items-center gap-3">
                <Toggle checked={form.directory_exten_visible} onChange={setToggle('directory_exten_visible')} />
                <span className="text-sm text-muted-foreground">{form.directory_exten_visible ? 'Yes' : 'No'}</span>
              </div>
            </Field>
            */}

          </div>
        )}

        {/* ── Configuration ── */}
        {activeTab === 'configuration' && (
          <div className="grid grid-cols-2 gap-x-4 gap-y-4">

            <SectionTitle>Media</SectionTitle>

            <Field
              label="Codecs"
              span2
            >
              <CodecPicker
                value={form.codec_preference}
                onChange={(v) => setForm(f => ({ ...f, codec_preference: v }))}
                bypassMedia={form.sip_bypass_media}
              />
            </Field>

            <Field label="Direct Media" span2 hint="Forces PCMU codec when enabled">
              <Select
                value={form.sip_bypass_media}
                onChange={e => {
                  const val = e.target.value
                  setForm(f => ({
                    ...f,
                    sip_bypass_media: val,
                    codec_preference: (val === 'true' || val === 'proxy') ? 'PCMU' : f.codec_preference,
                  }))
                }}
              >
                <option value="">Disabled — FreeSWITCH in RTP path</option>
                <option value="true">Bypass Media — direct RTP between endpoints</option>
                <option value="proxy">Proxy Media — FS forwards only, no processing</option>
              </Select>
            </Field>

            <SectionTitle>Routing</SectionTitle>

            <Field label="Call Group" hint="Ring groups this extension is a member of" span2>
              <MultiSelect
                options={ringGroupList.map(rg => ({
                  value: rg.ring_group_uuid || rg.id,
                  label: rg.ring_group_name,
                  sub: rg.ring_group_extension ? `ext ${rg.ring_group_extension}` : undefined,
                }))}
                selected={form.ring_group_ids}
                onChange={(ids) => setForm(f => ({ ...f, ring_group_ids: ids }))}
                loading={rgLoading}
                placeholder="Select ring groups…"
              />
            </Field>

            <SectionTitle>Behaviour</SectionTitle>

            <Field label="User Record">
              <Select value={form.user_record} onChange={set('user_record')}>
                <option value="">Disabled</option>
                <option value="all">All calls</option>
                <option value="local">Local only</option>
                <option value="outbound">Outbound only</option>
                <option value="inbound">Inbound only</option>
              </Select>
            </Field>

            <Field label="Call Screen">
              <div className="flex h-9 items-center gap-3">
                <Toggle checked={form.call_screen_enabled} onChange={setToggle('call_screen_enabled')} />
                <span className="text-sm text-muted-foreground">{form.call_screen_enabled ? 'Enabled' : 'Disabled'}</span>
              </div>
            </Field>

            <Field label="Decline Follows Forwarding Rules" hint="When any registered device declines the call, immediately apply busy/no-answer forwarding rules instead of waiting for timeout.">
              <div className="flex h-9 items-center gap-3">
                <Toggle
                  checked={form.reject_to_voicemail}
                  onChange={setToggle('reject_to_voicemail')}
                />
                <span className="text-sm text-muted-foreground">
                  {form.reject_to_voicemail ? 'Enabled' : 'Disabled'}
                </span>
              </div>
            </Field>

          </div>
        )}

        {/* ── Voicemail ── */}
        {activeTab === 'voicemail' && (
          <div className="grid grid-cols-2 gap-x-4 gap-y-4">

            <SectionTitle>Call Recording</SectionTitle>

            <Field label="Call Recording" span2 hint="Override the tenant-level recording setting for this extension.">
              <Select value={form.call_recording} onChange={set('call_recording')}>
                <option value="inherit">Inherit from tenant</option>
                <option value="enabled">Always record</option>
                <option value="disabled">Never record</option>
              </Select>
            </Field>

            <SectionTitle>Voicemail Box</SectionTitle>

            {/* Enable + MWI on the same row */}
            <Field label="Voicemail">
              <div className="flex h-9 items-center gap-3">
                <Toggle checked={form.voicemail_enabled} onChange={setToggle('voicemail_enabled')} />
                <span className="text-sm text-muted-foreground">
                  {form.voicemail_enabled ? 'Enabled' : 'Disabled'}
                </span>
              </div>
            </Field>

            <Field label="MWI Account (Message Waiting Indicator)" hint="Which voicemail box lights the MWI lamp">
              {vmLoading ? (
                <div className="flex h-9 items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading voicemail boxes…
                </div>
              ) : (
                <Select
                  value={form.mwi_account}
                  onChange={set('mwi_account')}
                  disabled={!form.voicemail_enabled}
                >
                  <option value="">Same as extension number (default)</option>
                  {voicemailBoxes.map(vm => (
                    <option key={vm.voicemail_uuid || vm.id} value={vm.voicemail_id}>
                      {vm.voicemail_id}
                      {vm.voicemail_id === form.extension ? ' (this extension)' : ''}
                      {vm.description ? ` — ${vm.description}` : ''}
                    </option>
                  ))}
                </Select>
              )}
            </Field>

            <Field label="Voicemail Mailbox ID" hint="Leave blank to use extension number">
              <Input
                placeholder={form.extension || 'e.g. 1001'}
                value={form.voicemail_id}
                onChange={set('voicemail_id')}
                disabled={!form.voicemail_enabled}
              />
            </Field>

            <Field
              label="Voicemail PIN"
              hint={matchedVoicemailBox
                ? `Linked to voicemail box ${matchedVoicemailBox.voicemail_id} — changes save to both`
                : '4-digit PIN to access voicemail'}
            >
              <Input
                type="text"
                placeholder="Auto-generated on create"
                value={form.voicemail_password}
                onChange={set('voicemail_password')}
                disabled={!form.voicemail_enabled}
                className="font-mono"
              />
            </Field>

            <Field
              label="Email for Voicemail"
              hint={matchedVoicemailBox
                ? `Linked to voicemail box ${matchedVoicemailBox.voicemail_id} — changes save to both`
                : 'Send voicemail notifications to this address'}
              span2
            >
              <Input
                type="email"
                placeholder="e.g. user@example.com"
                value={form.voicemail_mail_to}
                onChange={set('voicemail_mail_to')}
                disabled={!form.voicemail_enabled}
              />
            </Field>

            <Field label="Voicemail File Delivery">
              <Select value={form.voicemail_file} onChange={set('voicemail_file')} disabled={!form.voicemail_enabled}>
                <option value="attach">Attach — send audio file in email</option>
                <option value="link">Link — send download link</option>
                <option value="none">None — email notification only</option>
              </Select>
            </Field>

            <Field label="Keep VM after Email">
              <div className="flex h-9 items-center gap-3">
                <Toggle
                  checked={form.voicemail_local_after_email}
                  onChange={setToggle('voicemail_local_after_email')}
                  disabled={!form.voicemail_enabled}
                />
                <span className="text-sm text-muted-foreground">
                  {form.voicemail_local_after_email ? 'Keep' : 'Delete after email'}
                </span>
              </div>
            </Field>

          </div>
        )}

        {/* ── Outbound ── */}
        {activeTab === 'outbound' && (
          <div className="grid grid-cols-2 gap-x-4 gap-y-4">

            <SectionTitle>Routing</SectionTitle>

            <Field label="Default Outbound Gateway" hint="SIP trunk used for outbound calls from this extension" span2>
              {gwLoading ? (
                <div className="flex h-9 items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading gateways…
                </div>
              ) : (
                <Select value={form.outbound_route} onChange={set('outbound_route')}>
                  <option value="">Use dialplan routing (default)</option>
                  {gatewayList.map(gw => (
                    <option key={gw.gateway_uuid || gw.id} value={gw.gateway_uuid || gw.id}>
                      {gw.gateway} {gw.description ? `— ${gw.description}` : ''}
                    </option>
                  ))}
                </Select>
              )}
            </Field>

            <SectionTitle>Caller Identity</SectionTitle>

            <Field label="Outbound Caller ID (DID)" hint="Select a DID to associate with this extension" span2>
              {didLoading ? (
                <div className="flex h-9 items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading DIDs…
                </div>
              ) : (
                <Select
                  value={form.outbound_did}
                  onChange={e => {
                    const uuid = e.target.value
                    const did = didList.find(d => (d.destination_uuid || d.id) === uuid)
                    setForm(f => ({
                      ...f,
                      outbound_did: uuid,
                      outbound_caller_id_number: did ? did.destination_number : f.outbound_caller_id_number,
                      outbound_caller_id_name: did ? (did.destination_name || did.destination_number) : f.outbound_caller_id_name,
                    }))
                  }}
                >
                  <option value="">— None (use manual fields below) —</option>
                  {didList.map(d => (
                    <option key={d.destination_uuid || d.id} value={d.destination_uuid || d.id}>
                      {d.destination_number}{d.destination_name ? ` — ${d.destination_name}` : ''}
                    </option>
                  ))}
                </Select>
              )}
            </Field>

            <SectionTitle>Caller ID</SectionTitle>

            <Field
              label="External Caller ID Number"
              hint={form.outbound_did ? 'Set by selected DID' : ''}
            >
              <Input
                placeholder="e.g. +18005551234"
                value={form.outbound_caller_id_number}
                onChange={set('outbound_caller_id_number')}
                readOnly={!!form.outbound_did}
                className={form.outbound_did ? 'bg-muted text-muted-foreground' : ''}
              />
            </Field>

            <Field
              label="External Caller ID Name"
              hint={form.outbound_did ? 'Set by selected DID' : ''}
            >
              <Input
                placeholder="e.g. Company Name"
                value={form.outbound_caller_id_name}
                onChange={set('outbound_caller_id_name')}
                readOnly={!!form.outbound_did}
                className={form.outbound_did ? 'bg-muted text-muted-foreground' : ''}
              />
            </Field>

          </div>
        )}

        {/* ── Forwarding ── */}
        {activeTab === 'forwarding' && (
          <div className="space-y-4">

            <div className="flex items-center gap-3">
              <Toggle checked={form.call_forward_active} onChange={setToggle('call_forward_active')} />
              <span className="text-sm">
                {form.call_forward_active
                  ? 'Active — forwarding rules below are applied'
                  : 'Inactive — enable to configure forwarding rules'}
              </span>
            </div>

            <div className={cn('rounded-lg border divide-y transition-opacity', !form.call_forward_active && 'opacity-50')}>
              <ForwardRow
                label="Unconditional"
                enabled={form.forward_all_enabled}
                onToggle={setToggle('forward_all_enabled')}
                destination={form.forward_all_destination}
                onDestChange={(v) => setForm(f => ({ ...f, forward_all_destination: v }))}
                disabled={!form.call_forward_active}
                destData={destData} destLoading={destLoading}
                extensionNumber={form.extension}
              />
              <ForwardRow
                label="On No Answer"
                enabled={form.forward_no_answer_enabled}
                onToggle={setToggle('forward_no_answer_enabled')}
                destination={form.forward_no_answer_destination}
                onDestChange={(v) => setForm(f => ({ ...f, forward_no_answer_destination: v }))}
                disabled={!form.call_forward_active}
                destData={destData} destLoading={destLoading}
                extensionNumber={form.extension}
              />
              <ForwardRow
                label="On Busy"
                enabled={form.forward_busy_enabled}
                onToggle={setToggle('forward_busy_enabled')}
                destination={form.forward_busy_destination}
                onDestChange={(v) => setForm(f => ({ ...f, forward_busy_destination: v }))}
                disabled={!form.call_forward_active}
                destData={destData} destLoading={destLoading}
                extensionNumber={form.extension}
              />
              <ForwardRow
                label="Not Registered"
                enabled={form.forward_user_not_registered_enabled}
                onToggle={setToggle('forward_user_not_registered_enabled')}
                destination={form.forward_user_not_registered_destination}
                onDestChange={(v) => setForm(f => ({ ...f, forward_user_not_registered_destination: v }))}
                disabled={!form.call_forward_active}
                destData={destData} destLoading={destLoading}
                extensionNumber={form.extension}
              />
              <div className={cn('px-3 py-2.5', !form.call_forward_active && 'pointer-events-none')}>
                <div className="flex items-center gap-2 mb-2">
                  <Toggle
                    checked={form.forward_on_condition_enabled}
                    onChange={setToggle('forward_on_condition_enabled')}
                    disabled={!form.call_forward_active}
                  />
                  <span className="text-xs text-muted-foreground">On Condition</span>
                </div>
                {form.forward_on_condition_enabled && (
                  <div className="grid grid-cols-2 gap-2 pl-11">
                    <Input
                      placeholder="Condition (e.g. ${caller_id_number} == 1234)"
                      value={form.forward_on_condition}
                      onChange={(e) => setForm(f => ({ ...f, forward_on_condition: e.target.value }))}
                      className="h-8 text-xs"
                      disabled={!form.call_forward_active}
                    />
                    <div className={cn(!form.call_forward_active ? 'pointer-events-none opacity-40' : '')}>
                      <DestinationPicker
                        value={stringToDest(form.forward_on_condition_destination, destData)}
                        onChange={(d) => setForm(f => ({ ...f, forward_on_condition_destination: destToString(d, destData) }))}
                        data={destData}
                        loading={destLoading}
                        compact
                        placeholder="Select destination…"
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>

          </div>
        )}

      </div>
    </div>
  )
}

// ── Bulk Add Extensions Dialog ───────────────────────────────────────────────

function BulkAddExtensionsDialog({ open, onClose, onDone, currentTenant }) {
  const [mode, setMode] = useState('range')
  const [rangeStart, setRangeStart] = useState('')
  const [rangeEnd, setRangeEnd] = useState('')
  const [listText, setListText] = useState('')
  const [preview, setPreview] = useState([])
  const [step, setStep] = useState('input')
  const [progress, setProgress] = useState(0)
  const [results, setResults] = useState([])
  const [error, setError] = useState('')

  const reset = () => {
    setMode('range'); setRangeStart(''); setRangeEnd(''); setListText('')
    setPreview([]); setStep('input'); setProgress(0); setResults([]); setError('')
  }

  useEffect(() => { if (!open) reset() }, [open])

  const buildPreview = () => {
    setError('')
    let exts = []
    if (mode === 'range') {
      const s = parseInt(rangeStart, 10), e = parseInt(rangeEnd, 10)
      if (!s || !e || isNaN(s) || isNaN(e)) { setError('Enter valid start and end extension numbers.'); return }
      if (s > e) { setError('Start must be ≤ end.'); return }
      if (e - s > 99) { setError('Maximum 100 extensions per bulk add.'); return }
      for (let i = s; i <= e; i++) exts.push(String(i))
    } else {
      exts = listText.split(/[\n,]/).map(s => s.trim()).filter(Boolean)
      if (!exts.length) { setError('Enter at least one extension number.'); return }
      if (exts.length > 100) { setError('Maximum 100 extensions per bulk add.'); return }
      const bad = exts.filter(e => !/^\d{3,5}$/.test(e))
      if (bad.length) { setError(`Invalid (must be 3–5 digits): ${bad.slice(0, 5).join(', ')}`); return }
    }
    setPreview(exts.map(ext => ({ ext, password: generatePassword() })))
    setStep('preview')
  }

  const handleCreate = async () => {
    setStep('creating'); setProgress(0)
    const res = []
    for (let i = 0; i < preview.length; i++) {
      const { ext, password } = preview[i]
      try {
        await extensionsApi.create({
          extension: ext, password,
          effective_caller_id_name: '', description: '',
          codec_preference: DEFAULT_CODECS,
          voicemail_enabled: true, voicemail_file: 'attach',
          voicemail_local_after_email: true,
          enabled: true,
        })
        res.push({ ext, status: 'ok' })
      } catch (err) {
        const d = err?.response?.data
        const msg = (d?.extension?.[0] || d?.message || Object.values(d || {}).flat()[0] || 'Failed')
        res.push({ ext, status: 'error', error: String(msg) })
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
      <DialogContent className="w-[95vw] max-w-lg max-h-[90vh] flex flex-col p-0 overflow-hidden">
        <DialogHeader className="px-6 pt-5 pb-4 border-b">
          <DialogTitle className="flex items-center gap-2">
            <Layers className="h-4 w-4 text-primary" /> Bulk Add Extensions
          </DialogTitle>
        </DialogHeader>

        <div className="flex-1 overflow-y-auto px-6 py-5 space-y-4">

          {step === 'input' && (
            <>
              {/* Mode selector */}
              <div className="flex gap-2">
                {['range', 'list'].map(m => (
                  <button key={m} type="button"
                    onClick={() => setMode(m)}
                    className={cn('flex-1 rounded-lg border py-2 text-sm font-medium transition-colors',
                      mode === m ? 'border-primary bg-primary/10 text-primary' : 'border-input text-muted-foreground hover:border-primary/40')
                    }>
                    {m === 'range' ? 'Range (e.g. 1001–1010)' : 'Custom List'}
                  </button>
                ))}
              </div>

              {mode === 'range' ? (
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label className="text-xs">Start Extension</Label>
                    <Input placeholder="1001" value={rangeStart} onChange={e => setRangeStart(e.target.value)} />
                  </div>
                  <div className="space-y-1.5">
                    <Label className="text-xs">End Extension</Label>
                    <Input placeholder="1010" value={rangeEnd} onChange={e => setRangeEnd(e.target.value)} />
                  </div>
                </div>
              ) : (
                <div className="space-y-1.5">
                  <Label className="text-xs">Extension Numbers (one per line or comma-separated)</Label>
                  <textarea
                    className="flex min-h-[120px] w-full rounded-xl border border-input bg-background px-3 py-2 text-sm font-mono placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 transition-all"
                    placeholder={"1001\n1002\n1003"}
                    value={listText}
                    onChange={e => setListText(e.target.value)}
                  />
                </div>
              )}

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
                {preview.length} extension{preview.length !== 1 ? 's' : ''} will be created with auto-generated passwords. You can edit individual extensions after creation.
              </p>
              <div className="rounded-xl border overflow-hidden">
                <table className="w-full text-sm">
                  <thead className="border-b bg-muted/40">
                    <tr>
                      <th className="px-3 py-2 text-left text-xs font-semibold text-muted-foreground">Extension</th>
                      <th className="px-3 py-2 text-left text-xs font-semibold text-muted-foreground">SIP Username</th>
                      <th className="px-3 py-2 text-left text-xs font-semibold text-muted-foreground">Password</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y max-h-64 overflow-y-auto">
                    {preview.map(({ ext, password }) => (
                      <tr key={ext}>
                        <td className="px-3 py-1.5 font-mono font-bold text-blue-500">{ext}</td>
                        <td className="px-3 py-1.5 font-mono text-xs text-muted-foreground">
                          {ext}{currentTenant?.tenant_code ? `-${currentTenant.tenant_code}` : ''}
                        </td>
                        <td className="px-3 py-1.5 font-mono text-xs">{password}</td>
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
                <div
                  className="h-2 bg-primary transition-all duration-300 rounded-full"
                  style={{ width: `${(progress / preview.length) * 100}%` }}
                />
              </div>
              <div className="max-h-48 overflow-y-auto space-y-1">
                {results.map(r => (
                  <div key={r.ext} className={cn('flex items-center gap-2 text-xs px-2 py-1 rounded',
                    r.status === 'ok' ? 'text-emerald-600' : 'text-destructive bg-destructive/5')}>
                    {r.status === 'ok'
                      ? <CheckCircle2 className="h-3 w-3 shrink-0" />
                      : <AlertCircle className="h-3 w-3 shrink-0" />}
                    <span className="font-mono font-bold w-12">{r.ext}</span>
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
                {ok} created{bad > 0 ? `, ${bad} failed` : ' — all done!'}
              </div>
              {bad > 0 && (
                <div className="max-h-40 overflow-y-auto space-y-1">
                  {results.filter(r => r.status === 'error').map(r => (
                    <div key={r.ext} className="flex items-start gap-2 text-xs text-destructive">
                      <AlertCircle className="h-3 w-3 shrink-0 mt-0.5" />
                      <span><span className="font-mono font-bold">{r.ext}</span>: {r.error}</span>
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
            {step === 'preview' && (
              <Button variant="outline" onClick={() => setStep('input')}>Back</Button>
            )}
            {step === 'input' && (
              <Button onClick={buildPreview}>Preview →</Button>
            )}
            {step === 'preview' && (
              <Button onClick={handleCreate}>
                Create {preview.length} Extension{preview.length !== 1 ? 's' : ''}
              </Button>
            )}
            {step === 'done' && ok > 0 && (
              <Button onClick={() => { onClose(); onDone() }}>Done</Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}

// ── Status badge ──────────────────────────────────────────────────────────────

const STATUS_CONFIG = {
  online:   { label: 'Online',   dot: 'bg-green-500',  text: 'text-green-700 dark:text-green-400',  bg: 'bg-green-50 dark:bg-green-950/40',  border: 'border-green-200 dark:border-green-800' },
  offline:  { label: 'Offline',  dot: 'bg-slate-400',  text: 'text-slate-600 dark:text-slate-400',  bg: 'bg-slate-50 dark:bg-slate-900/40',  border: 'border-slate-200 dark:border-slate-700' },
  ringing:  { label: 'Ringing',  dot: 'bg-amber-400',  text: 'text-amber-700 dark:text-amber-400',  bg: 'bg-amber-50 dark:bg-amber-950/40',  border: 'border-amber-200 dark:border-amber-800' },
  in_use:   { label: 'In Use',   dot: 'bg-blue-500',   text: 'text-blue-700 dark:text-blue-400',   bg: 'bg-blue-50 dark:bg-blue-950/40',   border: 'border-blue-200 dark:border-blue-800' },
}

function ExtStatusBadge({ enabled, status }) {
  if (!enabled) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/40 px-2.5 py-0.5 text-xs font-medium text-slate-500 dark:text-slate-400">
        <span className="h-1.5 w-1.5 rounded-full bg-slate-400" />
        Disabled
      </span>
    )
  }
  const cfg = STATUS_CONFIG[status]
  if (!cfg) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/40 px-2.5 py-0.5 text-xs font-medium text-slate-400">
        <span className="h-1.5 w-1.5 rounded-full bg-slate-300 animate-pulse" />
        Connecting…
      </span>
    )
  }
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border ${cfg.border} ${cfg.bg} px-2.5 py-0.5 text-xs font-medium ${cfg.text}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot} ${status === 'ringing' ? 'animate-pulse' : ''}`} />
      {cfg.label}
    </span>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

const PAGE_SIZE = 20

export default function Extensions() {
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [deleting, setDeleting] = useState(null)
  const [copiedId, setCopiedId] = useState(null)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [bulkOpen, setBulkOpen] = useState(false)
  const [editId, setEditId] = useState(null)
  const [form, setForm] = useState(EMPTY_FORM)
  const [formError, setFormError] = useState('')
  const [flushing, setFlushing] = useState(false)
  const [activeTab, setActiveTab] = useState('general')
  const [ringGroupList, setRingGroupList] = useState([])
  const [rgLoading, setRgLoading] = useState(false)
  const { extStatuses, extSnapshotReceived } = useSelector(selectLive)
  const ringGroupsRef = useRef([])
  const originalRingGroupIdsRef = useRef([])

  const { currentTenant } = useSelector(selectTenant)

  const loadRingGroups = useCallback(async () => {
    if (ringGroupsRef.current.length > 0) return ringGroupsRef.current
    setRgLoading(true)
    try {
      const { data } = await ringGroupsApi.list({ page_size: 500 })
      const list = Array.isArray(data) ? data : data.results || []
      ringGroupsRef.current = list
      setRingGroupList(list)
      return list
    } catch { return [] }
    finally { setRgLoading(false) }
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { page, page_size: PAGE_SIZE }
      if (search) params.search = search
      const { data } = await extensionsApi.list(params)
      const list = Array.isArray(data) ? data : data.results || []
      setRows(list)
      setTotal(Array.isArray(data) ? list.length : data.count || 0)
    } finally {
      setLoading(false)
    }
  }, [page, search])

  useEffect(() => { load() }, [load])

  const openCreate = () => {
    setEditId(null)
    originalRingGroupIdsRef.current = []
    setForm({
      ...EMPTY_FORM,
      password: generatePassword(),
    })
    setFormError('')
    setActiveTab('general')
    setDialogOpen(true)
    loadRingGroups()
  }

  const rowToForm = (d) => ({
    ...EMPTY_FORM,
    extension:                               d.extension || '',
    effective_caller_id_name:                d.effective_caller_id_name || '',
    description:                             d.description || '',
    password:                                d.password || '',
    directory_full_name:                     d.directory_full_name || '',
    directory_visible:                       d.directory_visible !== false,
    directory_exten_visible:                 d.directory_exten_visible !== false,
    sip_bypass_media:                        d.sip_bypass_media || '',
    codec_preference:                        (d.sip_bypass_media === 'true' || d.sip_bypass_media === 'proxy') ? 'PCMU' : (d.codec_preference || DEFAULT_CODECS),
    absolute_codec_string:                   d.absolute_codec_string || '',
    call_group:                              d.call_group || '',
    hold_music:                              d.hold_music || '',
    language:                                d.language || '',
    call_screen_enabled:                     d.call_screen_enabled || false,
    user_record:                             d.user_record || '',
    call_recording:                          d.call_recording || 'inherit',
    reject_to_voicemail:                     d.reject_to_voicemail || false,
    voicemail_enabled:                       d.voicemail_enabled !== false,
    voicemail_id:                            d.voicemail_id || '',
    voicemail_password:                      d.voicemail_password || '',
    voicemail_mail_to:                       d.voicemail_mail_to || '',
    voicemail_file:                          d.voicemail_file || 'attach',
    voicemail_local_after_email:             d.voicemail_local_after_email !== false,
    mwi_account:                             d.mwi_account || '',
    outbound_did:                            d.outbound_did || '',
    outbound_caller_id_number:               d.outbound_caller_id_number || '',
    outbound_caller_id_name:                 d.outbound_caller_id_name || '',
    outbound_route:                          d.outbound_route || '',
    call_forward_active:                     d.call_forward_active || false,
    forward_all_enabled:                     d.forward_all_enabled || false,
    forward_all_destination:                 d.forward_all_destination || '',
    forward_no_answer_enabled:               d.forward_no_answer_enabled || false,
    forward_no_answer_destination:           d.forward_no_answer_destination || '',
    forward_busy_enabled:                    d.forward_busy_enabled || false,
    forward_busy_destination:                d.forward_busy_destination || '',
    forward_user_not_registered_enabled:     d.forward_user_not_registered_enabled || false,
    forward_user_not_registered_destination: d.forward_user_not_registered_destination || '',
    forward_on_condition_enabled:            d.forward_on_condition_enabled || false,
    forward_on_condition:                    d.forward_on_condition || '',
    forward_on_condition_destination:        d.forward_on_condition_destination || '',
    enabled:                                 d.enabled !== false,
  })

  const openEdit = async (row) => {
    const id = row.extension_uuid || row.id
    setEditId(id)
    setFormError('')
    setActiveTab('general')
    setDialogOpen(true)
    setForm({ ...EMPTY_FORM })
    try {
      const [extResult, rgs] = await Promise.all([
        extensionsApi.get(id),
        loadRingGroups(),
      ])
      const data = extResult.data
      const memberOf = rgs
        .filter(rg => (rg.destinations || []).some(d => d.destination_number === data.extension))
        .map(rg => rg.ring_group_uuid || rg.id)
      originalRingGroupIdsRef.current = memberOf
      setForm({ ...rowToForm(data), ring_group_ids: memberOf })
    } catch {
      setFormError('Failed to load extension details.')
    }
  }

  const handleSave = async () => {
    const ext = form.extension.trim()
    if (!ext) { setFormError('Extension number is required.'); return }
    if (!/^\d{3,5}$/.test(ext)) { setFormError('Extension must be 3–5 digits.'); return }
    if (!form.password) { setFormError('Password is required.'); return }

    setSaving(true)
    setFormError('')
    try {
      const payload = {
        // General
        extension:                               form.extension,
        effective_caller_id_name:                form.effective_caller_id_name,
        description:                             form.description,
        password:                                form.password,
        // Directory
        directory_full_name:                     form.directory_full_name,
        directory_visible:                       form.directory_visible,
        directory_exten_visible:                 form.directory_exten_visible,
        // Configuration
        sip_bypass_media:                        form.sip_bypass_media,
        codec_preference:                        (form.sip_bypass_media === 'true' || form.sip_bypass_media === 'proxy') ? 'PCMU' : form.codec_preference,
        absolute_codec_string:                   form.absolute_codec_string,
        call_group:                              form.call_group,
        hold_music:                              form.hold_music,
        language:                                form.language,
        call_screen_enabled:                     form.call_screen_enabled,
        user_record:                             form.user_record,
        // Recording
        call_recording:                          form.call_recording,
        // Voicemail
        voicemail_enabled:                       form.voicemail_enabled,
        voicemail_id:                            form.voicemail_id,
        voicemail_password:                      form.voicemail_password,
        voicemail_mail_to:                       form.voicemail_mail_to,
        voicemail_file:                          form.voicemail_file,
        voicemail_local_after_email:             form.voicemail_local_after_email,
        mwi_account:                             form.mwi_account,
        // Outbound
        outbound_did:                            form.outbound_did || null,
        outbound_caller_id_number:               form.outbound_caller_id_number,
        outbound_caller_id_name:                 form.outbound_caller_id_name,
        outbound_route:                          form.outbound_route || null,
        reject_to_voicemail:                     form.reject_to_voicemail,
        // Forwarding
        call_forward_active:                     form.call_forward_active,
        forward_all_enabled:                     form.forward_all_enabled,
        forward_all_destination:                 form.forward_all_destination,
        forward_no_answer_enabled:               form.forward_no_answer_enabled,
        forward_no_answer_destination:           form.forward_no_answer_destination,
        forward_busy_enabled:                    form.forward_busy_enabled,
        forward_busy_destination:                form.forward_busy_destination,
        forward_user_not_registered_enabled:     form.forward_user_not_registered_enabled,
        forward_user_not_registered_destination: form.forward_user_not_registered_destination,
        forward_on_condition_enabled:            form.forward_on_condition_enabled,
        forward_on_condition:                    form.forward_on_condition,
        forward_on_condition_destination:        form.forward_on_condition_destination,
        enabled:                                 form.enabled,
      }
      if (editId) {
        await extensionsApi.update(editId, payload)
      } else {
        await extensionsApi.create(payload)
      }

      // Sync email + PIN to the linked voicemail box so the two stay in lockstep.
      if (matchedVoicemailBox) {
        const emailChanged = (matchedVoicemailBox.voicemail_mail_to || '') !== (form.voicemail_mail_to || '')
        const pinChanged   = (matchedVoicemailBox.voicemail_password || '') !== (form.voicemail_password || '')
        if (emailChanged || pinChanged) {
          try {
            await voicemailsApi.update(
              matchedVoicemailBox.voicemail_uuid || matchedVoicemailBox.id,
              {
                ...matchedVoicemailBox,
                voicemail_mail_to: form.voicemail_mail_to || '',
                voicemail_password: form.voicemail_password || '',
              },
            )
          } catch (e) { console.error('Failed to sync voicemail box', e) }
        }
      }

      // Sync ring group memberships
      const extNum = form.extension
      const addedRgs = form.ring_group_ids.filter(id => !originalRingGroupIdsRef.current.includes(id))
      const removedRgs = originalRingGroupIdsRef.current.filter(id => !form.ring_group_ids.includes(id))
      for (const rgId of addedRgs) {
        try {
          const { data: rg } = await ringGroupsApi.get(rgId)
          const destinations = rg.destinations || []
          if (!destinations.some(d => d.destination_number === extNum)) {
            await ringGroupsApi.update(rgId, {
              ...rg,
              destinations: [...destinations, { destination_number: extNum, destination_delay: 0, destination_timeout: 30 }],
            })
          }
        } catch (e) { console.error('Failed to add extension to ring group', rgId, e) }
      }
      for (const rgId of removedRgs) {
        try {
          const { data: rg } = await ringGroupsApi.get(rgId)
          const destinations = (rg.destinations || []).filter(d => d.destination_number !== extNum)
          await ringGroupsApi.update(rgId, { ...rg, destinations })
        } catch (e) { console.error('Failed to remove extension from ring group', rgId, e) }
      }
      originalRingGroupIdsRef.current = form.ring_group_ids

      setDialogOpen(false)
      load()
    } catch (err) {
      const data = err?.response?.data
      setFormError(
        typeof data === 'string'
          ? data
          : data?.message || Object.values(data?.errors || data || {}).flat().join(' ') || 'Failed to save.'
      )
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this extension?')) return
    setDeleting(id)
    try { await extensionsApi.delete(id); load() }
    finally { setDeleting(null) }
  }

  const handleCopyPassword = (row) => {
    if (!row.password) return
    navigator.clipboard.writeText(row.password)
    setCopiedId(row.extension_uuid || row.id)
    setTimeout(() => setCopiedId(null), 1500)
  }

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="space-y-4">

      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search extensions…"
            className="pl-8"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1) }}
          />
        </div>
        <Button variant="outline" size="sm" onClick={() => extensionsApi.reload()} title="Reload FreeSWITCH XML">
          <RefreshCw className="h-4 w-4" />
        </Button>
        <Button variant="outline" size="sm" disabled={flushing} title="Flush dialplan/directory cache then reload FreeSWITCH"
          onClick={async () => {
            setFlushing(true)
            try { await freeswitchCache.flush(); await extensionsApi.reload() } catch { /* ignore */ }
            finally { setFlushing(false) }
          }}>
          {flushing ? <RefreshCw className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4 text-amber-500" />}
          Flush Cache
        </Button>
        <Button variant="outline" size="sm" onClick={() => setBulkOpen(true)}>
          <Layers className="h-4 w-4" />
          Bulk Add
        </Button>
        <Button size="sm" onClick={openCreate}>
          <Plus className="h-4 w-4" />
          Add Extension
        </Button>
      </div>

      <BulkAddExtensionsDialog
        open={bulkOpen}
        onClose={() => setBulkOpen(false)}
        onDone={() => { setBulkOpen(false); load() }}
        currentTenant={currentTenant}
      />

      {/* Table */}
      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Extension</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>SIP Username</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-20" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                [...Array(6)].map((_, i) => (
                  <TableRow key={i}>
                    {[...Array(6)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}
                  </TableRow>
                ))
              ) : rows.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center py-10 text-muted-foreground">No extensions found.</TableCell>
                </TableRow>
              ) : (
                rows.map((row) => {
                  const id = row.extension_uuid || row.id
                  return (
                    <TableRow key={id}>
                      <TableCell className="font-mono font-semibold">{row.extension}</TableCell>
                      <TableCell>{row.effective_caller_id_name || '—'}</TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">{row.sip_username || row.extension}</TableCell>
                      <TableCell className="text-muted-foreground text-sm">{row.description || '—'}</TableCell>
                      <TableCell>
                        <ExtStatusBadge
                          enabled={row.enabled !== false}
                          status={extSnapshotReceived ? (extStatuses[row.extension] || 'offline') : extStatuses[row.extension]}
                        />
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Button
                            variant="ghost" size="icon"
                            className="h-7 w-7 text-muted-foreground hover:text-foreground"
                            title="Copy password"
                            onClick={() => handleCopyPassword(row)}
                          >
                            {copiedId === id ? <Check className="h-3.5 w-3.5 text-green-500" /> : <Copy className="h-3.5 w-3.5" />}
                          </Button>
                          <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(row)}>
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost" size="icon"
                            className="h-7 w-7 text-destructive hover:text-destructive"
                            onClick={() => handleDelete(id)}
                            disabled={deleting === id}
                          >
                            {deleting === id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-muted-foreground">
          <span>{total} total</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Previous</Button>
            <span className="flex items-center px-2">{page} / {totalPages}</span>
            <Button variant="outline" size="sm" disabled={page === totalPages} onClick={() => setPage(p => p + 1)}>Next</Button>
          </div>
        </div>
      )}

      {/* Add / Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="w-[95vw] max-w-3xl h-[90vh] sm:h-[82vh] flex flex-col p-0 gap-0">

          <DialogHeader className="px-6 py-4 border-b mb-0 shrink-0">
            <DialogTitle>{editId ? 'Edit Extension' : 'New Extension'}</DialogTitle>
            <DialogClose onClose={() => setDialogOpen(false)} />
          </DialogHeader>

          {/* TabBar + scrollable content together */}
          <div className="flex-1 overflow-hidden flex flex-col">
            <ExtensionFormBody
              form={form}
              setForm={setForm}
              editId={editId}
              currentTenant={currentTenant}
              formError={formError}
              ringGroupList={ringGroupList}
              rgLoading={rgLoading}
              activeTab={activeTab}
              setActiveTab={setActiveTab}
            />
          </div>

          <div className="shrink-0 border-t px-6 py-3 flex items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <Toggle checked={form.enabled} onChange={(v) => setForm(f => ({ ...f, enabled: v }))} />
              <span className="text-sm text-muted-foreground">
                {form.enabled ? 'Extension enabled' : 'Extension disabled'}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-xs text-muted-foreground">
                Step {TABS.findIndex(t => t.id === activeTab) + 1} of {TABS.length}
              </span>
              <div className="flex gap-2">
                <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
                {TABS.findIndex(t => t.id === activeTab) > 0 && (
                  <Button variant="outline" onClick={() => setActiveTab(TABS[TABS.findIndex(t => t.id === activeTab) - 1].id)}>
                    ← Back
                  </Button>
                )}
                {TABS.findIndex(t => t.id === activeTab) < TABS.length - 1 ? (
                  <Button onClick={() => setActiveTab(TABS[TABS.findIndex(t => t.id === activeTab) + 1].id)}>
                    Next →
                  </Button>
                ) : (
                  <Button onClick={handleSave} disabled={saving}>
                    {saving && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
                    {editId ? 'Save Changes' : 'Create Extension'}
                  </Button>
                )}
              </div>
            </div>
          </div>

        </DialogContent>
      </Dialog>
    </div>
  )
}
