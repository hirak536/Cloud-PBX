import { useState, useEffect, useMemo, useCallback } from 'react'
import { useSelector } from 'react-redux'
import { selectLive } from '@/store'
import { freeswitch } from '@/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose } from '@/components/ui/dialog'
import { Phone, PhoneForwarded, Loader2, UserX, RefreshCw, Power, Activity } from 'lucide-react'

// ── Helpers ────────────────────────────────────────────────────────────────
const DESK_PHONE_AGENTS = /grandstream|yealink|polycom|cisco|snom|fanvil|htek|aastra/i

const STATE_LABELS = {
  available: 'Available',
  ringing: 'Ringing',
  inuse: 'In use',
  ringinuse: 'Ring in use',
  offline: 'Offline',
  unknown: 'Unknown',
}

const STATE_COLORS = {
  available: '#22c55e',
  ringing:   '#facc15',
  inuse:     '#3b82f6',
  ringinuse: '#a855f7',
  offline:   '#9ca3af',
  unknown:   '#d1d5db',
}

const STATE_BADGE_VARIANT = {
  available: 'success',
  ringing:   'warning',
  inuse:     'default',
  ringinuse: 'default',
  offline:   'secondary',
  unknown:   'outline',
}

const isDeskPhone = (ua) => !!ua && DESK_PHONE_AGENTS.test(ua)

const fmtTs = (epoch) => {
  if (!epoch) return '—'
  const d = new Date(epoch * 1000)
  if (isNaN(d)) return '—'
  return d.toLocaleString()
}

const tenantCodeFromUser = (user) => (user && user.includes('-') ? user.split('-').pop() : '')

