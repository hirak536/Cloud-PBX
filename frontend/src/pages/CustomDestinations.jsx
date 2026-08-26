import { useDebounce } from '@/hooks/useDebounce'
import { useInfiniteList } from '@/hooks/useInfiniteList'
import { InfiniteScroll, PageSizeSelector, DEFAULT_PAGE_SIZE } from '@/components/InfiniteScroll'
import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { customDestinations as api } from '@/api'
import { useDestinationData } from '@/hooks/useDestinationData'
import { useSelector } from 'react-redux'
import { selectTenant } from '@/store'
import DestinationPicker from '@/components/DestinationPicker'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Select } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { cn } from '@/lib/utils'
import {
  Plus, Pencil, Trash2, Search, Loader2, X, ChevronDown,
  PhoneForwarded, PhoneOff, History, Users, Sparkles, ToggleRight, RefreshCw,
} from 'lucide-react'

const DEST_META = {
  extension:     { label: 'Extension',     color: 'text-blue-500',   bg: 'bg-blue-500/10'   },
  ivr_menu:      { label: 'IVR Menu',      color: 'text-amber-500',  bg: 'bg-amber-500/10'  },
  ring_group:    { label: 'Ring Group',    color: 'text-green-600',  bg: 'bg-green-600/10'  },
  voicemail:     { label: 'Voicemail',     color: 'text-purple-500', bg: 'bg-purple-500/10' },
  conference:    { label: 'Conference',    color: 'text-sky-500',    bg: 'bg-sky-500/10'    },
  working_hours: { label: 'Working Hours', color: 'text-teal-500',   bg: 'bg-teal-500/10'   },
  time_condition:{ label: 'Time Cond.',    color: 'text-indigo-500', bg: 'bg-indigo-500/10' },
  call_flow:     { label: 'Call Flow',     color: 'text-pink-500',   bg: 'bg-pink-500/10'   },
  call_forward:  { label: 'Forward',       color: 'text-cyan-500',   bg: 'bg-cyan-500/10'   },
  external:           { label: 'External',           color: 'text-slate-500',  bg: 'bg-slate-500/10'   },
  fax:                { label: 'Fax',                color: 'text-orange-500', bg: 'bg-orange-500/10'  },
  hangup:             { label: 'Hangup',             color: 'text-red-500',    bg: 'bg-red-500/10'     },
  custom_destination: { label: 'Custom Destination', color: 'text-fuchsia-500',bg: 'bg-fuchsia-500/10' },
}

const EMPTY = {
  name: '',
  description: '',
  kind: 'simple',
  dest_type: '',
  dest_target_uuid: '',
  dest_external_number: '',
  callback_to_last_caller: false,
  enabled: true,
  // toggle kind
  toggle_extension: '',
  toggle_feature_code: '',
  toggle_default_on: true,
  toggle_state: true,
  toggle_on_dest: '',
  toggle_off_dest: '',
  // ON/OFF route as a full destination (any type), same as the ext route dropdown.
  toggle_on_type: '',
  toggle_on_target_uuid: '',
  toggle_on_external: '',
  toggle_off_type: '',
  toggle_off_target_uuid: '',
  toggle_off_external: '',
}

