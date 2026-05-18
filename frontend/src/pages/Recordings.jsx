import { useEffect, useState, useCallback, useRef } from 'react'
import { recordings as api, extensions as extensionsApi } from '@/api'
import { formatDate } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Dialog, DialogContent, DialogHeader, DialogFooter, DialogTitle, DialogClose } from '@/components/ui/dialog'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Plus, Pencil, Trash2, Search, Loader2, Music, Phone, Upload,
  PhoneCall, FileAudio, Download, ChevronDown, X,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// ─── Constants ────────────────────────────────────────────────────────────────

const FORMAT_OPTIONS = [
  { value: 'auto',   label: 'Automatic' },
  { value: 'wav_8k', label: 'WAV mono 8 kHz 64 kbps' },
  { value: 'wav_16k',label: 'WAV mono 16 kHz 128 kbps' },
  { value: 'sln_8k', label: 'SLN 8 kHz format' },
  { value: 'sln_16k',label: 'SLN 16 kHz format' },
  { value: 'none',   label: 'Leave as is' },
]

const PAGE_TABS = [
  { id: 'media',  label: 'Media Files' },
  { id: 'calls',  label: 'Call Recordings' },
]

const EMPTY_FORM = {
  recording_name: '',
  recording_description: '',
  recording_filename: '',
  recording_base64: '',
  recording_volume: 1.0,
  recording_format: 'auto',
  // dial-to-record fields (not persisted directly)
  _method: 'upload',          // 'dial' | 'upload'
  _dial_extension_uuid: '',
  _dial_external_number: '',
  _dial_block_caller_id: false,
  _file: null,
}

// ─── Extension Picker ─────────────────────────────────────────────────────────

