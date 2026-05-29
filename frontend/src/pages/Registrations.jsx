import { useState, useEffect, useCallback, useMemo } from 'react'
import { useSelector } from 'react-redux'
import { selectLive } from '@/store'
import { freeswitch, extensions as extensionsApi } from '@/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose } from '@/components/ui/dialog'
import { UserX, Loader2, Search, Power, Activity } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

const DESK_PHONE_AGENTS = /grandstream|yealink|polycom|cisco|snom|fanvil|htek|aastra/i
const isDeskPhone = (ua) => !!ua && DESK_PHONE_AGENTS.test(ua)

const STATE_LABELS = {
  available: 'Available', ringing: 'Ringing', inuse: 'In use',
  ringinuse: 'Ring in use', offline: 'Offline', unknown: 'Unknown',
}
const STATE_COLORS = {
  available: '#22c55e', ringing: '#facc15', inuse: '#3b82f6',
  ringinuse: '#a855f7', offline: '#9ca3af', unknown: '#d1d5db',
}
const STATE_BADGE_VARIANT = {
  available: 'success', ringing: 'warning', inuse: 'default',
  ringinuse: 'default', offline: 'secondary', unknown: 'outline',
}

// Map liveSlice extStatuses values to canonical state keys used by the chart.
const normalizeState = (s) => {
  if (!s) return 'unknown'
  const v = String(s).toLowerCase()
  if (v === 'online') return 'available'
  if (v === 'in_use' || v === 'inuse') return 'inuse'
  if (v === 'ring_in_use' || v === 'ringinuse') return 'ringinuse'
  if (v === 'ringing') return 'ringing'
  if (v === 'offline') return 'offline'
  return v in STATE_LABELS ? v : 'unknown'
}

function PeerStateChart({ history, days }) {
  const now = useMemo(() => Date.now(), [history])
  const t0 = now - days * 24 * 3600 * 1000

  const rows = useMemo(() => {
    if (!Array.isArray(history)) return []
    return history.map(h => ({
      state: normalizeState(h.state),
      start: Math.max(new Date(h.started_at).getTime(), t0),
      end:   Math.min(h.ended_at ? new Date(h.ended_at).getTime() : now, now),
    })).filter(r => r.end > r.start)
  }, [history, t0, now])

  const W = 900, H = 220
  const padL = 110, padR = 16, padT = 16, padB = 36
  const plotW = W - padL - padR
  const plotH = H - padT - padB
  const states = ['ringinuse', 'inuse', 'ringing', 'available', 'offline', 'unknown']
  const laneH = plotH / states.length
  const xOf = (t) => padL + ((t - t0) / (now - t0)) * plotW

  const ticks = []
  const d = new Date(t0)
  d.setHours(0, 0, 0, 0); d.setDate(d.getDate() + 1)
  while (d.getTime() < now) { ticks.push(new Date(d)); d.setDate(d.getDate() + 1) }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto bg-card text-foreground" role="img" aria-label="Peer state history">
      {states.map((s, i) => (
        <g key={s}>
          <text x={padL - 8} y={padT + i * laneH + laneH / 2 + 4} textAnchor="end" fontSize="11" fill="currentColor">{STATE_LABELS[s]}</text>
          <line x1={padL} x2={W - padR} y1={padT + i * laneH + laneH} y2={padT + i * laneH + laneH} stroke="currentColor" strokeOpacity="0.1" />
        </g>
      ))}
      {ticks.map((tk, i) => {
        const x = xOf(tk.getTime())
        return (
          <g key={i}>
            <line x1={x} x2={x} y1={padT} y2={H - padB} stroke="currentColor" strokeOpacity="0.08" />
            <text x={x} y={H - padB + 16} fontSize="10" textAnchor="middle" fill="currentColor">
              {tk.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
            </text>
          </g>
        )
      })}
      {rows.map((r, i) => {
        const laneIdx = states.indexOf(r.state)
        if (laneIdx < 0) return null
        const x = xOf(r.start)
        const w = Math.max(1, xOf(r.end) - x)
        const y = padT + laneIdx * laneH + 4
        return (
          <rect key={i} x={x} y={y} width={w} height={laneH - 8}
                fill={STATE_COLORS[r.state]} opacity="0.85">
            <title>{`${STATE_LABELS[r.state]}\n${new Date(r.start).toLocaleString()} → ${new Date(r.end).toLocaleString()}`}</title>
          </rect>
        )
      })}
      {rows.length === 0 && (
        <text x={W / 2} y={H / 2} textAnchor="middle" fill="currentColor" fontSize="12" opacity="0.6">
          No history recorded yet.
        </text>
      )}
    </svg>
  )
}

