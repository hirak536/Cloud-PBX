import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback, useRef } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { voicemails as voicemailsApi, recordings as recordingsApi } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { Plus, Pencil, Trash2, Search, Loader2, Upload } from 'lucide-react'
import { Select } from '@/components/ui/select'

const GREETING_LABELS = {
  auto_with_instructions: 'Automatic',
  tts_name: 'TTS',
  recorded_name: 'Recorded name',
  media_file: 'Media file',
}

const EMPTY = {
  extension: '', password: '', name: '', enabled: true,
  voicemail_greeting: 'auto_with_instructions', tts_greeting_text: '',
  voicemail_greeting_recording: '',
  voicemail_mail_to: '',
}

export default function Voicemails() {
  const navigate = useNavigate()
  // Route param drives the editor: undefined = list, 'new' = create, else edit by id.
  // The `/new` route has no :id param, so detect create from the path.
  const { id: editParamId } = useParams()
  const location = useLocation()
  const isCreate   = location.pathname.endsWith('/voicemails/new')
  const routeId    = editParamId
  const editorOpen = isCreate || routeId !== undefined

  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebounce(search, 300)
  const [editId, setEditId] = useState(null)
  const [form, setForm] = useState(EMPTY)
  const [saving, setSaving] = useState(false)
  const [formError, setFormError] = useState('')
  const [deleting, setDeleting] = useState(null)
  const [nameFile, setNameFile] = useState(null)
  const [uploadingName, setUploadingName] = useState(false)
  const [uploadMsg, setUploadMsg] = useState('')
  const [mediaFiles, setMediaFiles] = useState([])

  // Load Media Files (recordings) once, for the media-file greeting picker.
  useEffect(() => {
    recordingsApi.list({ page_size: 200 })
      .then(({ data }) => setMediaFiles(Array.isArray(data) ? data : data.results || []))
      .catch(() => setMediaFiles([]))
  }, [])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const params = {}
      if (search) params.search = search
      const { data } = await voicemailsApi.list(params)
      setRows(Array.isArray(data) ? data : data.results || [])
    } finally { setLoading(false) }
  }, [search])

  useEffect(() => { load() }, [load])

  const rowToForm = (r) => ({
    extension: r.voicemail_id || r.extension || '',
    password: r.voicemail_password || r.password || '',
    name: r.voicemail_name || '',
    enabled: r.voicemail_enabled !== false,
    voicemail_greeting: r.voicemail_greeting || 'auto_with_instructions',
    tts_greeting_text: r.tts_greeting_text || '',
    voicemail_greeting_recording: r.voicemail_greeting_recording || '',
    voicemail_mail_to: r.voicemail_mail_to || '',
  })

  // Navigate to the full-page editor; the route effect below loads the form.
  const openCreate  = () => navigate('/voicemails/new')
  const openEdit    = (r) => navigate(`/voicemails/${r.voicemail_uuid || r.id}/edit`)
  const closeEditor = () => navigate('/voicemails')

  // Sync form state to the current route. Guarded on the route key so it runs
  // once per editor-open — a re-run when the list `rows` refetch in the
  // background would otherwise clobber the user's in-progress edits.
  const lastRouteKeyRef = useRef(null)
  useEffect(() => {
    if (!editorOpen) { lastRouteKeyRef.current = null; return }
    const routeKey = isCreate ? 'new' : routeId
    if (lastRouteKeyRef.current === routeKey) return
    lastRouteKeyRef.current = routeKey
    setFormError(''); setNameFile(null); setUploadMsg('')
    if (isCreate) { setEditId(null); setForm(EMPTY); return }
    setEditId(routeId)
    const row = rows.find(r => (r.voicemail_uuid || r.id) === routeId)
    if (row) { setForm(rowToForm(row)); return }
    // Deep-link / refresh: fetch the row if the list isn't loaded yet.
    voicemailsApi.get?.(routeId)
      .then(({ data }) => setForm(rowToForm(data)))
      .catch(() => { setForm(EMPTY) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeId, isCreate, rows])

  const handleSave = async () => {
    if (!form.extension) { setFormError('Extension is required.'); return }
    setSaving(true); setFormError('')
    try {
      const payload = {
        voicemail_id: form.extension,
        voicemail_password: form.password,
        voicemail_name: form.name,
        voicemail_enabled: form.enabled,
        voicemail_greeting: form.voicemail_greeting,
        tts_greeting_text: form.tts_greeting_text,
        voicemail_greeting_recording:
          form.voicemail_greeting === 'media_file' ? (form.voicemail_greeting_recording || null) : null,
        voicemail_mail_to: form.voicemail_mail_to,
        voicemail_on_new_message: form.voicemail_mail_to ? 'both' : 'nothing',
        voicemail_file: form.voicemail_mail_to ? 'attach' : 'none',
      }
      editId ? await voicemailsApi.update(editId, payload) : await voicemailsApi.create(payload)
      load(); closeEditor()
    } catch (err) {
      const d = err?.response?.data
      setFormError(typeof d === 'string' ? d : Object.values(d || {}).flat().join(' ') || 'Save failed.')
    } finally { setSaving(false) }
  }

  const handleUploadName = async () => {
    if (!nameFile || !editId) return
    setUploadingName(true); setUploadMsg('')
    try {
      const fd = new FormData()
      fd.append('file', nameFile)
      await voicemailsApi.uploadName(editId, fd)
      setUploadMsg('Name recording saved.')
      setNameFile(null)
    } catch {
      setUploadMsg('Upload failed.')
    } finally { setUploadingName(false) }
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this voicemail?')) return
    setDeleting(id)
    try { await voicemailsApi.delete(id); load() } finally { setDeleting(null) }
  }

  // ── Full-page editor (routed) ──────────────────────────────────────────────
  if (editorOpen) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={closeEditor} className="-ml-2 gap-1">
            ← Voicemails
          </Button>
          <span className="text-muted-foreground">/</span>
          <h1 className="text-lg font-semibold">{isCreate ? 'New Voicemail' : 'Edit Voicemail'}</h1>
        </div>

        <Card>
          <div className="px-6 py-5 space-y-4">
            {formError && <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{formError}</div>}
            <div className="space-y-3">
              <div className="space-y-1.5"><Label>Extension *</Label><Input placeholder="1001" value={form.extension} onChange={(e) => setForm(f => ({ ...f, extension: e.target.value }))} /></div>
              <div className="space-y-1.5"><Label>PIN</Label><Input type="text" placeholder="4-digit PIN" value={form.password} onChange={(e) => setForm(f => ({ ...f, password: e.target.value }))} className="font-mono" /></div>
              <div className="space-y-1.5"><Label>Name / Description</Label><Input placeholder="John Doe" value={form.name} onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))} /></div>

              <div className="space-y-1.5">
                <Label>Greeting Mode</Label>
                <Select value={form.voicemail_greeting} onChange={(e) => setForm(f => ({ ...f, voicemail_greeting: e.target.value }))}>
                  <option value="auto_with_instructions">Automatic with instructions</option>
                  <option value="tts_name">Text-to-speech greeting</option>
                  <option value="recorded_name">Recorded name greeting</option>
                  <option value="media_file">Media file greeting</option>
                </Select>
              </div>

              {form.voicemail_greeting === 'media_file' && (
                <div className="space-y-1.5">
                  <Label>Greeting media file</Label>
                  <Select
                    value={form.voicemail_greeting_recording || ''}
                    onChange={(e) => setForm(f => ({ ...f, voicemail_greeting_recording: e.target.value }))}
                  >
                    <option value="">Select a media file…</option>
                    {mediaFiles.map((m) => (
                      <option key={m.recording_uuid} value={m.recording_uuid}>
                        {m.recording_name || m.recording_filename}
                      </option>
                    ))}
                  </Select>
                  <p className="text-xs text-muted-foreground">
                    Upload greetings on the <span className="font-medium">Media Files</span> page, then pick one here.
                  </p>
                </div>
              )}

              {form.voicemail_greeting === 'tts_name' && (
                <div className="space-y-1.5">
                  <Label>Custom TTS text <span className="text-muted-foreground text-xs">(optional)</span></Label>
                  <Input
                    placeholder={`You have reached extension ${form.extension || '1001'}. Please leave a message after the beep.`}
                    value={form.tts_greeting_text}
                    onChange={(e) => setForm(f => ({ ...f, tts_greeting_text: e.target.value }))}
                  />
                  <p className="text-xs text-muted-foreground">Leave blank to use the default message.</p>
                </div>
              )}

              {form.voicemail_greeting === 'recorded_name' && editId && (
                <div className="rounded-md border px-3 py-2.5 space-y-2">
                  <p className="text-sm font-medium">Name recording</p>
                  <p className="text-xs text-muted-foreground">
                    Dial <span className="font-mono bg-muted px-1 rounded">*95</span> from your extension to record your name, or upload a WAV file below.
                  </p>
                  <div className="flex items-center gap-2">
                    <Input
                      type="file" accept=".wav,audio/wav"
                      className="text-sm h-8"
                      onChange={(e) => { setNameFile(e.target.files[0]); setUploadMsg('') }}
                    />
                    {nameFile && (
                      <Button size="sm" onClick={handleUploadName} disabled={uploadingName}>
                        {uploadingName ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
                      </Button>
                    )}
                  </div>
                  {uploadMsg && (
                    <p className={`text-xs ${uploadMsg.includes('failed') ? 'text-destructive' : 'text-green-600'}`}>{uploadMsg}</p>
                  )}
                </div>
              )}

              {form.voicemail_greeting === 'recorded_name' && !editId && (
                <p className="text-xs text-muted-foreground rounded-md border px-3 py-2">
                  Save the voicemail first, then upload a name recording or dial <span className="font-mono bg-muted px-1 rounded">*95</span>.
                </p>
              )}

              <div className="rounded-md border px-3 py-3 space-y-3">
                <p className="text-sm font-medium">Email Notifications</p>
                <div className="space-y-1.5">
                  <Label>Notification Email</Label>
                  <Input
                    type="text"
                    placeholder="user@example.com, other@example.com"
                    value={form.voicemail_mail_to}
                    onChange={(e) => setForm(f => ({ ...f, voicemail_mail_to: e.target.value }))}
                  />
                  <p className="text-xs text-muted-foreground">Send new voicemail notifications to these addresses. Separate multiple with commas.</p>
                </div>
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-2 px-6 py-3 border-t">
            <Button variant="outline" onClick={closeEditor}>Cancel</Button>
            <Button onClick={handleSave} disabled={saving}>{saving && <Loader2 className="h-4 w-4 animate-spin" />}{isCreate ? 'Create' : 'Save'}</Button>
          </div>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input placeholder="Search..." className="pl-8" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <Button size="sm" onClick={openCreate}><Plus className="h-4 w-4" />Add Voicemail</Button>
      </div>

      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <TableHeader><TableRow>
              <TableHead>Extension</TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Greeting</TableHead>
              <TableHead className="w-20" />
            </TableRow></TableHeader>
            <TableBody>
              {loading ? [...Array(6)].map((_, i) => (
                <TableRow key={i}>{[...Array(4)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}</TableRow>
              )) : rows.length === 0 ? (
                <TableRow><TableCell colSpan={5} className="text-center py-10 text-muted-foreground">No voicemails found.</TableCell></TableRow>
              ) : rows.map((r) => {
                const id = r.voicemail_uuid || r.id
                return (
                  <TableRow key={id}>
                    <TableCell className="font-mono font-medium">{r.voicemail_id || r.extension}</TableCell>
                    <TableCell>{r.voicemail_name || '—'}</TableCell>
                    <TableCell><Badge variant={r.voicemail_enabled !== false ? 'success' : 'secondary'}>{r.voicemail_enabled !== false ? 'Active' : 'Disabled'}</Badge></TableCell>
                    <TableCell className="text-sm text-muted-foreground">{GREETING_LABELS[r.voicemail_greeting] || r.voicemail_greeting || '—'}</TableCell>
                    <TableCell>
                      <div className="flex gap-1">
                        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(r)}><Pencil className="h-3.5 w-3.5" /></Button>
                        <Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive" onClick={() => handleDelete(id)} disabled={deleting === id}>
                          {deleting === id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                )
              })}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