function ExtensionPicker({ value, onChange, extensions, loading }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const containerRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (!open) return
    const h = (e) => { if (!containerRef.current?.contains(e.target)) setOpen(false) }
    document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [open])

  useEffect(() => {
    if (open) requestAnimationFrame(() => inputRef.current?.focus())
  }, [open])

  const q = query.toLowerCase().trim()
  const filtered = !q ? extensions : extensions.filter(e =>
    e.extension.includes(q) ||
    (e.effective_caller_id_name || '').toLowerCase().includes(q) ||
    (e.description || '').toLowerCase().includes(q)
  )

  const selected = extensions.find(e => e.extension_uuid === value)

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className={cn(
          'flex h-9 w-full items-center justify-between gap-2 rounded-md border border-input bg-background px-3 py-1 text-sm shadow-sm',
          'hover:border-ring/60 transition-colors',
        )}
      >
        {loading ? (
          <span className="flex items-center gap-2 text-muted-foreground text-xs">
            <Loader2 className="h-3 w-3 animate-spin" /> Loading…
          </span>
        ) : selected ? (
          <span className="flex items-center gap-2">
            <span className="font-mono font-bold text-blue-500">{selected.extension}</span>
            <span className="text-sm text-muted-foreground truncate">
              {selected.effective_caller_id_name || selected.description || ''}
            </span>
          </span>
        ) : (
          <span className="text-muted-foreground text-sm">Choose an extension to dial</span>
        )}
        <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-full rounded-xl border border-border/60 bg-card shadow-2xl shadow-black/10 animate-dropdown-in">
          <div className="flex items-center gap-2 border-b px-3 py-2">
            <Search className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <input ref={inputRef} value={query} onChange={e => setQuery(e.target.value)}
              placeholder="Search extensions…"
              className="flex-1 text-sm bg-transparent outline-none placeholder:text-muted-foreground" />
            {query && <button type="button" onClick={() => setQuery('')}><X className="h-3 w-3 text-muted-foreground" /></button>}
          </div>
          <div className="max-h-48 overflow-y-auto p-1">
            {filtered.length === 0 ? (
              <p className="px-3 py-3 text-sm text-muted-foreground text-center">No extensions found</p>
            ) : filtered.map(e => (
              <button key={e.extension_uuid} type="button"
                onClick={() => { onChange(e.extension_uuid); setOpen(false); setQuery('') }}
                className={cn(
                  'w-full flex items-center gap-3 mx-1 px-3 py-2 rounded-lg hover:bg-muted text-left transition-colors text-sm',
                  value === e.extension_uuid && 'bg-muted',
                )}>
                <span className="font-mono font-bold text-blue-500 w-12 shrink-0">{e.extension}</span>
                <span className="text-sm text-muted-foreground truncate">
                  {e.effective_caller_id_name || e.description || ''}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function Recordings() {
  const [pageTab, setPageTab]       = useState('media')
  const [rows, setRows]             = useState([])
  const [callRows, setCallRows]     = useState([])
  const [loading, setLoading]       = useState(true)
  const [callLoading, setCallLoading] = useState(false)
  const [search, setSearch]         = useState('')
  const [callSearch, setCallSearch] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editId, setEditId]         = useState(null)
  const [form, setForm]             = useState(EMPTY_FORM)
  const [saving, setSaving]         = useState(false)
  const [formError, setFormError]   = useState('')
  const [deleting, setDeleting]     = useState(null)
  const [dialing, setDialing]       = useState(false)

  const extLoadedRef = useRef(false)
  const [extLoading, setExtLoading] = useState(false)
  const [extensions, setExtensions] = useState([])
  const fileInputRef = useRef(null)

  // ── Loaders ────────────────────────────────────────────────────────────────

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await api.list(search ? { search } : {})
      setRows(Array.isArray(data) ? data : data.results || [])
    } finally { setLoading(false) }
  }, [search])

  const loadCallRecordings = useCallback(async () => {
    setCallLoading(true)
    try {
      const { data } = await api.callRecordings(callSearch ? { search: callSearch } : {})
      setCallRows(Array.isArray(data) ? data : data.results || [])
    } finally { setCallLoading(false) }
  }, [callSearch])

  useEffect(() => { load() }, [load])
  useEffect(() => {
    if (pageTab === 'calls') loadCallRecordings()
  }, [pageTab, loadCallRecordings])

  const loadExtensions = useCallback(async () => {
    if (extLoadedRef.current) return
    setExtLoading(true)
    try {
      const { data } = await extensionsApi.list({ page_size: 500 })
      setExtensions(Array.isArray(data) ? data : data.results || [])
      extLoadedRef.current = true
    } finally { setExtLoading(false) }
  }, [])

  // ── Form helpers ────────────────────────────────────────────────────────────

  const f   = (key) => (e)   => setForm(p => ({ ...p, [key]: e.target.value }))
  const fN  = (key) => (e)   => setForm(p => ({ ...p, [key]: Number(e.target.value) }))
  const fB  = (key) => (val) => setForm(p => ({ ...p, [key]: val }))

  const handleFileChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      const dataUrl = ev.target.result
      const base64 = dataUrl.split(',')[1] ?? ''
      setForm(p => ({
        ...p,
        recording_filename: p.recording_filename || file.name,
        recording_base64: base64,
        _file: file,
      }))
    }
    reader.readAsDataURL(file)
  }

  // ── Dialog open helpers ─────────────────────────────────────────────────────

  const openCreate = () => {
    setEditId(null)
    setForm(EMPTY_FORM)
    setFormError('')
    setDialogOpen(true)
    loadExtensions()
  }

  const openEdit = async (r) => {
    const id = r.recording_uuid
    setEditId(id)
    setForm({
      ...EMPTY_FORM,
      recording_name:        r.recording_name || '',
      recording_description: r.recording_description || '',
      recording_filename:    r.recording_filename || '',
      recording_volume:      r.recording_volume ?? 1.0,
      recording_format:      r.recording_format || 'auto',
      _method: 'upload',
    })
    setFormError('')
    setDialogOpen(true)
    loadExtensions()
  }

  // ── Dial to record ──────────────────────────────────────────────────────────

  const handleDialRecord = async () => {
    if (!form._dial_extension_uuid && !form._dial_external_number) {
      setFormError('Choose an extension or enter an external number.')
      return
    }
    setDialing(true); setFormError('')
    try {
      await api.recordCall({
        extension_uuid:   form._dial_extension_uuid || undefined,
        external_number:  form._dial_external_number || undefined,
        block_caller_id:  form._dial_block_caller_id,
      })
    } catch (err) {
      const d = err?.response?.data
      setFormError(
        d?.message || d?.error ||
        (typeof d === 'string' ? d : 'Dial-to-record is not yet fully implemented.')
      )
    } finally { setDialing(false) }
  }

  // ── Save ────────────────────────────────────────────────────────────────────

  const handleSave = async () => {
    if (!form.recording_name)     { setFormError('Name is required.'); return }
    if (!form.recording_filename) { setFormError('Filename is required.'); return }
    setSaving(true); setFormError('')
    try {
      const payload = {
        recording_name:        form.recording_name,
        recording_description: form.recording_description,
        recording_filename:    form.recording_filename,
        recording_volume:      Number(form.recording_volume),
        recording_format:      form.recording_format,
        ...(form.recording_base64 ? { recording_base64: form.recording_base64 } : {}),
      }
      editId ? await api.update(editId, payload) : await api.create(payload)
      setDialogOpen(false); load()
    } catch (err) {
      const d = err?.response?.data
      setFormError(typeof d === 'string' ? d : Object.values(d || {}).flat().join(' ') || 'Save failed.')
    } finally { setSaving(false) }
  }

  // ── Delete ──────────────────────────────────────────────────────────────────

  const handleDelete = async (id) => {
    if (!confirm('Delete this recording?')) return
    setDeleting(id)
    try { await api.delete(id); load() } finally { setDeleting(null) }
  }

  // ── Render ──────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-4">
      {/* Page tabs */}
      <div className="flex gap-0 border-b">
        {PAGE_TABS.map(t => (
          <button key={t.id} type="button" onClick={() => setPageTab(t.id)}
            className={cn(
              'px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors',
              pageTab === t.id
                ? 'border-primary text-primary'
                : 'border-transparent text-muted-foreground hover:text-foreground',
            )}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ══ MEDIA FILES TAB ═══════════════════════════════════════════════════ */}
      {pageTab === 'media' && (
        <>
          <div className="flex items-center gap-3">
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input placeholder="Search recordings…" className="pl-8" value={search} onChange={e => setSearch(e.target.value)} />
            </div>
            <Button size="sm" onClick={openCreate}><Plus className="h-4 w-4" /> Add Recording</Button>
          </div>

          <Card><CardContent className="p-0 overflow-x-auto">
            <Table>
              <TableHeader><TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Filename</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Format</TableHead>
                <TableHead className="w-20" />
              </TableRow></TableHeader>
              <TableBody>
                {loading
                  ? [...Array(4)].map((_, i) => (
                      <TableRow key={i}>{[...Array(5)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}</TableRow>
                    ))
                  : rows.length === 0
                    ? (
                      <TableRow>
                        <TableCell colSpan={5} className="py-14 text-center">
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
                            {r.recording_format && r.recording_format !== 'auto' ? (
                              <Badge variant="secondary" className="text-xs">{r.recording_format}</Badge>
                            ) : (
                              <span className="text-xs text-muted-foreground">Auto</span>
                            )}
                          </TableCell>
                          <TableCell>
                            <div className="flex gap-1">
                              <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(r)}>
                                <Pencil className="h-3.5 w-3.5" />
                              </Button>
                              <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive"
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
        </>
      )}

      {/* ══ CALL RECORDINGS TAB ═══════════════════════════════════════════════ */}
      {pageTab === 'calls' && (
        <>
          <div className="relative max-w-xs">
            <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input placeholder="Search call recordings…" className="pl-8" value={callSearch} onChange={e => setCallSearch(e.target.value)} />
          </div>

          <Card><CardContent className="p-0 overflow-x-auto">
            <Table>
              <TableHeader><TableRow>
                <TableHead>Date</TableHead>
                <TableHead>Caller</TableHead>
                <TableHead>Destination</TableHead>
                <TableHead>Duration</TableHead>
                <TableHead>File</TableHead>
              </TableRow></TableHeader>
              <TableBody>
                {callLoading
                  ? [...Array(5)].map((_, i) => (
                      <TableRow key={i}>{[...Array(5)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}</TableRow>
                    ))
                  : callRows.length === 0
                    ? (
                      <TableRow>
                        <TableCell colSpan={5} className="py-14 text-center">
                          <div className="flex flex-col items-center gap-2 text-muted-foreground">
                            <FileAudio className="h-8 w-8 opacity-30" />
                            <p className="text-sm">No call recordings found.</p>
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                    : callRows.map(r => (
                        <TableRow key={r.call_recording_uuid}>
                          <TableCell className="text-xs text-muted-foreground">
                            {r.call_recording_start_stamp
                              ? formatDate(r.call_recording_start_stamp)
                              : '—'}
                          </TableCell>
                          <TableCell className="font-mono text-sm">
                            {r.call_recording_caller_id_number || '—'}
                          </TableCell>
                          <TableCell className="font-mono text-sm">
                            {r.call_recording_destination_number || '—'}
                          </TableCell>
                          <TableCell className="text-sm">
                            {r.call_recording_duration ? `${r.call_recording_duration}s` : '—'}
                          </TableCell>
                          <TableCell className="font-mono text-xs text-muted-foreground truncate max-w-xs">
                            {r.call_recording_filename || '—'}
                          </TableCell>
                        </TableRow>
                      ))
                }
              </TableBody>
            </Table>
          </CardContent></Card>
        </>
      )}

      {/* ══ ADD/EDIT DIALOG ════════════════════════════════════════════════════ */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="w-[95vw] max-w-lg h-auto max-h-[90vh] flex flex-col p-0 gap-0">

          <DialogHeader className="px-6 pt-6 pb-4 border-b shrink-0">
            <DialogTitle>{editId ? 'Edit Recording' : 'Define Media File'}</DialogTitle>
            <DialogClose className="absolute right-4 top-4" />
          </DialogHeader>

          <div className="flex-1 overflow-y-auto px-6 py-5 space-y-5">
            {formError && (
              <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
                {formError}
              </div>
            )}

            {/* Information */}
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground mb-3">Information</p>
              <div className="space-y-3">
                <div className="space-y-1.5">
                  <Label>Name <span className="text-destructive">*</span></Label>
                  <Input placeholder="Welcome Greeting" value={form.recording_name} onChange={f('recording_name')} />
                </div>
                <div className="space-y-1.5">
                  <Label>Description</Label>
                  <Input placeholder="Optional description" value={form.recording_description} onChange={f('recording_description')} />
                </div>
              </div>
            </div>

            {/* Dial-to-record section */}
            <div className="rounded-lg border bg-muted/30 p-4 space-y-3">
              <div className="flex items-center gap-2">
                <PhoneCall className="h-4 w-4 text-muted-foreground" />
                <p className="text-sm font-medium">Record dialing an extension or external number</p>
              </div>

              <div className="space-y-1.5">
                <Label>Extension</Label>
                <ExtensionPicker
                  value={form._dial_extension_uuid}
                  onChange={val => setForm(p => ({ ...p, _dial_extension_uuid: val, _dial_external_number: '' }))}
                  extensions={extensions}
                  loading={extLoading}
                />
              </div>

              <div className="flex items-center gap-3">
                <div className="flex-1 h-px bg-border" />
                <span className="text-xs text-muted-foreground">or</span>
                <div className="flex-1 h-px bg-border" />
              </div>

              <div className="space-y-1.5">
                <Label>External Number</Label>
                <Input
                  placeholder="+1 555 000 0000"
                  value={form._dial_external_number}
                  onChange={e => setForm(p => ({ ...p, _dial_external_number: e.target.value, _dial_extension_uuid: '' }))}
                />
              </div>

              <label className="flex items-center gap-2.5 cursor-pointer select-none">
                <input
                  type="checkbox"
                  checked={form._dial_block_caller_id}
                  onChange={e => setForm(p => ({ ...p, _dial_block_caller_id: e.target.checked }))}
                  className="h-4 w-4 rounded border-input accent-primary cursor-pointer"
                />
                <span className="text-sm text-muted-foreground">Block Caller ID</span>
              </label>

              <Button
                type="button"
                variant="outline"
                size="sm"
                className="w-full gap-2"
                onClick={handleDialRecord}
                disabled={dialing}
              >
                {dialing
                  ? <><Loader2 className="h-4 w-4 animate-spin" /> Dialing…</>
                  : <><Phone className="h-4 w-4" /> Start Recording</>}
              </Button>
            </div>

            {/* Upload section */}
            <div className="rounded-lg border bg-muted/30 p-4 space-y-4">
              <div className="flex items-center gap-2">
                <Upload className="h-4 w-4 text-muted-foreground" />
                <p className="text-sm font-medium">…or upload recording</p>
              </div>

              {/* Filename */}
              <div className="space-y-1.5">
                <Label>Filename <span className="text-destructive">*</span></Label>
                <Input
                  placeholder="greeting.wav"
                  value={form.recording_filename}
                  onChange={f('recording_filename')}
                />
              </div>

              {/* File input */}
              <div className="space-y-1.5">
                <Label>File</Label>
                <div className="flex items-center gap-2">
                  <Button type="button" variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
                    <Upload className="h-3.5 w-3.5" /> Choose File
                  </Button>
                  <span className="text-sm text-muted-foreground truncate">
                    {form._file ? form._file.name : 'No file chosen'}
                  </span>
                  {form._file && (
                    <button type="button" onClick={() => setForm(p => ({ ...p, _file: null, recording_base64: '' }))}>
                      <X className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground" />
                    </button>
                  )}
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="audio/*,.wav,.mp3,.ogg,.sln,.gsm"
                  className="hidden"
                  onChange={handleFileChange}
                />
              </div>

              {/* Transformations */}
              <div className="space-y-3 pt-1">
                <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Upload/create transformations
                </p>

                <div className="grid grid-cols-2 gap-3 items-center">
                  <Label>Volume correction</Label>
                  <Input
                    type="number"
                    step="0.1"
                    min="0.1"
                    max="4.0"
                    value={form.recording_volume}
                    onChange={fN('recording_volume')}
                    className="h-8"
                  />
                </div>

                <div className="space-y-1.5">
                  <Label>Format conversion</Label>
                  <div className="space-y-1.5 mt-1">
                    {FORMAT_OPTIONS.map(opt => (
                      <label key={opt.value} className="flex items-center gap-2.5 cursor-pointer select-none group">
                        <input
                          type="radio"
                          name="recording_format"
                          value={opt.value}
                          checked={form.recording_format === opt.value}
                          onChange={() => setForm(p => ({ ...p, recording_format: opt.value }))}
                          className="h-4 w-4 accent-primary cursor-pointer"
                        />
                        <span className="text-sm text-muted-foreground group-hover:text-foreground transition-colors">
                          {opt.label}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <DialogFooter className="px-6 py-4 border-t shrink-0 gap-2">
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              {editId ? 'Save Changes' : 'Create Recording'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
