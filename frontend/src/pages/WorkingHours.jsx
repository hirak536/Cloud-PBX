import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { selectAuth } from '@/store'
import { canPerformAction } from '@/lib/permissions'
import { workingHours as api } from '@/api'
import DestinationPicker, { DEST_META, EMPTY_DEST } from '@/components/DestinationPicker'
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
import { Plus, Pencil, Trash2, Search, Loader2, Clock, X, Check } from 'lucide-react'
import { cn } from '@/lib/utils'

// ─── Constants ───────────────────────────────────────────────────────────────

const DAYS = [
  { dow: 1, name: 'Monday',    short: 'Mon' },
  { dow: 2, name: 'Tuesday',   short: 'Tue' },
  { dow: 3, name: 'Wednesday', short: 'Wed' },
  { dow: 4, name: 'Thursday',  short: 'Thu' },
  { dow: 5, name: 'Friday',    short: 'Fri' },
  { dow: 6, name: 'Saturday',  short: 'Sat' },
  { dow: 7, name: 'Sunday',    short: 'Sun' },
]

// The grid is measured in MINUTES (0–1440) for exact 1-minute precision.
// Rendered at 0.4 px/min → 24 px/hour (unchanged from the old 5-min × 2px grid).
const MINUTES_PER_DAY = 1440
const SLOTS    = Array.from({ length: MINUTES_PER_DAY }, (_, i) => i)  // one entry per minute
const SLOT_H   = 24 / 60   // px per minute (0.4) → 24px/hour
const LABEL_W  = 44

const TIMEZONES = [
  { group: 'US & Canada', zones: [
    { value: 'America/New_York',    label: 'Eastern (ET)  — UTC-5/4'   },
    { value: 'America/Chicago',     label: 'Central (CT)  — UTC-6/5'   },
    { value: 'America/Denver',      label: 'Mountain (MT) — UTC-7/6'   },
    { value: 'America/Phoenix',     label: 'Arizona (MST) — UTC-7'     },
    { value: 'America/Los_Angeles', label: 'Pacific (PT)  — UTC-8/7'   },
    { value: 'America/Anchorage',   label: 'Alaska (AKT)  — UTC-9/8'   },
    { value: 'Pacific/Honolulu',    label: 'Hawaii (HST)  — UTC-10'    },
  ]},
  { group: 'Europe', zones: [
    { value: 'UTC',                 label: 'UTC — UTC+0'               },
    { value: 'Europe/London',       label: 'London (GMT)  — UTC+0/1'   },
    { value: 'Europe/Paris',        label: 'Paris (CET)   — UTC+1/2'   },
    { value: 'Europe/Berlin',       label: 'Berlin (CET)  — UTC+1/2'   },
    { value: 'Europe/Moscow',       label: 'Moscow (MSK)  — UTC+3'     },
  ]},
  { group: 'Asia & Pacific', zones: [
    { value: 'Asia/Dubai',          label: 'Dubai (GST)   — UTC+4'     },
    { value: 'Asia/Karachi',        label: 'Karachi (PKT) — UTC+5'     },
    { value: 'Asia/Kolkata',        label: 'India (IST)   — UTC+5:30'  },
    { value: 'Asia/Dhaka',          label: 'Dhaka (BST)   — UTC+6'     },
    { value: 'Asia/Bangkok',        label: 'Bangkok (ICT) — UTC+7'     },
    { value: 'Asia/Shanghai',       label: 'China (CST)   — UTC+8'     },
    { value: 'Asia/Tokyo',          label: 'Tokyo (JST)   — UTC+9'     },
    { value: 'Australia/Sydney',    label: 'Sydney (AEST) — UTC+10/11' },
    { value: 'Pacific/Auckland',    label: 'Auckland (NZST)— UTC+12/13'},
  ]},
]


const EMPTY_FORM = {
  working_hours_name: '',
  working_hours_description: '',
  working_hours_enabled: true,
  timezone: 'America/Chicago',
  open_dest:   { ...EMPTY_DEST },
  closed_dest: { ...EMPTY_DEST },
}

