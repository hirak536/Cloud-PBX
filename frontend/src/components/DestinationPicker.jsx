import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, Loader2, X, ChevronDown, PhoneForwarded, PhoneOff, ArrowUpRight } from 'lucide-react'
import { cn } from '@/lib/utils'
import { useDebounce } from '@/hooks/useDebounce'

// ─── Shared constants ─────────────────────────────────────────────────────────

export const DEST_META = {
  extension:           { label: 'Extension',      color: 'text-blue-500',    bg: 'bg-blue-500/10'    },
  voicemail:           { label: 'Voicemail',      color: 'text-purple-500',  bg: 'bg-purple-500/10'  },
  ivr_menu:            { label: 'IVR Menu',       color: 'text-amber-500',   bg: 'bg-amber-500/10'   },
  ring_group:          { label: 'Ring Group',     color: 'text-green-600',   bg: 'bg-green-600/10'   },
  working_hours:       { label: 'Working Hours',  color: 'text-teal-600',    bg: 'bg-teal-600/10'    },
  number:              { label: 'Dial Number',    color: 'text-slate-500',   bg: 'bg-slate-500/10'   },
  hangup:              { label: 'Hangup',         color: 'text-red-500',     bg: 'bg-red-500/10'     },
  custom_destination:  { label: 'Custom Dest',    color: 'text-indigo-500',  bg: 'bg-indigo-500/10'  },
}

export const EMPTY_DEST = { type: '', target_uuid: '', external_number: '' }

// ─── Label resolver ───────────────────────────────────────────────────────────

export function destLabel(dest, data) {
  if (!dest?.type) return null
  const { type, target_uuid, external_number } = dest
  if (type === 'hangup') return 'Hangup'
  if (type === 'number') return external_number || 'Dial Number'
  if (type === 'extension') {
    const e = data.extensions.find(x => x.extension_uuid === target_uuid)
    return e ? `${e.extension}${e.description ? ` — ${e.description}` : ''}` : (target_uuid ? `Ext ${target_uuid.slice(0, 8)}…` : null)
  }
  if (type === 'voicemail') {
    const v = data.voicemails.find(x => (x.voicemail_uuid || x.id) === target_uuid)
    return v ? `Voicemail ${v.voicemail_id}` : (external_number ? `Voicemail ${external_number}` : (target_uuid ? `VM ${target_uuid.slice(0, 8)}…` : null))
  }
  if (type === 'ivr_menu') {
    const i = data.ivr_menus.find(x => x.ivr_menu_uuid === target_uuid)
    return i ? i.ivr_menu_name : (target_uuid ? `IVR ${target_uuid.slice(0, 8)}…` : null)
  }
  if (type === 'ring_group') {
    const r = data.ring_groups.find(x => x.ring_group_uuid === target_uuid)
    return r ? r.ring_group_name : (target_uuid ? `Ring Group ${target_uuid.slice(0, 8)}…` : null)
  }
  if (type === 'custom_destination') {
    const cd = (data.custom_destinations ?? []).find(x => x.custom_destination_uuid === target_uuid)
    return cd ? cd.name : (target_uuid ? `Custom ${target_uuid.slice(0, 8)}…` : null)
  }
  if (type === 'working_hours') {
    const wh = (data.working_hours ?? []).find(x => x.working_hours_uuid === target_uuid)
    return wh ? wh.working_hours_name : (target_uuid ? `WH ${target_uuid.slice(0, 8)}…` : null)
  }
  return null
}

// ─── Setup-page route resolver ────────────────────────────────────────────────
// Returns the edit route for destinations that have a dedicated setup page, or
// null for types with nothing to navigate to (hangup, number, unset).

export function destRoute(dest) {
  if (!dest?.type || !dest.target_uuid) return null
  switch (dest.type) {
    case 'extension':          return `/extensions/${dest.target_uuid}/edit`
    case 'voicemail':          return `/voicemails/${dest.target_uuid}/edit`
    case 'ivr_menu':           return `/ivr-menus/${dest.target_uuid}/edit`
    case 'ring_group':         return `/ring-groups/${dest.target_uuid}/edit`
    case 'working_hours':      return `/working-hours/${dest.target_uuid}/edit`
    case 'custom_destination': return `/custom-destinations/${dest.target_uuid}/edit`
    default:                   return null
  }
}

// ─── Destination chip (used in multiple mode) ─────────────────────────────────