// ── Kind registry ────────────────────────────────────────────────────────────
// Each kind owns: label, short description, the body it renders inside the
// dialog, and how it derives back-compat flags before save. To add a new kind:
//   1. Add KIND_CHOICES entry in backend models.py
//   2. Add an entry here with renderBody + onSavePrep
const KIND_REGISTRY = {
  simple: {
    label: 'Simple Destination',
    icon: PhoneForwarded,
    description: 'Route directly to a target (extension, IVR, ring group, etc.).',
    renderBody: ({ form, setForm, destData, destLoading, destSearchLoading, searchDestData }) => (
      <Field label="Destination *" hint="Where calls using this preset go.">
        <TargetPicker
          value={form}
          onChange={(v) => setForm(p => ({ ...p, ...v }))}
          data={destData}
          loading={destLoading}
          searchLoading={destSearchLoading}
          onSearch={searchDestData}
        />
      </Field>
    ),
    onSavePrep: (form) => ({ ...form, callback_to_last_caller: false }),
  },

  sticky_last_agent: {
    label: 'Route to Last Agent',
    icon: Sparkles,
    description: 'If the caller has been dialed before, send them to that same extension. Falls back to the destination below when no match exists.',
    renderBody: ({ form, setForm, destData, destLoading, destSearchLoading, searchDestData, openAffinity }) => (
      <>
        <Field label="Fallback Destination *" hint="Used when no sticky agent is found for the caller.">
          <TargetPicker
            value={form}
            onChange={(v) => setForm(p => ({ ...p, ...v }))}
            data={destData}
            loading={destLoading}
            searchLoading={destSearchLoading}
            onSearch={searchDestData}
          />
        </Field>
        <div className="flex items-start gap-2 text-xs text-amber-700 rounded-lg border border-amber-200 bg-amber-500/5 px-3 py-2">
          <Sparkles className="h-3.5 w-3.5 shrink-0 mt-0.5" />
          <span>
            Affinity updates automatically whenever an extension makes an outbound call to a customer.{' '}
            <button type="button" onClick={openAffinity} className="underline font-medium">View current mappings</button>.
          </span>
        </div>
      </>
    ),
    onSavePrep: (form) => ({ ...form, callback_to_last_caller: true }),
  },

  toggle: {
    label: 'Toggle (BLF switch)',
    icon: ToggleRight,
    description: 'A BLF switch with its own dialable number. Subscribe a phone BLF key to the number: GREEN = ON (routes to the ON destination), RED = OFF (routes to the OFF destination). Pressing the key flips it.',
    renderBody: ({ form, setForm, destData, destLoading, destSearchLoading, searchDestData, editId, currentTenant }) => {
      const inUse = blfNumberConflict(form.toggle_extension, destData, editId)
      const tc = currentTenant?.tenant_code
      // Dialable form FreeSWITCH matches inside the tenant context (e.g. 801-DEMO),
      // mirroring how extensions are dialed. Subscribe the phone's BLF key to the
      // bare number; the lamp follows presence at <number>@domain.
      const dialForm = (n) => (n && tc ? `${n}-${tc}` : n || '')
      return (
      <>
        <div className="grid grid-cols-2 gap-3">
          <Field label="BLF Number *" hint='Dialable number for the BLF key, e.g. "801".'>
            <Input
              placeholder="801"
              value={form.toggle_extension}
              onChange={e => setForm(p => ({ ...p, toggle_extension: e.target.value }))}
              className={cn(inUse && 'border-amber-500 focus-visible:ring-amber-500')}
            />
            {inUse && (
              <p className="mt-1 text-xs text-amber-600">
                Already in use by {inUse.kind} “{inUse.label}”. Pick a different number.
              </p>
            )}
            {form.toggle_extension && tc && (
              <p className="mt-1 text-xs text-muted-foreground">
                Dials as <span className="font-mono text-foreground">{dialForm(form.toggle_extension)}</span> in this tenant.
                Subscribe the BLF key to <span className="font-mono text-foreground">{form.toggle_extension}</span>.
              </p>
            )}
          </Field>
          <Field label="Default State" hint="State before first toggle.">
            <div className="flex items-center gap-2 h-9">
              <Toggle
                checked={form.toggle_default_on}
                onChange={v => setForm(p => ({ ...p, toggle_default_on: v }))}
              />
              <span className="text-sm">{form.toggle_default_on ? 'ON (green)' : 'OFF (red)'}</span>
            </div>
          </Field>
        </div>
        <Field label="Feature Code" hint='Optional second dial string that also flips it, e.g. "*71".'>
          <Input
            placeholder="*71 (optional)"
            value={form.toggle_feature_code}
            onChange={e => setForm(p => ({ ...p, toggle_feature_code: e.target.value }))}
          />
          {form.toggle_feature_code && tc && (
            <p className="mt-1 text-xs text-muted-foreground">
              Dials as <span className="font-mono text-foreground">{dialForm(form.toggle_feature_code)}</span> in this tenant.
            </p>
          )}
        </Field>
        <Field label="ON destination (green) *" hint="Where calls go while the toggle is ON.">
          <DestinationPicker
            value={{ type: form.toggle_on_type, target_uuid: form.toggle_on_target_uuid, external_number: form.toggle_on_external }}
            onChange={(d) => setForm(p => ({ ...p, toggle_on_type: d.type || '', toggle_on_target_uuid: d.target_uuid || '', toggle_on_external: d.external_number || '' }))}
            data={destData}
            loading={destLoading}
            searchLoading={destSearchLoading}
            onSearch={searchDestData}
            compact
            placeholder="Select destination…"
          />
        </Field>
        <Field label="OFF destination (red) *" hint="Where calls go while the toggle is OFF.">
          <DestinationPicker
            value={{ type: form.toggle_off_type, target_uuid: form.toggle_off_target_uuid, external_number: form.toggle_off_external }}
            onChange={(d) => setForm(p => ({ ...p, toggle_off_type: d.type || '', toggle_off_target_uuid: d.target_uuid || '', toggle_off_external: d.external_number || '' }))}
            data={destData}
            loading={destLoading}
            searchLoading={destSearchLoading}
            onSearch={searchDestData}
            compact
            placeholder="Select destination…"
          />
        </Field>
        <div className="flex items-start gap-2 text-xs text-blue-700 rounded-lg border border-blue-200 bg-blue-500/5 px-3 py-2">
          <ToggleRight className="h-3.5 w-3.5 shrink-0 mt-0.5" />
          <span>
            Subscribe a phone BLF key to the BLF number to see the green/red lamp;
            pressing the key flips it. The ON and OFF destinations can be any
            destination — extension, IVR, ring group, voicemail, external number,
            or another custom destination.
          </span>
        </div>
      </>
      )
    },
    // Toggle doesn't route directly via dest_type; store a hangup placeholder so
    // the shared "pick a destination" validation/columns stay satisfied.
    onSavePrep: (form) => ({
      ...form,
      callback_to_last_caller: false,
      dest_type: form.dest_type || 'hangup',
      // New triple is authoritative; clear the legacy FK fields so they don't
      // override (the dialplan prefers the triple but falls back to the FK).
      toggle_on_dest: null,
      toggle_off_dest: null,
      toggle_on_target_uuid: form.toggle_on_target_uuid || '',
      toggle_off_target_uuid: form.toggle_off_target_uuid || '',
    }),
  },
}

