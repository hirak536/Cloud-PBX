import { useState, useCallback, useEffect } from 'react'
import { cdr as cdrApi, tenants as tenantsApi } from '@/api'
import { useSelector } from 'react-redux'
import { selectAuth } from '@/store'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Select } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Search, Loader2, ChevronRight, ChevronDown, PhoneIncoming, PhoneOutgoing } from 'lucide-react'
import { formatDate } from '@/lib/utils'

// Renders one leg's tshark-style numbered frame summary.
function FrameTable({ frames }) {
  if (!frames?.length) {
    return <div className="px-3 py-2 text-xs text-muted-foreground">No captured packets for this leg.</div>
  }
  return (
    <pre className="text-[11px] leading-snug font-mono overflow-x-auto bg-background/60 rounded border p-2">
      {frames.map((f) => {
        const n = String(f.n).padStart(4, ' ')
        const t = Number(f.time).toFixed(6).padStart(11, ' ')
        const len = f.length != null ? String(f.length) : ''
        return `${n}  ${t}  ${f.src} → ${f.dst}  ${f.proto} ${len} ${f.info}`
      }).join('\n')}
    </pre>
  )
}

// One captured call (grouped): headline row + expandable per-leg ladder.
function CallRow({ call, window }) {
  const [open, setOpen] = useState(false)
  // ladder state keyed by leg call_id
  const [ladders, setLadders] = useState({})

  const loadLeg = useCallback(async (cid) => {
    if (ladders[cid]) return
    setLadders((p) => ({ ...p, [cid]: { loading: true } }))
    try {
      const { data } = await cdrApi.homerLadder({ call_id: cid, from: window.from, to: window.to })
      setLadders((p) => ({ ...p, [cid]: { loading: false, frames: data.frames || [] } }))
    } catch {
      setLadders((p) => ({ ...p, [cid]: { loading: false, frames: [] } }))
    }
  }, [ladders, window])

  const toggle = () => {
    const next = !open
    setOpen(next)
    if (next) call.legs.forEach((l) => loadLeg(l.call_id))
  }

  // Direction heuristic: external (has +) → extension = inbound; reverse = outbound.
  const from = call.from_user || ''
  const inbound = from.startsWith('+') || /^\d{7,}$/.test(from.replace(/\D/g, ''))

  return (
    <>
      <TableRow className="cursor-pointer hover:bg-muted/40" onClick={toggle}>
        <TableCell className="w-6">
          {open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
        </TableCell>
        <TableCell>
          {inbound
            ? <PhoneIncoming className="inline h-3.5 w-3.5 text-emerald-600 mr-1" />
            : <PhoneOutgoing className="inline h-3.5 w-3.5 text-sky-600 mr-1" />}
          <span className="font-mono text-sm">{call.from_user}</span>
        </TableCell>
        <TableCell className="font-mono text-sm">{call.to_user}</TableCell>
        <TableCell className="text-xs text-muted-foreground">{formatDate(call.start_time)}</TableCell>
        <TableCell>
          {call.leg_count > 1
            ? <Badge variant="secondary">{call.leg_count} legs</Badge>
            : <span className="text-xs text-muted-foreground">1 leg</span>}
        </TableCell>
      </TableRow>
      {open && (
        <TableRow>
          <TableCell colSpan={5} className="bg-muted/20 p-3 space-y-3">
            {call.legs.map((leg, i) => (
              <div key={leg.call_id}>
                <div className="text-xs font-medium mb-1">
                  {i === 0 ? 'First Leg' : `Second Leg ${i - 1}`}
                  <span className="text-muted-foreground font-normal ml-2">
                    {leg.src_ip} → {leg.dst_ip} · {leg.call_id}
                  </span>
                </div>
                {ladders[leg.call_id]?.loading
                  ? <div className="px-3 py-2 text-xs text-muted-foreground">Decoding…</div>
                  : <FrameTable frames={ladders[leg.call_id]?.frames} />}
              </div>
            ))}
          </TableCell>
        </TableRow>
      )}
    </>
  )
}

export default function SipSearchPanel() {
  const { user } = useSelector(selectAuth)
  const isSuperAdmin = user?.is_superuser === true

  const [number, setNumber] = useState('')
  const [extension, setExtension] = useState('')
  const [callId, setCallId] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [tenant, setTenant] = useState('')
  const [tenantList, setTenantList] = useState([])

  const [page, setPage] = useState(1)
  const [state, setState] = useState({ loading: false, results: [], total: 0, hasMore: false, window: null, ran: false })
  const PAGE_SIZE = 20

  useEffect(() => {
    if (!isSuperAdmin) return
    tenantsApi.list?.({ page_size: 200 })
      .then(({ data }) => setTenantList(Array.isArray(data) ? data : data.results || []))
      .catch(() => {})
  }, [isSuperAdmin])

  const runSearch = useCallback(async (toPage = 1) => {
    setState((s) => ({ ...s, loading: true }))
    const params = { page: toPage, page_size: PAGE_SIZE }
    if (number) params.number = number
    if (extension) params.extension = extension
    if (callId) params.call_id = callId
    if (dateFrom) params.from = dateFrom
    if (dateTo) params.to = dateTo
    if (isSuperAdmin && tenant) params.tenant = tenant
    try {
      const { data } = await cdrApi.homerSearch(params)
      setState({
        loading: false, results: data.results || [], total: data.total || 0,
        hasMore: data.has_more || false, window: data.window, ran: true,
      })
      setPage(toPage)
    } catch {
      setState({ loading: false, results: [], total: 0, hasMore: false, window: null, ran: true })
    }
  }, [number, extension, callId, dateFrom, dateTo, tenant, isSuperAdmin])

  const onSubmit = (e) => { e.preventDefault(); runSearch(1) }

  return (
    <div className="space-y-4">
      <form onSubmit={onSubmit}>
        <Card>
          <CardContent className="p-3 flex flex-wrap items-end gap-3">
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Number</label>
              <Input className="w-40" placeholder="caller / callee" value={number} onChange={(e) => setNumber(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Extension</label>
              <Input className="w-28" placeholder="e.g. 101" value={extension} onChange={(e) => setExtension(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">Call-ID</label>
              <Input className="w-48" placeholder="exact Call-ID" value={callId} onChange={(e) => setCallId(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">From</label>
              <Input className="w-44" type="datetime-local" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            </div>
            <div className="space-y-1">
              <label className="text-xs text-muted-foreground">To</label>
              <Input className="w-44" type="datetime-local" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
            </div>
            {isSuperAdmin && (
              <div className="space-y-1">
                <label className="text-xs text-muted-foreground">Tenant</label>
                <Select className="w-40" value={tenant} onChange={(e) => setTenant(e.target.value)}>
                  <option value="">All tenants</option>
                  {tenantList.map((t) => (
                    <option key={t.tenant_uuid || t.id} value={t.tenant_uuid || t.id}>
                      {t.tenant_code || t.tenant_name}
                    </option>
                  ))}
                </Select>
              </div>
            )}
            <Button type="submit" size="sm" disabled={state.loading}>
              {state.loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
              Search
            </Button>
          </CardContent>
        </Card>
      </form>

      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-6" />
                <TableHead>From</TableHead>
                <TableHead>To</TableHead>
                <TableHead>Start</TableHead>
                <TableHead>Legs</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {state.loading ? (
                [...Array(5)].map((_, i) => (
                  <TableRow key={i}>{[...Array(5)].map((_, j) => (
                    <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                  ))}</TableRow>
                ))
              ) : !state.ran ? (
                <TableRow><TableCell colSpan={5} className="text-center py-10 text-muted-foreground">Enter filters and search captured SIP.</TableCell></TableRow>
              ) : state.results.length === 0 ? (
                <TableRow><TableCell colSpan={5} className="text-center py-10 text-muted-foreground">No calls found for these filters.</TableCell></TableRow>
              ) : (
                state.results.map((call) => (
                  <CallRow key={call.call_id} call={call} window={state.window} />
                ))
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {state.ran && state.total > 0 && (
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            Showing {state.results.length} of {state.total}{state.hasMore ? '+' : ''} calls (page {page})
          </span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1 || state.loading} onClick={() => runSearch(page - 1)}>Prev</Button>
            <Button variant="outline" size="sm" disabled={!state.hasMore || state.loading} onClick={() => runSearch(page + 1)}>Next</Button>
          </div>
        </div>
      )}
    </div>
  )
}
