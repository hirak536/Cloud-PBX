import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { extensions, gateways, freeswitch, cdr, destinations } from '@/api'
import { formatDuration, formatDate } from '@/lib/utils'
import { Phone, Network, Activity, PhoneCall, PhoneOff, Clock, TrendingUp, Hash } from 'lucide-react'
import { useSelector } from 'react-redux'
import { selectLive } from '@/store'

const statAccents = [
  'from-sky-500 to-cyan-400',
  'from-violet-500 to-purple-400',
  'from-emerald-500 to-green-400',
  'from-amber-500 to-orange-400',
]

function StatCard({ title, value, sub, icon: Icon, loading, accentIdx = 0, onClick }) {
  const accent = statAccents[accentIdx % statAccents.length]
  return (
    <Card
      onClick={onClick}
      className={`relative overflow-hidden group${onClick ? ' cursor-pointer transition-shadow hover:shadow-md' : ''}`}
    >
      {/* Subtle gradient accent top bar */}
      <div className={`absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r ${accent}`} />
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">{title}</CardTitle>
          <div className={`flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br ${accent} opacity-90 shadow-sm`}>
            <Icon className="h-3.5 w-3.5 text-white" />
          </div>
        </div>
      </CardHeader>
      <CardContent>
        {loading ? (
          <Skeleton className="h-8 w-20 shimmer" />
        ) : (
          <>
            <p className="text-3xl font-extrabold tracking-tight">{value ?? '—'}</p>
            {sub && <p className="text-xs text-muted-foreground mt-1 font-medium">{sub}</p>}
          </>
        )}
      </CardContent>
    </Card>
  )
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [stats, setStats] = useState({})
  const [recentCdr, setRecentCdr] = useState([])
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  const callStartTimes = useRef({})
  const { wsConnected, activeCalls: liveActiveCalls } = useSelector(selectLive)

  useEffect(() => {
    async function load() {
      try {
        const [extRes, gwRes, fsRes, cdrRes, didRes] = await Promise.allSettled([
          extensions.list({ page_size: 1 }),
          gateways.list({ page_size: 100 }),
          freeswitch.status(),
          cdr.list({ page_size: 10, ordering: '-start_stamp' }),
          destinations.list({ page_size: 1 }),
        ])
        const extData  = extRes.status  === 'fulfilled' ? extRes.value.data  : null
        const gwData   = gwRes.status   === 'fulfilled' ? gwRes.value.data   : null
        const fsData   = fsRes.status   === 'fulfilled' ? fsRes.value.data   : null
        const cdrData  = cdrRes.status  === 'fulfilled' ? cdrRes.value.data  : null
        const didData  = didRes.status  === 'fulfilled' ? didRes.value.data  : null
        const gwList   = Array.isArray(gwData) ? gwData : gwData?.results || []
        const upGateways = gwList.filter((g) => g.state === 'REGED' || g.state === 'UP').length
        setStats({
          extensions: extData?.count ?? extData?.length ?? 0,
          dids: didData?.count ?? (Array.isArray(didData) ? didData.length : 0),
          gateways: gwList.length,
          upGateways,
          activeCalls: fsData?.calls ?? 0,
          registrations: fsData?.registrations ?? 0,
          uptime: fsData?.uptime ?? null,
        })
        const cdrList = Array.isArray(cdrData) ? cdrData : cdrData?.results || []
        setRecentCdr(cdrList.slice(0, 8))
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [])

  // Live 1-second tick for call durations
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1000)
    return () => clearInterval(id)
  }, [])

  // On mount: seed call start times from API so duration is accurate immediately
  // (avoids reset-to-zero when navigating back to this page)
  useEffect(() => {
    freeswitch.calls().then(({ data }) => {
      const calls = data.calls || data || []
      const now = Date.now()
      calls.forEach((c) => {
        const id = c.uuid || c.call_uuid
        if (id) callStartTimes.current[id] = now - (Number(c.duration) || 0) * 1000
      })
    }).catch(() => {})
  }, [])

  // Track call start times from WebSocket — only fill gaps (API seed takes priority)
  useEffect(() => {
    const now = Date.now()
    callStartTimes.current = Object.fromEntries(
      liveActiveCalls.map((c) => [
        c.uuid,
        callStartTimes.current[c.uuid] ?? (now - (Number(c.duration) || 0) * 1000),
      ])
    )
  }, [liveActiveCalls])

  return (
    <div className="space-y-6">
      {/* Stat grid */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
        <StatCard title="Extensions"    value={stats.extensions}   icon={Phone}     loading={loading} accentIdx={0}
                  onClick={() => navigate('/extensions')} />
        <StatCard title="DIDs"          value={stats.dids}         icon={Hash}      loading={loading} accentIdx={4}
                  onClick={() => navigate('/destinations')} />
        <StatCard title="Active Calls"  value={liveActiveCalls.length}  icon={PhoneCall} loading={loading} accentIdx={1}
                  onClick={() => navigate('/active-calls')} />
        <StatCard title="Gateways"      value={stats.gateways}     icon={Network}   loading={loading} accentIdx={2}
                  sub={`${stats.upGateways ?? 0} registered`}
                  onClick={() => navigate('/gateways')} />
        <StatCard title="Registrations" value={stats.registrations} icon={Activity} loading={loading} accentIdx={3}
                  onClick={() => navigate('/registrations')} />
      </div>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* Active Calls */}
        <Card>
          <CardHeader className="border-b border-border/50">
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-sm font-semibold">
                <div className="flex h-6 w-6 items-center justify-center rounded-md bg-violet-500/15">
                  <PhoneCall className="h-3.5 w-3.5 text-violet-500" />
                </div>
                Active Calls
              </CardTitle>
              {!loading && (
                <div className={`flex items-center gap-1.5 text-xs font-semibold ${wsConnected ? 'text-emerald-500' : 'text-muted-foreground'}`}>
                  <span className={`h-1.5 w-1.5 rounded-full inline-block ${wsConnected ? 'bg-emerald-500 animate-live-pulse' : 'bg-muted-foreground'}`} />
                  {wsConnected ? 'Live' : 'Connecting…'}
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent className="p-0 overflow-x-auto">
            {loading ? (
              <div className="p-5 space-y-2.5">
                {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-8 w-full shimmer" />)}
              </div>
            ) : liveActiveCalls.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted/50 mb-3">
                  <PhoneOff className="h-6 w-6 opacity-40" />
                </div>
                <p className="text-sm font-medium">No active calls</p>
                <p className="text-xs text-muted-foreground/60 mt-0.5">All lines are clear</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent border-b border-border/50">
                    <TableHead className="text-xs font-semibold uppercase tracking-wide">Caller</TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wide">Destination</TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wide">Duration</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {liveActiveCalls.slice(0, 5).map((call, i) => (
                    <TableRow
                      key={i}
                      onClick={() => navigate('/active-calls')}
                      className="transition-colors cursor-pointer hover:bg-muted/50"
                    >
                      <TableCell className="font-mono text-xs">{call.cid_num || call.caller_id_number}</TableCell>
                      <TableCell className="font-mono text-xs">{call.dest}</TableCell>
                      <TableCell>
                        <Badge variant="secondary" className="text-xs font-mono">
                          {formatDuration(
                            callStartTimes.current[call.uuid]
                              ? Math.floor((Date.now() - callStartTimes.current[call.uuid]) / 1000)
                              : call.duration
                          )}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Recent CDR */}
        <Card>
          <CardHeader className="border-b border-border/50">
            <CardTitle className="flex items-center gap-2 text-sm font-semibold">
              <div className="flex h-6 w-6 items-center justify-center rounded-md bg-sky-500/15">
                <TrendingUp className="h-3.5 w-3.5 text-sky-500" />
              </div>
              Recent Calls
            </CardTitle>
          </CardHeader>
          <CardContent className="p-0 overflow-x-auto">
            {loading ? (
              <div className="p-5 space-y-2.5">
                {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-8 w-full shimmer" />)}
              </div>
            ) : recentCdr.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted/50 mb-3">
                  <Clock className="h-6 w-6 opacity-40" />
                </div>
                <p className="text-sm font-medium">No recent calls</p>
                <p className="text-xs text-muted-foreground/60 mt-0.5">Call history will appear here</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="hover:bg-transparent border-b border-border/50">
                    <TableHead className="text-xs font-semibold uppercase tracking-wide">From</TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wide">To</TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wide">Duration</TableHead>
                    <TableHead className="text-xs font-semibold uppercase tracking-wide">Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recentCdr.map((row) => (
                    <TableRow
                      key={row.uuid || row.call_uuid}
                      onClick={() => navigate('/cdr')}
                      className="transition-colors cursor-pointer hover:bg-muted/50"
                    >
                      <TableCell className="font-mono text-xs">{row.caller_id_number}</TableCell>
                      <TableCell className="font-mono text-xs">{row.destination_number}</TableCell>
                      <TableCell className="text-xs font-mono">{formatDuration(row.duration)}</TableCell>
                      <TableCell>
                        <Badge
                          variant={row.hangup_cause === 'NORMAL_CLEARING' ? 'success' : 'secondary'}
                          className="text-xs"
                        >
                          {row.hangup_cause === 'NORMAL_CLEARING' ? 'Answered' : row.hangup_cause || '—'}
                        </Badge>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
