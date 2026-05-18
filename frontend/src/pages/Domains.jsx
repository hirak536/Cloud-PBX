import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback } from 'react'
import { domains as api } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogClose } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { Plus, Pencil, Trash2, Search, Loader2 } from 'lucide-react'
import { formatDate } from '@/lib/utils'

const EMPTY = { domain_name: '', domain_description: '', domain_enabled: true }

export default function Domains() {
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
    setEditId(r.domain_uuid || r.id)
    setForm({ domain_name: r.domain_name || '', domain_description: r.domain_description || '', domain_enabled: r.domain_enabled !== false })
    setFormError(''); setDialogOpen(true)
  }

  const handleSave = async () => {
    if (!form.domain_name) { setFormError('Domain name is required.'); return }
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
    if (!confirm('Delete this domain? This will affect all associated resources.')) return
    setDeleting(id)
    try { await api.delete(id); load() } finally { setDeleting(null) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Search domains..." className="pl-8" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <Button size="sm" onClick={openCreate}><Plus className="h-4 w-4" />Add Domain</Button>
      </div>
      <Card><CardContent className="p-0 overflow-x-auto">
        <Table>
          <TableHeader><TableRow>
            <TableHead>Domain Name</TableHead><TableHead>Description</TableHead><TableHead>Created</TableHead><TableHead>Status</TableHead><TableHead className="w-20" />
          </TableRow></TableHeader>
          <TableBody>
            {loading ? [...Array(5)].map((_, i) => <TableRow key={i}>{[...Array(5)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}</TableRow>)
              : rows.length === 0 ? <TableRow><TableCell colSpan={5} className="text-center py-10 text-muted-foreground">No domains found.</TableCell></TableRow>
              : rows.map((r) => {
                const id = r.domain_uuid || r.id
                return <TableRow key={id}>
                  <TableCell className="font-medium">{r.domain_name}</TableCell>
                  <TableCell className="text-muted-foreground text-sm">{r.domain_description || '—'}</TableCell>
                  <TableCell className="text-xs text-muted-foreground">{formatDate(r.insert_date || r.created)}</TableCell>
                  <TableCell><Badge variant={r.domain_enabled !== false ? 'success' : 'secondary'}>{r.domain_enabled !== false ? 'Active' : 'Disabled'}</Badge></TableCell>
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
            <DialogTitle>{editId ? 'Edit Domain' : 'New Domain'}</DialogTitle>
            <DialogClose onClose={() => setDialogOpen(false)} />
          </DialogHeader>
          <div className="px-6 py-5 space-y-4">
          {formError && <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{formError}</div>}
          <div className="space-y-3">
            <div className="space-y-1.5"><Label>Domain Name *</Label><Input placeholder="company.pbx.com" value={form.domain_name} onChange={f('domain_name')} /></div>
            <div className="space-y-1.5"><Label>Description</Label><Input placeholder="Optional" value={form.domain_description} onChange={f('domain_description')} /></div>
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
