import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { domains as api } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { Plus, Pencil, Trash2, Search, Loader2 } from 'lucide-react'
import { formatDate } from '@/lib/utils'

const EMPTY = { domain_name: '', domain_description: '', domain_enabled: true }

export default function Domains() {
  const navigate = useNavigate()
  // Route param drives the editor: undefined = list, /new = create, else edit by id.
  // The `/new` route has no :id param, so detect create from the path and only
  // use the param for edit.
  const { id: editParamId } = useParams()
  const location = useLocation()
  const isCreate   = location.pathname.endsWith('/domains/new')
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
    domain_name: r.domain_name || '',
    domain_description: r.domain_description || '',
    domain_enabled: r.domain_enabled !== false,
  })

  // Navigate to the full-page editor; the route effect below loads the form.
  const openCreate  = () => navigate('/domains/new')
  const openEdit    = (r) => navigate('/domains/' + r.domain_uuid + '/edit')
  const closeEditor = () => navigate('/domains')

  // Sync form state to the current route.
  useEffect(() => {
    if (!editorOpen) return
    setFormError('')
    if (isCreate) { setEditId(null); setForm(EMPTY); return }
    setEditId(routeId)
    const row = rows.find(r => r.domain_uuid === routeId)
    if (row) { setForm(rowToForm(row)); return }
    // Deep-link / refresh: fetch the row if the list isn't loaded yet.
    api.get?.(routeId)
      .then(({ data }) => setForm(rowToForm(data)))
      .catch(() => { setForm(EMPTY) })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeId, isCreate, rows])

  const handleSave = async () => {
    if (!form.domain_name) { setFormError('Domain name is required.'); return }
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
    if (!confirm('Delete this domain? This will affect all associated resources.')) return
    setDeleting(id)
    try { await api.delete(id); load() } finally { setDeleting(null) }
  }

  // ── Full-page editor (routed) ──────────────────────────────────────────────
  if (editorOpen) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={closeEditor} className="-ml-2 gap-1">
            ← Domains
          </Button>
          <span className="text-muted-foreground">/</span>
          <h1 className="text-lg font-semibold">{isCreate ? 'New Domain' : 'Edit Domain'}</h1>
        </div>

        <Card>
          <div className="px-6 py-5 space-y-4">
            {formError && <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{formError}</div>}
            <div className="space-y-3">
              <div className="space-y-1.5"><Label>Domain Name *</Label><Input placeholder="company.pbx.com" value={form.domain_name} onChange={f('domain_name')} /></div>
              <div className="space-y-1.5"><Label>Description</Label><Input placeholder="Optional" value={form.domain_description} onChange={f('domain_description')} /></div>
            </div>
          </div>

          <div className="flex justify-end gap-2 px-6 py-3 border-t">
            <Button variant="outline" size="sm" onClick={closeEditor}>Cancel</Button>
            <Button size="sm" onClick={handleSave} disabled={saving} className="gap-1.5">
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
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
    </div>
  )
}