export default function Registrations() {
  const { wsConnected, registrations: regs, extStatuses } = useSelector(selectLive)
  const [deregistering, setDeregistering] = useState(null)
  const [rebooting, setRebooting] = useState(null)
  const [search, setSearch] = useState('')
  const [extensions, setExtensions] = useState([])
  const [loadingExts, setLoadingExts] = useState(true)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [historyPeer, setHistoryPeer] = useState(null)
  const [history, setHistory] = useState(null)
  const [historyLoading, setHistoryLoading] = useState(false)

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

  const handleReboot = async (reg) => {
    if (!reg?.call_id) return
    if (!confirm(`Reboot phone for ${reg.reg_user}? This will send a SIP NOTIFY check-sync.`)) return
    setRebooting(reg.call_id)
    try {
      const user = reg.reg_user || ''
      const tenant_code = user.includes('-') ? user.split('-').pop() : ''
      await freeswitch.reboot(reg.call_id, reg.profile || 'internal', tenant_code)
      toast.success(`Reboot signal sent to ${reg.reg_user}`)
    } catch (err) {
      toast.error(err?.response?.data?.error || 'Reboot failed')
    } finally { setRebooting(null) }
  }

  const openHistory = async (sipUser) => {
    setHistoryPeer(sipUser)
    setHistoryOpen(true)
    setHistory(null)
    setHistoryLoading(true)
    try {
      const res = await freeswitch.peerHistory(sipUser, 5)
      setHistory(res.data?.history || [])
    } catch {
      setHistory([])
    } finally {
      setHistoryLoading(false)
    }
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
                <TableHead className="w-28 text-right">Actions</TableHead>
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

                const rawState = isRegistered ? (extStatuses?.[peer] || 'online') : 'offline'
                const stateKey = normalizeState(rawState)
                const contactShort = reg?.url
                  ? reg.url.length > 35 ? reg.url.slice(0, 35) + '…' : reg.url
                  : '—'
                const desk = isDeskPhone(reg?.user_agent)

                return (
                  <TableRow key={`${peer}-${i}`} className={cn(!isRegistered && 'opacity-50')}>
                    <TableCell className="font-mono text-sm font-medium">{peer}</TableCell>
                    <TableCell className="text-sm">{extName || '—'}</TableCell>
                    <TableCell className="font-mono text-sm">{reg?.network_ip || '—'}</TableCell>
                    <TableCell className="font-mono text-xs text-muted-foreground max-w-[160px] truncate" title={reg?.url}>{contactShort}</TableCell>
                    <TableCell className="tabular-nums text-sm">{reg?.network_port || '—'}</TableCell>
                    <TableCell className="tabular-nums text-xs">{phoneTime}</TableCell>
                    <TableCell className="text-xs text-muted-foreground max-w-[140px] truncate" title={reg?.user_agent}>{reg?.user_agent || '—'}</TableCell>
                    <TableCell className="tabular-nums text-sm">{reg?.ping_ms != null ? `${reg.ping_ms} ms` : '—'}</TableCell>
                    <TableCell>
                      <Badge variant={STATE_BADGE_VARIANT[stateKey] || 'outline'} className="text-xs">
                        {STATE_LABELS[stateKey] || stateKey}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex gap-0.5 justify-end">
                        <Button
                          variant="ghost" size="icon" className="h-7 w-7"
                          title="Peer state history" onClick={() => openHistory(peer)}
                        >
                          <Activity className="h-3.5 w-3.5" />
                        </Button>
                        {isRegistered && desk && (
                          <Button
                            variant="ghost" size="icon" className="h-7 w-7"
                            title="Reboot phone (SIP check-sync)" disabled={rebooting === reg.call_id}
                            onClick={() => handleReboot(reg)}
                          >
                            {rebooting === reg.call_id
                              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              : <Power className="h-3.5 w-3.5" />}
                          </Button>
                        )}
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
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
        <DialogContent className="max-w-4xl">
          <DialogClose onClose={() => setHistoryOpen(false)} />
          <DialogHeader>
            <DialogTitle>Peer State History — {historyPeer}</DialogTitle>
          </DialogHeader>
          {historyLoading
            ? <div className="flex justify-center py-12"><Loader2 className="h-5 w-5 animate-spin" /></div>
            : <PeerStateChart history={history || []} days={5} />
          }
          <DialogFooter>
            <Button variant="outline" onClick={() => setHistoryOpen(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
