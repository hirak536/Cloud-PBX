import { useEffect, useState, useCallback } from 'react'
import { destinations as destApi, extensions as extApi } from '@/api'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { Search, Phone, MapPin } from 'lucide-react'

function TenantBadge({ code }) {
  if (!code) return <span className="text-muted-foreground text-xs">—</span>
  return <Badge variant="outline" className="text-xs font-normal">{code}</Badge>
}

function EnabledBadge({ enabled }) {
  return enabled
    ? <Badge variant="success">Active</Badge>
    : <Badge variant="secondary">Disabled</Badge>
}

// ─── DID List ────────────────────────────────────────────────────────────────
function DidList() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { tenant: null }
      if (search) params.search = search
      const res = await destApi.list(params)
      const data = res.data
      setRows(Array.isArray(data) ? data : data.results || [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [search])

  useEffect(() => { load() }, [load])

  return (
    <div className="space-y-3">
      <div className="relative max-w-sm">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search number or name…"
          className="pl-8"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>DID Number</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Routes To</TableHead>
                <TableHead>Tenant</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading
                ? Array.from({ length: 8 }).map((_, i) => (
                    <TableRow key={i}>
                      {Array.from({ length: 5 }).map((_, j) => (
                        <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                      ))}
                    </TableRow>
                  ))
                : rows.length === 0
                ? (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center text-muted-foreground py-10">
                        No DIDs found
                      </TableCell>
                    </TableRow>
                  )
                : rows.map(row => (
                    <TableRow key={row.destination_uuid}>
                      <TableCell className="font-mono text-sm font-medium">
                        {row.destination_number || row.destination_number_regex || <span className="text-muted-foreground">—</span>}
                      </TableCell>
                      <TableCell className="text-sm">
                        {row.destination_name || <span className="text-muted-foreground">—</span>}
                      </TableCell>
                      <TableCell className="text-xs">
                        {row.dest_type_display || row.dest_type || <span className="text-muted-foreground">—</span>}
                      </TableCell>
                      <TableCell>
                        <TenantBadge code={row.tenant_code} />
                      </TableCell>
                      <TableCell>
                        <EnabledBadge enabled={row.destination_enabled} />
                      </TableCell>
                    </TableRow>
                  ))
              }
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <p className="text-xs text-muted-foreground">{rows.length} DID{rows.length !== 1 ? 's' : ''}</p>
    </div>
  )
}

// ─── Extension List ───────────────────────────────────────────────────────────
function ExtensionList() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = { tenant: null }
      if (search) params.search = search
      const res = await extApi.list(params)
      const data = res.data
      setRows(Array.isArray(data) ? data : data.results || [])
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }, [search])

  useEffect(() => { load() }, [load])

  return (
    <div className="space-y-3">
      <div className="relative max-w-sm">
        <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <Input
          placeholder="Search extension or name…"
          className="pl-8"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Extension</TableHead>
                <TableHead>Caller ID Name</TableHead>
                <TableHead>Caller ID Number</TableHead>
                <TableHead>SIP Username</TableHead>
                <TableHead>Voicemail</TableHead>
                <TableHead>Tenant</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading
                ? Array.from({ length: 8 }).map((_, i) => (
                    <TableRow key={i}>
                      {Array.from({ length: 7 }).map((_, j) => (
                        <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                      ))}
                    </TableRow>
                  ))
                : rows.length === 0
                ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center text-muted-foreground py-10">
                        No extensions found
                      </TableCell>
                    </TableRow>
                  )
                : rows.map(row => (
                    <TableRow key={row.extension_uuid}>
                      <TableCell className="font-mono text-sm font-medium">
                        {row.extension}
                      </TableCell>
                      <TableCell className="text-sm">
                        {row.effective_caller_id_name || <span className="text-muted-foreground">—</span>}
                      </TableCell>
                      <TableCell className="text-sm font-mono">
                        {row.effective_caller_id_number || <span className="text-muted-foreground">—</span>}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground font-mono">
                        {row.sip_username || '—'}
                      </TableCell>
                      <TableCell>
                        {row.voicemail_enabled
                          ? <Badge variant="outline" className="text-xs">Enabled</Badge>
                          : <span className="text-muted-foreground text-xs">—</span>
                        }
                      </TableCell>
                      <TableCell>
                        <TenantBadge code={row.tenant_code} />
                      </TableCell>
                      <TableCell>
                        <EnabledBadge enabled={row.enabled} />
                      </TableCell>
                    </TableRow>
                  ))
              }
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <p className="text-xs text-muted-foreground">{rows.length} extension{rows.length !== 1 ? 's' : ''}</p>
    </div>
  )
}

// ─── Page ─────────────────────────────────────────────────────────────────────
const TABS = [
  { id: 'dids',       label: 'DIDs',       icon: MapPin,  Component: DidList },
  { id: 'extensions', label: 'Extensions', icon: Phone,   Component: ExtensionList },
]

export default function AdminInventory() {
  const [tab, setTab] = useState('dids')
  const active = TABS.find(t => t.id === tab)

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">Admin Inventory</h1>
        <p className="text-sm text-muted-foreground">Global DID and extension list across all tenants</p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 border-b">
        {TABS.map(t => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              tab === t.id
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground'
            }`}
          >
            <t.icon className="h-4 w-4" />
            {t.label}
          </button>
        ))}
      </div>

      {active && <active.Component />}
    </div>
  )
}