// Return {kind, label} if `number` is already a dialable number on this tenant
// (an extension, ring group, IVR, or another toggle/BLF), else null. excludeId
// is the current custom-destination uuid so editing its own number is allowed.
function blfNumberConflict(number, data, excludeId) {
  const n = (number || '').trim()
  if (!n) return null
  const ext = (data.extensions || []).find(e => String(e.extension) === n)
  if (ext) return { kind: 'extension', label: ext.extension }
  const rg = (data.ring_groups || []).find(r => String(r.ring_group_extension) === n)
  if (rg) return { kind: 'ring group', label: rg.ring_group_name || n }
  const ivr = (data.ivr_menus || []).find(i => String(i.ivr_menu_extension) === n)
  if (ivr) return { kind: 'IVR menu', label: ivr.ivr_menu_name || n }
  const cd = (data.custom_destinations || []).find(
    c => c.custom_destination_uuid !== excludeId && String(c.toggle_extension || '') === n)
  if (cd) return { kind: 'BLF toggle', label: cd.name || n }
  return null
}

function CustomDestSelect({ value, onChange, options, excludeId }) {
  const items = (options || []).filter(o => o.custom_destination_uuid !== excludeId)
  return (
    <Select value={value || ''} onChange={e => onChange(e.target.value)}>
      <option value="">Select a custom destination…</option>
      {items.map(o => (
        <option key={o.custom_destination_uuid} value={o.custom_destination_uuid}>
          {o.name}
        </option>
      ))}
    </Select>
  )
}

const KIND_LIST = Object.entries(KIND_REGISTRY).map(([value, def]) => ({ value, ...def }))

function targetLabel(type, targetUuid, extNumber, data) {
  if (!type) return null
  if (type === 'hangup')   return 'Hangup'
  if (type === 'external') return extNumber || 'External Number'
  if (type === 'extension') {
    const e = data.extensions.find(x => x.extension_uuid === targetUuid)
    return e ? `${e.extension}${e.effective_caller_id_name ? ` — ${e.effective_caller_id_name}` : ''}` : null
  }
  if (type === 'voicemail') {
    const v = data.voicemails.find(x => (x.voicemail_uuid || x.id) === targetUuid)
    return v ? `Voicemail ${v.voicemail_id}` : null
  }
  if (type === 'ivr_menu') {
    const i = data.ivr_menus.find(x => x.ivr_menu_uuid === targetUuid)
    return i?.ivr_menu_name || null
  }
  if (type === 'ring_group') {
    const r = data.ring_groups.find(x => x.ring_group_uuid === targetUuid)
    return r?.ring_group_name || null
  }
  if (type === 'conference') {
    const c = data.conferences.find(x => x.conference_uuid === targetUuid)
    return c?.conference_name || null
  }
  if (type === 'working_hours') {
    const w = data.working_hours.find(x => x.working_hours_uuid === targetUuid)
    return w?.working_hours_name || null
  }
  if (type === 'custom_destination') {
    const c = (data.custom_destinations || []).find(x => x.custom_destination_uuid === targetUuid)
    return c?.name || null
  }
  return null
}

