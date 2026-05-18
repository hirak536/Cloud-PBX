import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback } from 'react'
import { conferences as api } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogClose } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { Plus, Pencil, Trash2, Search, Loader2 } from 'lucide-react'

const EMPTY = { conference_extension: '', conference_name: '', conference_pin: '', conference_max_members: 0, enabled: true }

export default function Conferences() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebounce(search, 300)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editId, setEditId] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [deleting, setDeleting] = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.list(debouncedSearch ? { search: debouncedSearch } : {})
      setRows(Array.isArray(data) ? data : data.results || [])
    } finally { setLoading(false) }
  }, [search])

  useEffect(() => { load() }, [load])

  const f = (key) => (e) => setForm(p => ({ ...p, [key]: e.target.value }))
  const openCreate = () => { setEditId(null); setForm(EMPTY); setFormError(''); setDialogOpen(true) }
  const openEdit = (r) => {
    setEditId(r.conference_uuid || r.id)
    setForm({ conference_extension: r.conference_extension || '', conference_name: r.conference_name || '', conference_pin: r.conference_pin || '', conference_max_members: r.conference_max_members || 0, enabled: r.conference_enabled !== false })
    setFormError(''); setDialogOpen(true)
  }

  const handleSave = async () => {
    if (!form.conference_extension) { setFormError('Extension is required.'); return }
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
    if (!confirm('Delete this conference room?')) return
    setDeleting(id)
    try { await api.delete(id); load() } finally { setDeleting(null) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Search conferences..." className="pl-8" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <Button size="sm" onClick={openCreate}><Plus className="h-4 w-4" />Add Conference</Button>
      </div>
      <Card><CardContent className="p-0 overflow-x-auto">
        <Table>
          <TableHeader><TableRow>
            <TableHead>Extension</TableHead><TableHead>Name</TableHead><TableHead>Max Members</TableHead><TableHead>PIN</TableHead><TableHead>Status</TableHead><TableHead className="w-20" />
          </TableRow></TableHeader>
          <TableBody>
            {loading ? [...Array(4)].map((_, i) => <TableRow key={i}>{[...Array(6)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}</TableRow>)
              : rows.length === 0 ? <TableRow><TableCell colSpan={6} className="text-center py-10 text-muted-foreground">No conference rooms found.</TableCell></TableRow>
              : rows.map((r) => {
                const id = r.conference_uuid || r.id
                return <TableRow key={id}>
                  <TableCell className="font-mono font-medium">{r.conference_extension}</TableCell>
                  <TableCell>{r.conference_name}</TableCell>
                  <TableCell>{r.conference_max_members || '∞'}</TableCell>
                  <TableCell>{r.conference_pin ? '••••' : '—'}</TableCell>
                  <TableCell><Badge variant={r.conference_enabled !== false ? 'success' : 'secondary'}>{r.conference_enabled !== false ? 'Active' : 'Disabled'}</Badge></TableCell>
                  <TableCell><div className="flex gap-1">
                    <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(r)}><Pencil className="h-3.5 w-3.5" /></Button>
                    <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive" onClick={() => handleDelete(id)} disabled={deleting === id}>
                      {deleting === id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                    </Button>
                  </div></TableCell>
                </TableRow>
              })}
          </TableBody>
        </Table>
      </CardContent></Card>

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="w-[95vw] max-w-sm p-0 gap-0">
          <DialogHeader className="px-6 py-4 border-b">
            <DialogTitle>{editId ? 'Edit Conference' : 'New Conference Room'}</DialogTitle>
            <DialogClose onClose={() => setDialogOpen(false)} />
          </DialogHeader>
          <div className="px-6 py-5 space-y-4">
          {formError && <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{formError}</div>}
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5"><Label>Extension *</Label><Input placeholder="9000" value={form.conference_extension} onChange={f('conference_extension')} /></div>
            <div className="space-y-1.5"><Label>Name</Label><Input placeholder="Board Room" value={form.conference_name} onChange={f('conference_name')} /></div>
            <div className="space-y-1.5"><Label>PIN</Label><Input type="password" placeholder="Optional PIN" value={form.conference_pin} onChange={f('conference_pin')} /></div>
            <div className="space-y-1.5"><Label>Max Members</Label><Input type="number" placeholder="0 = unlimited" value={form.conference_max_members} onChange={f('conference_max_members')} /></div>
          </div>
          </div>
          <DialogFooter className="px-6 py-3 border-t gap-2">
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving}>{saving && <Loader2 className="h-4 w-4 animate-spin" />}{editId ? 'Save' : 'Create'}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
