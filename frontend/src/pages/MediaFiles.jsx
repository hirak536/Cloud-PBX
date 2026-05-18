import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback, useRef } from 'react'
import { recordings as api } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogClose } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import { Plus, Pencil, Trash2, Search, Loader2, Music, Upload, X } from 'lucide-react'
import AudioPlayer from '@/components/AudioPlayer'

const EMPTY_FORM = {
  recording_name: '',
  recording_description: '',
  recording_filename: '',
  recording_base64: '',
  _file: null,
}

export default function MediaFiles() {
  const [rows, setRows]             = useState([])
  const [loading, setLoading]       = useState(true)
  const [search, setSearch]         = useState('')
  const debouncedSearch             = useDebounce(search, 300)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editId, setEditId]         = useState(null)
  const [form, setForm]             = useState(EMPTY_FORM)
  const [saving, setSaving]         = useState(false)
  const [formError, setFormError]   = useState('')
  const [deleting, setDeleting]     = useState(null)
  const fileInputRef                = useRef(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.list(debouncedSearch ? { search: debouncedSearch } : {})
      setRows(Array.isArray(data) ? data : data.results || [])
    } finally { setLoading(false) }
  }, [debouncedSearch])

  useEffect(() => { load() }, [load])

  const f = (key) => (e) => setForm(p => ({ ...p, [key]: e.target.value }))

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (!file.name.toLowerCase().endsWith('.wav')) {
      setFormError('Only WAV files are supported.')
      e.target.value = ''
      return
    }
    setFormError('')
    const reader = new FileReader()
    reader.onload = (ev) => {
      const base64 = ev.target.result.split(',')[1] ?? ''
      setForm(p => ({
        ...p,
        recording_filename: p.recording_filename || file.name,
        recording_base64: base64,
        _file: file,
      }))
    }
    reader.readAsDataURL(file)
  }

  const openCreate = () => {
    setEditId(null); setForm(EMPTY_FORM); setFormError(''); setDialogOpen(true)
  }

  const openEdit = (r) => {
    setEditId(r.recording_uuid)
    setForm({ ...EMPTY_FORM, recording_name: r.recording_name || '', recording_description: r.recording_description || '', recording_filename: r.recording_filename || '' })
    setFormError(''); setDialogOpen(true)
  }

  const handleSave = async () => {
    if (!form.recording_name)     { setFormError('Name is required.'); return }
    if (!form.recording_filename) { setFormError('Filename is required.'); return }
    setSaving(true); setFormError('')
    try {
      const payload = {
        recording_name:        form.recording_name,
        recording_description: form.recording_description,
        recording_filename:    form.recording_filename,
        ...(form.recording_base64 ? { recording_base64: form.recording_base64 } : {}),
      }
      editId ? await api.update(editId, payload) : await api.create(payload)
      setDialogOpen(false); load()
    } catch (err) {
      const d = err?.response?.data
      setFormError(typeof d === 'string' ? d : Object.values(d || {}).flat().join(' ') || 'Save failed.')
    } finally { setSaving(false) }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this recording?')) return
    setDeleting(id)
    try { await api.delete(id); load() } finally { setDeleting(null) }
  }

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Search recordings…" className="pl-8" value={search} onChange={e => setSearch(e.target.value)} />
        </div>
        <Button size="sm" onClick={openCreate}><Plus className="h-4 w-4 mr-1" /> Add Media File</Button>
      </div>

      {/* Table */}
      <Card><CardContent className="p-0 overflow-x-auto">
        <Table>
          <TableHeader><TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Filename</TableHead>
            <TableHead>Description</TableHead>
            <TableHead className="w-56" />
          </TableRow></TableHeader>
          <TableBody>
            {loading
              ? [...Array(4)].map((_, i) => (
                  <TableRow key={i}>{[...Array(4)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}</TableRow>
                ))
              : rows.length === 0
                ? (
                  <TableRow>
                    <TableCell colSpan={4} className="py-14 text-center">
                      <div className="flex flex-col items-center gap-2 text-muted-foreground">
                        <Music className="h-8 w-8 opacity-30" />
                        <p className="text-sm">No media files found.</p>
                      </div>
                    </TableCell>
                  </TableRow>
                )
                : rows.map(r => (
                    <TableRow key={r.recording_uuid}>
                      <TableCell className="font-medium">{r.recording_name}</TableCell>
                      <TableCell className="font-mono text-xs text-muted-foreground">{r.recording_filename}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">{r.recording_description || '—'}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <AudioPlayer fetchAudio={() => api.streamMediaFile(r.recording_uuid)} />
                          <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0" onClick={() => openEdit(r)}>
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button variant="ghost" size="icon" className="h-7 w-7 shrink-0 text-destructive hover:text-destructive"
                            onClick={() => handleDelete(r.recording_uuid)} disabled={deleting === r.recording_uuid}>
                            {deleting === r.recording_uuid
                              ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              : <Trash2 className="h-3.5 w-3.5" />}
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
            }
          </TableBody>
        </Table>
      </CardContent></Card>

      {/* Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="w-[95vw] max-w-md flex flex-col p-0 gap-0">
          <DialogHeader className="px-6 py-4 border-b shrink-0">
            <DialogTitle>{editId ? 'Edit Recording' : 'Add Media File'}</DialogTitle>
            <DialogClose onClose={() => setDialogOpen(false)} />
          </DialogHeader>

          <div className="px-6 py-5 space-y-4">
            {formError && (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {formError}
              </div>
            )}

            <div className="space-y-1.5">
              <Label>Name <span className="text-destructive">*</span></Label>
              <Input placeholder="Welcome Greeting" value={form.recording_name} onChange={f('recording_name')} />
            </div>

            <div className="space-y-1.5">
              <Label>Description</Label>
              <Input placeholder="Optional description" value={form.recording_description} onChange={f('recording_description')} />
            </div>

            <div className="space-y-1.5">
              <Label>Filename <span className="text-destructive">*</span></Label>
              <Input placeholder="greeting.wav" value={form.recording_filename} onChange={f('recording_filename')} />
            </div>

            <div className="space-y-1.5">
              <Label>WAV File</Label>
              <div className="flex items-center gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
                  <Upload className="h-3.5 w-3.5 mr-1" /> Choose File
                </Button>
                <span className="text-sm text-muted-foreground truncate flex-1">
                  {form._file ? form._file.name : 'No file chosen'}
                </span>
                {form._file && (
                  <button type="button" onClick={() => setForm(p => ({ ...p, _file: null, recording_base64: '' }))}>
                    <X className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground" />
                  </button>
                )}
              </div>
              <p className="text-xs text-muted-foreground">WAV format only (8 kHz mono recommended)</p>
              <input ref={fileInputRef} type="file" accept=".wav,audio/wav,audio/x-wav" className="hidden" onChange={handleFileChange} />
            </div>
          </div>

          <DialogFooter className="px-6 py-3 border-t shrink-0 gap-2">
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 animate-spin mr-1" />}
              {editId ? 'Save Changes' : 'Create'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
