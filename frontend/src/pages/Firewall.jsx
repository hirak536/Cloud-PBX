import { useEffect, useState, useCallback } from 'react'
import { firewall as firewallApi } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import {
  RefreshCw, Loader2, ShieldOff, Shield, Search, X,
  ShieldCheck, ShieldAlert, AlertTriangle, CheckCircle2,
  Ban, ListFilter, Activity,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// ── helpers ───────────────────────────────────────────────────────────────────

function Msg({ msg }) {
  if (!msg) return null
  return (
    <p className={cn('text-xs mt-1.5', msg.type === 'success' ? 'text-green-600' : 'text-red-500')}>
      {msg.type === 'success' ? '✓' : '✗'} {msg.text}
    </p>
  )
}

function StatCard({ icon: Icon, label, value, color }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-3 py-4 px-4">
        <div className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-lg', color)}>
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0">
          <p className="text-2xl font-bold leading-none">{value}</p>
          <p className="text-xs text-muted-foreground mt-0.5 truncate">{label}</p>
        </div>
      </CardContent>
    </Card>
  )
}

const ACTION_COLORS = {
  ALLOW:  'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
  DENY:   'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  LIMIT:  'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  REJECT: 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400',
}

// ── main component ────────────────────────────────────────────────────────────

export default function Firewall() {
  const [jails, setJails]     = useState([])
  const [ufw, setUfw]         = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]     = useState(null)
  const [expandedJail, setExpandedJail] = useState(null)
  const [inlineUnbanning, setInlineUnbanning] = useState({})
  const [inlineBanning, setInlineBanning] = useState({})
  const [jailTab, setJailTab] = useState('banned')

  // action panel
  const [tab, setTab]               = useState('unban')
  const [actionIp, setActionIp]     = useState('')
  const [actionJail, setActionJail] = useState('')
  const [actionLoading, setActionLoading] = useState(false)
  const [actionMsg, setActionMsg]   = useState(null)
  const [checkResult, setCheckResult] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [f2b, ufwRes] = await Promise.allSettled([
        firewallApi.fail2banStatus(),
        firewallApi.ufwStatus(),
      ])
      if (f2b.status === 'fulfilled') setJails(f2b.value.data)
      else setError(f2b.reason?.response?.data?.error || 'Failed to load fail2ban')
      if (ufwRes.status === 'fulfilled') setUfw(ufwRes.value.data)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const totalBanned = jails.reduce((s, j) => s + j.banned_ips.length, 0)
  const totalFailed = jails.reduce((s, j) => s + j.currently_failed, 0)

  // ── inline one-click unban ────────────────────────────────────────────────
  const quickUnban = async (ip, jail) => {
    const key = `${jail}:${ip}`
    setInlineUnbanning(p => ({ ...p, [key]: true }))
    try {
      await firewallApi.unban({ ip, jail })
      await load()
    } finally {
      setInlineUnbanning(p => { const n = { ...p }; delete n[key]; return n })
    }
  }

  const quickBan = async (ip, jail) => {
    const key = `${jail}:${ip}`
    setInlineBanning(p => ({ ...p, [key]: true }))
    try {
      await firewallApi.ban({ ip, jail })
      await load()
    } finally {
      setInlineBanning(p => { const n = { ...p }; delete n[key]; return n })
    }
  }

  // ── action panel ──────────────────────────────────────────────────────────
  const clearAction = () => { setActionMsg(null); setCheckResult(null) }

  const handleAction = async () => {
    const ip = actionIp.trim()
    if (!ip) return
    setActionLoading(true)
    clearAction()
    try {
      if (tab === 'unban') {
        await firewallApi.unban({ ip, jail: actionJail.trim() || undefined })
        setActionMsg({ type: 'success', text: `Unbanned ${ip}${actionJail ? ` from ${actionJail}` : ' from all jails'}` })
        setActionIp('')
        load()
      } else if (tab === 'whitelist') {
        const jail = actionJail.trim() || 'sshd'
        await firewallApi.whitelist({ ip, jail })
        setActionMsg({ type: 'success', text: `Whitelisted ${ip} in ${jail}` })
        setActionIp('')
      } else {
        const { data } = await firewallApi.checkIp(ip)
        setCheckResult(data)
      }
    } catch (e) {
      setActionMsg({ type: 'error', text: e.response?.data?.error || 'Operation failed' })
    } finally {
      setActionLoading(false)
    }
  }

  const handleUnblockIptables = async () => {
    if (!checkResult?.ip) return
    setActionLoading(true)
    try {
      await firewallApi.unblockIp({ ip: checkResult.ip, chain: 'INPUT' })
      setActionMsg({ type: 'success', text: `Unblocked ${checkResult.ip} from iptables` })
      setCheckResult(null)
      setActionIp('')
    } catch (e) {
      setActionMsg({ type: 'error', text: e.response?.data?.error || 'Failed to unblock' })
    } finally {
      setActionLoading(false)
    }
  }

  const actionPlaceholder  = tab === 'whitelist' ? 'Jail (default: sshd)' : 'Jail (blank = all jails)'
  const actionBtnLabel     = { unban: 'Unban IP', whitelist: 'Whitelist IP', check: 'Check iptables' }
  const actionBtnVariant   = { unban: 'destructive', whitelist: 'default', check: 'outline' }

  return (
    <div className="flex flex-col gap-4 h-full">

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">Firewall</h1>
          <p className="text-xs text-muted-foreground mt-0.5">Fail2ban · UFW · iptables</p>
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
          <span className="ml-1.5">Refresh</span>
        </Button>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <StatCard icon={ListFilter} label="Active Jails"     value={loading ? '…' : jails.length}  color="bg-primary/10 text-primary" />
        <StatCard icon={Ban}        label="Banned IPs"       value={loading ? '…' : totalBanned}   color="bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400" />
        <StatCard icon={Activity}   label="Currently Failed" value={loading ? '…' : totalFailed}   color="bg-amber-100 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400" />
        <StatCard
          icon={ufw?.status === 'active' ? ShieldCheck : ShieldAlert}
          label={`UFW · ${ufw?.status ?? '…'}`}
          value={ufw ? `${ufw.rules?.length ?? 0} rules` : '…'}
          color={ufw?.status === 'active'
            ? 'bg-green-100 text-green-600 dark:bg-green-900/30 dark:text-green-400'
            : 'bg-muted text-muted-foreground'}
        />
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/8 px-4 py-2.5 text-sm text-destructive">
          <AlertTriangle className="h-4 w-4 shrink-0" /> {error}
        </div>
      )}

      {/* Two-column layout */}
      <div className="flex gap-4 flex-1 min-h-0">

        {/* Left — jails + UFW rules */}
        <div className="flex-1 min-w-0 space-y-4 overflow-y-auto">

          {/* Fail2ban Jails */}
          <Card>
            <CardHeader className="py-3 px-4 border-b">
              <CardTitle className="text-sm font-semibold flex items-center gap-2">
                <Shield className="h-4 w-4 text-primary" /> Fail2ban Jails
                <div className="ml-auto flex rounded-md border overflow-hidden text-[11px]">
                  <button
                    onClick={() => setJailTab('banned')}
                    className={cn('px-3 py-1 flex items-center gap-1 transition-colors',
                      jailTab === 'banned' ? 'bg-primary text-primary-foreground' : 'text-muted-foreground hover:bg-muted')}
                  >
                    <Ban className="h-3 w-3" /> Banned
                    {!loading && <span className="ml-1 font-bold">{totalBanned}</span>}
                  </button>
                  <button
                    onClick={() => setJailTab('failed')}
                    className={cn('px-3 py-1 flex items-center gap-1 transition-colors',
                      jailTab === 'failed' ? 'bg-amber-500 text-white' : 'text-muted-foreground hover:bg-muted')}
                  >
                    <Activity className="h-3 w-3" /> Failed
                    {!loading && <span className="ml-1 font-bold">{totalFailed}</span>}
                  </button>
                </div>
              </CardTitle>
            </CardHeader>
            <CardContent className="p-0 overflow-x-auto">
              {loading ? (
                <div className="flex items-center justify-center gap-2 py-10 text-muted-foreground text-sm">
                  <Loader2 className="h-4 w-4 animate-spin" /> Loading…
                </div>
              ) : jails.length === 0 ? (
                <div className="text-center py-10 text-muted-foreground text-sm">No jails found</div>
              ) : jailTab === 'banned' ? (
                <div className="divide-y">
                  <div className="grid grid-cols-[160px_1fr_90px_100px] gap-2 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground bg-muted/30">
                    <span>Jail</span><span>Banned IPs</span><span>Total Banned</span><span>Status</span>
                  </div>
                  {jails.map(jail => {
                    const isExpanded = expandedJail === jail.jail
                    return (
                      <div key={jail.jail}>
                        <button
                          onClick={() => setExpandedJail(isExpanded ? null : jail.jail)}
                          className="grid grid-cols-[160px_1fr_90px_100px] gap-2 w-full items-center px-4 py-2.5 hover:bg-muted/40 transition-colors text-left"
                        >
                          <span className="font-mono text-sm font-medium truncate">{jail.jail}</span>
                          <span className="text-xs text-muted-foreground">
                            {jail.banned_ips.length === 0
                              ? <span className="text-green-600">none</span>
                              : <span className="font-mono">{jail.banned_ips.slice(0, 3).join(', ')}{jail.banned_ips.length > 3 ? ` +${jail.banned_ips.length - 3} more` : ''}</span>
                            }
                          </span>
                          <span className="text-xs font-semibold text-red-500">{jail.total_banned}</span>
                          <span className="flex items-center gap-1.5">
                            {jail.banned_ips.length > 0 ? (
                              <Badge variant="destructive" className="text-[10px] px-1.5 py-0">
                                {jail.banned_ips.length} banned
                              </Badge>
                            ) : (
                              <Badge variant="outline" className="text-[10px] px-1.5 py-0 text-green-600 border-green-300 dark:border-green-700">
                                clean
                              </Badge>
                            )}
                            <span className={cn('text-muted-foreground text-xs transition-transform duration-150', isExpanded && 'rotate-180')}>▾</span>
                          </span>
                        </button>
                        {isExpanded && (
                          <div className="px-4 pb-3 pt-1 bg-muted/20 border-t">
                            {jail.banned_ips.length === 0 ? (
                              <div className="flex items-center gap-1.5 text-xs text-green-600 py-1.5">
                                <CheckCircle2 className="h-3.5 w-3.5" /> No banned IPs in this jail
                              </div>
                            ) : (
                              <div className="flex flex-wrap gap-1.5 pt-1.5">
                                {jail.banned_ips.map(ip => {
                                  const key = `${jail.jail}:${ip}`
                                  const busy = !!inlineUnbanning[key]
                                  return (
                                    <span key={ip} className="inline-flex items-center gap-1 rounded-md border border-red-200 bg-red-50 dark:bg-red-900/20 dark:border-red-800 px-2 py-0.5 font-mono text-xs text-red-700 dark:text-red-400">
                                      {ip}
                                      <button
                                        onClick={e => { e.stopPropagation(); quickUnban(ip, jail.jail) }}
                                        disabled={busy}
                                        title={`Unban ${ip}`}
                                        className="ml-0.5 rounded hover:bg-red-200 dark:hover:bg-red-800 p-0.5 transition-colors disabled:opacity-50"
                                      >
                                        {busy ? <Loader2 className="h-2.5 w-2.5 animate-spin" /> : <X className="h-2.5 w-2.5" />}
                                      </button>
                                    </span>
                                  )
                                })}
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              ) : (
                /* Failed tab */
                <div className="divide-y">
                  {jails.filter(j => j.currently_failed > 0).length === 0 ? (
                    <div className="flex items-center justify-center gap-1.5 py-10 text-sm text-green-600">
                      <CheckCircle2 className="h-4 w-4" /> No active failures
                    </div>
                  ) : (
                    jails.filter(j => j.currently_failed > 0).map(jail => (
                      <div key={jail.jail}>
                        <div className="flex items-center gap-2 px-4 py-2 bg-muted/30 border-b">
                          <span className="font-mono text-sm font-semibold">{jail.jail}</span>
                          <Badge className="text-[10px] px-1.5 py-0 bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                            {jail.currently_failed} failing
                          </Badge>
                        </div>
                        <div className="px-4 py-2.5 flex flex-wrap gap-1.5">
                          {jail.failing_ips && jail.failing_ips.length > 0 ? jail.failing_ips.map(ip => {
                            const key = `${jail.jail}:${ip}`
                            const busy = !!inlineBanning[key]
                            return (
                              <span key={ip} className="inline-flex items-center gap-1 rounded-md border border-amber-200 bg-amber-50 dark:bg-amber-900/20 dark:border-amber-800 px-2 py-0.5 font-mono text-xs text-amber-700 dark:text-amber-400">
                                {ip}
                                <button
                                  onClick={() => quickBan(ip, jail.jail)}
                                  disabled={busy}
                                  title={`Ban ${ip} from ${jail.jail}`}
                                  className="ml-0.5 rounded hover:bg-amber-200 dark:hover:bg-amber-800 p-0.5 transition-colors disabled:opacity-50"
                                >
                                  {busy ? <Loader2 className="h-2.5 w-2.5 animate-spin" /> : <Ban className="h-2.5 w-2.5" />}
                                </button>
                              </span>
                            )
                          }) : (
                            <span className="text-xs text-muted-foreground italic">Log data unavailable — use manual ban</span>
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </CardContent>
          </Card>

          {/* UFW Rules */}
          {ufw && (
            <Card>
              <CardHeader className="py-3 px-4 border-b">
                <CardTitle className="text-sm font-semibold flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-green-600" />
                  UFW Rules
                  <Badge className={cn('ml-1 text-xs px-1.5 py-0 capitalize font-medium',
                    ufw.status === 'active'
                      ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                      : 'bg-muted text-muted-foreground')}>
                    {ufw.status}
                  </Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="p-0 overflow-x-auto">
                {!ufw.rules?.length ? (
                  <div className="text-center py-8 text-muted-foreground text-sm">No rules configured</div>
                ) : (
                  <div className="divide-y">
                    <div className="grid grid-cols-[2rem_1fr_6rem_4rem_1fr] gap-3 px-4 py-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground bg-muted/30">
                      <span>#</span><span>To / Port</span><span>Action</span><span>Dir</span><span>From</span>
                    </div>
                    {ufw.rules.map(rule => (
                      <div key={rule.num} className="grid grid-cols-[2rem_1fr_6rem_4rem_1fr] gap-3 px-4 py-2 text-xs items-center hover:bg-muted/30 transition-colors">
                        <span className="text-muted-foreground font-mono">{rule.num}</span>
                        <span className="font-mono truncate" title={rule.to}>{rule.to || '—'}</span>
                        <span>
                          {rule.action ? (
                            <span className={cn('inline-block rounded px-1.5 py-0.5 font-semibold text-[10px]',
                              ACTION_COLORS[rule.action] ?? 'bg-muted text-muted-foreground')}>
                              {rule.action}
                            </span>
                          ) : '—'}
                        </span>
                        <span className="text-muted-foreground">{rule.direction || '—'}</span>
                        <span className="font-mono truncate" title={rule.from_}>{rule.from_ || 'Anywhere'}</span>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </div>

        {/* Right — sticky action panel */}
        <div className="w-64 shrink-0">
          <Card className="sticky top-0">
            <CardHeader className="py-3 px-4 border-b">
              <CardTitle className="text-sm font-semibold">IP Actions</CardTitle>
            </CardHeader>
            <CardContent className="p-3 space-y-3">

              {/* Tab switcher */}
              <div className="flex rounded-lg border overflow-hidden text-[11px]">
                {[
                  { key: 'unban',     icon: ShieldOff, label: 'Unban'     },
                  { key: 'whitelist', icon: Shield,     label: 'Whitelist' },
                  { key: 'check',     icon: Search,     label: 'Check'     },
                ].map(({ key, icon: Icon, label }) => (
                  <button
                    key={key}
                    onClick={() => { setTab(key); clearAction() }}
                    className={cn(
                      'flex-1 flex flex-col items-center gap-0.5 py-2 transition-colors',
                      tab === key
                        ? 'bg-primary text-primary-foreground'
                        : 'text-muted-foreground hover:bg-muted'
                    )}
                  >
                    <Icon className="h-3.5 w-3.5" />
                    <span>{label}</span>
                  </button>
                ))}
              </div>

              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {tab === 'unban'     && 'Remove an IP from fail2ban jail(s).'}
                {tab === 'whitelist' && 'Add an IP to the ignore list so it never gets banned.'}
                {tab === 'check'     && 'Look up if an IP is blocked in the iptables INPUT chain.'}
              </p>

              <div className="space-y-2">
                <Input
                  placeholder="IP address"
                  value={actionIp}
                  onChange={e => { setActionIp(e.target.value); clearAction() }}
                  className="font-mono text-xs h-8"
                />
                {tab !== 'check' && (
                  <Input
                    placeholder={actionPlaceholder}
                    value={actionJail}
                    onChange={e => setActionJail(e.target.value)}
                    className="text-xs h-8"
                  />
                )}
              </div>

              <Button
                size="sm"
                variant={actionBtnVariant[tab]}
                className="w-full h-8 text-xs"
                disabled={actionLoading || !actionIp.trim()}
                onClick={handleAction}
              >
                {actionLoading && <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />}
                {actionBtnLabel[tab]}
              </Button>

              <Msg msg={actionMsg} />

              {/* iptables check result */}
              {checkResult && !checkResult.error && (
                <div className="space-y-2 rounded-lg border bg-muted/30 p-2.5">
                  <div className="flex items-center gap-2">
                    <Badge className={cn('text-xs',
                      checkResult.blocked
                        ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                        : 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400')}>
                      {checkResult.blocked ? 'BLOCKED' : 'CLEAR'}
                    </Badge>
                    <span className="font-mono text-[10px] text-muted-foreground truncate">{checkResult.ip}</span>
                  </div>
                  {checkResult.rules?.map((rule, i) => (
                    <p key={i} className="text-[10px] font-mono bg-muted rounded px-2 py-1 break-all">{rule}</p>
                  ))}
                  {checkResult.blocked && (
                    <Button size="sm" variant="destructive" className="w-full h-7 text-xs" onClick={handleUnblockIptables} disabled={actionLoading}>
                      <X className="h-3 w-3 mr-1" /> Unblock from iptables
                    </Button>
                  )}
                </div>
              )}
              {checkResult?.error && <p className="text-xs text-red-500">✗ {checkResult.error}</p>}

              {/* Tip */}
              <div className="rounded-lg bg-muted/50 border px-2.5 py-2 text-[10px] text-muted-foreground leading-relaxed">
                <strong className="text-foreground block mb-0.5">Quick unban</strong>
                Click a jail row, then tap the <X className="inline h-2.5 w-2.5 mx-0.5" /> next to any IP chip to unban instantly.
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
