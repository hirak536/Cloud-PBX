import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { devices as api } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { Plus, Pencil, Trash2, Search, Loader2 } from 'lucide-react'

const EMPTY = { device_mac_address: '', device_label: '', device_vendor: '', device_model: '', device_profile_name: '', enabled: true }

export default function Devices() {
  const navigate = useNavigate()
  const { id: editParamId } = useParams()
  const location = useLocation()
  const isCreate   = location.pathname.endsWith('/devices/new')
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
    device_mac_address: r.device_mac_address || '',
    device_label: r.device_label || '',
    device_vendor: r.device_vendor || '',
    device_model: r.device_model || '',
    device_profile_name: r.device_profile_name || '',
    enabled: r.device_enabled !== false,
  })

  const openCreate  = () => navigate('/devices/new')
  const openEdit    = (r) => navigate('/devices/' + r.device_uuid + '/edit')
  const closeEditor = () => navigate('/devices')

  useEffect(() => {
    if (!editorOpen) return
    setFormError('')
    if (isCreate) { setEditId(null); setForm(EMPTY); return }
    setEditId(routeId)
    const row = rows.find(r => r.device_uuid === routeId)
    if (row) { setForm(rowToForm(row)); return }
    api.get(routeId).then(({data}) => setForm(rowToForm(data))).catch(() => setForm(EMPTY))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [routeId, isCreate])

  const handleSave = async () => {
    if (!form.device_mac_address) { setFormError('MAC address is required.'); return }
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
    if (!confirm('Delete this device?')) return
    setDeleting(id)
    try { await api.delete(id); load() } finally { setDeleting(null) }
  }

  // ── Full-page editor (routed) ──────────────────────────────────────────────
  if (editorOpen) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={closeEditor} className="-ml-2 gap-1">
            ← Devices
          </Button>
          <span className="text-muted-foreground">/</span>
          <h1 className="text-lg font-semibold">{isCreate ? 'New Device' : 'Edit Device'}</h1>
        </div>

        <Card>
          <div className="px-6 py-5 space-y-4">
            {formError && <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{formError}</div>}
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2 space-y-1.5"><Label>MAC Address *</Label><Input placeholder="00:11:22:33:44:55" value={form.device_mac_address} onChange={f('device_mac_address')} /></div>
              <div className="space-y-1.5"><Label>Label</Label><Input placeholder="Reception Phone" value={form.device_label} onChange={f('device_label')} /></div>
              <div className="space-y-1.5"><Label>Vendor</Label><Input placeholder="Yealink" value={form.device_vendor} onChange={f('device_vendor')} /></div>
              <div className="space-y-1.5"><Label>Model</Label><Input placeholder="T46G" value={form.device_model} onChange={f('device_model')} /></div>
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
          <Input placeholder="Search devices..." className="pl-8" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <Button size="sm" onClick={openCreate}><Plus className="h-4 w-4" />Add Device</Button>
      </div>
      <Card><CardContent className="p-0 overflow-x-auto">
        <Table>
          <TableHeader><TableRow>
            <TableHead>MAC Address</TableHead><TableHead>Label</TableHead><TableHead>Vendor</TableHead><TableHead>Model</TableHead><TableHead>Status</TableHead><TableHead className="w-20" />
          </TableRow></TableHeader>
          <TableBody>
            {loading ? [...Array(5)].map((_, i) => <TableRow key={i}>{[...Array(6)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}</TableRow>)
              : rows.length === 0 ? <TableRow><TableCell colSpan={6} className="text-center py-10 text-muted-foreground">No devices found.</TableCell></TableRow>
              : rows.map((r) => {
                const id = r.device_uuid || r.id
                return <TableRow key={id}>
                  <TableCell className="font-mono text-sm">{r.device_mac_address}</TableCell>
                  <TableCell>{r.device_label || '—'}</TableCell>
                  <TableCell>{r.device_vendor || '—'}</TableCell>
                  <TableCell>{r.device_model || '—'}</TableCell>
                  <TableCell><Badge variant={r.device_enabled !== false ? 'success' : 'secondary'}>{r.device_enabled !== false ? 'Active' : 'Disabled'}</Badge></TableCell>
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