function DestChip({ dest, data, onRemove, onOpen }) {
  const meta  = DEST_META[dest.type]
  const label = destLabel(dest, data)
  const route = destRoute(dest)
  if (!label) return null
  return (
    <span className={cn('inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium', meta?.color, meta?.bg)}>
      {label}
      {route && (
        <button
          type="button"
          onClick={(e) => { e.stopPropagation(); onOpen(route) }}
          title={`Open ${meta?.label ?? 'destination'} setup`}
          className="hover:opacity-70 transition-opacity"
        >
          <ArrowUpRight className="h-2.5 w-2.5" />
        </button>
      )}
      <button type="button" onClick={onRemove} className="hover:opacity-70 transition-opacity">
        <X className="h-2.5 w-2.5" />
      </button>
    </span>
  )
}

// ─── Dropdown rows ────────────────────────────────────────────────────────────

function SectionHeader({ label }) {
  return <p className="px-3 pt-2 pb-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>
}

function DestRow({ onClick, isSelected, children }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'w-full flex items-center gap-3 px-3 py-1.5 hover:bg-muted text-left transition-colors',
        isSelected && 'bg-muted/70',
      )}
    >
      {children}
    </button>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

/**
 * DestinationPicker
 *
 * Single mode (default):
 *   value    = { type, target_uuid, external_number } | null
 *   onChange = (dest) => void
 *
 * Multiple mode:
 *   multiple = true
 *   value    = [{ type, target_uuid, external_number }, ...]
 *   onChange = (destArray) => void
 *   Dropdown stays open; items toggle on/off; chips shown in trigger.
 */
