import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback, useRef } from 'react'
import { fax as faxApi, destinations as destApi } from '@/api'
import { useSelector } from 'react-redux'
import { selectAuth } from '@/store'
import { roleOf } from '@/lib/permissions'
import { formatDate } from '@/lib/utils'
import { toast } from 'sonner'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogClose } from '@/components/ui/dialog'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Plus, Search, Loader2, Send, Download,
  ArrowUpRight, ArrowDownLeft, AlertCircle, Eye, RefreshCw,
  Pencil, Trash2, Inbox,
} from 'lucide-react'

const STATUS_VARIANT = { sent: 'success', received: 'success', pending: 'warning', failed: 'destructive' }
const SEND_EMPTY = { fax_uuid: '', destination_number: '' }
const BOX_EMPTY = {
  fax_name: '', fax_extension: '', fax_email: '',
  fax_caller_id_number: '', fax_description: '', fax_enabled: true,
}

// ─── FaxBoxDialog ────────────────────────────────────────────────────────────

function FaxBoxDialog({ open, onClose, editBox }) {
  const [form, setForm] = useState(BOX_EMPTY)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [dids, setDids] = useState([])
  const [didsLoading, setDidsLoading] = useState(false)

  useEffect(() => {
    if (!open) return
    setError('')
    // Load enabled DIDs
    setDidsLoading(true)
    destApi.list({ page_size: 500, destination_enabled: true })
      .then(res => setDids(Array.isArray(res.data) ? res.data : res.data.results || []))
      .catch(() => setDids([]))
      .finally(() => setDidsLoading(false))

    if (editBox) {
      setForm({
        // Single name field — prefer the existing name, fall back to the
        // previously-separate caller ID name for older records.
        fax_name:             editBox.fax_name || editBox.fax_caller_id_name || '',
        fax_extension:        editBox.fax_extension || '',
        fax_email:            editBox.fax_email || '',
        fax_caller_id_number: editBox.fax_caller_id_number || '',
        fax_description:      editBox.fax_description || '',
        fax_enabled:          editBox.fax_enabled !== false,
      })
    } else {
      setForm(BOX_EMPTY)
    }
  }, [open, editBox])

  const sf = (key) => (e) => setForm(p => ({ ...p, [key]: e.target.value }))
  const sb = (key) => (e) => setForm(p => ({ ...p, [key]: e.target.value === 'true' }))

  const handleSave = async () => {
    if (!form.fax_name.trim())      { setError('Name is required.');      return }
    if (!form.fax_extension.trim()) { setError('Extension is required.'); return }
    setSaving(true); setError('')
    // The single Name field drives both fax_name and fax_caller_id_name on the
    // backend (which still stores them separately and uses caller-id name when
    // dialing). Forward number is no longer collected.
    const payload = { ...form, fax_caller_id_name: form.fax_name.trim() }
    try {
      if (editBox) {
        await faxApi.update(editBox.fax_uuid, payload)
        toast.success('Fax box updated.')
      } else {
        await faxApi.create(payload)
        toast.success('Fax box created.')
      }
      onClose(true)
    } catch (err) {
      const d = err?.response?.data
      setError(typeof d === 'string' ? d : Object.values(d || {}).flat().join(' ') || 'Save failed.')
    } finally { setSaving(false) }
  }

  return (
    <Dialog open={open} onOpenChange={() => { if (!saving) onClose(false) }}>
      <DialogContent className="w-[95vw] max-w-lg flex flex-col p-0 gap-0">
        <DialogHeader className="px-6 py-4 border-b shrink-0">
          <DialogTitle>{editBox ? 'Edit Fax Box' : 'New Fax Box'}</DialogTitle>
          <DialogClose onClose={() => !saving && onClose(false)} />
        </DialogHeader>
        <div className="space-y-4 px-6 py-5 overflow-y-auto">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Name *</Label>
              <Input placeholder="Main Fax" value={form.fax_name} onChange={sf('fax_name')} disabled={saving} />
              <p className="text-xs text-muted-foreground">Also used as the outbound caller ID name.</p>
            </div>
            <div className="space-y-1.5">
              <Label>Extension *</Label>
              <Input placeholder="9000" value={form.fax_extension} onChange={sf('fax_extension')} disabled={saving} />
            </div>
            <div className="space-y-1.5">
              <Label>Notification Email</Label>
              <Input type="text" placeholder="fax@company.com, alerts@company.com" value={form.fax_email} onChange={sf('fax_email')} disabled={saving} />
              <p className="text-xs text-muted-foreground">Inbound faxes are emailed here as a PDF attachment. Separate multiple addresses with commas.</p>
            </div>
            <div className="space-y-1.5">
              <Label>Status</Label>
              <Select value={String(form.fax_enabled)} onChange={sb('fax_enabled')} disabled={saving}>
                <option value="true">Enabled</option>
                <option value="false">Disabled</option>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Caller ID Number</Label>
              <Select value={form.fax_caller_id_number} onChange={sf('fax_caller_id_number')} disabled={saving || didsLoading}>
                <option value="">— Select DID —</option>
                {dids.map(d => (
                  <option key={d.destination_uuid} value={d.destination_number}>
                    {d.destination_number}{d.destination_description ? ` — ${d.destination_description}` : ''}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1.5 sm:col-span-2">
              <Label>Description</Label>
              <Input placeholder="Optional description" value={form.fax_description} onChange={sf('fax_description')} disabled={saving} />
            </div>
          </div>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter className="px-6 py-3 border-t shrink-0">
          <Button variant="outline" onClick={() => onClose(false)} disabled={saving}>Cancel</Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? <><Loader2 className="h-4 w-4 animate-spin" />Saving…</> : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ─── FaxBoxes tab ────────────────────────────────────────────────────────────

function FaxBoxes() {
  // Only admins/superusers may create, edit, or delete fax boxes. Standard
  // Fax box management lives in the DIDs page now. This tab is a read-only
  // reference list (rendered only for superusers by the parent).
  const canManage = false
  const [boxes, setBoxes]     = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch]   = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editBox, setEditBox] = useState(null)
  const [deleting, setDeleting] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = {}
      if (search) params.search = search
      const { data } = await faxApi.list(params)
      setBoxes(Array.isArray(data) ? data : data.results || [])
    } finally { setLoading(false) }
  }, [search])

  useEffect(() => { load() }, [load])

  const openCreate = () => { setEditBox(null); setDialogOpen(true) }
  const openEdit   = (b) => { setEditBox(b);   setDialogOpen(true) }

  const handleDelete = async (b) => {
    if (!confirm(`Delete fax box "${b.fax_name}"?`)) return
    setDeleting(b.fax_uuid)
    try {
      await faxApi.delete(b.fax_uuid)
      toast.success('Fax box deleted.')
      load()
    } catch {
      toast.error('Failed to delete fax box.')
    } finally { setDeleting(null) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input placeholder="Search fax boxes…" className="pl-8 w-52" value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <Button variant="ghost" size="icon" onClick={load} title="Refresh">
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
        {canManage && (
          <Button size="sm" onClick={openCreate}>
            <Plus className="h-4 w-4" />New Fax Box
          </Button>
        )}
      </div>

      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Extension</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Caller ID</TableHead>
                <TableHead>Status</TableHead>
                {canManage && <TableHead className="w-24 text-right">Actions</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading
                ? [...Array(4)].map((_, i) => (
                    <TableRow key={i}>
                      {[...Array(canManage ? 6 : 5)].map((_, j) => (
                        <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                      ))}
                    </TableRow>
                  ))
                : boxes.length === 0
                  ? (
                    <TableRow>
                      <TableCell colSpan={canManage ? 6 : 5} className="py-16 text-center text-sm text-muted-foreground">
                        {canManage
                          ? <>No fax boxes yet. Click <strong>New Fax Box</strong> to create one.</>
                          : 'No fax boxes available.'}
                      </TableCell>
                    </TableRow>
                  )
                  : boxes.map(b => (
                    <TableRow key={b.fax_uuid}>
                      <TableCell className="font-medium">{b.fax_name}</TableCell>
                      <TableCell className="font-mono text-sm">{b.fax_extension}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">{b.fax_email || '—'}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {b.fax_caller_id_name || b.fax_caller_id_number
                          ? `${b.fax_caller_id_name || ''} ${b.fax_caller_id_number || ''}`.trim()
                          : '—'}
                      </TableCell>
                      <TableCell>
                        <Badge variant={b.fax_enabled ? 'success' : 'secondary'}>
                          {b.fax_enabled ? 'Enabled' : 'Disabled'}
                        </Badge>
                      </TableCell>
                      {canManage && (
                        <TableCell>
                          <div className="flex justify-end gap-1">
                            <Button variant="ghost" size="icon" className="h-7 w-7" title="Edit" onClick={() => openEdit(b)}>
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                            <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive" title="Delete"
                              disabled={deleting === b.fax_uuid} onClick={() => handleDelete(b)}>
                              {deleting === b.fax_uuid
                                ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                : <Trash2 className="h-3.5 w-3.5" />}
                            </Button>
                          </div>
                        </TableCell>
                      )}
                    </TableRow>
                  ))
              }
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <FaxBoxDialog
        open={dialogOpen}
        onClose={(reload) => { setDialogOpen(false); if (reload) load() }}
        editBox={editBox}
      />
    </div>
  )
}

