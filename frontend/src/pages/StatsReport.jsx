import { useState, useCallback, useMemo } from 'react'
import { statsReport } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Calendar } from '@/components/ui/calendar'
import { Popover, PopoverTrigger, PopoverContent } from '@/components/ui/popover'
import {
  Loader2, RefreshCw, FileSpreadsheet, FileText,
  Phone, PhoneIncoming, PhoneOutgoing, PhoneMissed,
  PhoneOff, Voicemail, Clock, CalendarIcon,
} from 'lucide-react'
import { format } from 'date-fns'
import { toast } from 'sonner'

// ── Helpers ────────────────────────────────────────────────────────────────

function fmtDur(sec) {
  if (!sec) return '0:00:00'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
}

function defaultRange() {
  const end = new Date()
  const start = new Date(end)
  start.setHours(0, 0, 0, 0)
  return { startDate: start, endDate: end }
}

function fmtRangeLabel(start, end) {
  if (!start || !end) return ''
  return `${format(start, 'MMM d, yyyy h:mm a')} — ${format(end, 'MMM d, yyyy h:mm a')}`
}

function pad2(n) { return String(n).padStart(2, '0') }

// Merge a Date + HH:MM time string into a new Date
function applyTime(date, timeStr) {
  if (!date) return date
  const [h, m] = timeStr.split(':').map(Number)
  const d = new Date(date)
  d.setHours(h || 0, m || 0, 0, 0)
  return d
}

// ── Summary cards ─────────────────────────────────────────────────────────

function StatCard({ icon: Icon, label, value, sub, color = 'text-primary' }) {
  return (
    <div className="rounded-xl border bg-card p-4 flex gap-3 items-start shadow-sm">
      <div className={`mt-0.5 rounded-lg p-2 bg-muted ${color}`}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="flex flex-col min-w-0">
        <span className="text-xs text-muted-foreground font-medium">{label}</span>
        <span className="text-lg font-bold leading-tight">{value}</span>
        {sub && <span className="text-xs text-muted-foreground mt-0.5">{sub}</span>}
      </div>
    </div>
  )
}

function SummaryCards({ data }) {
  if (!data) return null

  const ua = data.user_activity ?? []
  const totals = ua.find(r => r.extension === 'TOTAL') ?? {}
  const ob = totals.outbound ?? {}
  const ib = totals.inbound ?? {}

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
      <StatCard icon={Phone}          label="Total Calls"       value={(totals.total_calls ?? 0).toLocaleString()} color="text-primary" />
      <StatCard icon={PhoneOutgoing}  label="Outbound Answered" value={(ob.answered ?? 0).toLocaleString()} sub={`of ${(ob.total ?? 0)} outbound`} color="text-green-500" />
      <StatCard icon={PhoneIncoming}  label="Inbound Answered"  value={(ib.answered ?? 0).toLocaleString()} sub={`of ${(ib.total ?? 0)} inbound`} color="text-blue-500" />
      <StatCard icon={PhoneMissed}    label="No Answer"         value={((ob.no_answer ?? 0) + (ib.no_answer ?? 0)).toLocaleString()} color="text-orange-500" />
      <StatCard icon={Voicemail}      label="Voicemail"         value={(ib.voicemail ?? 0).toLocaleString()} color="text-purple-500" />
      <StatCard icon={Clock}          label="Total Talk Time"   value={fmtDur(totals.total_talk_sec ?? 0)} color="text-teal-500" />
    </div>
  )
}

// ── User Activity ──────────────────────────────────────────────────────────

