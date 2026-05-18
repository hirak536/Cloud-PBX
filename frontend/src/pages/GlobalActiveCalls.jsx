import { useEffect, useRef, useState } from 'react'
import { useSelector } from 'react-redux'
import { selectLive } from '@/store'
import { freeswitch } from '@/api'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { formatDuration } from '@/lib/utils'
import { PhoneOff, Ear, MessageSquare, Users } from 'lucide-react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

const MODES = [
  { key: 'listen',  label: 'Listen',  icon: Ear,           title: 'Listen Only',  desc: 'Hear both legs silently' },
  { key: 'whisper', label: 'Whisper', icon: MessageSquare, title: 'Whisper',       desc: 'Speak to called party only' },
  { key: 'barge',   label: 'Barge',   icon: Users,         title: 'Barge In',      desc: 'Full three-way, both legs hear you' },
]

export default function GlobalActiveCalls() {
  const { wsConnected, activeCalls } = useSelector(selectLive)
  const [hanging, setHanging]   = useState(null)
  const [tick, setTick]         = useState(0)
  const callStartRef            = useRef({})
  const seededRef               = useRef(false)
  const [eavesdropDialog, setEavesdropDialog] = useState(null)
  const [spyExt, setSpyExt]     = useState('')
  const [spying, setSpying]     = useState(false)

  // Seed accurate durations from API on mount
  useEffect(() => {
    freeswitch.calls().then(({ data }) => {
      const calls = data.calls || data || []
      const now = Date.now()
      calls.forEach((c) => {
        const id = c.uuid || c.call_uuid
        if (id) callStartRef.current[id] = now - (Number(c.duration) || 0) * 1000
      })
      seededRef.current = true
    }).catch(() => { seededRef.current = true })
  }, [])

  // 1-second ticker for duration display
  useEffect(() => {
    const t = setInterval(() => setTick((n) => n + 1), 1000)
    return () => clearInterval(t)
  }, [])

  // Track new calls from WS
  useEffect(() => {
    const now = Date.now()
    activeCalls.forEach((c) => {
      const id = c.uuid || c.call_uuid
      if (!callStartRef.current[id])
        callStartRef.current[id] = now - (Number(c.duration) || 0) * 1000
    })
    const ids = new Set(activeCalls.map((c) => c.uuid || c.call_uuid))
    Object.keys(callStartRef.current).forEach((id) => { if (!ids.has(id)) delete callStartRef.current[id] })
  }, [activeCalls])

  const getLiveDuration = (c) => {
    const id = c.uuid || c.call_uuid
    const startTime = callStartRef.current[id]
    if (!startTime || !c.answered) return Number(c.duration) || 0
    return Math.floor((Date.now() - startTime) / 1000)
  }

  const handleHangup = async (uuid) => {
    if (!confirm('Hangup this call?')) return
    setHanging(uuid)
    try { await freeswitch.hangup({ uuid }) }
    catch { toast.error('Hangup failed') }
    finally { setHanging(null) }
  }

  const handleEavesdrop = async () => {
    if (!spyExt.trim()) return
    setSpying(true)
    try {
      await freeswitch.eavesdrop({ uuid: eavesdropDialog.uuid, spy_ext: spyExt.trim(), mode: eavesdropDialog.mode })
      toast.success(`${MODES.find(m => m.key === eavesdropDialog.mode)?.title} started`)
      setEavesdropDialog(null)
    } catch (err) {
      toast.error(err?.response?.data?.error || 'Eavesdrop failed')
    } finally { setSpying(false) }
  }

  const activeMode = MODES.find(m => m.key === eavesdropDialog?.mode)

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <Badge variant={activeCalls.length > 0 ? 'success' : 'secondary'}>{activeCalls.length} active</Badge>
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          <span className={cn('inline-block h-2 w-2 rounded-full', wsConnected ? 'bg-green-500 animate-pulse' : 'bg-amber-400')} />
          {wsConnected ? 'Live · All Tenants' : 'Connecting…'}
        </span>
      </div>

      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Call UUID</TableHead>
                <TableHead>Caller</TableHead>
                <TableHead>Caller ID</TableHead>
                <TableHead>Destination</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>State</TableHead>
                <TableHead className="w-36">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {activeCalls.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="py-14 text-center text-muted-foreground text-sm">
                    <div className="flex flex-col items-center gap-2">
                      <PhoneOff className="h-8 w-8 opacity-40" />
                      <p>No active calls</p>
                    </div>
                  </TableCell>
                </TableRow>
              ) : activeCalls.map((c) => (
                <TableRow key={c.uuid || c.call_uuid}>
                  <TableCell className="font-mono text-xs text-muted-foreground">{(c.uuid || c.call_uuid || '').slice(0, 8)}…</TableCell>
                  <TableCell className="font-mono text-sm">{c.cid_num || c.caller_id_number || '—'}</TableCell>
                  <TableCell className="text-sm">{c.cid_name || c.caller_id_name || '—'}</TableCell>
                  <TableCell className="font-mono text-sm">{c.dest || c.destination_number || '—'}</TableCell>
                  <TableCell><Badge variant="secondary">{formatDuration(getLiveDuration(c))}</Badge></TableCell>
                  <TableCell><Badge variant={c.answered ? 'success' : 'warning'}>{c.state || (c.answered ? 'Active' : 'Ringing')}</Badge></TableCell>
                  <TableCell>
                    <div className="flex items-center gap-1">
                      {MODES.map(({ key, icon: Icon, label }) => (
                        <Button key={key} variant="ghost" size="icon" className="h-7 w-7" title={label}
                          onClick={() => { setSpyExt(''); setEavesdropDialog({ uuid: c.uuid || c.call_uuid, mode: key }) }}>
                          <Icon className="h-3.5 w-3.5" />
                        </Button>
                      ))}
                      <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive"
                        onClick={() => handleHangup(c.uuid || c.call_uuid)}
                        disabled={hanging === (c.uuid || c.call_uuid)}>
                        <PhoneOff className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <Dialog open={!!eavesdropDialog} onOpenChange={(open) => { if (!open) setEavesdropDialog(null) }}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>{activeMode?.title}</DialogTitle>
            <p className="text-sm text-muted-foreground">{activeMode?.desc}</p>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <div className="space-y-1">
              <Label>Your extension (supervisor)</Label>
              <Input placeholder="e.g. 1002" value={spyExt} onChange={(e) => setSpyExt(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleEavesdrop()} autoFocus />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEavesdropDialog(null)}>Cancel</Button>
            <Button onClick={handleEavesdrop} disabled={!spyExt.trim() || spying}>
              {spying ? 'Connecting…' : `Start ${activeMode?.label}`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