// ── Inline state-history SVG chart ─────────────────────────────────────────
function PeerStateChart({ history, days }) {
  // history: [{state, started_at (iso), ended_at (iso|null)}]
  const now = useMemo(() => Date.now(), [history])
  const t0 = now - days * 24 * 3600 * 1000

  const rows = useMemo(() => {
    if (!Array.isArray(history)) return []
    return history.map(h => ({
      state: h.state,
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

  // Time-axis ticks: one per day boundary
  const ticks = []
  const d = new Date(t0)
  d.setHours(0, 0, 0, 0)
  d.setDate(d.getDate() + 1)
  while (d.getTime() < now) {
    ticks.push(new Date(d))
    d.setDate(d.getDate() + 1)
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto bg-card text-foreground" role="img" aria-label="Peer state history">
      {/* lanes */}
      {states.map((s, i) => (
        <g key={s}>
          <text x={padL - 8} y={padT + i * laneH + laneH / 2 + 4} textAnchor="end" fontSize="11" fill="currentColor">{STATE_LABELS[s]}</text>
          <line x1={padL} x2={W - padR} y1={padT + i * laneH + laneH} y2={padT + i * laneH + laneH} stroke="currentColor" strokeOpacity="0.1" />
        </g>
      ))}
      {/* time ticks */}
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
      {/* bars */}
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

// ── Main page ──────────────────────────────────────────────────────────────
export default function OperatorPanel() {
  const [registrations, setRegistrations] = useState([])
  const [loading, setLoading] = useState(false)
  const [selected, setSelected] = useState(null)
  const [deregistering, setDeregistering] = useState(false)
  const [rebooting, setRebooting] = useState(false)
  const [originateOpen, setOriginateOpen] = useState(false)
  const [origForm, setOrigForm] = useState({ caller: '', callee: '' })
  const [originating, setOriginating] = useState(false)
  const [historyOpen, setHistoryOpen] = useState(false)
  const [historyRow, setHistoryRow] = useState(null)
  const [history, setHistory] = useState(null)
  const [historyLoading, setHistoryLoading] = useState(false)

  const { systemMetrics, dbStatus } = useSelector(selectLive)
  const { currentTenant } = useSelector((s) => s.tenant)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await freeswitch.registrations()
      setRegistrations(res.data?.registrations || [])
    } catch {
      setRegistrations([])
    } finally {
      setLoading(false)
    }
  }, [])

  // Reload when tenant changes or page mounts
  useEffect(() => { load() }, [load, currentTenant?.tenant_uuid])

  const registeredCount = registrations.filter(r => r.state !== 'offline').length

  const handleDeregister = async (reg) => {
    if (!reg?.call_id) return
    setDeregistering(true)
    try {
      await freeswitch.deregister(reg.call_id, reg.profile || 'internal', tenantCodeFromUser(reg.user))
      await load()
      setSelected(null)
    } catch {} finally { setDeregistering(false) }
  }

  const handleReboot = async (reg) => {
    if (!reg?.call_id) return
    setRebooting(true)
    try {
      await freeswitch.reboot(reg.call_id, reg.profile || 'internal', tenantCodeFromUser(reg.user))
    } catch {} finally { setRebooting(false) }
  }

  const openHistory = async (reg) => {
    setHistoryRow(reg)
    setHistoryOpen(true)
    setHistory(null)
    setHistoryLoading(true)
    try {
      const res = await freeswitch.peerHistory(reg.user, 5)
      setHistory(res.data?.history || [])
    } catch {
      setHistory([])
    } finally {
      setHistoryLoading(false)
    }
  }

  const handleOriginate = async () => {
    if (!origForm.caller || !origForm.callee) return
    setOriginating(true)
    try {
      await freeswitch.originate({ caller: origForm.caller, callee: origForm.callee })
      setOriginateOpen(false)
      setOrigForm({ caller: '', callee: '' })
    } catch {} finally { setOriginating(false) }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex gap-2">
          <Badge variant="secondary">{registeredCount} registered / {registrations.length} total</Badge>
          {systemMetrics && (
            <Badge variant="outline">CPU {Math.round(systemMetrics.cpu_percent || 0)}%</Badge>
          )}
          {dbStatus && (
            <Badge variant={dbStatus.ok ? 'success' : 'destructive'}>
              {dbStatus.ok ? `${Math.round((dbStatus.latency || 0) * 1000)}ms` : 'DB Down'}
            </Badge>
          )}
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={load} disabled={loading}>
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Refresh
          </Button>
          <Button variant="outline" size="sm" onClick={() => setOriginateOpen(true)}>
            <Phone className="h-4 w-4" />
            Originate Call
          </Button>
        </div>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-sm">Peers Status</CardTitle></CardHeader>
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Peer</TableHead>
                <TableHead>Extension</TableHead>
                <TableHead>Tech</TableHead>
                <TableHead>IP Address</TableHead>
                <TableHead>Full Contact</TableHead>
                <TableHead>Port</TableHead>
                <TableHead>Registered Since</TableHead>
                <TableHead>User Agent</TableHead>
                <TableHead>Latency</TableHead>
                <TableHead>State</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {registrations.length === 0
                ? <TableRow><TableCell colSpan={11} className="text-center py-6 text-muted-foreground text-sm">No extensions.</TableCell></TableRow>
                : registrations.map((r) => {
                    const desk = isDeskPhone(r.user_agent)
                    const offline = r.state === 'offline'
                    return (
                      <TableRow key={r.user || r.extension} className="hover:bg-muted/50">
                        <TableCell className="font-mono text-xs">{r.user || '—'}</TableCell>
                        <TableCell className="text-xs">{r.extension_name || '—'}</TableCell>
                        <TableCell><Badge variant="outline" className="font-mono text-[10px]">SIP</Badge></TableCell>
                        <TableCell className="font-mono text-xs">{r.network_ip || '—'}</TableCell>
                        <TableCell className="font-mono text-[11px] truncate max-w-48" title={r.full_contact}>{r.full_contact || '—'}</TableCell>
                        <TableCell className="font-mono text-xs">{r.network_port || '—'}</TableCell>
                        <TableCell className="text-xs">{fmtTs(r.registered_since)}</TableCell>
                        <TableCell className="text-xs text-muted-foreground truncate max-w-32" title={r.user_agent}>{r.user_agent || '—'}</TableCell>
                        <TableCell className="text-xs">{r.ping_ms != null ? `${r.ping_ms} ms` : '—'}</TableCell>
                        <TableCell>
                          <Badge variant={STATE_BADGE_VARIANT[r.state] || 'outline'}>
                            {STATE_LABELS[r.state] || r.state || '—'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex gap-1 justify-end">
                            <Button variant="ghost" size="icon" title="Peer Agent Status"
                                    onClick={() => openHistory(r)}>
                              <Activity className="h-4 w-4" />
                            </Button>
                            <Button variant="ghost" size="icon" title="Unregister" disabled={offline || deregistering}
                                    onClick={() => handleDeregister(r)}>
                              <UserX className="h-4 w-4" />
                            </Button>
                            {desk && (
                              <Button variant="ghost" size="icon" title="Reboot" disabled={offline || rebooting}
                                      onClick={() => handleReboot(r)}>
                                <Power className="h-4 w-4" />
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

      <Dialog open={originateOpen} onOpenChange={setOriginateOpen}>
        <DialogContent className="max-w-sm">
          <DialogClose onClose={() => setOriginateOpen(false)} />
          <DialogHeader><DialogTitle className="flex items-center gap-2"><PhoneForwarded className="h-4 w-4" />Originate Call</DialogTitle></DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1.5"><Label>From (caller extension)</Label><Input placeholder="1001" value={origForm.caller} onChange={(e) => setOrigForm(f => ({ ...f, caller: e.target.value }))} /></div>
            <div className="space-y-1.5"><Label>To (destination)</Label><Input placeholder="1002 or +1234567890" value={origForm.callee} onChange={(e) => setOrigForm(f => ({ ...f, callee: e.target.value }))} /></div>
          </div>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setOriginateOpen(false)}>Cancel</Button>
            <Button onClick={handleOriginate} disabled={originating || !origForm.caller || !origForm.callee}>
              {originating && <Loader2 className="h-4 w-4 animate-spin" />}
              Originate
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={historyOpen} onOpenChange={setHistoryOpen}>
        <DialogContent className="max-w-4xl">
          <DialogClose onClose={() => setHistoryOpen(false)} />
          <DialogHeader>
            <DialogTitle>
              Peer Status Graph — {historyRow?.extension_name ? `${historyRow.extension_name} (${historyRow.user})` : historyRow?.user}
            </DialogTitle>
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