const UA_COLS = [
  { key: 'name',         label: 'Name (Extension)',  group: null,       sticky: true },
  { key: 'ob_answered',  label: 'Answered',          group: 'Outbound' },
  { key: 'ob_busy',      label: 'Busy',              group: 'Outbound' },
  { key: 'ob_no_answer', label: 'No Answer',         group: 'Outbound' },
  { key: 'ob_failed',    label: 'Failed',            group: 'Outbound' },
  { key: 'ob_congestion',label: 'Congestion',        group: 'Outbound' },
  { key: 'ob_total',     label: 'Total',             group: 'Outbound' },
  { key: 'ob_talk',      label: 'Talk Time',         group: 'Outbound' },
  { key: 'ob_avg',       label: 'Avg. Talk',         group: 'Outbound' },
  { key: 'ib_answered',  label: 'Answered',          group: 'Inbound'  },
  { key: 'ib_busy',      label: 'Busy',              group: 'Inbound'  },
  { key: 'ib_no_answer', label: 'No Answer',         group: 'Inbound'  },
  { key: 'ib_failed',    label: 'Failed',            group: 'Inbound'  },
  { key: 'ib_congestion',label: 'Congestion',        group: 'Inbound'  },
  { key: 'ib_voicemail', label: 'Voicemail',         group: 'Inbound'  },
  { key: 'ib_total',     label: 'Total',             group: 'Inbound'  },
  { key: 'ib_talk',      label: 'Talk Time',         group: 'Inbound'  },
  { key: 'ib_avg',       label: 'Avg. Talk',         group: 'Inbound'  },
  { key: 'total_talk',   label: 'Total Talk',        group: 'Summary'  },
  { key: 'total_calls',  label: 'Total Calls',       group: 'Summary'  },
]

const GROUP_COLORS = {
  Outbound: 'bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300',
  Inbound:  'bg-blue-50 dark:bg-blue-950/30 text-blue-700 dark:text-blue-300',
  Summary:  'bg-violet-50 dark:bg-violet-950/30 text-violet-700 dark:text-violet-300',
}

function uaVal(row, key) {
  if (key === 'name')         return row.extension === 'TOTAL' ? 'TOTAL' : `${row.name || '—'} (${row.extension})`
  if (key === 'ob_answered')  return row.outbound?.answered  ?? 0
  if (key === 'ob_busy')      return row.outbound?.busy      ?? 0
  if (key === 'ob_no_answer') return row.outbound?.no_answer ?? 0
  if (key === 'ob_failed')    return row.outbound?.failed    ?? 0
  if (key === 'ob_congestion')return row.outbound?.congestion?? 0
  if (key === 'ob_total')     return row.outbound?.total     ?? 0
  if (key === 'ob_talk')      return fmtDur(row.outbound?.talk_sec)
  if (key === 'ob_avg')       return fmtDur(row.outbound?.avg_talk_sec)
  if (key === 'ib_answered')  return row.inbound?.answered   ?? 0
  if (key === 'ib_busy')      return row.inbound?.busy       ?? 0
  if (key === 'ib_no_answer') return row.inbound?.no_answer  ?? 0
  if (key === 'ib_failed')    return row.inbound?.failed     ?? 0
  if (key === 'ib_congestion')return row.inbound?.congestion ?? 0
  if (key === 'ib_voicemail') return row.inbound?.voicemail  ?? 0
  if (key === 'ib_total')     return row.inbound?.total      ?? 0
  if (key === 'ib_talk')      return fmtDur(row.inbound?.talk_sec)
  if (key === 'ib_avg')       return fmtDur(row.inbound?.avg_talk_sec)
  if (key === 'total_talk')   return fmtDur(row.total_talk_sec)
  if (key === 'total_calls')  return row.total_calls ?? 0
  return ''
}

