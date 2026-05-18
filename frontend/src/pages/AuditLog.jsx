import { useEffect, useState, useCallback } from 'react'
import { auditLogs as api } from '@/api'
import { useDebounce } from '@/hooks/useDebounce'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table'
import { ChevronDown, ChevronRight, Search, RefreshCw } from 'lucide-react'

const ACTION_STYLES = {
  create: 'bg-emerald-500/10 text-emerald-600 border-emerald-500/20',
  update: 'bg-amber-500/10 text-amber-600 border-amber-500/20',
  delete: 'bg-red-500/10 text-red-600 border-red-500/20',
}

const ACTION_OPTIONS = ['', 'create', 'update', 'delete']

function ActionBadge({ action }) {
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold capitalize ${ACTION_STYLES[action] ?? 'bg-muted text-muted-foreground border-border'}`}>
      {action}
    </span>
  )
}

function ChangesPanel({ changes }) {
  if (!changes) return <p className="text-xs text-muted-foreground italic">No field-level changes recorded.</p>
  const { before = {}, after = {} } = changes
  const fields = Object.keys({ ...before, ...after })
  if (!fields.length) return <p className="text-xs text-muted-foreground italic">No field-level changes recorded.</p>
  return (
    <table className="w-full text-xs border-collapse">
      <thead>
        <tr className="text-muted-foreground text-left">
          <th className="pr-4 pb-1 font-semibold w-1/4">Field</th>
          <th className="pr-4 pb-1 font-semibold w-1/3">Before</th>
          <th className="pb-1 font-semibold w-1/3">After</th>
        </tr>
      </thead>
      <tbody>
        {fields.map((f) => (
          <tr key={f} className="border-t border-border/40">
            <td className="py-1 pr-4 font-mono text-muted-foreground">{f}</td>
            <td className="py-1 pr-4 text-red-500/80">{before[f] ?? <span className="italic opacity-50">—</span>}</td>
            <td className="py-1 text-emerald-600">{after[f] ?? <span className="italic opacity-50">—</span>}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function AuditRow({ row }) {
  const [expanded, setExpanded] = useState(false)

  return (
    <>
      <TableRow
        className="cursor-pointer hover:bg-muted/40 transition-colors"
        onClick={() => setExpanded((v) => !v)}
      >
        <TableCell className="w-6 pl-3">
          {expanded
            ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
            : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />}
        </TableCell>
        <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
          {new Date(row.timestamp).toLocaleString(undefined, {
            month: 'short', day: 'numeric', year: 'numeric',
            hour: '2-digit', minute: '2-digit', second: '2-digit',
          })}
        </TableCell>
        <TableCell className="font-medium text-sm">{row.username || '—'}</TableCell>
        <TableCell><ActionBadge action={row.action} /></TableCell>
        <TableCell className="text-xs font-mono text-muted-foreground">{row.resource_type}</TableCell>
        <TableCell className="text-sm truncate max-w-48">{row.resource_name || '—'}</TableCell>
        <TableCell className="text-xs text-muted-foreground">{row.ip_address || '—'}</TableCell>
      </TableRow>
      {expanded && (
        <TableRow className="bg-muted/20 hover:bg-muted/20">
          <TableCell colSpan={7} className="px-6 py-3">
            <ChangesPanel changes={row.changes} />
          </TableCell>
        </TableRow>
      )}
    </>
  )
}

export default function AuditLog() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [actionFilter, setActionFilter] = useState('')
  const [next, setNext] = useState(null)
  const [prev, setPrev] = useState(null)
  const [page, setPage] = useState(1)

  const debouncedSearch = useDebounce(search, 400)

  const load = useCallback(async (pageNum = 1) => {
    setLoading(true)
    try {
      const params = { page: pageNum, page_size: 50 }
      if (debouncedSearch) params.username = debouncedSearch
      if (actionFilter) params.action = actionFilter
      const { data } = await api.list(params)
      const results = Array.isArray(data) ? data : (data.results ?? [])
      setRows(results)
      setNext(data.next ?? null)
      setPrev(data.previous ?? null)
    } finally {
      setLoading(false)
    }
  }, [debouncedSearch, actionFilter])

  useEffect(() => { setPage(1) }, [debouncedSearch, actionFilter])
  useEffect(() => { load(page) }, [load, page])

  return (
    <div className="space-y-4">
      {/* Filters */}
      <Card>
        <CardContent className="py-3 px-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-48">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground pointer-events-none" />
              <Input
                placeholder="Filter by username…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="pl-8 h-8 text-sm"
              />
            </div>
            <select
              value={actionFilter}
              onChange={(e) => setActionFilter(e.target.value)}
              className="h-8 rounded-md border border-input bg-background px-3 text-sm text-foreground outline-none focus:ring-1 focus:ring-primary/40"
            >
              {ACTION_OPTIONS.map((a) => (
                <option key={a} value={a}>{a ? a.charAt(0).toUpperCase() + a.slice(1) : 'All actions'}</option>
              ))}
            </select>
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => load(page)} title="Refresh">
              <RefreshCw className="h-3.5 w-3.5" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-6" />
                <TableHead>Timestamp</TableHead>
                <TableHead>User</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Resource Type</TableHead>
                <TableHead>Resource</TableHead>
                <TableHead>IP Address</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                Array.from({ length: 8 }).map((_, i) => (
                  <TableRow key={i}>
                    {Array.from({ length: 7 }).map((__, j) => (
                      <TableCell key={j}><Skeleton className="h-4 w-full shimmer" /></TableCell>
                    ))}
                  </TableRow>
                ))
              ) : rows.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="py-12 text-center text-muted-foreground text-sm">
                    No audit log entries found.
                  </TableCell>
                </TableRow>
              ) : (
                rows.map((row) => <AuditRow key={row.audit_log_uuid} row={row} />)
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Pagination */}
      {(prev || next) && (
        <div className="flex items-center justify-end gap-2">
          <Button variant="outline" size="sm" disabled={!prev} onClick={() => setPage((p) => Math.max(1, p - 1))}>
            Previous
          </Button>
          <span className="text-sm text-muted-foreground">Page {page}</span>
          <Button variant="outline" size="sm" disabled={!next} onClick={() => setPage((p) => p + 1)}>
            Next
          </Button>
        </div>
      )}
    </div>
  )
}
