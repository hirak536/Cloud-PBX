import { useState, useRef, useCallback } from 'react'
import { systemLog as logApi } from '@/api'
import { useSelector } from 'react-redux'
import { selectAuth } from '@/store'
import { Navigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { RefreshCw, Download, ScrollText } from 'lucide-react'
import { cn } from '@/lib/utils'

const LEVEL_COLOR = {
  ERROR:   'text-red-400',
  WARNING: 'text-amber-400',
  DEBUG:   'text-gray-500',
  INFO:    'text-gray-300',
}

const LEVEL_BADGE = {
  ERROR:   'destructive',
  WARNING: 'outline',
  DEBUG:   'outline',
  INFO:    'secondary',
}

const LINE_COUNTS = [100, 200, 500, 1000]
const LEVELS = ['ALL', 'ERROR', 'WARNING', 'INFO', 'DEBUG']

export default function SystemLog() {
  const { user } = useSelector(selectAuth)
  if (!user?.is_superuser) return <Navigate to="/" replace />

  const [lines, setLines] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [lineCount, setLineCount] = useState(200)
  const [levelFilter, setLevelFilter] = useState('ALL')
  const bottomRef = useRef(null)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const params = { lines: lineCount }
      if (levelFilter !== 'ALL') params.level = levelFilter
      const { data } = await logApi.fetch(params)
      setLines(data.lines || [])
      setTotal(data.total || 0)
      setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 50)
    } catch (e) {
      setError(e?.response?.data?.error || 'Failed to fetch logs.')
    } finally {
      setLoading(false)
    }
  }, [lineCount, levelFilter])

  const displayed = search
    ? lines.filter(l => l.line.toLowerCase().includes(search.toLowerCase()))
    : lines

  const download = () => {
    const text = lines.map(l => l.line).join('\n')
    const blob = new Blob([text], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `system-log-${new Date().toISOString().slice(0, 19)}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }

  const counts = lines.reduce((acc, l) => {
    acc[l.level] = (acc[l.level] || 0) + 1
    return acc
  }, {})

  return (
    <div className="space-y-4 p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ScrollText className="h-5 w-5 text-muted-foreground" />
          <h1 className="text-xl font-semibold">System Log</h1>
        </div>
        <div className="flex items-center gap-2">
          {lines.length > 0 && (
            <Button variant="outline" size="sm" onClick={download}>
              <Download className="h-3.5 w-3.5 mr-1" /> Download
            </Button>
          )}
          <Button onClick={fetch} disabled={loading} size="sm">
            <RefreshCw className={cn('h-3.5 w-3.5 mr-1', loading && 'animate-spin')} />
            {loading ? 'Loading…' : lines.length ? 'Refresh' : 'Fetch Logs'}
          </Button>
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap gap-2 items-center">
        <div className="flex items-center gap-1 text-sm text-muted-foreground">
          <span>Lines:</span>
          {LINE_COUNTS.map(n => (
            <button
              key={n}
              onClick={() => setLineCount(n)}
              className={cn(
                'px-2 py-0.5 rounded text-xs border',
                lineCount === n ? 'bg-primary text-primary-foreground border-primary' : 'border-border hover:bg-muted'
              )}
            >{n}</button>
          ))}
        </div>
        <div className="flex items-center gap-1 text-sm text-muted-foreground">
          <span>Level:</span>
          {LEVELS.map(l => (
            <button
              key={l}
              onClick={() => setLevelFilter(l)}
              className={cn(
                'px-2 py-0.5 rounded text-xs border',
                levelFilter === l ? 'bg-primary text-primary-foreground border-primary' : 'border-border hover:bg-muted'
              )}
            >{l}</button>
          ))}
        </div>
        {lines.length > 0 && (
          <Input
            placeholder="Search…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="h-7 w-48 text-xs"
          />
        )}
      </div>

      {/* Summary badges */}
      {lines.length > 0 && (
        <div className="flex gap-2 flex-wrap text-xs">
          <span className="text-muted-foreground">{total} lines</span>
          {Object.entries(counts).sort().map(([lvl, cnt]) => (
            <Badge key={lvl} variant={LEVEL_BADGE[lvl] || 'secondary'} className="text-xs">
              {lvl}: {cnt}
            </Badge>
          ))}
          {search && <span className="text-muted-foreground">{displayed.length} matching</span>}
        </div>
      )}

      {error && <p className="text-sm text-destructive">{error}</p>}

      {/* Log output */}
      {lines.length > 0 ? (
        <Card>
          <CardContent className="p-0">
            <div className="bg-zinc-950 rounded-md overflow-auto max-h-[70vh] font-mono text-xs p-3 space-y-0.5">
              {displayed.map((entry, i) => (
                <div key={i} className={cn('whitespace-pre-wrap break-all leading-relaxed', LEVEL_COLOR[entry.level])}>
                  {entry.line}
                </div>
              ))}
              <div ref={bottomRef} />
            </div>
          </CardContent>
        </Card>
      ) : !loading && (
        <Card>
          <CardContent className="py-16 flex flex-col items-center gap-2 text-muted-foreground">
            <ScrollText className="h-8 w-8 opacity-30" />
            <p className="text-sm">Click <strong>Fetch Logs</strong> to load recent log entries.</p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
