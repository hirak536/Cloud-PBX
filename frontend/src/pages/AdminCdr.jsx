import { useMemo, useState } from 'react'
import { cdr as cdrApi } from '@/api'
import { useInfiniteList } from '@/hooks/useInfiniteList'
import { InfiniteScroll, PageSizeSelector, DEFAULT_PAGE_SIZE } from '@/components/InfiniteScroll'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDuration, formatDate } from '@/lib/utils'
import { Search, Download, Phone, PhoneIncoming, PhoneOutgoing } from 'lucide-react'

function DispositionBadge({ status, hangupCause }) {
  const s = status || hangupCause
  if (!s) return <Badge variant="secondary">—</Badge>
  if (s === 'ANSWERED' || s === 'NORMAL_CLEARING') return <Badge variant="success">Answered</Badge>
  if (s === 'MISSED' || s === 'NO_ANSWER') return <Badge variant="destructive">Missed</Badge>
  if (s === 'BUSY' || s === 'USER_BUSY') return <Badge variant="warning">Busy</Badge>
  if (s === 'WENT_TO_VOICEMAIL') return <Badge variant="outline" className="text-orange-500 border-orange-300">Voicemail</Badge>
  if (s === 'ORIGINATOR_CANCEL') return <Badge variant="secondary">Cancelled</Badge>
  if (s === 'FAILED') return <Badge variant="destructive">Failed</Badge>
  return <Badge variant="secondary">{s.replace(/_/g, ' ')}</Badge>
}

function DirectionBadge({ direction, context }) {
  if (direction === 'outbound')
    return <span className="flex items-center gap-1 text-xs text-blue-500"><PhoneOutgoing className="h-3.5 w-3.5" /> Out</span>
  if (direction === 'local')
    return <span className="flex items-center gap-1 text-xs text-purple-500"><Phone className="h-3.5 w-3.5" /> Local</span>
  if (context === 'public')
    return <span className="flex items-center gap-1 text-xs text-amber-500"><PhoneIncoming className="h-3.5 w-3.5" /> GW In</span>
  return <span className="flex items-center gap-1 text-xs text-green-600"><PhoneIncoming className="h-3.5 w-3.5" /> In</span>
}

export default function AdminCdr() {
  const [search, setSearch] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)
  const [exporting, setExporting] = useState(false)

  const params = useMemo(() => {
    const p = {
      tenant: null,   // opt out of per-tenant scoping — show all tenants
      leg: 'a',
    }
    if (search) p.search = search
    if (startDate) p.start_stamp__gte = startDate
    if (endDate) p.end_date = endDate
    return p
  }, [search, startDate, endDate])

  const {
    rows: records,
    total,
    loading,
    loadingMore,
    hasMore,
    loadMore,
  } = useInfiniteList(cdrApi.list, { params, pageSize })

  async function handleExport() {
    setExporting(true)
    try {
      const params = { tenant: null }
      if (search) params.search = search
      if (startDate) params.start_stamp__gte = startDate
      if (endDate) params.end_date = endDate
      const res = await cdrApi.export(params)
      const url = URL.createObjectURL(new Blob([res.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = 'admin-cdr.csv'
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Admin CDR</h1>
          <p className="text-sm text-muted-foreground">All call detail records across all tenants</p>
        </div>
        <Button variant="outline" size="sm" onClick={handleExport} disabled={exporting}>
          <Download className="h-4 w-4 mr-1" />
          {exporting ? 'Exporting…' : 'Export CSV'}
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="pt-4 pb-3">
          <div className="flex flex-wrap gap-3 items-end">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
              <Input
                placeholder="Search caller, destination…"
                className="pl-8"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
            <div className="flex items-center gap-2">
              <Input
                type="date"
                className="w-40"
                value={startDate}
                onChange={e => setStartDate(e.target.value)}
              />
              <span className="text-muted-foreground text-sm">to</span>
              <Input
                type="date"
                className="w-40"
                value={endDate}
                onChange={e => setEndDate(e.target.value)}
              />
            </div>
            {(search || startDate || endDate) && (
              <Button variant="ghost" size="sm" onClick={() => { setSearch(''); setStartDate(''); setEndDate('') }}>
                Clear
              </Button>
            )}
            <PageSizeSelector value={pageSize} onChange={setPageSize} className="ml-auto" />
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Start</TableHead>
                <TableHead>Caller ID</TableHead>
                <TableHead>Source</TableHead>
                <TableHead>Destination</TableHead>
                <TableHead>Direction</TableHead>
                <TableHead className="text-right">Duration</TableHead>
                <TableHead className="text-right">Talk Time</TableHead>
                <TableHead>Tenant</TableHead>
                <TableHead>Disposition</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading
                ? Array.from({ length: 10 }).map((_, i) => (
                    <TableRow key={i}>
                      {Array.from({ length: 9 }).map((_, j) => (
                        <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                      ))}
                    </TableRow>
                  ))
                : records.length === 0
                ? (
                    <TableRow>
                      <TableCell colSpan={9} className="text-center text-muted-foreground py-10">
                        No records found
                      </TableCell>
                    </TableRow>
                  )
                : records.map(row => (
                    <TableRow key={row.xml_cdr_uuid}>
                      <TableCell className="text-xs whitespace-nowrap">
                        {row.start_stamp ? formatDate(row.start_stamp) : '—'}
                      </TableCell>
                      <TableCell className="text-xs">
                        <div className="font-medium">{row.caller_id_number || '—'}</div>
                        {row.caller_id_name && (
                          <div className="text-muted-foreground">{row.caller_id_name}</div>
                        )}
                      </TableCell>
                      <TableCell className="text-xs">{row.caller_id_number || '—'}</TableCell>
                      <TableCell className="text-xs font-medium">{row.destination_number || '—'}</TableCell>
                      <TableCell>
                        <DirectionBadge direction={row.direction} context={row.context} />
                      </TableCell>
                      <TableCell className="text-right text-xs">{formatDuration(row.duration)}</TableCell>
                      <TableCell className="text-right text-xs">{formatDuration(row.billsec)}</TableCell>
                      <TableCell className="text-xs">
                        {row.tenant_code
                          ? <Badge variant="outline" className="text-xs font-normal">{row.tenant_code}</Badge>
                          : <span className="text-muted-foreground">—</span>
                        }
                      </TableCell>
                      <TableCell>
                        <DispositionBadge status={row.status} hangupCause={row.hangup_cause} />
                      </TableCell>
                    </TableRow>
                  ))
              }
            </TableBody>
          </Table>
          <InfiniteScroll
            hasMore={hasMore}
            loadingMore={loadingMore}
            onLoadMore={loadMore}
            loaded={records.length}
            total={total}
          />
        </CardContent>
      </Card>
    </div>
  )
}