export default function DestinationPicker({
  value,
  onChange,
  data = { extensions: [], voicemails: [], ivr_menus: [], ring_groups: [], custom_destinations: [], working_hours: [] },
  loading = false,
  multiple = false,
  placeholder,
  compact = false,
  searchLoading = false,
  onSearch,
}) {
  const navigate            = useNavigate()
  const [open, setOpen]     = useState(false)
  const [dropUp, setDropUp] = useState(false)
  const [query, setQuery]   = useState('')
  const debouncedQuery      = useDebounce(query, 300)
  const containerRef        = useRef(null)
  const inputRef            = useRef(null)

  const defaultPlaceholder = multiple ? 'Add destinations…' : 'Select destination…'
  const ph = placeholder ?? defaultPlaceholder

  const toggleOpen = () => {
    if (!open && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect()
      setDropUp(rect.bottom + 320 > window.innerHeight)
    }
    setOpen(o => !o)
  }

  // ── Close on outside click ───────────────────────────────────────────────

  useEffect(() => {
    if (!open) return
    const h = (e) => { if (!containerRef.current?.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [open])

  useEffect(() => {
    if (open) requestAnimationFrame(() => inputRef.current?.focus())
  }, [open])

  // ── Server-side search (optional) ─────────────────────────────────────────
  // When onSearch is supplied the parent re-fetches every record with a search
  // filter, so the picker covers data beyond the first loaded page. Without it
  // the picker falls back to client-side filtering of whatever is in `data`.
  useEffect(() => {
    if (!open || !onSearch) return
    onSearch(debouncedQuery)
  }, [debouncedQuery, open])

  useEffect(() => {
    if (!open && query && onSearch) { setQuery(''); onSearch('') }
  }, [open])

  // ── Normalised selection helpers ─────────────────────────────────────────

  const isSelected = (type, target_uuid, external_number) => {
    if (!multiple) return false
    const arr = Array.isArray(value) ? value : []
    return arr.some(d =>
      d.type === type &&
      d.target_uuid === target_uuid &&
      d.external_number === external_number
    )
  }

  const select = (type, target_uuid = '', external_number = '') => {
    if (!multiple) {
      onChange({ type, target_uuid, external_number })
      setOpen(false)
      setQuery('')
      return
    }
    const arr = Array.isArray(value) ? value : []
    const already = arr.findIndex(d =>
      d.type === type &&
      d.target_uuid === target_uuid &&
      d.external_number === external_number
    )
    if (already >= 0) {
      onChange(arr.filter((_, i) => i !== already))
    } else {
      onChange([...arr, { type, target_uuid, external_number }])
    }
    // Keep dropdown open in multiple mode
  }

  const removeItem = (idx) => {
    const arr = Array.isArray(value) ? value : []
    onChange(arr.filter((_, i) => i !== idx))
  }

  // ── Filtering ────────────────────────────────────────────────────────────

  const q = query.toLowerCase().trim()
  // With server-side search the incoming `data` is already filtered — don't
  // filter again client-side or it would hide records the server matched on
  // fields the client doesn't know about.
  const filter = (items, fields) =>
    (onSearch || !q) ? items : items.filter(item => fields.some(f => String(item[f] || '').toLowerCase().includes(q)))

  const exts = filter(data.extensions,           ['extension', 'description', 'sip_username'])
  const vms  = filter(data.voicemails,           ['voicemail_id', 'description'])
  const ivrs = filter(data.ivr_menus,            ['ivr_menu_name', 'ivr_menu_extension'])
  const rgs  = filter(data.ring_groups,          ['ring_group_name', 'ring_group_extension'])
  const cds  = filter(data.custom_destinations ?? [], ['name', 'description'])
  const whs  = filter(data.working_hours ?? [],  ['working_hours_name'])
  const showNumber = q.length >= 2 && /^[\d+\s().-]+$/.test(q)
  const hasAny = exts.length || vms.length || ivrs.length || rgs.length || cds.length || whs.length || showNumber

  // ── Trigger display ──────────────────────────────────────────────────────

  const singleLabel = !multiple ? destLabel(value, data) : null
  const singleMeta  = !multiple && value?.type ? DEST_META[value.type] : null
  const singleRoute = !multiple ? destRoute(value) : null
  const multiArr    = multiple ? (Array.isArray(value) ? value : []) : []

  const h = compact ? 'h-8' : 'h-9'

  return (
    <div ref={containerRef} className="relative">

      {/* ── Trigger (+ optional deep-link arrow) ────────────────────────── */}
      <div className="flex items-center gap-1.5">
      <button
        type="button"
        onClick={toggleOpen}
        className={cn(
          `flex ${h} w-full items-center justify-between gap-2 rounded-xl border border-input bg-background px-3 py-1 text-sm shadow-sm`,
          'hover:border-ring/60 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring transition-colors',
          multiple && multiArr.length > 0 && 'h-auto min-h-9 py-1.5 flex-wrap',
        )}
      >
        {loading ? (
          <span className="flex items-center gap-2 text-muted-foreground text-xs">
            <Loader2 className="h-3 w-3 animate-spin" /> Loading…
          </span>
        ) : multiple ? (
          multiArr.length > 0 ? (
            <span className="flex flex-wrap gap-1 flex-1">
              {multiArr.map((d, i) => (
                <DestChip key={i} dest={d} data={data} onOpen={(r) => navigate(r)} onRemove={(e) => { e.stopPropagation(); removeItem(i) }} />
              ))}
            </span>
          ) : (
            <span className="text-muted-foreground text-sm">{ph}</span>
          )
        ) : singleLabel ? (
          <span className="flex items-center gap-2 min-w-0">
            <span className={cn('shrink-0 text-[10px] font-bold uppercase tracking-wide px-1 py-0.5 rounded', singleMeta?.color, singleMeta?.bg)}>
              {singleMeta?.label}
            </span>
            <span className="truncate text-sm">{singleLabel}</span>
          </span>
        ) : (
          <span className="text-muted-foreground text-sm">{ph}</span>
        )}
        <ChevronDown className={cn('shrink-0 text-muted-foreground', compact ? 'h-3 w-3' : 'h-3.5 w-3.5')} />
      </button>

      {singleRoute && (
        <button
          type="button"
          onClick={() => navigate(singleRoute)}
          title={`Open ${singleMeta?.label ?? 'destination'} setup`}
          className={cn(
            `flex ${h} shrink-0 aspect-square items-center justify-center rounded-xl border border-input bg-background text-muted-foreground shadow-sm`,
            'hover:border-ring/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring transition-colors',
          )}
        >
          <ArrowUpRight className={compact ? 'h-3.5 w-3.5' : 'h-4 w-4'} />
        </button>
      )}
      </div>

      {/* ── Dropdown ────────────────────────────────────────────────────── */}
      {open && (
        <div className={cn("absolute z-50 w-full min-w-[300px] rounded-xl border border-border/60 bg-card shadow-2xl shadow-black/10 animate-dropdown-in", dropUp ? "bottom-full mb-1" : "mt-1")}>
          <div className="flex items-center gap-2 border-b px-3 py-2">
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
            {query && (
              <button type="button" onClick={() => setQuery('')}>
                <X className="h-3 w-3 text-muted-foreground hover:text-foreground" />
              </button>
            )}
          </div>

          <div className="max-h-64 overflow-y-auto py-1">
            {loading ? (
              <div className="flex items-center justify-center py-6 text-sm text-muted-foreground gap-2">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading destinations…
              </div>
            ) : (
              <>
                {exts.length > 0 && (
                  <div>
                    <SectionHeader label="Extensions" />
                    {exts.map(e => (
                      <DestRow key={e.extension_uuid} isSelected={isSelected('extension', e.extension_uuid)}
                        onClick={() => select('extension', e.extension_uuid)}>
                        <span className="font-mono font-bold text-blue-500 shrink-0 mr-2">{e.extension}</span>
                        <span className="text-sm truncate min-w-0 text-muted-foreground">{e.description || e.sip_username || ''}</span>
                      </DestRow>
                    ))}
                  </div>
                )}
                {vms.length > 0 && (
                  <div>
                    <SectionHeader label="Voicemail" />
                    {vms.map(v => (
                      <DestRow key={v.voicemail_uuid || v.id} isSelected={isSelected('voicemail', v.voicemail_uuid || v.id)}
                        onClick={() => select('voicemail', v.voicemail_uuid || v.id)}>
                        <span className="font-mono font-bold text-purple-500 shrink-0 mr-2">{v.voicemail_id}</span>
                        <span className="text-sm truncate min-w-0 text-muted-foreground">{v.voicemail_name || ''}</span>
                      </DestRow>
                    ))}
                  </div>
                )}
                {ivrs.length > 0 && (
                  <div>
                    <SectionHeader label="IVR Menus" />
                    {ivrs.map(i => (
                      <DestRow key={i.ivr_menu_uuid} isSelected={isSelected('ivr_menu', i.ivr_menu_uuid)}
                        onClick={() => select('ivr_menu', i.ivr_menu_uuid)}>
                        <span className="font-mono font-bold text-amber-500 shrink-0 mr-2">{i.ivr_menu_extension || '—'}</span>
                        <span className="text-sm truncate min-w-0">{i.ivr_menu_name}</span>
                      </DestRow>
                    ))}
                  </div>
                )}
                {rgs.length > 0 && (
                  <div>
                    <SectionHeader label="Ring Groups" />
                    {rgs.map(r => (
                      <DestRow key={r.ring_group_uuid} isSelected={isSelected('ring_group', r.ring_group_uuid)}
                        onClick={() => select('ring_group', r.ring_group_uuid)}>
                        <span className="font-mono font-bold text-green-600 shrink-0 mr-2">{r.ring_group_extension || '—'}</span>
                        <span className="text-sm truncate min-w-0">{r.ring_group_name}</span>
                      </DestRow>
                    ))}
                  </div>
                )}
                {cds.length > 0 && (
                  <div>
                    <SectionHeader label="Custom Destinations" />
                    {cds.map(cd => (
                      <DestRow key={cd.custom_destination_uuid}
                        isSelected={isSelected('custom_destination', cd.custom_destination_uuid)}
                        onClick={() => select('custom_destination', cd.custom_destination_uuid)}>
                        <span className="font-mono font-bold text-indigo-500 shrink-0 mr-2 text-xs">CD</span>
                        <span className="text-sm truncate min-w-0">{cd.name}</span>
                        {cd.description && (
                          <span className="text-xs text-muted-foreground truncate ml-1">— {cd.description}</span>
                        )}
                      </DestRow>
                    ))}
                  </div>
                )}
                {whs.length > 0 && (
                  <div>
                    <SectionHeader label="Working Hours" />
                    {whs.map(wh => (
                      <DestRow key={wh.working_hours_uuid}
                        isSelected={isSelected('working_hours', wh.working_hours_uuid)}
                        onClick={() => select('working_hours', wh.working_hours_uuid)}>
                        <span className="font-mono font-bold text-teal-600 shrink-0 mr-2 text-xs">WH</span>
                        <span className="text-sm truncate min-w-0">{wh.working_hours_name}</span>
                      </DestRow>
                    ))}
                  </div>
                )}
                {showNumber && (
                  <div>
                    <SectionHeader label="Dial Number" />
                    <DestRow isSelected={isSelected('number', '', query)} onClick={() => select('number', '', query)}>
                      <PhoneForwarded className="h-4 w-4 text-slate-500 shrink-0" />
                      <span className="text-sm">Forward to <span className="font-mono font-semibold">{query}</span></span>
                    </DestRow>
                  </div>
                )}
                {q && !hasAny && (
                  <p className="px-3 py-4 text-sm text-muted-foreground text-center">No results for &ldquo;{query}&rdquo;</p>
                )}

                {/* Hangup + optional clear for multiple */}
                <div className="border-t mt-1 pt-1">
                  <DestRow isSelected={!multiple && value?.type === 'hangup'} onClick={() => select('hangup')}>
                    <PhoneOff className="h-4 w-4 text-red-500 shrink-0" />
                    <span className="text-sm text-red-500 font-medium">Hangup</span>
                  </DestRow>
                  {!multiple && value?.type && (
                    <DestRow onClick={() => { onChange(EMPTY_DEST); setOpen(false) }}>
                      <X className="h-4 w-4 text-muted-foreground shrink-0" />
                      <span className="text-sm text-muted-foreground">Clear</span>
                    </DestRow>
                  )}
                  {multiple && multiArr.length > 0 && (
                    <DestRow onClick={() => { onChange([]); setOpen(false) }}>
                      <X className="h-4 w-4 text-muted-foreground shrink-0" />
                      <span className="text-sm text-muted-foreground">Clear all</span>
                    </DestRow>
                  )}
                </div>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
