import { useEffect, useState, useCallback } from 'react'
import { voicemailMessages as messagesApi } from '@/api'
import { useSelector } from 'react-redux'
import { selectTenant } from '@/store'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { ChevronDown, ChevronRight, Inbox, Phone, Trash2, Loader2, RefreshCw, Volume2 } from 'lucide-react'
import AudioPlayer from '@/components/AudioPlayer'

function formatDuration(secs) {
  if (!secs) return '0:00'
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

function formatDate(epoch) {
  if (!epoch) return '—'
  return new Date(epoch * 1000).toLocaleString()
}

// ── Mailbox Group (expandable) ────────────────────────────────────────────────

function MailboxGroup({ username, messages, onDelete, onMarkRead }) {
  const [expanded, setExpanded] = useState(false)
  const unread = messages.filter(m => !m.is_read).length

  return (
    <>
      <TableRow className="cursor-pointer hover:bg-muted/40" onClick={() => setExpanded(v => !v)}>
        <TableCell className="w-6 pl-4 pr-1">
          {expanded ? <ChevronDown className="h-4 w-4 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 text-muted-foreground" />}
        </TableCell>
        <TableCell className="font-mono font-medium">{username}</TableCell>
        <TableCell>
          <span className="text-sm text-muted-foreground">{messages.length} message{messages.length !== 1 ? 's' : ''}</span>
          {unread > 0 && <span className="ml-2 inline-flex items-center rounded-full bg-primary px-2 py-0.5 text-xs font-medium text-primary-foreground">{unread} new</span>}
        </TableCell>
      </TableRow>

      {expanded && (
        <TableRow>
          <TableCell colSpan={3} className="p-0 bg-muted/20">
            <div className="px-4 py-2">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-xs text-muted-foreground border-b">
                    <th className="text-left pb-2 pl-2 font-medium">Caller</th>
                    <th className="text-left pb-2 font-medium">Date</th>
                    <th className="text-left pb-2 font-medium">Duration</th>
                    <th className="text-left pb-2 font-medium w-64">Play</th>
                    <th className="pb-2 w-10" />
                  </tr>
                </thead>
                <tbody>
                {messages.map(msg => (
                    <tr key={msg.uuid} className={msg.is_read ? 'opacity-60' : 'font-medium'}>
                      <td className="py-1.5 pl-2">
                        <div className="flex items-center gap-1.5">
                          <Phone className="h-3 w-3 text-muted-foreground shrink-0" />
                          <span>{msg.cid_number || '—'}</span>
                          {msg.cid_name && msg.cid_name !== msg.cid_number && (
                            <span className="text-muted-foreground font-normal">({msg.cid_name})</span>
                          )}
                        </div>
                      </td>
                      <td className="py-1.5 text-muted-foreground font-normal tabular-nums text-xs">{formatDate(msg.created_epoch)}</td>
                      <td className="py-1.5 font-mono tabular-nums">{formatDuration(msg.message_len)}</td>
                      <td className="py-1.5 min-w-[200px]">
                        <AudioPlayer
                          fetchAudio={() => messagesApi.fetchAudio(msg.uuid)}
                          onPlay={msg.is_read ? undefined : () => onMarkRead(msg)}
                        />
                      </td>
                      <td className="py-1.5 text-right pr-2">
                        <Button variant="ghost" size="icon" className="h-6 w-6 text-destructive hover:text-destructive"
                          onClick={e => { e.stopPropagation(); onDelete(msg.uuid) }}>
                          <Trash2 className="h-3 w-3" />
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </TableCell>
        </TableRow>
      )}
    </>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function VoicemailInbox() {
  const { currentTenant } = useSelector(selectTenant)
  const [grouped, setGrouped] = useState({})   // { username: [msg, ...] }
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      // Load all messages for the tenant's domain
      const params = currentTenant?.tenant_uuid ? { tenant: currentTenant.tenant_uuid } : {}
      const { data } = await messagesApi.list(params)
      const msgs = Array.isArray(data) ? data : data.results || []
      // Group by mailbox_name (extension number resolved from UUID)
      const groups = {}
      for (const m of msgs) {
        const key = m.mailbox_name || m.username
        if (!groups[key]) groups[key] = []
        groups[key].push(m)
      }
      setGrouped(groups)
    } catch {
      setError('Failed to load voicemail messages.')
    } finally {
      setLoading(false)
    }
  }, [currentTenant?.tenant_uuid])

  useEffect(() => { load() }, [load])

  const handleDelete = async (uuid) => {
    if (!confirm('Delete this voicemail message?')) return
    try {
      await messagesApi.delete(uuid)
      setGrouped(prev => {
        const next = { ...prev }
        for (const u of Object.keys(next)) {
          next[u] = next[u].filter(m => m.uuid !== uuid)
          if (next[u].length === 0) delete next[u]
        }
        return next
      })
    } catch { /* ignore */ }
  }

  const handleMarkRead = async (msg) => {
    try {
      await messagesApi.markRead(msg.uuid)
      setGrouped(prev => {
        const next = { ...prev }
        for (const u of Object.keys(next)) {
          next[u] = next[u].map(m => m.uuid === msg.uuid ? { ...m, is_read: true } : m)
        }
        return next
      })
    } catch (err) {
      console.error('mark_read failed:', err?.response?.status, err?.response?.data)
    }
  }

  const usernames = Object.keys(grouped).sort()

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 flex-1">
          <Volume2 className="h-5 w-5 text-muted-foreground" />
          <h2 className="text-base font-semibold">Voicemail Inbox</h2>
          {!loading && <span className="text-sm text-muted-foreground">— {usernames.length} mailbox{usernames.length !== 1 ? 'es' : ''}</span>}
        </div>
        <Button variant="outline" size="sm" onClick={load} disabled={loading}>
          <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </Button>
      </div>

      {error && <div className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">{error}</div>}

      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-6 pl-4" />
                <TableHead>Mailbox</TableHead>
                <TableHead>Messages</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading
                ? [...Array(4)].map((_, i) => (
                    <TableRow key={i}>
                      {[...Array(3)].map((_, j) => <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>)}
                    </TableRow>
                  ))
                : usernames.length === 0
                  ? (
                    <TableRow>
                      <TableCell colSpan={3} className="py-12 text-center text-muted-foreground">
                        <Inbox className="h-8 w-8 mx-auto mb-2 opacity-30" />
                        No voicemail messages found.
                      </TableCell>
                    </TableRow>
                  )
                  : usernames.map(u => (
                      <MailboxGroup
                        key={u}
                        username={u}
                        messages={grouped[u]}
                        onDelete={handleDelete}
                        onMarkRead={handleMarkRead}
                      />
                    ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}