function UserActivityTable({ rows, search }) {
  const filtered = useMemo(() => {
    if (!rows?.length) return []
    const q = search.toLowerCase()
    return rows.filter(r =>
      r.extension === 'TOTAL' || r.extension === 'Other' ||
      !q ||
      r.name?.toLowerCase().includes(q) ||
      r.extension?.toLowerCase().includes(q)
    )
  }, [rows, search])

  if (!filtered.length) return <p className="text-sm text-muted-foreground py-8 text-center">No matching rows</p>

  const groups = ['Outbound', 'Inbound', 'Summary']

  return (
    <div className="overflow-auto rounded-xl border shadow-sm">
      <table className="text-xs border-collapse min-w-max w-full">
        <thead>
          <tr>
            <th
              className="sticky left-0 z-20 border-b border-r bg-muted px-3 py-2 text-left min-w-[200px] font-semibold"
              rowSpan={2}
            >
              Name (Extension)
            </th>
            {groups.map(g => {
              const cols = UA_COLS.filter(c => c.group === g)
              return (
                <th
                  key={g}
                  colSpan={cols.length}
                  className={`border-b border-r px-2 py-1.5 text-center text-xs font-semibold tracking-wide uppercase ${GROUP_COLORS[g]}`}
                >
                  {g}
                </th>
              )
            })}
          </tr>
          <tr className="bg-muted/50">
            {UA_COLS.filter(c => c.group !== null).map(col => (
              <th key={col.key} className="border-b border-r px-2 py-1.5 whitespace-nowrap text-center font-medium text-muted-foreground">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filtered.map((row, i) => {
            const isTotal = row.extension === 'TOTAL'
            const isOther = row.extension === 'Other'
            const hasActivity = (row.total_calls ?? 0) > 0
            return (
              <tr
                key={row.extension + i}
                className={
                  isTotal
                    ? 'bg-primary/10 font-bold border-t-2 border-primary/30'
                    : isOther
                    ? 'bg-muted/40 italic text-muted-foreground'
                    : hasActivity
                    ? 'hover:bg-muted/30'
                    : 'hover:bg-muted/10 opacity-50'
                }
              >
                {UA_COLS.map(col => {
                  const val = uaVal(row, col.key)
                  const isZero = (val === 0 || val === '0:00:00') && col.key !== 'name'
                  const isNameCol = col.key === 'name'
                  return (
                    <td
                      key={col.key}
                      className={[
                        'border-b border-r px-2 py-1.5 whitespace-nowrap',
                        isNameCol ? 'sticky left-0 z-10 bg-background font-medium' : 'text-center tabular-nums',
                        isZero ? 'text-muted-foreground/25' : '',
                        isTotal && !isNameCol ? 'font-bold' : '',
                      ].join(' ')}
                    >
                      {isNameCol && !isTotal && !isOther && hasActivity && (
                        <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-400 mr-1.5 mb-0.5" />
                      )}
                      {String(val)}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ── DID Activity ───────────────────────────────────────────────────────────

const DID_COLS = [
  { key: 'did_label',     label: 'DID',              group: null,       sticky: true },
  { key: 'ib_total',      label: 'Total',             group: 'Inbound'  },
  { key: 'ib_answered',   label: 'Answered',          group: 'Inbound'  },
  { key: 'ib_talk',       label: 'Talk Duration',     group: 'Inbound'  },
  { key: 'ib_avg',        label: 'Avg. Talk',         group: 'Inbound'  },
  { key: 'ib_busy',       label: 'Busy',              group: 'Inbound'  },
  { key: 'ib_no_answer',  label: 'No Answer',         group: 'Inbound'  },
  { key: 'ib_no_ans_dur', label: 'NA Duration',       group: 'Inbound'  },
  { key: 'ib_failed',     label: 'Failed',            group: 'Inbound'  },
  { key: 'ib_congestion', label: 'Congestion',        group: 'Inbound'  },
  { key: 'ob_total',      label: 'Total',             group: 'Outbound' },
  { key: 'ob_answered',   label: 'Answered',          group: 'Outbound' },
  { key: 'ob_talk',       label: 'Talk Duration',     group: 'Outbound' },
  { key: 'ob_avg',        label: 'Avg. Talk',         group: 'Outbound' },
  { key: 'ob_busy',       label: 'Busy',              group: 'Outbound' },
  { key: 'ob_no_answer',  label: 'No Answer',         group: 'Outbound' },
  { key: 'ob_failed',     label: 'Failed',            group: 'Outbound' },
  { key: 'ob_congestion', label: 'Congestion',        group: 'Outbound' },
  { key: 'total_calls',   label: 'Total Calls',       group: 'Summary'  },
  { key: 'total_talk',    label: 'Total Talk',        group: 'Summary'  },
]

function didVal(row, key) {
  if (key === 'did_label')     return row.did === 'TOTAL' ? 'TOTAL' : (row.label ? `${row.did} — ${row.label}` : row.did)
  if (key === 'ib_total')      return row.inbound?.total      ?? 0
  if (key === 'ib_answered')   return row.inbound?.answered   ?? 0
  if (key === 'ib_talk')       return fmtDur(row.inbound?.talk_sec)
  if (key === 'ib_avg')        return fmtDur(row.inbound?.avg_talk_sec)
  if (key === 'ib_busy')       return row.inbound?.busy       ?? 0
  if (key === 'ib_no_answer')  return row.inbound?.no_answer  ?? 0
  if (key === 'ib_no_ans_dur') return fmtDur(row.inbound?.no_answer_sec)
  if (key === 'ib_failed')     return row.inbound?.failed     ?? 0
  if (key === 'ib_congestion') return row.inbound?.congestion ?? 0
  if (key === 'ob_total')      return row.outbound?.total      ?? 0
  if (key === 'ob_answered')   return row.outbound?.answered   ?? 0
  if (key === 'ob_talk')       return fmtDur(row.outbound?.talk_sec)
  if (key === 'ob_avg')        return fmtDur(row.outbound?.avg_talk_sec)
  if (key === 'ob_busy')       return row.outbound?.busy       ?? 0
  if (key === 'ob_no_answer')  return row.outbound?.no_answer  ?? 0
  if (key === 'ob_failed')     return row.outbound?.failed     ?? 0
  if (key === 'ob_congestion') return row.outbound?.congestion ?? 0
  if (key === 'total_calls')   return row.total_calls    ?? 0
  if (key === 'total_talk')    return fmtDur(row.total_talk_sec)
  return ''
}

function DidActivityTable({ rows, search }) {
  const filtered = useMemo(() => {
    if (!rows?.length) return []
    const q = search.toLowerCase()
    return rows.filter(r =>
      r.did === 'TOTAL' || !q ||
      r.did?.toLowerCase().includes(q) ||
      r.label?.toLowerCase().includes(q)
    )
  }, [rows, search])

  if (!filtered.length) return <p className="text-sm text-muted-foreground py-8 text-center">No matching rows</p>

  const groups = ['Inbound', 'Outbound', 'Summary']

  return (
    <div className="overflow-auto rounded-xl border shadow-sm">
      <table className="text-xs border-collapse min-w-max w-full">
        <thead>
          <tr>
            <th
              className="sticky left-0 z-20 border-b border-r bg-muted px-3 py-2 text-left min-w-[260px] font-semibold"
              rowSpan={2}
            >
              DID
            </th>
            {groups.map(g => {
              const cols = DID_COLS.filter(c => c.group === g)
              return (
                <th
                  key={g}
                  colSpan={cols.length}
                  className={`border-b border-r px-2 py-1.5 text-center text-xs font-semibold tracking-wide uppercase ${GROUP_COLORS[g]}`}
                >
                  {g}
                </th>
              )
            })}
          </tr>
          <tr className="bg-muted/50">
            {DID_COLS.filter(c => c.group !== null).map(col => (
              <th key={col.key} className="border-b border-r px-2 py-1.5 whitespace-nowrap text-center font-medium text-muted-foreground">
                {col.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filtered.map((row, i) => {
            const isTotal = row.did === 'TOTAL'
            const hasActivity = (row.total_calls ?? 0) > 0
            return (
              <tr
                key={row.did + i}
                className={
                  isTotal
                    ? 'bg-primary/10 font-bold border-t-2 border-primary/30'
                    : hasActivity
                    ? 'hover:bg-muted/30'
                    : 'hover:bg-muted/10 opacity-50'
                }
              >
                {DID_COLS.map(col => {
                  const val = didVal(row, col.key)
                  const isZero = (val === 0 || val === '0:00:00') && col.key !== 'did_label'
                  return (
                    <td
                      key={col.key}
                      className={[
                        'border-b border-r px-2 py-1.5 whitespace-nowrap',
                        col.sticky ? 'sticky left-0 z-10 bg-background font-medium text-left' : 'text-center tabular-nums',
                        isZero ? 'text-muted-foreground/25' : '',
                        isTotal && col.key !== 'did_label' ? 'font-bold' : '',
                      ].join(' ')}
                    >
                      {String(val)}
                    </td>
                  )
                })}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ── Export helpers ─────────────────────────────────────────────────────────

function buildUaSheetData(rows) {
  const headers = UA_COLS.map(c => c.label)
  const body = rows.map(row => UA_COLS.map(c => {
    const v = uaVal(row, c.key)
    return typeof v === 'number' ? v : String(v)
  }))
  return [headers, ...body]
}

function buildDidSheetData(rows) {
  const visibleCols = DID_COLS
  const headers = visibleCols.map(c => c.label)
  const body = rows.map(row => visibleCols.map(c => {
    const v = didVal(row, c.key)
    return typeof v === 'number' ? v : String(v)
  }))
  return [headers, ...body]
}

async function exportExcel(data, rangeLabel) {
  // Lazy-load the heavy xlsx lib so it stays out of the main bundle.
  const XLSX = await import('xlsx')
  const wb = XLSX.utils.book_new()

  const uaData = buildUaSheetData(data.user_activity ?? [])
  const didData = buildDidSheetData(data.did_activity ?? [])

  const wsUa = XLSX.utils.aoa_to_sheet(uaData)
  const wsDid = XLSX.utils.aoa_to_sheet(didData)

  XLSX.utils.book_append_sheet(wb, wsUa, 'User Activity')
  XLSX.utils.book_append_sheet(wb, wsDid, 'DID Activity')

  const filename = `stats-report-${new Date().toISOString().slice(0, 10)}.xlsx`
  XLSX.writeFile(wb, filename)
  toast.success('Excel file downloaded')
}

async function exportPdf(data, rangeLabel) {
  // Lazy-load the heavy pdf libs so they stay out of the main bundle.
  const [{ default: jsPDF }, { default: autoTable }] = await Promise.all([
    import('jspdf'),
    import('jspdf-autotable'),
  ])
  const doc = new jsPDF({ orientation: 'landscape', unit: 'pt', format: 'a3' })

  doc.setFontSize(14)
  doc.text('Stats Report', 40, 40)
  doc.setFontSize(9)
  doc.setTextColor(120)
  doc.text(rangeLabel, 40, 58)
  doc.setTextColor(0)

  // User Activity
  doc.setFontSize(11)
  doc.text('User Activity', 40, 80)

  const uaData = buildUaSheetData(data.user_activity ?? [])
  autoTable(doc, {
    startY: 90,
    head: [uaData[0]],
    body: uaData.slice(1),
    styles: { fontSize: 7, cellPadding: 2 },
    headStyles: { fillColor: [59, 130, 246], textColor: 255, fontStyle: 'bold' },
    alternateRowStyles: { fillColor: [245, 247, 250] },
    didParseCell(data) {
      const lastRow = uaData.length - 2
      if (data.row.index === lastRow) {
        data.cell.styles.fillColor = [219, 234, 254]
        data.cell.styles.fontStyle = 'bold'
      }
    },
  })

  // DID Activity on new page
  doc.addPage()
  doc.setFontSize(14)
  doc.text('Stats Report', 40, 40)
  doc.setFontSize(9)
  doc.setTextColor(120)
  doc.text(rangeLabel, 40, 58)
  doc.setTextColor(0)
  doc.setFontSize(11)
  doc.text('DID Activity', 40, 80)

  const didData = buildDidSheetData(data.did_activity ?? [])
  autoTable(doc, {
    startY: 90,
    head: [didData[0]],
    body: didData.slice(1),
    styles: { fontSize: 7, cellPadding: 2 },
    headStyles: { fillColor: [99, 102, 241], textColor: 255, fontStyle: 'bold' },
    alternateRowStyles: { fillColor: [245, 247, 250] },
    didParseCell(data) {
      const lastRow = didData.length - 2
      if (data.row.index === lastRow) {
        data.cell.styles.fillColor = [219, 234, 254]
        data.cell.styles.fontStyle = 'bold'
      }
    },
  })

  doc.save(`stats-report-${new Date().toISOString().slice(0, 10)}.pdf`)
  toast.success('PDF file downloaded')
}

// ── Quick range presets ────────────────────────────────────────────────────

const PRESETS = [
  { label: 'Today',      fn: () => { const e = new Date(); const s = new Date(e); s.setHours(0,0,0,0); return { startDate: s, endDate: e } } },
  { label: 'Yesterday',  fn: () => { const s = new Date(); s.setDate(s.getDate()-1); s.setHours(0,0,0,0); const e = new Date(s); e.setHours(23,59,59); return { startDate: s, endDate: e } } },
  { label: 'This Week',  fn: () => { const e = new Date(); const s = new Date(e); s.setDate(s.getDate() - s.getDay()); s.setHours(0,0,0,0); return { startDate: s, endDate: e } } },
  { label: 'This Month', fn: () => { const e = new Date(); const s = new Date(e.getFullYear(), e.getMonth(), 1); return { startDate: s, endDate: e } } },
  { label: 'Last Month', fn: () => { const now = new Date(); const s = new Date(now.getFullYear(), now.getMonth()-1, 1); const e = new Date(now.getFullYear(), now.getMonth(), 0, 23, 59, 59); return { startDate: s, endDate: e } } },
]

// ── Main Page ──────────────────────────────────────────────────────────────

const TABS = ['User Activity', 'DID Activity']

export default function StatsReport() {
  const def = defaultRange()
  const [startDate, setStartDate] = useState(def.startDate)
  const [endDate,   setEndDate]   = useState(def.endDate)
  const [startTime, setStartTime] = useState('00:00')
  const [endTime,   setEndTime]   = useState(() => `${pad2(def.endDate.getHours())}:${pad2(def.endDate.getMinutes())}`)
  const [calOpen,   setCalOpen]   = useState(false)
  const [activeTab, setActiveTab]   = useState(0)
  const [loading,   setLoading]     = useState(false)
  const [data,      setData]        = useState(null)
  const [search,    setSearch]      = useState('')
  const [rangeLabel, setRangeLabel] = useState('')

  // Merged Date objects with time applied
  const startDT = useMemo(() => applyTime(startDate, startTime), [startDate, startTime])
  const endDT   = useMemo(() => applyTime(endDate,   endTime),   [endDate,   endTime])

  const runReport = useCallback(async () => {
    if (!startDT || !endDT) return
    setLoading(true)
    setSearch('')
    try {
      const res = await statsReport.get({
        start: startDT.toISOString(),
        end:   endDT.toISOString(),
      })
      setData(res.data)
      setRangeLabel(fmtRangeLabel(startDT, endDT))
    } catch (err) {
      toast.error(err?.response?.data?.detail || 'Failed to load stats report')
    } finally {
      setLoading(false)
    }
  }, [startDT, endDT])

  function applyPreset(preset) {
    const { startDate: s, endDate: e } = preset.fn()
    setStartDate(s)
    setEndDate(e)
    setStartTime(`${pad2(s.getHours())}:${pad2(s.getMinutes())}`)
    setEndTime(`${pad2(e.getHours())}:${pad2(e.getMinutes())}`)
    setCalOpen(false)
  }

  // react-day-picker range selection handler
  function handleRangeSelect(range) {
    if (range?.from) setStartDate(range.from)
    if (range?.to)   setEndDate(range.to)
    else if (range?.from) setEndDate(range.from)
  }

  const rowCount = data
    ? activeTab === 0 ? (data.user_activity?.length ?? 0) : (data.did_activity?.length ?? 0)
    : 0

  // Button label
  const rangeButtonLabel = startDate && endDate
    ? `${format(startDate, 'MMM d, yyyy')}  →  ${format(endDate, 'MMM d, yyyy')}`
    : 'Pick date range'

  return (
    <div className="flex flex-col gap-5 p-5 min-h-0">

      {/* Header row */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Stats Report</h1>
          <p className="text-sm text-muted-foreground">Per-extension and per-DID call activity summary</p>
        </div>
        {data && (
          <div className="flex gap-2">
            <Button variant="outline" size="sm" className="gap-1.5" onClick={() => exportExcel(data, rangeLabel)}>
              <FileSpreadsheet className="h-4 w-4 text-green-600" />
              Export Excel
            </Button>
            <Button variant="outline" size="sm" className="gap-1.5" onClick={() => exportPdf(data, rangeLabel)}>
              <FileText className="h-4 w-4 text-red-500" />
              Export PDF
            </Button>
          </div>
        )}
      </div>

      {/* Filter bar */}
      <div className="rounded-xl border bg-card shadow-sm p-4 flex flex-wrap items-end gap-3">

        {/* Presets */}
        <div className="flex flex-col gap-1.5">
          <span className="text-xs text-muted-foreground font-medium">Quick Range</span>
          <div className="flex gap-1.5 flex-wrap">
            {PRESETS.map(p => (
              <button
                key={p.label}
                onClick={() => applyPreset(p)}
                className="px-2.5 py-1 rounded-md text-xs border hover:bg-muted transition-colors font-medium"
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        <div className="h-8 w-px bg-border hidden sm:block" />

        {/* Date range picker */}
        <div className="flex flex-col gap-1.5">
          <span className="text-xs text-muted-foreground font-medium">Date Range</span>
          <Popover open={calOpen} onOpenChange={setCalOpen}>
            <PopoverTrigger asChild>
              <Button
                variant="outline"
                className="h-9 gap-2 text-sm font-normal min-w-[260px] justify-start"
              >
                <CalendarIcon className="h-4 w-4 text-muted-foreground" />
                {rangeButtonLabel}
              </Button>
            </PopoverTrigger>
            <PopoverContent align="start" className="max-w-[calc(100vw-2rem)] overflow-x-auto p-3">
              <Calendar
                mode="range"
                selected={{ from: startDate, to: endDate }}
                onSelect={handleRangeSelect}
                numberOfMonths={2}
                initialFocus
              />
              <div className="border-t pt-3 mt-1 flex gap-2 justify-end">
                <Button size="sm" onClick={() => setCalOpen(false)}>
                  Apply
                </Button>
              </div>
            </PopoverContent>
          </Popover>
        </div>

        {/* Time pickers */}
        <div className="flex gap-3 items-end">
          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-muted-foreground font-medium">From time</label>
            <Input
              type="time"
              value={startTime}
              onChange={e => setStartTime(e.target.value)}
              className="w-28 h-9 text-sm"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <label className="text-xs text-muted-foreground font-medium">To time</label>
            <Input
              type="time"
              value={endTime}
              onChange={e => setEndTime(e.target.value)}
              className="w-28 h-9 text-sm"
            />
          </div>
        </div>

        <Button onClick={runReport} disabled={loading} className="gap-2 h-9">
          {loading
            ? <Loader2 className="h-4 w-4 animate-spin" />
            : <RefreshCw className="h-4 w-4" />}
          Run Report
        </Button>
      </div>

      {/* Empty state */}
      {!data && !loading && (
        <div className="flex flex-col items-center justify-center py-24 text-muted-foreground gap-3 rounded-xl border border-dashed">
          <PhoneOff className="h-10 w-10 opacity-20" />
          <p className="text-sm">Select a date range and click <strong className="text-foreground">Run Report</strong></p>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex flex-col items-center justify-center py-24 gap-3 text-muted-foreground rounded-xl border">
          <Loader2 className="h-8 w-8 animate-spin" />
          <p className="text-sm">Fetching call data…</p>
        </div>
      )}

      {/* Results */}
      {data && !loading && (
        <>
          {/* Summary cards */}
          <SummaryCards data={data} />

          {/* Range label */}
          {rangeLabel && (
            <p className="text-xs text-muted-foreground -mt-1">
              Showing data for <span className="font-medium text-foreground">{rangeLabel}</span>
            </p>
          )}

          {/* Tabs + search */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex border-b gap-0">
              {TABS.map((tab, i) => (
                <button
                  key={tab}
                  onClick={() => { setActiveTab(i); setSearch('') }}
                  className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors flex items-center gap-1.5 ${
                    activeTab === i
                      ? 'border-primary text-primary'
                      : 'border-transparent text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {tab}
                  <Badge variant="secondary" className="text-xs h-4 px-1.5">
                    {i === 0
                      ? (data.user_activity?.length ?? 0)
                      : (data.did_activity?.length ?? 0)}
                  </Badge>
                </button>
              ))}
            </div>

            <Input
              placeholder="Search…"
              value={search}
              onChange={e => setSearch(e.target.value)}
              className="w-48 h-8 text-sm"
            />
          </div>

          {/* Table */}
          {activeTab === 0 && <UserActivityTable rows={data.user_activity} search={search} />}
          {activeTab === 1 && <DidActivityTable  rows={data.did_activity}  search={search} />}

          {/* Footer */}
          <p className="text-xs text-muted-foreground text-right">
            {rowCount} {rowCount === 1 ? 'row' : 'rows'} · exported reports include all rows
          </p>
        </>
      )}
    </div>
  )
}
