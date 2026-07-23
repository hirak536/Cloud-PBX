import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { selectAuth } from '@/store'
import { canPerformAction } from '@/lib/permissions'
import { conferences as api } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { Plus, Pencil, Trash2, Search, Loader2 } from 'lucide-react'

const EMPTY = { conference_extension: '', conference_name: '', conference_pin: '', conference_max_members: 0, enabled: true }

export default function Conferences() {
  const navigate = useNavigate()
  const { id: editParamId } = useParams()
  const location = useLocation()
  const isCreate   = location.pathname.endsWith('/conferences/new')
  const routeId    = editParamId
  const editorOpen = isCreate || routeId !== undefined

  const { user: authUser } = useSelector(selectAuth)
  const canAdd    = canPerformAction(authUser, 'conferences', 'add')
  const canEdit   = canPerformAction(authUser, 'conferences', 'edit')
  const canDelete = canPerformAction(authUser, 'conferences', 'delete')

  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebounce(search, 300)
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

  const rowToForm = (r) => ({
    conference_extension: r.conference_extension || '',
    conference_name: r.conference_name || '',
    conference_pin: r.conference_pin || '',
    conference_max_members: r.conference_max_members || 0,
    enabled: r.conference_enabled !== false,
  })

  const openCreate  = () => navigate('/conferences/new')
  const openEdit    = (r) => navigate('/conferences/' + r.conference_uuid + '/edit')
  const closeEditor = () => navigate('/conferences')

  useEffect(() => {
    if (!editorOpen) return
    setFormError('')
    if (isCreate) { setEditId(null); setForm(EMPTY); return }
    setEditId(routeId)
    const row = rows.find(r => r.conference_uuid === routeId)
    if (row) { setForm(rowToForm(row)); return }
    api.get(routeId).then(({ data }) => setForm(rowToForm(data))).catch(() => setForm(EMPTY))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeId, isCreate])

  const handleSave = async () => {
    if (!form.conference_extension) { setFormError('Extension is required.'); return }
    setSaving(true); setFormError('')
    try {
      editId ? await api.update(editId, form) : await api.create(form)
      load(); closeEditor()
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

  if (editorOpen) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={closeEditor} className="-ml-2 gap-1">
            ← Conferences
          </Button>
          <span className="text-muted-foreground">/</span>
          <h1 className="text-lg font-semibold">{isCreate ? 'New Conference' : 'Edit Conference'}</h1>
        </div>

        <Card>
          <div className="px-6 py-5 space-y-4">
            {formError && <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{formError}</div>}
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5"><Label>Extension *</Label><Input placeholder="9000" value={form.conference_extension} onChange={f('conference_extension')} /></div>
              <div className="space-y-1.5"><Label>Name</Label><Input placeholder="Board Room" value={form.conference_name} onChange={f('conference_name')} /></div>
              <div className="space-y-1.5"><Label>PIN</Label><Input type="password" placeholder="Optional PIN" value={form.conference_pin} onChange={f('conference_pin')} /></div>
              <div className="space-y-1.5"><Label>Max Members</Label><Input type="number" placeholder="0 = unlimited" value={form.conference_max_members} onChange={f('conference_max_members')} /></div>
            </div>
          </div>
          <div className="flex justify-end gap-2 px-6 py-3 border-t">
            <Button variant="outline" size="sm" onClick={closeEditor}>Cancel</Button>
            <Button size="sm" onClick={handleSave} disabled={saving} className="gap-1.5">
              {saving && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {isCreate ? 'Create' : 'Save'}
            </Button>
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
          <Input placeholder="Search conferences..." className="pl-8" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        {canAdd && (<Button size="sm" onClick={openCreate}><Plus className="h-4 w-4" />Add Conference</Button>)}
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
                    {canEdit && (<Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(r)}><Pencil className="h-3.5 w-3.5" /></Button>)}
                    {canDelete && (<Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive" onClick={() => handleDelete(id)} disabled={deleting === id}>
                      {deleting === id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                    </Button>)}
                  </div></TableCell>
                </TableRow>
              })}
          </TableBody>
        </Table>
      </CardContent></Card>
    </div>
  )
}