function TargetPicker({ value, onChange, data, loading, searchLoading, onSearch }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const debouncedQuery = useDebounce(query, 300)
  const ref = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (!open) return
    const h = (e) => { if (!ref.current?.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [open])

  useEffect(() => { if (open) requestAnimationFrame(() => inputRef.current?.focus()) }, [open])

  // Fire API search whenever the debounced query changes (server-side, so it
  // covers every record — not just the first page loaded into memory).
  useEffect(() => {
    if (!open || !onSearch) return
    onSearch(debouncedQuery)
  }, [debouncedQuery, open])

  // When closed, reset to the unfiltered list
  useEffect(() => {
    if (!open && query) { setQuery(''); onSearch?.('') }
  }, [open])

  const exts  = data.extensions          || []
  const vms   = data.voicemails          || []
  const ivrs  = data.ivr_menus           || []
  const rgs   = data.ring_groups         || []
  const confs = data.conferences         || []
  const whs   = data.working_hours       || []
  const cds   = data.custom_destinations || []
  const q = query.trim()
  const showNum = q.length >= 2 && /^[\d+\s().-]+$/.test(q)

  const pick = (type, target_uuid = '', external_number = '') => {
    onChange({ dest_type: type, dest_target_uuid: target_uuid, dest_external_number: external_number })
    setOpen(false); setQuery('')
  }

  const label = targetLabel(value.dest_type, value.dest_target_uuid, value.dest_external_number, data)
  const meta = value.dest_type ? DEST_META[value.dest_type] : null

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="flex h-9 w-full items-center justify-between gap-2 rounded-md border border-input bg-background px-3 text-sm shadow-sm hover:border-ring/60 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring transition-colors"
      >
        {loading ? (
          <span className="flex items-center gap-2 text-muted-foreground text-xs">
            <Loader2 className="h-3 w-3 animate-spin" /> Loading…
          </span>
        ) : label ? (
          <span className="flex items-center gap-2 min-w-0">
            <span className={cn('shrink-0 text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded', meta?.color, meta?.bg)}>{meta?.label}</span>
            <span className="truncate text-sm">{label}</span>
          </span>
        ) : (
          <span className="text-muted-foreground text-sm">Select destination…</span>
        )}
        <ChevronDown className="h-3 w-3 shrink-0 text-muted-foreground" />
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-full min-w-[300px] rounded-xl border border-border/60 bg-card shadow-2xl">
          <div className="flex items-center gap-2 border-b px-3 py-1.5">
            {searchLoading
              ? <Loader2 className="h-3.5 w-3.5 shrink-0 text-muted-foreground animate-spin" />
              : <Search className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />}
            <input
              ref={inputRef}
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search or type a number…"
              className="flex-1 text-sm bg-transparent outline-none placeholder:text-muted-foreground"
            />
            {query && <button type="button" onClick={() => setQuery('')}><X className="h-3 w-3 text-muted-foreground" /></button>}
          </div>
          <div className="max-h-60 overflow-y-auto py-1">
            {exts.length > 0 && (
              <Section title="Extensions">
                {exts.map(e => (
                  <ResultBtn key={e.extension_uuid} onClick={() => pick('extension', e.extension_uuid)}>
                    <span className="font-mono font-bold text-blue-500 w-10 shrink-0">{e.extension}</span>
                    <span className="text-sm truncate text-muted-foreground">{e.effective_caller_id_name || e.description || ''}</span>
                  </ResultBtn>
                ))}
              </Section>
            )}
            {rgs.length > 0 && (
              <Section title="Ring Groups">
                {rgs.map(r => (
                  <ResultBtn key={r.ring_group_uuid} onClick={() => pick('ring_group', r.ring_group_uuid)}>
                    <span className="font-mono font-bold text-green-600 w-10 shrink-0">{r.ring_group_extension || '—'}</span>
                    <span className="text-sm truncate">{r.ring_group_name}</span>
                  </ResultBtn>
                ))}
              </Section>
            )}
            {ivrs.length > 0 && (
              <Section title="IVR Menus">
                {ivrs.map(i => (
                  <ResultBtn key={i.ivr_menu_uuid} onClick={() => pick('ivr_menu', i.ivr_menu_uuid)}>
                    <span className="font-mono font-bold text-amber-500 w-10 shrink-0">{i.ivr_menu_extension || '—'}</span>
                    <span className="text-sm truncate">{i.ivr_menu_name}</span>
                  </ResultBtn>
                ))}
              </Section>
            )}
            {vms.length > 0 && (
              <Section title="Voicemail">
                {vms.map(v => (
                  <ResultBtn key={v.voicemail_uuid || v.id} onClick={() => pick('voicemail', v.voicemail_uuid || v.id)}>
                    <span className="font-mono font-bold text-purple-500 w-10 shrink-0">{v.voicemail_id}</span>
                    <span className="text-sm truncate text-muted-foreground">{v.voicemail_name || ''}</span>
                  </ResultBtn>
                ))}
              </Section>
            )}
            {confs.length > 0 && (
              <Section title="Conferences">
                {confs.map(c => (
                  <ResultBtn key={c.conference_uuid} onClick={() => pick('conference', c.conference_uuid)}>
                    <span className="font-mono font-bold text-sky-500 w-10 shrink-0">{c.conference_extension || '—'}</span>
                    <span className="text-sm truncate">{c.conference_name}</span>
                  </ResultBtn>
                ))}
              </Section>
            )}
            {whs.length > 0 && (
              <Section title="Working Hours">
                {whs.map(w => (
                  <ResultBtn key={w.working_hours_uuid} onClick={() => pick('working_hours', w.working_hours_uuid)}>
                    <span className="font-mono font-bold text-teal-500 w-10 shrink-0">WH</span>
                    <span className="text-sm truncate">{w.working_hours_name}</span>
                  </ResultBtn>
                ))}
              </Section>
            )}
            {cds.length > 0 && (
              <Section title="Custom Destinations">
                {cds.map(c => (
                  <ResultBtn key={c.custom_destination_uuid} onClick={() => pick('custom_destination', c.custom_destination_uuid)}>
                    <span className="font-mono font-bold text-fuchsia-500 w-10 shrink-0">CD</span>
                    <span className="text-sm truncate">{c.name}</span>
                    {c.callback_to_last_caller && <span className="text-[10px] text-amber-600 ml-auto shrink-0">sticky</span>}
                  </ResultBtn>
                ))}
              </Section>
            )}
            {showNum && (
              <Section title="External Number">
                <ResultBtn onClick={() => pick('external', '', query)}>
                  <PhoneForwarded className="h-4 w-4 text-slate-500 shrink-0" />
                  <span className="text-sm">Forward to <span className="font-mono font-semibold">{query}</span></span>
                </ResultBtn>
              </Section>
            )}
            <div className="border-t mt-1 pt-1">
              <ResultBtn onClick={() => pick('hangup')}>
                <PhoneOff className="h-4 w-4 text-red-500 shrink-0" />
                <span className="text-sm text-red-500 font-medium">Hangup</span>
              </ResultBtn>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function Section({ title, children }) {
  return (
    <div>
      <p className="px-3 pt-2 pb-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{title}</p>
      {children}
    </div>
  )
}

function ResultBtn({ onClick, children }) {
  return (
    <button type="button" onClick={onClick}
      className="w-full flex items-center gap-3 mx-1 px-3 py-1.5 rounded-lg hover:bg-muted text-left transition-colors text-sm">
      {children}
    </button>
  )
}

// Live ON/OFF indicator for a toggle destination. Reads the runtime state from
// FreeSWITCH (via the backend) so a phone-side flip is reflected, and lets the
// user flip it from here (which republishes presence so phone lamps update).
function ToggleStateBadge({ row }) {
  const [state, setState] = useState(row.toggle_state !== false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    let alive = true
    api.toggleState(row.custom_destination_uuid)
      .then(({ data }) => { if (alive && typeof data.state === 'boolean') setState(data.state) })
      .catch(() => {})
    return () => { alive = false }
  }, [row.custom_destination_uuid])

  const flip = async (e) => {
    e.stopPropagation()
    setBusy(true)
    try {
      const { data } = await api.setToggleState(row.custom_destination_uuid, !state)
      setState(data.state)
    } catch { /* leave state as-is on error */ }
    finally { setBusy(false) }
  }

  return (
    <button
      type="button" onClick={flip} disabled={busy}
      title="Click to flip — updates the phone BLF lamp"
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-semibold transition-colors',
        state ? 'bg-emerald-500/15 text-emerald-600 hover:bg-emerald-500/25'
              : 'bg-red-500/15 text-red-600 hover:bg-red-500/25',
      )}
    >
      {busy
        ? <Loader2 className="h-3 w-3 animate-spin" />
        : <span className={cn('h-2 w-2 rounded-full', state ? 'bg-emerald-500' : 'bg-red-500')} />}
      {state ? 'ON' : 'OFF'}
    </button>
  )
}

