import { useState, useEffect, useCallback } from 'react'
import { useSelector } from 'react-redux'
import { selectLive } from '@/store'
import { freeswitch, extensions as extensionsApi } from '@/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { UserX, Loader2, Search } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

export default function Registrations() {
  const { wsConnected, registrations: regs } = useSelector(selectLive)
  const [deregistering, setDeregistering] = useState(null)
  const [search, setSearch] = useState('')
  const [extensions, setExtensions] = useState([])
  const [loadingExts, setLoadingExts] = useState(true)

  const loadExtensions = useCallback(async () => {
    setLoadingExts(true)
    try {
      const all = []
      let page = 1
      while (true) {
        const { data } = await extensionsApi.list({ page, page_size: 100 })
        const results = Array.isArray(data) ? data : data.results || []
        all.push(...results)
        if (Array.isArray(data) || !data.next) break
        page++
      }
      setExtensions(all)
    } catch {
      setExtensions([])
    } finally {
      setLoadingExts(false)
    }
  }, [])

  useEffect(() => { loadExtensions() }, [loadExtensions])

  const handleDeregister = async (reg) => {
    if (!reg?.call_id) return
    if (!confirm(`Deregister ${reg.reg_user}?`)) return
    setDeregistering(reg.call_id)
    try {
      const user = reg.reg_user || ''
      const tenant_code = user.includes('-') ? user.split('-').pop() : ''
      await freeswitch.deregister(reg.call_id, reg.profile || 'internal', tenant_code)
      toast.success(`${reg.reg_user} deregistered`)
    } catch (err) {
      toast.error(err?.response?.data?.error || 'Deregister failed')
    } finally { setDeregistering(null) }
  }

  // Build a map: sip_username → [reg, reg, ...] (multiple registrations possible)
  const regMap = {}
  for (const r of regs) {
    const key = r.reg_user || r.user || ''
    if (!key) continue
    if (!regMap[key]) regMap[key] = []
    regMap[key].push(r)
  }

  // Build merged rows: one row per (extension × registration), or one UNAVAILABLE row if no reg
  const merged = []
  for (const ext of extensions) {
    const sipUser = ext.sip_username || ext.extension
    const extRegs = regMap[sipUser] || []
    if (extRegs.length === 0) {
      merged.push({ ext, reg: null })
    } else {
      for (const reg of extRegs) {
        merged.push({ ext, reg })
      }
    }
  }

  // Sort: peer name alphabetically
  merged.sort((a, b) => {
    const pa = (a.ext.sip_username || a.ext.extension || '').toLowerCase()
    const pb = (b.ext.sip_username || b.ext.extension || '').toLowerCase()
    return pa.localeCompare(pb)
  })

  const q = search.trim().toLowerCase()
  const filtered = q
    ? merged.filter(({ ext, reg }) => {
        const peer = ext.sip_username || ext.extension || ''
        const name = ext.effective_caller_id_name || ext.description || ''
        const ip = reg?.network_ip || ''
        const ua = reg?.user_agent || ''
        return (
          peer.toLowerCase().includes(q) ||
          name.toLowerCase().includes(q) ||
          ip.includes(q) ||
          ua.toLowerCase().includes(q)
        )
      })
    : merged

  const activeCount = regs.length

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Badge variant={activeCount > 0 ? 'success' : 'secondary'}>{activeCount} registered</Badge>
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <span className={cn('inline-block h-2 w-2 rounded-full', wsConnected ? 'bg-green-500 animate-pulse' : 'bg-amber-400')} />
            {wsConnected ? 'Live · All Tenants' : 'Connecting…'}
          </span>
        </div>
        <div className="relative">
          <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            className="pl-8 h-8 w-56 text-sm"
            placeholder="Search peer, IP, agent…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>

      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Peer</TableHead>
                <TableHead>Extension</TableHead>
                <TableHead>IP Address</TableHead>
                <TableHead>Full Contact</TableHead>
                <TableHead>Port</TableHead>
                <TableHead>Phone Time</TableHead>
                <TableHead>User Agent</TableHead>
                <TableHead>Latency</TableHead>
                <TableHead>State</TableHead>
                <TableHead className="w-16">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loadingExts ? (
                [...Array(8)].map((_, i) => (
                  <TableRow key={i}>
                    {[...Array(10)].map((_, j) => (
                      <TableCell key={j}><div className="h-4 w-full bg-muted animate-pulse rounded" /></TableCell>
                    ))}
                  </TableRow>
                ))
              ) : filtered.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={10} className="py-14 text-center text-muted-foreground text-sm">
                    No extensions found.
                  </TableCell>
                </TableRow>
              ) : filtered.map(({ ext, reg }, i) => {
                const peer = ext.sip_username || ext.extension || '—'
                const extName = ext.effective_caller_id_name || ext.description || ''
                const isRegistered = !!reg

                // Phone time: convert absolute epoch expires to a date string
                let phoneTime = '—'
                if (reg?.expires) {
                  try {
                    const exp = parseInt(reg.expires)
                    if (exp > 0) {
                      const d = new Date(exp * 1000)
                      phoneTime = d.toLocaleDateString('en-US', {
                        month: '2-digit', day: '2-digit', year: '2-digit',
                        hour: '2-digit', minute: '2-digit', second: '2-digit',
                        hour12: false,
                      })
                    }
                  } catch { /* ignore */ }
                }

                const state = isRegistered ? 'NOT_INUSE' : 'UNAVAILABLE'
                const contactShort = reg?.url
                  ? reg.url.length > 35 ? reg.url.slice(0, 35) + '…' : reg.url
                  : '—'

                return (
                  <TableRow key={`${peer}-${i}`} className={cn(!isRegistered && 'opacity-50')}>
                    <TableCell className="font-mono text-sm font-medium">{peer}</TableCell>
                    <TableCell className="text-sm">{extName || '—'}</TableCell>
                    <TableCell className="font-mono text-sm">{reg?.network_ip || '—'}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground max-w-[160px] truncate" title={reg?.url}>{contactShort}</TableCell>
                    <TableCell className="tabular-nums text-sm">{reg?.network_port || '—'}</TableCell>
                    <TableCell className="tabular-nums text-xs">{phoneTime}</TableCell>
                    <TableCell className="text-xs text-muted-foreground max-w-[140px] truncate" title={reg?.user_agent}>{reg?.user_agent || '—'}</TableCell>
                    <TableCell className="tabular-nums text-sm">{reg ? '—' : '—'}</TableCell>
                    <TableCell>
                      <Badge variant={isRegistered ? 'success' : 'secondary'} className="text-xs">
                        {state}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      {isRegistered && (
                        <Button
                          variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive"
                          title="Deregister" disabled={deregistering === reg.call_id}
                          onClick={() => handleDeregister(reg)}
                        >
                          {deregistering === reg.call_id
                            ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            : <UserX className="h-3.5 w-3.5" />}
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