// ─── Slot ↔ time helpers ──────────────────────────────────────────────────────

// slot == minute-of-day (0–1440). 1-minute precision, no rounding.
const slotToTime  = (slot) => { const h = Math.floor(slot / 60), m = slot % 60; return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}` }
const timeToSlot  = (t)    => { if (!t) return 0; const [h, m] = t.split(':').map(Number); return h * 60 + m }
const slotToLabel = (slot) => { if (slot % 60 !== 0) return ''; const h = slot / 60; if (h === 0) return '12 am'; if (h < 12) return `${h} am`; if (h === 12) return '12 pm'; return `${h - 12} pm` }

// ─── Grid ↔ API converters ───────────────────────────────────────────────────
// grid shape: { [dow]: [{start, end}, ...] }  — each range is [start, end) in minutes-of-day

const makeEmptyGrid   = () => { const g = {}; for (const { dow } of DAYS) g[dow] = []; return g }
const makeDefaultGrid = () => { const g = {}; for (const { dow } of DAYS) g[dow] = dow <= 5 ? [{ start: 540, end: 1020 }] : []; return g }
// 540 = 9:00 (9×60), 1020 = 17:00 (17×60)

const gridToApiDays = (grid) => {
  const days = []
  for (const { dow } of DAYS) {
    for (const { start, end } of grid[dow]) {
      if (end > start) days.push({ day_of_week: dow, is_open: true, open_time: slotToTime(start), close_time: slotToTime(end) })
    }
  }
  return days
}

const apiDaysToGrid = (days) => {
  const grid = makeEmptyGrid()
  for (const slot of days ?? []) {
    if (!slot.is_open || !slot.open_time || !slot.close_time) continue
    const start = timeToSlot(slot.open_time), end = timeToSlot(slot.close_time)
    if (end > start) grid[slot.day_of_week].push({ start, end })
  }
  for (const { dow } of DAYS) grid[dow].sort((a, b) => a.start - b.start)
  return grid
}

const getRangesLabel = (ranges) => {
  if (!ranges.length) return null
  return ranges.map(({ start, end }) => `${slotToTime(start)}–${slotToTime(end)}`)
}


// ─── Vertical Weekly Grid ─────────────────────────────────────────────────────

const HANDLE_PX = 2
const TOTAL_H   = SLOTS.length * SLOT_H  // 1440 min × 0.4px = 576 px
// Gridline/label boundaries: every 30 minutes (hour lines + half-hour ticks).
// We render only these, not all 1440 minutes, to keep the DOM light.
const GRID_BOUNDARIES = Array.from({ length: MINUTES_PER_DAY / 30 + 1 }, (_, i) => i * 30)

function DayColumn({ ranges, onChange, gridRef, alignRight }) {
  const dragInfo = useRef(null)  // { idx, mode, startY, origStart, origEnd, allRanges }
  const colRef   = useRef(null)
  const [editIdx, setEditIdx]   = useState(null)   // index of block being typed-edited, or null
  const [draft, setDraft]       = useState({ open: '', close: '' })

  const openEditor = (e, idx) => {
    e.preventDefault(); e.stopPropagation()
    const r = ranges[idx]
    setDraft({ open: slotToTime(r.start), close: slotToTime(r.end) })
    setEditIdx(idx)
  }

  const saveEditor = (e) => {
    e.preventDefault(); e.stopPropagation()
    const start = timeToSlot(draft.open), end = timeToSlot(draft.close)
    if (end <= start) return  // invalid range — keep editor open
    onChange(ranges
      .map((r, i) => i === editIdx ? { start, end } : r)
      .sort((a, b) => a.start - b.start))
    setEditIdx(null)
  }

  const yToSlot = (clientY) => {
    const containerRect = gridRef?.current?.getBoundingClientRect() ?? colRef.current.getBoundingClientRect()
    const scrollTop = gridRef?.current?.scrollTop ?? 0
    const relY = clientY - containerRect.top + scrollTop
    return Math.max(0, Math.min(MINUTES_PER_DAY - 1, Math.round(relY / SLOT_H)))
  }

  useEffect(() => {
    const onMove = (e) => {
      if (!dragInfo.current) return
      const { idx, mode, startY, origStart, origEnd, allRanges } = dragInfo.current
      const dSlot = Math.round((e.clientY - startY) / SLOT_H)
      const next  = allRanges.map((r, i) => i === idx ? { ...r } : { ...r })
      if (mode === 'move') {
        const len = origEnd - origStart
        let ns = origStart + dSlot, ne = origEnd + dSlot
        if (ns < 0)   { ns = 0;       ne = len }
        if (ne > MINUTES_PER_DAY) { ne = MINUTES_PER_DAY; ns = MINUTES_PER_DAY - len }
        next[idx] = { start: ns, end: ne }
      } else if (mode === 'top') {
        next[idx] = { start: Math.max(0, Math.min(origStart + dSlot, origEnd - 1)), end: origEnd }
      } else if (mode === 'bottom') {
        next[idx] = { start: origStart, end: Math.min(MINUTES_PER_DAY, Math.max(origEnd + dSlot, origStart + 1)) }
      }
      onChange(next)
    }
    const onUp = () => { dragInfo.current = null }
    window.addEventListener('mousemove', onMove)
    window.addEventListener('mouseup',  onUp)
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp) }
  }, [onChange])

  const onMouseDownBar = (e, idx, mode) => {
    e.preventDefault(); e.stopPropagation()
    const r = ranges[idx]
    dragInfo.current = { idx, mode, startY: e.clientY, origStart: r.start, origEnd: r.end, allRanges: ranges }
  }

  const removeBlock = (e, idx) => {
    e.preventDefault(); e.stopPropagation()
    onChange(ranges.filter((_, i) => i !== idx))
  }

  const onClickColumn = (e) => {
    // ignore clicks on existing bars (they stopPropagation)
    const slot  = yToSlot(e.clientY)
    // drop a default 1-hour block centered on the click
    const start = Math.max(0, Math.min(MINUTES_PER_DAY - 60, slot - 30))
    const end   = start + 60
    // don't add if overlaps an existing block
    const overlaps = ranges.some(r => start < r.end && end > r.start)
    if (overlaps) return
    onChange([...ranges, { start, end }].sort((a, b) => a.start - b.start))
  }

  return (
    <div
      ref={colRef}
      className={cn(
        'relative flex-1 border-l border-border/20 cursor-cell',
        // While an editor is open, lift the WHOLE column above its siblings.
        // The editor popover is wider than one column and spills into the
        // neighbouring day; without this, a populated bar in that next column
        // (its own stacking context) paints over the editor and hides it.
        editIdx !== null ? 'z-40' : 'z-0',
      )}
      style={{ height: TOTAL_H }}
      onClick={onClickColumn}
    >
      {ranges.map(({ start, end }, idx) => {
        const barTop    = start * SLOT_H
        const barHeight = (end - start) * SLOT_H
        return (
          <div
            key={idx}
            className="absolute inset-x-0.5 rounded-md bg-primary/80 hover:bg-primary z-10 select-none group"
            style={{ top: barTop, height: barHeight }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Top resize handle */}
            <div
              className="absolute inset-x-0 top-0 bg-primary-foreground/20 hover:bg-primary-foreground/30 cursor-ns-resize rounded-t-md"
              style={{ height: HANDLE_PX }}
              onMouseDown={(e) => onMouseDownBar(e, idx, 'top')}
            />
            {/* Body — move */}
            <div
              className="absolute inset-x-0 cursor-grab active:cursor-grabbing"
              style={{ top: HANDLE_PX, bottom: HANDLE_PX }}
              onMouseDown={(e) => onMouseDownBar(e, idx, 'move')}
            >
              {barHeight >= 14 && (
                <span className="absolute inset-0 flex items-center justify-center text-[9px] font-semibold text-primary-foreground/90 leading-tight text-center pointer-events-none select-none px-0.5">
                  {slotToTime(start)}<br />{slotToTime(end)}
                </span>
              )}
            </div>
            {/* Edit (type exact times) button */}
            <button
              type="button"
              title="Edit times"
              onMouseDown={(e) => e.stopPropagation()}
              onClick={(e) => openEditor(e, idx)}
              className="absolute top-0.5 right-4 z-20 hidden group-hover:flex items-center justify-center h-3.5 w-3.5 rounded-full bg-primary-foreground/20 hover:bg-primary-foreground/40 text-primary-foreground transition-colors"
            >
              <Pencil className="h-2 w-2" />
            </button>
            {/* Remove button */}
            <button
              type="button"
              onMouseDown={(e) => e.stopPropagation()}
              onClick={(e) => removeBlock(e, idx)}
              className="absolute top-0.5 right-0.5 z-20 hidden group-hover:flex items-center justify-center h-3.5 w-3.5 rounded-full bg-primary-foreground/20 hover:bg-destructive text-primary-foreground hover:text-white transition-colors"
            >
              <X className="h-2 w-2" />
            </button>
            {/* Inline time editor */}
            {editIdx === idx && (
              <div
                onClick={(e) => e.stopPropagation()}
                onMouseDown={(e) => e.stopPropagation()}
                className={cn(
                  'absolute z-30 flex w-max items-center gap-1 rounded-lg border border-border bg-popover p-1.5 shadow-md text-foreground',
                  // open upward when the block sits in the lower half of the day so the
                  // editor doesn't get clipped by the grid wrapper's bottom edge
                  start > 720 ? 'bottom-full mb-1' : 'top-full mt-1',
                  // anchor to the right edge for the last couple of columns so the
                  // wide editor doesn't spill past the grid's right border
                  alignRight ? 'right-0' : 'left-0',
                )}
              >
                <input
                  type="time" value={draft.open}
                  onChange={(e) => setDraft(d => ({ ...d, open: e.target.value }))}
                  className="h-6 w-[112px] rounded border border-border bg-background px-1.5 text-[11px]"
                />
                <span className="text-[10px] text-muted-foreground">–</span>
                <input
                  type="time" value={draft.close}
                  onChange={(e) => setDraft(d => ({ ...d, close: e.target.value }))}
                  className="h-6 w-[112px] rounded border border-border bg-background px-1.5 text-[11px]"
                />
                <button type="button" title="Apply" onClick={saveEditor}
                  className="flex items-center justify-center h-6 w-6 rounded bg-primary text-primary-foreground hover:bg-primary/90">
                  <Check className="h-3 w-3" />
                </button>
                <button type="button" title="Cancel" onClick={(e) => { e.stopPropagation(); setEditIdx(null) }}
                  className="flex items-center justify-center h-6 w-6 rounded border border-border hover:bg-muted">
                  <X className="h-3 w-3" />
                </button>
              </div>
            )}
            {/* Bottom resize handle */}
            <div
              className="absolute inset-x-0 bottom-0 bg-primary-foreground/20 hover:bg-primary-foreground/30 cursor-ns-resize rounded-b-md"
              style={{ height: HANDLE_PX }}
              onMouseDown={(e) => onMouseDownBar(e, idx, 'bottom')}
            />
          </div>
        )
      })}
    </div>
  )
}

function TimeSlotGrid({ grid, setGrid, scrollRef }) {
  const clearDay = (dow) => setGrid(g => ({ ...g, [dow]: [] }))

  return (
    <div className="border border-border/60 rounded-xl select-none">
      {/* Day header */}
      <div className="flex bg-muted/50 border-b border-border/60 sticky top-0 z-10">
        <div className="shrink-0 border-r border-border/40" style={{ width: LABEL_W }} />
        {DAYS.map(({ dow, short, name }) => (
          <div key={dow} className="flex-1 flex flex-col items-center justify-center py-1.5 border-l border-border/40 min-w-0">
            <span className="text-xs font-semibold text-foreground">{short}</span>
            <button type="button" title={`Clear ${name}`} onClick={() => clearDay(dow)}
              className="mt-0.5 rounded-md p-0.5 text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors">
              <X className="h-2.5 w-2.5" />
            </button>
          </div>
        ))}
      </div>

      {/* Scrollable area: time axis + day columns */}
      <div ref={scrollRef} className="flex">
        {/* Time labels column */}
        <div className="shrink-0 border-r border-border/40 relative" style={{ width: LABEL_W, height: TOTAL_H }}>
          {GRID_BOUNDARIES.map((slot) => {
            const isHourBoundary = slot % 60 === 0
            const label = slotToLabel(slot)
            return (
              <div
                key={slot}
                className={cn(
                  'absolute w-full flex items-center justify-end pr-2 text-[9px] text-muted-foreground',
                  isHourBoundary ? 'border-t border-border/30' : 'border-t border-border/[0.08]',
                )}
                style={{ top: slot * SLOT_H, height: 60 * SLOT_H }}
              >
                {label}
              </div>
            )
          })}
        </div>

        {/* Grid lines overlay + day columns */}
        <div className="flex flex-1 relative">
          {/* Horizontal grid lines (rendered once, shared across all columns) */}
          <div className="absolute inset-0 pointer-events-none">
            {GRID_BOUNDARIES.map((slot) => (
              slot % 60 === 0 ? (
                <div key={slot} className="absolute inset-x-0 border-t border-border/30" style={{ top: slot * SLOT_H }} />
              ) : (
                <div key={slot} className="absolute inset-x-0 border-t border-border/[0.08]" style={{ top: slot * SLOT_H }} />
              )
            ))}
            {/* Business hours background — 08:00 (480) to 18:00 (1080) */}
            <div className="absolute inset-x-0 bg-muted/20 pointer-events-none" style={{ top: 480 * SLOT_H, height: (1080 - 480) * SLOT_H }} />
          </div>

          {/* Day columns */}
          {DAYS.map(({ dow }, di) => (
            <DayColumn
              key={dow}
              alignRight={di >= DAYS.length - 2}
              ranges={grid[dow]}
              onChange={(newRanges) => setGrid(g => ({ ...g, [dow]: newRanges }))}
              gridRef={scrollRef}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Summary strip ────────────────────────────────────────────────────────────

function ScheduleSummary({ grid }) {
  return (
    <div className="grid grid-cols-7 gap-1 text-[10px]">
      {DAYS.map(({ dow, short }) => {
        const ranges = getRangesLabel(grid[dow])
        return (
          <div key={dow} className="flex flex-col gap-0.5">
            <span className="font-semibold text-foreground">{short}</span>
            {ranges
              ? ranges.map((r, i) => <Badge key={i} variant="secondary" className="text-[9px] px-1 py-0 w-fit">{r}</Badge>)
              : <span className="text-muted-foreground italic">Closed</span>}
          </div>
        )
      })}
    </div>
  )
}

// ─── Preset strip ─────────────────────────────────────────────────────────────

function GridPresets({ setGrid }) {
  const presets = [
    { label: 'Mon–Fri 9–5', fn: () => { const g = makeEmptyGrid(); for (let d = 1; d <= 5; d++) g[d] = [{ start: 540, end: 1020 }]; return g } },
    { label: 'Mon–Fri 8–6', fn: () => { const g = makeEmptyGrid(); for (let d = 1; d <= 5; d++) g[d] = [{ start: 480, end: 1080 }]; return g } },
    { label: 'Mon–Sat 9–5', fn: () => { const g = makeEmptyGrid(); for (let d = 1; d <= 6; d++) g[d] = [{ start: 540, end: 1020 }]; return g } },
    { label: '24 / 7',      fn: () => { const g = makeEmptyGrid(); for (let d = 1; d <= 7; d++) g[d] = [{ start: 0,   end: MINUTES_PER_DAY }]; return g } },
    { label: 'Clear All',   fn: makeEmptyGrid },
  ]
  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      <span className="text-[11px] text-muted-foreground font-medium">Presets:</span>
      {presets.map(({ label, fn }) => (
        <button key={label} type="button" onClick={() => setGrid(fn())}
          className="text-[11px] px-2.5 py-1 rounded-lg border border-border hover:bg-muted transition-colors font-medium">
          {label}
        </button>
      ))}
    </div>
  )
}

// ─── Main page ────────────────────────────────────────────────────────────────


export default function WorkingHours() {
  const { user: authUser } = useSelector(selectAuth)
  const canAdd    = canPerformAction(authUser, 'working-hours', 'add')
  const canEdit   = canPerformAction(authUser, 'working-hours', 'edit')
  const canDelete = canPerformAction(authUser, 'working-hours', 'delete')

  const [rows, setRows]               = useState([])
  const [loading, setLoading]         = useState(true)
  const [search, setSearch]           = useState('')
  const debouncedSearch               = useDebounce(search, 300)
  const [dialogOpen, setDialogOpen]   = useState(false)
  const [editId, setEditId]           = useState(null)
  const [form, setForm]               = useState(EMPTY_FORM)
  const [grid, setGrid]               = useState(makeDefaultGrid)
  const [saving, setSaving]           = useState(false)
  const [formError, setFormError]     = useState('')
  const errorRef                      = useRef(null)
  const [deleting, setDeleting]       = useState(null)
  const [tzTime, setTzTime]           = useState('')
  const { destData, destLoading, loadDestData } = useDestinationData()
  const scrollRef                               = useRef(null)
  const navigate                                = useNavigate()

  // Scroll the error banner into view whenever a validation error appears.
  useEffect(() => {
    if (formError) errorRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [formError])
  const { id: routeId }                         = useParams()

  useEffect(() => {
    const tick = () => {
      try {
        setTzTime(new Intl.DateTimeFormat('en-US', {
          timeZone: form.timezone, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: true,
        }).format(new Date()))
      } catch { setTzTime('') }
    }
    tick(); const id = setInterval(tick, 1000); return () => clearInterval(id)
  }, [form.timezone])

  useEffect(() => {
    if (dialogOpen) loadDestData()
  }, [dialogOpen, loadDestData])

  const load = useCallback(async () => {
    setLoading(true)
    try { const { data } = await api.list(debouncedSearch ? { search: debouncedSearch } : {}); setRows(Array.isArray(data) ? data : data.results || []) }
    finally { setLoading(false) }
  }, [search])

  useEffect(() => { load() }, [load])
  useEffect(() => { if (dialogOpen && scrollRef.current) scrollRef.current.scrollTop = 480 * SLOT_H }, [dialogOpen])
// scroll to 8 am: minute 480 (8h × 60min/h) × SLOT_H

  const f = (key) => (e) => setForm(p => ({ ...p, [key]: e.target.value }))

  const openCreate = () => { setEditId(null); setForm(EMPTY_FORM); setGrid(makeDefaultGrid()); setFormError(''); setDialogOpen(true) }

  const openEdit = async (r) => {
    const id = r.working_hours_uuid || r.id
    setEditId(id)
    setForm({ working_hours_name: r.working_hours_name || '', working_hours_description: r.working_hours_description || '', working_hours_enabled: r.working_hours_enabled !== false, timezone: r.timezone || 'America/Chicago', open_dest: { ...EMPTY_DEST }, closed_dest: { ...EMPTY_DEST } })
    setGrid(makeEmptyGrid()); setFormError(''); setDialogOpen(true)
    try {
      const { data } = await api.get(id)
      setGrid(apiDaysToGrid(data.days || []))
      setForm(p => ({
        ...p,
        working_hours_name:        data.working_hours_name ?? p.working_hours_name,
        working_hours_description: data.working_hours_description ?? p.working_hours_description,
        working_hours_enabled:     data.working_hours_enabled !== false,
        timezone:                  data.timezone || p.timezone,
        open_dest:   { type: data.open_dest_type === 'external' && data.open_dest_external_number ? 'number' : (data.open_dest_type || ''), target_uuid: data.open_dest_target_uuid || '', external_number: data.open_dest_external_number || '' },
        closed_dest: { type: data.closed_dest_type === 'external' && data.closed_dest_external_number ? 'number' : (data.closed_dest_type || ''), target_uuid: data.closed_dest_target_uuid || '', external_number: data.closed_dest_external_number || '' },
      }))
    } catch { /* keep */ }
  }

  const closeEditor = () => {
    setDialogOpen(false)
    if (routeId) navigate('/working-hours', { replace: true })
  }

  // Deep-link: /working-hours/:id/edit opens the editor for that record.
  useEffect(() => {
    if (routeId && routeId !== editId) openEdit({ working_hours_uuid: routeId })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeId])

  const handleSave = async () => {
    if (!form.working_hours_name.trim()) { setFormError('Name is required.'); return }
    if (!form.open_dest.type)   { setFormError('Open Hours destination is required.'); return }
    if (!form.closed_dest.type) { setFormError('Closed Hours destination is required.'); return }
    setSaving(true); setFormError('')
    try {
      const payload = {
        working_hours_name: form.working_hours_name, working_hours_description: form.working_hours_description,
        working_hours_enabled: form.working_hours_enabled, timezone: form.timezone,
        open_dest_type: (form.open_dest.type === 'number' ? 'external' : form.open_dest.type) || '', open_dest_target_uuid: form.open_dest.target_uuid || null, open_dest_external_number: form.open_dest.external_number || '',
        closed_dest_type: (form.closed_dest.type === 'number' ? 'external' : form.closed_dest.type) || '', closed_dest_target_uuid: form.closed_dest.target_uuid || null, closed_dest_external_number: form.closed_dest.external_number || '',
        days: gridToApiDays(grid),
      }
      editId ? await api.update(editId, payload) : await api.create(payload)
      setDialogOpen(false); load()
    } catch (err) {
      const d = err?.response?.data
      setFormError(typeof d === 'string' ? d : Object.values(d || {}).flat().join(' ') || 'Save failed.')
    } finally { setSaving(false) }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this working hours schedule?')) return
    setDeleting(id)
    try { await api.delete(id); load() } finally { setDeleting(null) }
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Search schedules..." className="pl-8" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        {canAdd && (<Button size="sm" onClick={openCreate}><Plus className="h-4 w-4" />Add Schedule</Button>)}
      </div>

      {/* Table */}
      <Card><CardContent className="p-0 overflow-x-auto">
        <Table>
          <TableHeader><TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Extension</TableHead>
            <TableHead>Open Route</TableHead>
            <TableHead>Closed Route</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="w-20" />
          </TableRow></TableHeader>
          <TableBody>
            {loading
              ? [...Array(4)].map((_, i) => <TableRow key={i}>{[...Array(6)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}</TableRow>)
              : rows.length === 0
                ? <TableRow><TableCell colSpan={6} className="text-center py-10 text-muted-foreground">No working hours schedules found.</TableCell></TableRow>
                : rows.map((r) => {
                    const id = r.working_hours_uuid || r.id
                    const openMeta   = r.open_dest_type   ? DEST_META[r.open_dest_type]   : null
                    const closedMeta = r.closed_dest_type ? DEST_META[r.closed_dest_type] : null
                    return (
                      <TableRow key={id}>
                        <TableCell className="font-medium">{r.working_hours_name}</TableCell>
                        <TableCell className="font-mono text-sm">{r.dialplan_extension || '—'}</TableCell>
                        <TableCell>{openMeta   ? <Badge variant="success"   className={cn('text-xs', openMeta.color)}>{openMeta.label}</Badge>   : <span className="text-muted-foreground text-sm">—</span>}</TableCell>
                        <TableCell>{closedMeta ? <Badge variant="secondary" className={cn('text-xs', closedMeta.color)}>{closedMeta.label}</Badge> : <span className="text-muted-foreground text-sm">—</span>}</TableCell>
                        <TableCell><Badge variant={r.working_hours_enabled !== false ? 'success' : 'secondary'}>{r.working_hours_enabled !== false ? 'Active' : 'Disabled'}</Badge></TableCell>
                        <TableCell><div className="flex gap-1">
                          {canEdit && (<Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(r)}><Pencil className="h-3.5 w-3.5" /></Button>)}
                          {canDelete && (<Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive" onClick={() => handleDelete(id)} disabled={deleting === id}>
                            {deleting === id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                          </Button>)}
                        </div></TableCell>
                      </TableRow>
                    )
                  })}
          </TableBody>
        </Table>
      </CardContent></Card>

      {/* Dialog */}
      <Dialog open={dialogOpen} onOpenChange={(v) => { if (!v) closeEditor(); else setDialogOpen(true) }}>
        <DialogContent className="max-w-[min(95vw,860px)] p-0 overflow-hidden flex flex-col max-h-[95vh]">
          <DialogClose onClose={closeEditor} />

          {/* Header */}
          <DialogHeader className="px-6 pt-5 pb-4 border-b border-border/60 shrink-0">
            <DialogTitle className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary/10">
                <Clock className="h-4 w-4 text-primary" />
              </div>
              {editId ? 'Edit Schedule' : 'New Working Hours Schedule'}
            </DialogTitle>
          </DialogHeader>

          {/* Body */}
          <div className="overflow-y-auto flex-1 px-6 py-5 space-y-5">
            {formError && (
              <div ref={errorRef} className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-2.5 text-sm text-destructive scroll-mt-4">
                {formError}
              </div>
            )}

            {/* Name + Timezone */}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Schedule Name <span className="text-destructive">*</span></Label>
                <Input placeholder="Business Hours" value={form.working_hours_name} onChange={f('working_hours_name')} />
              </div>
              <div className="space-y-1.5">
                <div className="flex items-baseline justify-between">
                  <Label>Timezone</Label>
                  {tzTime && <span className="text-xs font-mono text-primary tabular-nums">{tzTime}</span>}
                </div>
                <Select value={form.timezone} onChange={f('timezone')}>
                  {TIMEZONES.map(({ group, zones }) => (
                    <optgroup key={group} label={group}>
                      {zones.map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
                    </optgroup>
                  ))}
                </Select>
              </div>
            </div>

            {/* Grid header */}
            <div className="flex items-center justify-between">
              <p className="text-sm font-semibold">Weekly Schedule</p>
              <GridPresets setGrid={setGrid} />
            </div>

            {/* Grid */}
            <TimeSlotGrid grid={grid} setGrid={setGrid} scrollRef={scrollRef} />

            {/* Destinations */}
            <div className="grid grid-cols-2 gap-3 pt-1 border-t border-border/50">
              <div className="space-y-1.5 pt-4">
                <Label className="flex items-center gap-1.5">
                  <span className="inline-block h-2 w-2 rounded-full bg-green-500" />
                  Destination when open <span className="text-destructive">*</span>
                </Label>
                <DestinationPicker value={form.open_dest} onChange={(d) => setForm(p => ({ ...p, open_dest: d }))} data={destData} loading={destLoading} placeholder="Select open destination…" />
              </div>
              <div className="space-y-1.5 pt-4">
                <Label className="flex items-center gap-1.5">
                  <span className="inline-block h-2 w-2 rounded-full bg-red-400" />
                  Destination when closed <span className="text-destructive">*</span>
                </Label>
                <DestinationPicker value={form.closed_dest} onChange={(d) => setForm(p => ({ ...p, closed_dest: d }))} data={destData} loading={destLoading} placeholder="Select closed destination…" />
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-2 px-6 py-4 border-t border-border/60 bg-muted/30 rounded-b-2xl shrink-0">
            <Button variant="outline" onClick={closeEditor}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              {editId ? 'Save Changes' : 'Create Schedule'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}
