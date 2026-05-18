import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback } from 'react'
import { callParking as api, musicOnHold as mohApi } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogClose } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { Plus, Pencil, Trash2, Search, Loader2, Layers } from 'lucide-react'

const EMPTY = {
  slot_number: '',
  slot_name: '',
  parking_timeout: 60,
  timeout_action: 'hangup',
  timeout_voicemail_extension: '',
  music_on_hold: '',
  slot_enabled: true,
}

const EMPTY_BULK = {
  slot_start: 7100,
  slot_end: 7109,
  parking_timeout: 60,
  timeout_action: 'hangup',
  timeout_voicemail_extension: '',
  music_on_hold: '',
  slot_enabled: true,
}

export default function CallParking() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebounce(search, 300)

  // Single slot dialog
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editId, setEditId] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')

  // Bulk create dialog
  const [bulkOpen, setBulkOpen] = useState(false)
  const [bulkForm, setBulkForm] = useState(EMPTY_BULK)
  const [bulkSaving, setBulkSaving] = useState(false)
  const [bulkError, setBulkError] = useState('')
  const [bulkResult, setBulkResult] = useState(null)

  const [deleting, setDeleting] = useState(null)
  const [mohOptions, setMohOptions] = useState([])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.list(debouncedSearch ? { search: debouncedSearch } : {})
      setRows(Array.isArray(data) ? data : data.results || [])
    } finally { setLoading(false) }
  }, [debouncedSearch])

  useEffect(() => { load() }, [load])

  const loadMoh = useCallback(async () => {
    if (mohOptions.length) return
    try {
      const { data } = await mohApi.list({})
      setMohOptions(Array.isArray(data) ? data : data.results || [])
    } catch { /* non-fatal */ }
  }, [mohOptions.length])

  const f = (key) => (e) => setForm(p => ({ ...p, [key]: e.target.value }))
  const fNum = (key) => (e) => setForm(p => ({ ...p, [key]: Number(e.target.value) }))
  const bf = (key) => (e) => setBulkForm(p => ({ ...p, [key]: e.target.value }))
  const bfNum = (key) => (e) => setBulkForm(p => ({ ...p, [key]: Number(e.target.value) }))

  const openCreate = () => {
    setEditId(null); setForm(EMPTY); setFormError(''); setDialogOpen(true); loadMoh()
  }
  const openEdit = async (r) => {
    setEditId(r.call_parking_slot_uuid)
    setForm({ ...EMPTY })
    setFormError('')
    setDialogOpen(true)
    loadMoh()
    try {
      const { data: d } = await api.get(r.call_parking_slot_uuid)
      setForm({
        slot_number: d.slot_number ?? '',
        slot_name: d.slot_name || '',
        parking_timeout: d.parking_timeout ?? 60,
        timeout_action: d.timeout_action || 'hangup',
        timeout_voicemail_extension: d.timeout_voicemail_extension || '',
        music_on_hold: d.music_on_hold || '',
        slot_enabled: d.slot_enabled !== false,
      })
    } catch { /* keep empty */ }
  }

  const handleSave = async () => {
    if (form.slot_number === '' || form.slot_number === null) { setFormError('Slot number is required.'); return }
    setSaving(true); setFormError('')
    try {
      editId ? await api.update(editId, form) : await api.create(form)
      setDialogOpen(false); load()
    } catch (err) {
      const d = err?.response?.data
      setFormError(typeof d === 'string' ? d : Object.values(d || {}).flat().join(' ') || 'Save failed.')
    } finally { setSaving(false) }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this parking slot?')) return
    setDeleting(id)
    try { await api.delete(id); load() } finally { setDeleting(null) }
  }

  const openBulk = () => {
    setBulkForm(EMPTY_BULK); setBulkError(''); setBulkResult(null); setBulkOpen(true); loadMoh()
  }
  const handleBulkCreate = async () => {
    if (bulkForm.slot_start > bulkForm.slot_end) { setBulkError('Start must be ≤ End.'); return }
    if (bulkForm.slot_end - bulkForm.slot_start > 99) { setBulkError('Range cannot exceed 100 slots.'); return }
    setBulkSaving(true); setBulkError(''); setBulkResult(null)
    try {
      const { data } = await api.bulkCreate(bulkForm)
      setBulkResult(data)
      load()
    } catch (err) {
      const d = err?.response?.data
      setBulkError(typeof d === 'string' ? d : Object.values(d || {}).flat().join(' ') || 'Bulk create failed.')
    } finally { setBulkSaving(false) }
  }

  const MohSelect = ({ value, onChange }) => (
    <select
      className="flex h-9 w-full rounded-lg border border-input bg-background px-3 py-1 text-sm shadow-sm transition-all duration-150 hover:border-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:border-primary/60"
      value={value}
      onChange={onChange}
    >
      <option value="">System Default</option>
      {mohOptions.map((m) => (
        <option key={m.music_on_hold_uuid} value={`local_stream://${m.music_on_hold_name}`}>
          {m.music_on_hold_name}
        </option>
      ))}
    </select>
  )

  const TimeoutFields = ({ formState, fFn, fNumFn, setFn }) => (
    <>
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <Label>Timeout (seconds)</Label>
          <Input type="number" value={formState.parking_timeout} onChange={fNumFn('parking_timeout')} />
        </div>
        <div className="space-y-1.5">
          <Label>On Timeout</Label>
          <select
            className="flex h-9 w-full rounded-lg border border-input bg-background px-3 py-1 text-sm shadow-sm transition-all duration-150 hover:border-primary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:border-primary/60"
            value={formState.timeout_action}
            onChange={fFn('timeout_action')}
          >
            <option value="hangup">Hangup</option>
            <option value="return_to_parker">Return to Parker</option>
            <option value="voicemail">Send to Voicemail</option>
          </select>
        </div>
      </div>
      {formState.timeout_action === 'voicemail' && (
        <div className="space-y-1.5">
          <Label>Voicemail Extension</Label>
          <Input placeholder="1001" value={formState.timeout_voicemail_extension} onChange={fFn('timeout_voicemail_extension')} />
        </div>
      )}
      <div className="space-y-1.5">
        <Label>Music on Hold</Label>
        <MohSelect value={formState.music_on_hold} onChange={fFn('music_on_hold')} />
      </div>
    </>
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Search slots..." className="pl-8" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <Button size="sm" variant="outline" onClick={openBulk}><Layers className="h-4 w-4" />Bulk Create</Button>
        <Button size="sm" onClick={openCreate}><Plus className="h-4 w-4" />Add Slot</Button>
      </div>

      <Card><CardContent className="p-0 overflow-x-auto">
        <Table>
          <TableHeader><TableRow>
            <TableHead>Slot</TableHead>
            <TableHead>Name</TableHead>
            <TableHead>Timeout</TableHead>
            <TableHead>On Timeout</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="w-20" />
          </TableRow></TableHeader>
          <TableBody>
            {loading
              ? [...Array(4)].map((_, i) => <TableRow key={i}>{[...Array(6)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}</TableRow>)
              : rows.length === 0
                ? <TableRow><TableCell colSpan={6} className="text-center py-10 text-muted-foreground">No parking slots found.</TableCell></TableRow>
                : rows.map((r) => (
                  <TableRow key={r.call_parking_slot_uuid}>
                    <TableCell className="font-mono font-medium">{r.slot_number}</TableCell>
                    <TableCell>{r.slot_name || <span className="text-muted-foreground">—</span>}</TableCell>
                    <TableCell>{r.parking_timeout}s</TableCell>
                    <TableCell className="capitalize">{r.timeout_action?.replace('_', ' ')}</TableCell>
                    <TableCell><Badge variant={r.slot_enabled !== false ? 'success' : 'secondary'}>{r.slot_enabled !== false ? 'Active' : 'Disabled'}</Badge></TableCell>
                    <TableCell><div className="flex gap-1">
                      <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(r)}><Pencil className="h-3.5 w-3.5" /></Button>
                      <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive" onClick={() => handleDelete(r.call_parking_slot_uuid)} disabled={deleting === r.call_parking_slot_uuid}>
                        {deleting === r.call_parking_slot_uuid ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                      </Button>
                    </div></TableCell>
                  </TableRow>
                ))
            }
          </TableBody>
        </Table>
      </CardContent></Card>

      {/* ── Single slot dialog ── */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="w-[95vw] max-w-sm p-0 gap-0">
          <DialogHeader className="px-6 py-4 border-b">
            <DialogTitle>{editId ? 'Edit Parking Slot' : 'New Parking Slot'}</DialogTitle>
            <DialogClose onClose={() => setDialogOpen(false)} />
          </DialogHeader>
          <div className="px-6 py-5 space-y-4">
            {formError && <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{formError}</div>}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Slot Number *</Label>
                <Input type="number" placeholder="7100" value={form.slot_number} onChange={fNum('slot_number')} disabled={!!editId} />
              </div>
              <div className="space-y-1.5">
                <Label>Name</Label>
                <Input placeholder="Reception" value={form.slot_name} onChange={f('slot_name')} />
              </div>
            </div>
            <TimeoutFields formState={form} fFn={f} fNumFn={fNum} setFn={setForm} />
            <div className="flex items-center gap-2">
              <input type="checkbox" id="slot_enabled" checked={form.slot_enabled} onChange={(e) => setForm(p => ({ ...p, slot_enabled: e.target.checked }))} className="h-4 w-4 rounded border-input" />
              <Label htmlFor="slot_enabled">Enabled</Label>
            </div>
          </div>
          <DialogFooter className="px-6 py-3 border-t gap-2">
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving}>{saving && <Loader2 className="h-4 w-4 animate-spin" />}{editId ? 'Save' : 'Create'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ── Bulk create dialog ── */}
      <Dialog open={bulkOpen} onOpenChange={setBulkOpen}>
        <DialogContent className="w-[95vw] max-w-sm p-0 gap-0">
          <DialogHeader className="px-6 py-4 border-b">
            <DialogTitle>Bulk Create Slots</DialogTitle>
            <DialogClose onClose={() => setBulkOpen(false)} />
          </DialogHeader>
          <div className="px-6 py-5 space-y-4">
            {bulkError && <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{bulkError}</div>}
            {bulkResult && (
              <div className="rounded-md border border-green-500/30 bg-green-500/10 px-3 py-2 text-sm text-green-700">
                Created {bulkResult.created.length} slot{bulkResult.created.length !== 1 ? 's' : ''}.
                {bulkResult.skipped.length > 0 && ` Skipped ${bulkResult.skipped.length} already existing.`}
              </div>
            )}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>From</Label>
                <Input type="number" value={bulkForm.slot_start} onChange={bfNum('slot_start')} />
              </div>
              <div className="space-y-1.5">
                <Label>To</Label>
                <Input type="number" value={bulkForm.slot_end} onChange={bfNum('slot_end')} />
              </div>
            </div>
            <p className="text-xs text-muted-foreground -mt-2">Creates one slot per number. Max 100. Skips existing.</p>
            <TimeoutFields formState={bulkForm} fFn={bf} fNumFn={bfNum} setFn={setBulkForm} />
          </div>
          <DialogFooter className="px-6 py-3 border-t gap-2">
            <Button variant="outline" onClick={() => setBulkOpen(false)}>Close</Button>
            <Button onClick={handleBulkCreate} disabled={bulkSaving}>{bulkSaving && <Loader2 className="h-4 w-4 animate-spin" />}Create Slots</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
