import { useEffect, useState } from 'react'
import { freeswitch } from '@/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { RefreshCw, Users, PhoneCall, Database, Network, Server, Activity, CheckCircle2, XCircle } from 'lucide-react'
import { formatDuration } from '@/lib/utils'
import { cn } from '@/lib/utils'

function StatBar({ label, pct, detail }) {
  const p = Math.min(100, Math.max(0, pct ?? 0))
  const color = p >= 90 ? 'bg-destructive' : p >= 70 ? 'bg-yellow-500' : 'bg-green-500'
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium">{label}</span>
        <span className="text-muted-foreground tabular-nums">{detail}</span>
      </div>
      <div className="h-2 w-full rounded-full bg-muted overflow-hidden">
        <div className={cn('h-full rounded-full transition-all', color)} style={{ width: `${p}%` }} />
      </div>
    </div>
  )
}

function DbItem({ label, value }) {
  return (
    <div className="flex items-center justify-between rounded-md border px-3 py-2">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className="font-semibold tabular-nums text-sm">{value ?? '—'}</span>
    </div>
  )
}

export default function FreeSWITCH() {
  const [status, setStatus]       = useState(null)
  const [regs, setRegs]           = useState([])
  const [calls, setCalls]         = useState([])
  const [sofia, setSofia]         = useState([])
  const [dbStats, setDbStats]     = useState(null)
  const [srvHealth, setSrvHealth] = useState(null)
  const [loading, setLoading]     = useState(true)

  const load = async () => {
    setLoading(true)
    try {
      const [statusRes, regsRes, callsRes, sofiaRes, dbRes, srvRes] = await Promise.allSettled([
        freeswitch.status(),
        freeswitch.registrations(),
        freeswitch.calls(),
        freeswitch.sofia(),
        freeswitch.dbStats(),
        freeswitch.serverHealth(),
      ])
      if (statusRes.status === 'fulfilled') setStatus(statusRes.value.data)
      if (regsRes.status === 'fulfilled') {
        const d = regsRes.value.data
        setRegs(Array.isArray(d) ? d : d.registrations || [])
      }
      if (callsRes.status === 'fulfilled') {
        const d = callsRes.value.data
        setCalls(Array.isArray(d) ? d : d.calls || d.result || [])
      }
      if (sofiaRes.status === 'fulfilled') setSofia(sofiaRes.value.data?.profiles || [])
      if (dbRes.status === 'fulfilled')    setDbStats(dbRes.value.data)
      if (srvRes.status === 'fulfilled')   setSrvHealth(srvRes.value.data)
    } finally { setLoading(false) }
  }

  useEffect(() => {
    load()
    const interval = setInterval(async () => {
      try {
        const [statusRes, regsRes, callsRes, srvRes] = await Promise.allSettled([
          freeswitch.status(),
          freeswitch.registrations(),
          freeswitch.calls(),
          freeswitch.serverHealth(),
        ])
        if (statusRes.status === 'fulfilled') setStatus(statusRes.value.data)
        if (regsRes.status === 'fulfilled') {
          const d = regsRes.value.data
          setRegs(Array.isArray(d) ? d : d.registrations || [])
        }
        if (srvRes.status === 'fulfilled') setSrvHealth(srvRes.value.data)
        if (callsRes.status === 'fulfilled') {
          const d = callsRes.value.data
          setCalls(Array.isArray(d) ? d : d.calls || d.result || [])
        }
      } catch (_) {}
    }, 5000)
    return () => clearInterval(interval)
  }, [])

  const cpuUsed = status?.cpu_idle != null ? (100 - status.cpu_idle).toFixed(1) : null
  const cpuMin  = status?.cpu_idle_min != null ? (100 - status.cpu_idle_min).toFixed(1) : null

  return (
    <div className="space-y-6">

      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {!loading && status && (
            <Badge variant={status.running ? 'success' : 'destructive'} className="text-sm">
              {status.running ? 'FreeSWITCH Running' : 'FreeSWITCH Stopped'}
            </Badge>
          )}
          {!loading && status?.version && (
            <span className="text-xs text-muted-foreground">v{status.version}</span>
          )}
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <span className="inline-block h-2 w-2 rounded-full bg-green-500 animate-pulse" />
            Live
          </span>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={cn('h-4 w-4', loading && 'animate-spin')} />
          Refresh
        </Button>
      </div>

      {/* Server Overview Table */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <Server className="h-4 w-4" />
            Server Overview
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Version</TableHead>
                <TableHead>Uptime</TableHead>
                <TableHead>Active Sessions</TableHead>
                <TableHead>Total Sessions</TableHead>
                <TableHead>Sessions/Sec</TableHead>
                <TableHead>Max Sessions</TableHead>
                <TableHead>Registrations</TableHead>
                <TableHead>Active Calls</TableHead>
                <TableHead>CPU Usage</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading
                ? <TableRow>{[...Array(9)].map((_, i) => <TableCell key={i}><Skeleton className="h-4 w-full" /></TableCell>)}</TableRow>
                : (
                  <TableRow>
                    <TableCell className="font-mono text-sm">{status?.version ? `v${status.version}` : '—'}</TableCell>
                    <TableCell className="tabular-nums text-sm">{status?.uptime ? formatDuration(status.uptime) : '—'}</TableCell>
                    <TableCell>
                      <Badge variant="secondary">{status?.sessions_active ?? status?.calls ?? 0}</Badge>
                    </TableCell>
                    <TableCell className="tabular-nums text-sm">{status?.sessions_since_startup ?? 0}</TableCell>
                    <TableCell className="tabular-nums text-sm">
                      {status?.sessions_per_sec ?? 0}
                      {status?.sessions_per_sec_max ? <span className="text-muted-foreground text-xs ml-1">(max {status.sessions_per_sec_max})</span> : null}
                    </TableCell>
                    <TableCell className="tabular-nums text-sm">{status?.max_sessions ?? 0}</TableCell>
                    <TableCell>
                      <Badge variant={regs.length > 0 ? 'success' : 'secondary'}>{regs.length}</Badge>
                    </TableCell>
                    <TableCell>
                      <Badge variant={calls.length > 0 ? 'default' : 'secondary'}>{calls.length}</Badge>
                    </TableCell>
                    <TableCell>
                      {cpuUsed != null
                        ? <Badge variant={parseFloat(cpuUsed) > 80 ? 'destructive' : 'outline'}>{cpuUsed}%{cpuMin ? ` / peak ${cpuMin}%` : ''}</Badge>
                        : '—'}
                    </TableCell>
                  </TableRow>
                )
              }
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* OS Stats */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <Activity className="h-4 w-4" />
            System Resources
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {loading ? (
            <div className="space-y-3">
              {[...Array(5)].map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}
            </div>
          ) : !srvHealth ? (
            <p className="text-sm text-muted-foreground">No data available.</p>
          ) : (
            <>
              {/* Row 1: summary chips */}
              <div className="flex flex-wrap gap-2 text-xs">
                {srvHealth.system.uptime_sec != null && (
                  <span className="rounded-full border px-2.5 py-1 text-muted-foreground">
                    Uptime <span className="font-medium text-foreground">{formatDuration(srvHealth.system.uptime_sec)}</span>
                  </span>
                )}
                {srvHealth.system.cpu?.cores != null && (
                  <span className="rounded-full border px-2.5 py-1 text-muted-foreground">
                    <span className="font-medium text-foreground">{srvHealth.system.cpu.cores}</span> CPU cores
                  </span>
                )}
                {srvHealth.system.process_count != null && (
                  <span className="rounded-full border px-2.5 py-1 text-muted-foreground">
                    <span className="font-medium text-foreground">{srvHealth.system.process_count}</span> processes
                  </span>
                )}
                {srvHealth.system.network && (
                  <span className="rounded-full border px-2.5 py-1 text-muted-foreground">
                    Net ↑ <span className="font-medium text-foreground">{srvHealth.system.network.bytes_sent_gb} GB</span>
                    {' / '}↓ <span className="font-medium text-foreground">{srvHealth.system.network.bytes_recv_gb} GB</span>
                  </span>
                )}
              </div>

              {/* CPU */}
              {srvHealth.system.cpu?.pct != null && (
                <StatBar
                  label="CPU Usage"
                  pct={srvHealth.system.cpu.pct}
                  detail={`load ${srvHealth.system.load_avg?.['1min']} / ${srvHealth.system.load_avg?.['5min']} / ${srvHealth.system.load_avg?.['15min']} (1m · 5m · 15m)`}
                />
              )}

              {/* Memory */}
              {srvHealth.system.memory?.total_gb != null && (
                <StatBar
                  label="Memory"
                  pct={srvHealth.system.memory.pct}
                  detail={`${srvHealth.system.memory.used_gb} / ${srvHealth.system.memory.total_gb} GB  ·  cached ${srvHealth.system.memory.cached_gb} GB`}
                />
              )}

              {/* Swap */}
              {srvHealth.system.swap?.total_gb > 0 && (
                <StatBar
                  label="Swap"
                  pct={srvHealth.system.swap.pct}
                  detail={`${srvHealth.system.swap.used_gb} / ${srvHealth.system.swap.total_gb} GB`}
                />
              )}

              {/* Disks */}
              {srvHealth.system.disks && Object.entries(srvHealth.system.disks).map(([path, d]) =>
                d ? (
                  <StatBar
                    key={path}
                    label={`Disk ${path}`}
                    pct={d.pct}
                    detail={`${d.used_gb} / ${d.total_gb} GB`}
                  />
                ) : null
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Health Status */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <CheckCircle2 className="h-4 w-4" />
            Health Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex gap-4">
              {[...Array(4)].map((_, i) => <Skeleton key={i} className="h-10 w-32" />)}
            </div>
          ) : (
            <div className="flex flex-wrap gap-3">
              {[
                { label: 'Django',   ok: true },
                { label: 'Database', ok: srvHealth?.health?.database?.ok, error: srvHealth?.health?.database?.error },
                { label: 'Celery',   ok: srvHealth?.health?.celery?.ok,   extra: srvHealth?.health?.celery?.workers?.length ? `${srvHealth.health.celery.workers.length} worker(s)` : null },
                { label: 'FreeSWITCH', ok: status?.running },
              ].map(({ label, ok, error, extra }) => (
                <div key={label} className={cn(
                  'flex items-center gap-2 rounded-md border px-3 py-2 text-sm',
                  ok === false ? 'border-destructive/50 bg-destructive/5' : 'border-green-500/30 bg-green-500/5'
                )}>
                  {ok === false
                    ? <XCircle className="h-4 w-4 text-destructive shrink-0" />
                    : <CheckCircle2 className="h-4 w-4 text-green-500 shrink-0" />
                  }
                  <span className="font-medium">{label}</span>
                  {extra && <span className="text-xs text-muted-foreground">{extra}</span>}
                  {error && <span className="text-xs text-destructive truncate max-w-xs" title={error}>{error}</span>}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* SIP Profiles */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <Network className="h-4 w-4" />
            SIP Profiles
            {!loading && <Badge variant="secondary">{sofia.length}</Badge>}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Profile</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>SIP URI</TableHead>
                <TableHead>State</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading
                ? [...Array(2)].map((_, i) => <TableRow key={i}>{[...Array(4)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}</TableRow>)
                : sofia.length === 0
                  ? <TableRow><TableCell colSpan={4} className="text-center py-6 text-muted-foreground text-sm">No profiles found.</TableCell></TableRow>
                  : sofia.map((p) => (
                      <TableRow key={p.name}>
                        <TableCell className="font-mono font-medium">{p.name}</TableCell>
                        <TableCell><Badge variant="outline" className="capitalize">{p.type}</Badge></TableCell>
                        <TableCell className="font-mono text-xs text-muted-foreground">{p.data || '—'}</TableCell>
                        <TableCell><Badge variant={p.running ? 'success' : 'destructive'}>{p.state}</Badge></TableCell>
                      </TableRow>
                    ))
              }
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Active Calls */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <PhoneCall className="h-4 w-4" />
            Active Calls
            {!loading && <Badge variant="secondary">{calls.length}</Badge>}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>From</TableHead>
                <TableHead>To</TableHead>
                <TableHead>Direction</TableHead>
                <TableHead>State</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>Codec</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading
                ? [...Array(3)].map((_, i) => <TableRow key={i}>{[...Array(6)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}</TableRow>)
                : calls.length === 0
                  ? <TableRow><TableCell colSpan={6} className="text-center py-8 text-muted-foreground">No active calls.</TableCell></TableRow>
                  : calls.map((c, i) => (
                      <TableRow key={i}>
                        <TableCell className="font-mono text-sm">{c.cid_num || c.caller_id_number || '—'}</TableCell>
                        <TableCell className="font-mono text-sm">{c.dest || c.destination_number || '—'}</TableCell>
                        <TableCell><Badge variant="outline" className="capitalize">{c.direction || 'inbound'}</Badge></TableCell>
                        <TableCell><Badge variant="secondary">{c.callstate || c.state || '—'}</Badge></TableCell>
                        <TableCell className="tabular-nums text-sm">{formatDuration(c.duration || c.elapsed_seconds)}</TableCell>
                        <TableCell className="font-mono text-xs text-muted-foreground">{c.read_codec || '—'}</TableCell>
                      </TableRow>
                    ))
              }
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Registrations */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <Users className="h-4 w-4" />
            Active Registrations
            {!loading && <Badge variant="secondary">{regs.length}</Badge>}
          </CardTitle>
        </CardHeader>
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Extension</TableHead>
                <TableHead>Realm</TableHead>
                <TableHead>Network IP</TableHead>
                <TableHead>Port</TableHead>
                <TableHead>User Agent</TableHead>
                <TableHead>Expires</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading
                ? [...Array(4)].map((_, i) => <TableRow key={i}>{[...Array(6)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}</TableRow>)
                : regs.length === 0
                  ? <TableRow><TableCell colSpan={6} className="text-center py-8 text-muted-foreground">No registrations.</TableCell></TableRow>
                  : regs.map((r, i) => (
                      <TableRow key={i}>
                        <TableCell className="font-mono font-medium">{r.user || '—'}</TableCell>
                        <TableCell className="font-mono text-xs text-muted-foreground">{r.realm || '—'}</TableCell>
                        <TableCell className="font-mono text-sm">{r.network_ip || '—'}</TableCell>
                        <TableCell className="tabular-nums text-sm">{r.network_port || '—'}</TableCell>
                        <TableCell className="text-xs text-muted-foreground truncate max-w-xs">{r.user_agent || '—'}</TableCell>
                        <TableCell className="tabular-nums text-sm">{r.expires ? `${r.expires}s` : '—'}</TableCell>
                      </TableRow>
                    ))
              }
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* DB Stats */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-sm">
            <Database className="h-4 w-4" />
            Database Records
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {[...Array(12)].map((_, i) => <Skeleton key={i} className="h-10 w-full" />)}
            </div>
          ) : (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
              <DbItem label="Extensions"   value={dbStats?.extensions} />
              <DbItem label="Voicemails"   value={dbStats?.voicemails} />
              <DbItem label="Gateways"     value={dbStats?.gateways} />
              <DbItem label="Ring Groups"  value={dbStats?.ring_groups} />
              <DbItem label="IVR Menus"    value={dbStats?.ivr_menus} />
              <DbItem label="DIDs"         value={dbStats?.destinations} />
              <DbItem label="Devices"      value={dbStats?.devices} />
              <DbItem label="Conferences"  value={dbStats?.conferences} />
              <DbItem label="Call Centers" value={dbStats?.call_centers} />
              <DbItem label="Dialplans"    value={dbStats?.dialplans} />
              <DbItem label="Tenants"      value={dbStats?.tenants} />
              <DbItem label="Domains"      value={dbStats?.domains} />
            </div>
          )}
        </CardContent>
      </Card>

    </div>
  )
}