function Field({ label, hint, children, className }) {
  return (
    <div className={cn('space-y-1.5', className)}>
      <Label className="text-sm font-medium">{label}</Label>
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}

function Toggle({ checked, onChange }) {
  return (
    <button
      type="button" role="switch" aria-checked={checked}
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

const SOURCE_LABELS = { manual_seed: 'seeded', manual_ui: 'manual', outbound: 'outbound' }

export function AffinityPanel({ open, onClose }) {
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  // Add-row form
  const [newCaller, setNewCaller] = useState('')
  const [newExt, setNewExt] = useState('')
  // Inline edit
  const [editId, setEditId] = useState(null)
  const [editExt, setEditExt] = useState('')
  // Search + page size
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebounce(search, 350)
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)
  const scrollRef = useRef(null)
  // Full tenant total (independent of search) for the header stat.
  const [grandTotal, setGrandTotal] = useState(0)

  const params = debouncedSearch ? { search: debouncedSearch } : {}
  const {
    rows, total, loading, loadingMore, hasMore, loadMore, reload,
  } = useInfiniteList(api.affinityStats, {
    params,
    pageSize,
    enabled: open,
    selectResults: (d) => d.recent || [],
    selectCount: (d) => d.filtered_total ?? (d.recent || []).length,
  })

  // Header stat = unfiltered tenant total; refresh on open and after mutations.
  const refreshGrandTotal = useCallback(() => {
    api.affinityStats({ page: 1, page_size: 1 })
      .then(({ data }) => setGrandTotal(data.total || 0))
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!open) return
    setError(''); setNewCaller(''); setNewExt(''); setEditId(null)
    refreshGrandTotal()
  }, [open, refreshGrandTotal])

  const afterMutation = () => { reload(); refreshGrandTotal() }

  const add = async (overwrite = false) => {
    if (!newCaller.trim() || !newExt.trim()) return
    setBusy(true); setError('')
    try {
      await api.affinityCreate({
        caller_number: newCaller.trim(), extension_number: newExt.trim(),
        ...(overwrite ? { overwrite: true } : {}),
      })
      setNewCaller(''); setNewExt(''); afterMutation()
    } catch (e) {
      if (e?.response?.status === 409) {
        const ex = e.response.data?.existing
        const ok = window.confirm(
          `${ex?.caller_number} is already mapped to extension ${ex?.extension_number}.\n\nOverwrite it with ${newExt.trim()}?`
        )
        if (ok) { setBusy(false); return add(true) }
      } else {
        setError(e?.response?.data?.detail || 'Could not add mapping.')
      }
    } finally { setBusy(false) }
  }

  const saveEdit = async (id) => {
    if (!editExt.trim()) return
    setBusy(true); setError('')
    try {
      await api.affinityUpdate(id, { extension_number: editExt.trim() })
      setEditId(null); afterMutation()
    } catch (e) {
      setError(e?.response?.data?.detail || 'Could not update mapping.')
    } finally { setBusy(false) }
  }

  const remove = async (id) => {
    setBusy(true); setError('')
    try {
      await api.affinityDelete(id); afterMutation()
    } catch (e) {
      setError(e?.response?.data?.detail || 'Could not delete mapping.')
    } finally { setBusy(false) }
  }

  return (
    <Dialog open={open} onOpenChange={v => { if (!v) onClose() }}>
      <DialogContent className="w-[95vw] max-w-2xl h-[640px] max-h-[90vh] flex flex-col p-0 overflow-hidden">
        <DialogHeader className="px-6 pt-5 pb-4 border-b">
          <DialogTitle className="flex items-center gap-2">
            <History className="h-4 w-4 text-primary" /> Caller → Extension Affinity
          </DialogTitle>
        </DialogHeader>
        <div className="px-6 py-4 border-b bg-muted/30 flex items-center gap-4">
          <div className="flex items-center gap-3">
            <Users className="h-5 w-5 text-muted-foreground" />
            <div>
              <p className="text-2xl font-bold">{grandTotal.toLocaleString()}</p>
              <p className="text-xs text-muted-foreground">customers mapped to a sticky extension</p>
            </div>
          </div>
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search by number or extension…"
              className="pl-8 font-mono"
            />
          </div>
          <PageSizeSelector value={pageSize} onChange={setPageSize} />
        </div>

        {/* Add row */}
        <div className="px-6 py-3 border-b flex items-end gap-2">
          <div className="flex-1">
            <Label className="text-xs">Customer number</Label>
            <Input value={newCaller} onChange={e => setNewCaller(e.target.value)}
              placeholder="e.g. 7133034589" className="font-mono" />
          </div>
          <div className="w-32">
            <Label className="text-xs">Extension</Label>
            <Input value={newExt} onChange={e => setNewExt(e.target.value)}
              placeholder="e.g. 432" className="font-mono"
              onKeyDown={e => { if (e.key === 'Enter') add() }} />
          </div>
          <Button onClick={add} disabled={busy || !newCaller.trim() || !newExt.trim()} size="sm">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            <span className="ml-1">Add</span>
          </Button>
        </div>
        {error && <div className="px-6 py-2 text-sm text-red-500 border-b">{error}</div>}
        <p className="px-6 pt-2 text-[11px] text-muted-foreground">
          Manual mappings are temporary — the next outbound call from an extension to this customer overwrites them.
        </p>

        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : rows.length === 0 ? (
            <div className="px-6 py-12 text-center text-sm text-muted-foreground">
              {debouncedSearch
                ? `No mappings match "${debouncedSearch}".`
                : 'No mappings yet. Add one above, or outbound calls will populate this automatically.'}
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Customer</TableHead>
                  <TableHead>Extension</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Last seen</TableHead>
                  <TableHead className="w-24 text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map(r => (
                  <TableRow key={r.affinity_uuid}>
                    <TableCell className="font-mono text-sm">{r.caller_number}</TableCell>
                    <TableCell>
                      {editId === r.affinity_uuid ? (
                        <Input value={editExt} onChange={e => setEditExt(e.target.value)}
                          className="font-mono h-8 w-28"
                          onKeyDown={e => { if (e.key === 'Enter') saveEdit(r.affinity_uuid) }}
                          autoFocus />
                      ) : (
                        <span className="font-mono font-bold text-blue-500">{r.extension_number}</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline" className="text-xs">
                        {SOURCE_LABELS[r.source] || r.source}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {r.last_seen ? new Date(r.last_seen).toLocaleString() : '—'}
                    </TableCell>
                    <TableCell className="text-right whitespace-nowrap">
                      {editId === r.affinity_uuid ? (
                        <>
                          <Button size="sm" variant="ghost" disabled={busy}
                            onClick={() => saveEdit(r.affinity_uuid)}>Save</Button>
                          <Button size="sm" variant="ghost" onClick={() => setEditId(null)}>
                            <X className="h-4 w-4" />
                          </Button>
                        </>
                      ) : (
                        <>
                          <Button size="sm" variant="ghost" disabled={busy}
                            onClick={() => { setEditId(r.affinity_uuid); setEditExt(r.extension_number) }}>
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button size="sm" variant="ghost" disabled={busy}
                            onClick={() => remove(r.affinity_uuid)}>
                            <Trash2 className="h-4 w-4 text-red-500" />
                          </Button>
                        </>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {!loading && rows.length > 0 && (
            <InfiniteScroll
              hasMore={hasMore}
              loadingMore={loadingMore}
              onLoadMore={loadMore}
              loaded={rows.length}
              total={total}
              rootRef={scrollRef}
            />
          )}
        </div>
        <div className="px-6 py-4 border-t flex items-center justify-between gap-3">
          <div className="text-xs text-muted-foreground">
            {loading ? '' : <>{(total || 0).toLocaleString()} {debouncedSearch ? 'matching' : 'total'}</>}
          </div>
          <Button variant="outline" onClick={onClose}>Close</Button>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default function CustomDestinations() {
  const { currentTenant } = useSelector(selectTenant)
  const navigate = useNavigate()
  const { id: editParamId } = useParams()
  const location = useLocation()
  const isCreate   = location.pathname.endsWith('/custom-destinations/new')
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
  const [affinityOpen, setAffinityOpen] = useState(false)
  const [resyncing, setResyncing] = useState(false)

  const { destData, destLoading, destSearchLoading, loadDestData, searchDestData } = useDestinationData({ withConferences: true })

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.list(debouncedSearch ? { search: debouncedSearch } : {})
      setRows(Array.isArray(data) ? data : data.results || [])
    } finally { setLoading(false) }
  }, [debouncedSearch])

  useEffect(() => { load() }, [load])

  const rowToForm = (r) => ({
    name: r.name || '',
    description: r.description || '',
    kind: r.kind || (r.callback_to_last_caller ? 'sticky_last_agent' : 'simple'),
    dest_type: r.dest_type || '',
    dest_target_uuid: r.dest_target_uuid || '',
    dest_external_number: r.dest_external_number || '',
    callback_to_last_caller: !!r.callback_to_last_caller,
    enabled: r.enabled !== false,
    toggle_extension: r.toggle_extension || '',
    toggle_feature_code: r.toggle_feature_code || '',
    toggle_default_on: r.toggle_default_on !== false,
    toggle_state: r.toggle_state !== false,
    toggle_on_dest: r.toggle_on_dest || '',
    toggle_off_dest: r.toggle_off_dest || '',
    toggle_on_type: r.toggle_on_type || '',
    toggle_on_target_uuid: r.toggle_on_target_uuid || '',
    toggle_on_external: r.toggle_on_external || '',
    toggle_off_type: r.toggle_off_type || '',
    toggle_off_target_uuid: r.toggle_off_target_uuid || '',
    toggle_off_external: r.toggle_off_external || '',
  })

  const openCreate = () => navigate('/custom-destinations/new')
  const openEdit = (r) => navigate('/custom-destinations/' + r.custom_destination_uuid + '/edit')
  const closeEditor = () => navigate('/custom-destinations')

  // Sync form state to the current route. Guarded on the route key so a spurious
  // re-run can't re-seed the form and discard the user's in-progress edits.
  const lastRouteKeyRef = useRef(null)
  useEffect(() => {
    if (!editorOpen) { lastRouteKeyRef.current = null; return }
    const routeKey = isCreate ? 'new' : routeId
    if (lastRouteKeyRef.current === routeKey) return
    lastRouteKeyRef.current = routeKey
    setFormError('')
    loadDestData()
    if (isCreate) { setEditId(null); setForm(EMPTY); return }
    setEditId(routeId)
    const row = rows.find(r => r.custom_destination_uuid === routeId)
    if (row) { setForm(rowToForm(row)); return }
    api.get?.(routeId).then(({ data }) => setForm(rowToForm(data))).catch(() => setForm(EMPTY))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeId, isCreate])

  const handleSave = async () => {
    if (!form.name.trim()) { setFormError('Name is required.'); return }
    if (form.kind === 'toggle') {
      if (!form.toggle_extension.trim()) { setFormError('BLF number is required.'); return }
      if (!form.toggle_on_type)  { setFormError('Pick an ON destination.'); return }
      if (!form.toggle_off_type) { setFormError('Pick an OFF destination.'); return }
    } else if (!form.dest_type) {
      setFormError('Pick a destination.'); return
    }
    setSaving(true); setFormError('')
    try {
      const kindDef = KIND_REGISTRY[form.kind] || KIND_REGISTRY.simple
      const prepped = kindDef.onSavePrep ? kindDef.onSavePrep(form) : form
      const payload = {
        ...prepped,
        dest_target_uuid: prepped.dest_target_uuid || null,
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

  const handleResync = async () => {
    setResyncing(true)
    try {
      const { data } = await api.resyncToggles()
      load()
      alert(`Resynced ${data.pushed} toggle${data.pushed === 1 ? '' : 's'} to the phones.` +
        (data.failed ? ` ${data.failed} could not reach FreeSWITCH.` : ''))
    } catch {
      alert('Resync failed — could not reach FreeSWITCH.')
    } finally { setResyncing(false) }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this custom destination?')) return
    setDeleting(id)
    try { await api.delete(id); load() } finally { setDeleting(null) }
  }

  // ── Full-page editor (routed) ──────────────────────────────────────────────
  if (editorOpen) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={closeEditor} className="-ml-2 gap-1">
            ← Custom Destinations
          </Button>
          <span className="text-muted-foreground">/</span>
          <h1 className="text-lg font-semibold">{isCreate ? 'New Custom Destination' : 'Edit Custom Destination'}</h1>
        </div>

        <Card>
          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
            {formError && (
              <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-2.5 text-sm text-destructive">{formError}</div>
            )}

            <Field label="Type *" hint={KIND_REGISTRY[form.kind]?.description}>
              <Select value={form.kind} onChange={e => setForm(p => ({ ...p, kind: e.target.value }))}>
                {KIND_LIST.map(k => (
                  <option key={k.value} value={k.value}>{k.label}</option>
                ))}
              </Select>
            </Field>

            <Field label="Name *">
              <Input placeholder='e.g. "After Hours VM"' value={form.name} onChange={e => setForm(p => ({ ...p, name: e.target.value }))} />
            </Field>
            <Field label="Description">
              <Input placeholder="Optional notes" value={form.description} onChange={e => setForm(p => ({ ...p, description: e.target.value }))} />
            </Field>

            {/* Kind-specific body */}
            {(KIND_REGISTRY[form.kind] || KIND_REGISTRY.simple).renderBody({
              form, setForm, destData, destLoading, destSearchLoading, searchDestData,
              cdOptions: rows, editId, currentTenant,
              openAffinity: () => setAffinityOpen(true),
            })}

            <ToggleRow
              label="Enabled"
              checked={form.enabled}
              onChange={v => setForm(p => ({ ...p, enabled: v }))}
            />
          </div>
          <div className="flex items-center justify-end gap-2 px-6 py-4 border-t bg-muted/30 shrink-0">
            <Button variant="outline" onClick={closeEditor}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
              {isCreate ? 'Create' : 'Save Changes'}
            </Button>
          </div>
        </Card>

        <AffinityPanel open={affinityOpen} onClose={() => setAffinityOpen(false)} />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Search…" className="pl-8" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <Button variant="outline" size="sm" onClick={() => setAffinityOpen(true)}>
          <History className="h-4 w-4 mr-1" /> View Affinity
        </Button>
        <Button variant="outline" size="sm" onClick={handleResync} disabled={resyncing}
          title="Re-push all toggle states to the phones (fixes BLF lamps after a reboot)">
          {resyncing ? <Loader2 className="h-4 w-4 mr-1 animate-spin" /> : <RefreshCw className="h-4 w-4 mr-1" />}
          Resync BLF
        </Button>
        <Button size="sm" onClick={openCreate}><Plus className="h-4 w-4 mr-1" />New Destination</Button>
      </div>

      <AffinityPanel open={affinityOpen} onClose={() => setAffinityOpen(false)} />

      <Card><CardContent className="p-0 overflow-x-auto">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Kind</TableHead>
              <TableHead>Destination</TableHead>
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
                ? <TableRow><TableCell colSpan={5} className="text-center py-10 text-muted-foreground">No custom destinations defined.</TableCell></TableRow>
                : rows.map((r) => {
                    const meta = DEST_META[r.dest_type]
                    const kindKey = r.kind || (r.callback_to_last_caller ? 'sticky_last_agent' : 'simple')
                    const kindDef = KIND_REGISTRY[kindKey] || KIND_REGISTRY.simple
                    const KindIcon = kindDef.icon
                    return (
                      <TableRow key={r.custom_destination_uuid}>
                        <TableCell>
                          <div className="font-medium">{r.name}</div>
                          {r.description && <div className="text-xs text-muted-foreground truncate max-w-md">{r.description}</div>}
                        </TableCell>
                        <TableCell>
                          <span className="inline-flex items-center gap-1.5 text-xs">
                            <KindIcon className="h-3.5 w-3.5 text-muted-foreground" />
                            <span className="font-medium">{kindDef.label}</span>
                          </span>
                        </TableCell>
                        <TableCell>
                          {kindKey === 'toggle' ? (
                            <span className="inline-flex items-center gap-1.5 text-xs font-mono font-bold text-emerald-600">
                              <ToggleRight className="h-3.5 w-3.5" />
                              {r.toggle_extension || '—'}
                              {r.toggle_feature_code && <span className="text-muted-foreground font-normal">/ {r.toggle_feature_code}</span>}
                            </span>
                          ) : (
                            <span className={cn('text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded', meta?.color, meta?.bg)}>
                              {meta?.label || r.dest_type || '—'}
                            </span>
                          )}
                        </TableCell>
                        <TableCell>
                          {kindKey === 'toggle' ? (
                            <ToggleStateBadge row={r} />
                          ) : (
                            <Badge variant={r.enabled !== false ? 'success' : 'secondary'}>
                              {r.enabled !== false ? 'Active' : 'Disabled'}
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(r)}>
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive"
                              onClick={() => handleDelete(r.custom_destination_uuid)}
                              disabled={deleting === r.custom_destination_uuid}>
                              {deleting === r.custom_destination_uuid
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
