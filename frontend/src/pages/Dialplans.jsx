import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback } from 'react'
import { dialplans as api } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { Search } from 'lucide-react'

export default function Dialplans() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebounce(search, 300)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.list(debouncedSearch ? { search: debouncedSearch } : {})
      setRows(Array.isArray(data) ? data : data.results || [])
    } finally { setLoading(false) }
  }, [search])

  useEffect(() => { load() }, [load])

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Search dialplans..." className="pl-8" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
      </div>
      <Card><CardContent className="p-0 overflow-x-auto">
        <Table>
          <TableHeader><TableRow>
            <TableHead>Name</TableHead><TableHead>Context</TableHead><TableHead>Order</TableHead><TableHead>Status</TableHead>
          </TableRow></TableHeader>
          <TableBody>
            {loading ? [...Array(8)].map((_, i) => <TableRow key={i}>{[...Array(4)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}</TableRow>)
              : rows.length === 0 ? <TableRow><TableCell colSpan={4} className="text-center py-10 text-muted-foreground">No dialplans found.</TableCell></TableRow>
              : rows.map((r) => {
                const id = r.dialplan_uuid || r.id
                return <TableRow key={id}>
                  <TableCell className="font-medium">{r.dialplan_name || r.name}</TableCell>
                  <TableCell className="text-muted-foreground text-sm">{r.dialplan_context || r.context || '—'}</TableCell>
                  <TableCell>{r.dialplan_order ?? r.order ?? '—'}</TableCell>
                  <TableCell><Badge variant={r.dialplan_enabled !== false ? 'success' : 'secondary'}>{r.dialplan_enabled !== false ? 'Active' : 'Disabled'}</Badge></TableCell>
                </TableRow>
              })}
          </TableBody>
        </Table>
      </CardContent></Card>
    </div>
  )
}