// ─── SendFaxDialog ────────────────────────────────────────────────────────────

function SendFaxDialog({ open, onClose }) {
  const [form, setForm]       = useState(SEND_EMPTY)
  const [file, setFile]       = useState(null)
  const [sending, setSending] = useState(false)
  const [boxes, setBoxes]     = useState([])
  const [boxesLoading, setBoxesLoading] = useState(false)
  const fileRef = useRef(null)

  useEffect(() => {
    if (!open) return
    setForm(SEND_EMPTY)
    setFile(null)
    if (fileRef.current) fileRef.current.value = ''
    // Load enabled fax boxes — the chosen box supplies caller ID + gateway server-side.
    setBoxesLoading(true)
    faxApi.list({ page_size: 500, fax_enabled: true })
      .then(({ data }) => {
        const list = Array.isArray(data) ? data : data.results || []
        setBoxes(list)
        // Auto-select when there's exactly one box.
        if (list.length === 1) setForm(p => ({ ...p, fax_uuid: list[0].fax_uuid }))
      })
      .catch(() => setBoxes([]))
      .finally(() => setBoxesLoading(false))
  }, [open])

  const selectedBox = boxes.find(b => b.fax_uuid === form.fax_uuid)

  const handleSend = async () => {
    if (!form.fax_uuid) { toast.error('Please select a fax box.'); return }
    if (!form.destination_number.trim()) { toast.error('Destination number is required.'); return }
    // Accept 10 digits, 1+10 digits, or +1+10 digits. The server normalizes to +1XXXXXXXXXX.
    const digits = form.destination_number.replace(/\D/g, '')
    if (!(digits.length === 10 || (digits.length === 11 && digits.startsWith('1')))) {
      toast.error('Enter a valid US number: 10 digits, or 1 / +1 followed by 10 digits.')
      return
    }
    if (!file) { toast.error('Please select a TIFF or PDF file.'); return }

    // Caller ID and gateway are derived from the fax box on the server — we only
    // send the box, destination, and file.
    const fd = new FormData()
    fd.append('destination_number', form.destination_number.trim())
    fd.append('file', file)

    setSending(true)
    try {
      const { data } = await faxApi.send(form.fax_uuid, fd)
      if (data.status === 'pending') {
        toast.success('Fax queued successfully.', { description: `Sending to ${form.destination_number}` })
        onClose(true)
      } else {
        toast.error('Fax failed to originate.', { description: data.esl_result || data.message || '' })
      }
    } catch (err) {
      const d = err?.response?.data
      toast.error(typeof d === 'string' ? d : Object.values(d || {}).flat().join(' ') || 'Send failed.')
    } finally { setSending(false) }
  }

  const sf = (key) => (e) => setForm(p => ({ ...p, [key]: e.target.value }))

  // Caller ID preview that mirrors the server's resolution order:
  // box caller-id name/number, falling back to box name/extension.
  const previewName   = selectedBox ? (selectedBox.fax_caller_id_name || selectedBox.fax_name || '—') : ''
  const previewNumber = selectedBox ? (selectedBox.fax_caller_id_number || selectedBox.fax_extension || '—') : ''

  return (
    <Dialog open={open} onOpenChange={() => { if (!sending) onClose(false) }}>
      <DialogContent className="w-[95vw] max-w-lg flex flex-col p-0 gap-0">
        <DialogHeader className="px-6 py-4 border-b shrink-0">
          <DialogTitle>Send Fax</DialogTitle>
          <DialogClose onClose={() => !sending && onClose(false)} />
        </DialogHeader>
        <div className="space-y-4 px-6 py-5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <Label>Fax Box *</Label>
              <Select value={form.fax_uuid} onChange={sf('fax_uuid')} disabled={sending || boxesLoading}>
                <option value="">{boxesLoading ? 'Loading…' : 'Select fax box'}</option>
                {boxes.map(b => (
                  <option key={b.fax_uuid} value={b.fax_uuid}>
                    {b.fax_name}{b.fax_extension ? ` (${b.fax_extension})` : ''}
                  </option>
                ))}
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Destination Number *</Label>
              <Input placeholder="9725329272 or +19725329272" value={form.destination_number} onChange={sf('destination_number')} disabled={sending} />
            </div>
          </div>

          {selectedBox && (
            <div className="rounded-md border bg-muted/40 px-3 py-2.5 text-sm">
              <p className="text-xs font-medium text-muted-foreground mb-1">Caller ID (from fax box)</p>
              <p className="font-mono">
                {previewName}
                {previewNumber && previewNumber !== '—' && <span className="text-muted-foreground"> · {previewNumber}</span>}
              </p>
            </div>
          )}

          <div className="space-y-1.5">
            <Label>File (TIFF or PDF) *</Label>
            <div className="flex items-center gap-2">
              <input ref={fileRef} type="file" accept=".tif,.tiff,.pdf" className="hidden"
                onChange={e => setFile(e.target.files?.[0] || null)} disabled={sending} />
              <Button variant="outline" size="sm" onClick={() => fileRef.current?.click()} disabled={sending} className="shrink-0">
                Choose File
              </Button>
              <span className="text-sm text-muted-foreground truncate">{file ? file.name : 'No file selected'}</span>
            </div>
          </div>
        </div>
        <DialogFooter className="px-6 py-3 border-t shrink-0">
          <Button variant="outline" onClick={() => onClose(false)} disabled={sending}>Cancel</Button>
          <Button onClick={handleSend} disabled={sending}>
            {sending ? <><Loader2 className="h-4 w-4 animate-spin" />Sending…</> : <><Send className="h-4 w-4" />Send Fax</>}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ─── PreviewDialog ──────────────────────────────────────────────────────────

function PreviewDialog({ open, onClose, file, token }) {
  if (!file) return null
  const base = `/api/v1/fax/files/${file.fax_file_uuid}/download/`
  const url = token ? `${base}?token=${token}` : base
  const downloadUrl = token ? `${base}?token=${token}&attachment=1` : base

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="w-[95vw] max-w-3xl h-[88vh] sm:h-[80vh] flex flex-col p-0 gap-0">
        <DialogHeader className="px-6 py-4 border-b shrink-0">
          <DialogTitle className="text-sm font-medium truncate">{file.fax_file_name || 'Fax Preview'}</DialogTitle>
          <DialogClose onClose={() => onClose(false)} />
        </DialogHeader>
        <div className="flex-1 overflow-hidden px-6 py-5">
          <iframe src={url} className="w-full h-full rounded border" title="Fax Preview" />
        </div>
        <DialogFooter className="px-6 py-3 border-t shrink-0">
          <Button variant="outline" size="sm" onClick={() => window.open(downloadUrl, '_blank')}>
            <Download className="h-4 w-4" />Download
          </Button>
          <Button variant="outline" onClick={() => onClose(false)}>Close</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ─── FaxHistory tab ──────────────────────────────────────────────────────────

function FaxHistory() {
  const token = useSelector(selectAuth).accessToken

  const [files, setFiles]     = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch]   = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [showSend, setShowSend]         = useState(false)
  const [previewOpen, setPreviewOpen]   = useState(false)
  const [previewFile, setPreviewFile]   = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = {}
      if (search) params.search = search
      if (statusFilter !== 'all') params.fax_file_status = statusFilter
      const { data } = await faxApi.files(params)
      setFiles(Array.isArray(data) ? data : data.results || [])
      if (data.summary) setSummary(data.summary)
    } finally { setLoading(false) }
  }, [search, statusFilter])

  useEffect(() => { load() }, [load])

  const openPreview = (f) => { setPreviewFile(f); setPreviewOpen(true) }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input placeholder="Search faxes…" className="pl-8 w-52" value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
            className="h-9 w-36 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring"
          >
            <option value="all">All Statuses</option>
            <option value="sent">Sent</option>
            <option value="received">Received</option>
            <option value="pending">Pending</option>
            <option value="failed">Failed</option>
          </select>
          <Button variant="ghost" size="icon" onClick={load} title="Refresh">
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
        <Button size="sm" onClick={() => setShowSend(true)}>
          <Plus className="h-4 w-4" />Send Fax
        </Button>
      </div>

      <SendFaxDialog
        open={showSend}
        onClose={(reloadNeeded) => { setShowSend(false); if (reloadNeeded) load() }}
      />

      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {[
            { label: 'Total',    value: summary.total,    color: 'text-foreground' },
            { label: 'Sent',     value: summary.sent,     color: 'text-blue-500' },
            { label: 'Received', value: summary.received, color: 'text-green-500' },
            { label: 'Pending',  value: summary.pending,  color: 'text-yellow-500' },
            { label: 'Failed',   value: summary.failed,   color: 'text-destructive' },
          ].map(({ label, value, color }) => (
            <Card key={label} className="py-3 px-4">
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className={`text-2xl font-semibold ${color}`}>{value ?? '—'}</p>
            </Card>
          ))}
        </div>
      )}

      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-8" />
                <TableHead>Date</TableHead>
                <TableHead>Sender</TableHead>
                <TableHead>Receiver</TableHead>
                <TableHead>Name</TableHead>
                <TableHead>Pages</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-24 text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading
                ? [...Array(6)].map((_, i) => (
                    <TableRow key={i}>
                      {[...Array(8)].map((_, j) => (
                        <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                      ))}
                    </TableRow>
                  ))
                : files.length === 0
                  ? (
                    <TableRow>
                      <TableCell colSpan={8} className="py-16 text-center text-sm text-muted-foreground">
                        No fax records found.
                      </TableCell>
                    </TableRow>
                  )
                  : files.map(f => {
                    const isInbound = f.fax_file_status === 'received'
                    const sender    = isInbound ? (f.fax_file_caller_id_number || '—') : (f.fax_caller_id_number || '—')
                    const receiver  = f.fax_file_destination_number || '—'
                    const name      = isInbound
                      ? (f.fax_file_caller_id_number || f.fax_name || '—')
                      : (f.fax_caller_id_name || f.fax_name || '—')

                    return (
                      <TableRow key={f.fax_file_uuid}>
                        <TableCell>
                          {isInbound
                            ? <ArrowDownLeft className="h-4 w-4 text-green-500" title="Inbound" />
                            : f.fax_file_status === 'failed'
                              ? <AlertCircle className="h-4 w-4 text-destructive" title="Failed" />
                              : <ArrowUpRight className="h-4 w-4 text-blue-500" title="Outbound" />}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                          {formatDate(f.fax_file_date || f.insert_date)}
                        </TableCell>
                        <TableCell className="font-mono text-sm">{sender}</TableCell>
                        <TableCell className="font-mono text-sm">{receiver}</TableCell>
                        <TableCell className="text-sm text-muted-foreground">{name}</TableCell>
                        <TableCell className="text-sm">{f.fax_file_pages || '—'}</TableCell>
                        <TableCell>
                          <Badge variant={STATUS_VARIANT[f.fax_file_status] || 'secondary'}>
                            {f.fax_file_status}
                          </Badge>
                        </TableCell>
                        <TableCell>
                          <div className="flex justify-end gap-1">
                            {f.fax_file_path && (
                              <Button variant="ghost" size="icon" className="h-7 w-7" title="Preview" onClick={() => openPreview(f)}>
                                <Eye className="h-3.5 w-3.5" />
                              </Button>
                            )}
                            {f.fax_file_path && (
                              <Button variant="ghost" size="icon" className="h-7 w-7" title="Download"
                                onClick={() => window.open(`/api/v1/fax/files/${f.fax_file_uuid}/download/?token=${token}&attachment=1`, '_blank')}>
                                <Download className="h-3.5 w-3.5" />
                              </Button>
                            )}
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })
              }
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <PreviewDialog open={previewOpen} onClose={() => setPreviewOpen(false)} file={previewFile} token={token} />
    </div>
  )
}

// ─── Page ────────────────────────────────────────────────────────────────────

export default function Fax() {
  // Fax box management now lives in the DIDs page. Here the Fax Boxes tab is a
  // read-only reference for superusers only; everyone else sees only History.
  const isSuperuser = roleOf(useSelector(selectAuth).user) === 'superuser'
  const TABS = [
    ...(isSuperuser ? [{ id: 'boxes', label: 'Fax Boxes', icon: Inbox }] : []),
    { id: 'history', label: 'Fax History', icon: ArrowDownLeft },
  ]
  const [tab, setTab] = useState(isSuperuser ? 'boxes' : 'history')

  return (
    <div className="space-y-4">
      {/* Tab bar */}
      <div className="flex gap-1 border-b">
        {TABS.map(t => {
          const Icon = t.icon
          return (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={[
                'flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
                tab === t.id
                  ? 'border-primary text-primary'
                  : 'border-transparent text-muted-foreground hover:text-foreground',
              ].join(' ')}
            >
              <Icon className="h-4 w-4" />
              {t.label}
            </button>
          )
        })}
      </div>

      {tab === 'boxes'   && <FaxBoxes />}
      {tab === 'history' && <FaxHistory />}
    </div>
  )
}
