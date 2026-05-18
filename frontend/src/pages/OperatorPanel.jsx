import { useState } from 'react'
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
import { Phone, PhoneForwarded, Loader2, UserX } from 'lucide-react'

export default function OperatorPanel() {
  const [selected, setSelected] = useState(null)
  const [deregistering, setDeregistering] = useState(false)
  const [originateOpen, setOriginateOpen] = useState(false)
  const [origForm, setOrigForm] = useState({ caller: '', callee: '' })
  const [originating, setOriginating] = useState(false)
  const { wsConnected, systemMetrics, fsStatus, dbStatus, registrations: allLiveRegs } = useSelector(selectLive)
  const { currentTenant } = useSelector((s) => s.tenant)
  const _suffix = currentTenant?.tenant_code ? `-${currentTenant.tenant_code}` : null
  const displayRegs = _suffix
    ? allLiveRegs.filter(r => String(r.user || r.reg_user || '').endsWith(_suffix))
    : allLiveRegs

  const handleDeregister = async (reg) => {
    if (!reg?.call_id) return
    setDeregistering(true)
    try {
      const user = reg.user || reg.reg_user || ''
      const tenant_code = user.includes('-') ? user.split('-').pop() : ''
      await freeswitch.deregister(reg.call_id, reg.profile || 'internal', tenant_code)
      setSelected(null)
    } catch {} finally { setDeregistering(false) }
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
          <Badge variant="secondary">{displayRegs.length} registered</Badge>
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
          <Button variant="outline" size="sm" onClick={() => setOriginateOpen(true)}>
            <Phone className="h-4 w-4" />
            Originate Call
          </Button>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle className="text-sm">Registered Extensions</CardTitle></CardHeader>
          <CardContent className="p-0 overflow-x-auto">
            <Table>
              <TableHeader><TableRow>
                <TableHead>Extension</TableHead><TableHead>IP</TableHead><TableHead>User Agent</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {displayRegs.length === 0
                  ? <TableRow><TableCell colSpan={3} className="text-center py-6 text-muted-foreground text-sm">No registrations.</TableCell></TableRow>
                  : displayRegs.map((r, i) => (
                    <TableRow key={i} className="cursor-pointer hover:bg-muted/50" onClick={() => setSelected(r)}>
                      <TableCell className="font-mono">{r.user || r.reg_user || '—'}</TableCell>
                      <TableCell className="font-mono text-xs">{r.network_ip || '—'}</TableCell>
                      <TableCell className="text-xs text-muted-foreground truncate max-w-32">{r.user_agent || '—'}</TableCell>
                    </TableRow>
                  ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-sm">Registration Detail</CardTitle>
            {selected && (
              <Button variant="destructive" size="sm" onClick={() => handleDeregister(selected)} disabled={deregistering}>
                {deregistering ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserX className="h-4 w-4" />}
                Deregister
              </Button>
            )}
          </CardHeader>
          <CardContent>
            {!selected
              ? <p className="text-sm text-muted-foreground py-6 text-center">Select a registration to view details.</p>
              : (
                <dl className="space-y-2 text-sm">
                  {[
                    ['Extension',   selected.user || selected.reg_user],
                    ['Realm',       selected.realm],
                    ['Network IP',  selected.network_ip],
                    ['Port',        selected.network_port],
                    ['User Agent',  selected.user_agent],
                    ['URL',         selected.url],
                    ['Call-ID',     selected.call_id],
                    ['Expires',     selected.expires ? `${Math.max(0, parseInt(selected.expires) - Math.floor(Date.now()/1000))}s` : '—'],
                  ].map(([label, value]) => (
                    <div key={label} className="flex gap-2">
                      <dt className="w-28 shrink-0 text-muted-foreground">{label}</dt>
                      <dd className="font-mono text-xs break-all">{value || '—'}</dd>
                    </div>
                  ))}
                </dl>
              )
            }
          </CardContent>
        </Card>
      </div>

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
    </div>
  )
}
