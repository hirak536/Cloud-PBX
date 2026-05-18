import { useState, useEffect, useRef, useCallback } from 'react'
import { freeswitch as fsApi } from '@/api'
import { useSelector } from 'react-redux'
import { selectAuth } from '@/store'
import { Navigate } from 'react-router-dom'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Select } from '@/components/ui/select'
import { RefreshCw, Play, Pause, Search, Terminal } from 'lucide-react'
import { cn } from '@/lib/utils'

const LEVEL_STYLES = {
  ERROR:   'text-red-400',
  WARNING: 'text-amber-400',
  NOTICE:  'text-blue-400',
  DEBUG:   'text-gray-500',
  INFO:    'text-gray-300',
}

const LEVEL_BADGE = {
  ERROR:   'destructive',
  WARNING: 'warning',
  NOTICE:  'secondary',
  DEBUG:   'outline',
  INFO:    'secondary',
}

// Highlight IPs and known keywords in a log line
function HighlightedLine({ text }) {
  // Split on IPs (IPv4) to highlight them
  const parts = text.split(/(\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b)/)
  return (
    <span>
      {parts.map((part, i) =>
        /^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$/.test(part)
          ? <span key={i} className="text-cyan-400 font-semibold">{part}</span>
          : <span key={i}>{part}</span>
      )}
    </span>
  )
}

export default function FreeSwitchLog() {
  const { user } = useSelector(selectAuth)
  if (!user?.is_superuser) return <Navigate to="/" replace />

  const [lines, setLines] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [level, setLevel] = useState('ALL')
  const [lineCount, setLineCount] = useState('200')
  const [autoRefresh, setAutoRefresh] = useState(false)
  const [lastUpdated, setLastUpdated] = useState(null)
  const bottomRef = useRef(null)
  const intervalRef = useRef(null)

  const fetchLog = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params = { lines: lineCount }
      if (level !== 'ALL') params.level = level
      if (search) params.search = search
      const { data } = await fsApi.log(params)
      setLines(data.lines || [])
      setLastUpdated(new Date())
    } catch (e) {
      setError(e.response?.data?.error || 'Failed to fetch log')
    } finally {
      setLoading(false)
    }
  }, [lineCount, level, search])

  useEffect(() => {
    fetchLog()
  }, [])  // initial load only — manual refresh for filter changes

  // Auto-refresh
  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(fetchLog, 5000)
    } else {
      clearInterval(intervalRef.current)
    }
    return () => clearInterval(intervalRef.current)
  }, [autoRefresh, fetchLog])

  // Scroll to bottom when lines update and auto-refresh is on
  useEffect(() => {
    if (autoRefresh && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [lines, autoRefresh])

  const levelCounts = lines.reduce((acc, l) => {
    acc[l.level] = (acc[l.level] || 0) + 1
    return acc
  }, {})

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-3">
        <Terminal className="h-5 w-5 text-muted-foreground" />
        <div>
          <h1 className="text-lg font-semibold">FreeSWITCH Log</h1>
          <p className="text-xs text-muted-foreground">/var/log/freeswitch/freeswitch.log</p>
        </div>
        {lastUpdated && (
          <span className="ml-auto text-xs text-muted-foreground">
            Updated {lastUpdated.toLocaleTimeString()}
          </span>
        )}
      </div>

      {/* Level summary badges */}
      {lines.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {['ERROR', 'WARNING', 'NOTICE', 'INFO', 'DEBUG'].map((lvl) =>
            levelCounts[lvl] ? (
              <Badge key={lvl} variant={LEVEL_BADGE[lvl]} className="gap-1">
                {lvl} <span className="opacity-70">{levelCounts[lvl]}</span>
              </Badge>
            ) : null
          )}
          <span className="text-xs text-muted-foreground self-center">{lines.length} lines shown</span>
        </div>
      )}

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="relative min-w-48 flex-1">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Filter log lines..."
            className="pl-8 font-mono text-sm"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && fetchLog()}
          />
        </div>

        <Select className="w-32" value={level} onChange={(e) => setLevel(e.target.value)}>
          <option value="ALL">All Levels</option>
          <option value="ERROR">ERROR</option>
          <option value="WARNING">WARNING</option>
          <option value="NOTICE">NOTICE</option>
          <option value="INFO">INFO</option>
          <option value="DEBUG">DEBUG</option>
        </Select>

        <Select className="w-28" value={lineCount} onChange={(e) => setLineCount(e.target.value)}>
          <option value="100">100 lines</option>
          <option value="200">200 lines</option>
          <option value="500">500 lines</option>
          <option value="1000">1000 lines</option>
          <option value="2000">2000 lines</option>
        </Select>

        <Button variant="outline" size="sm" onClick={fetchLog} disabled={loading}>
          <RefreshCw className={cn('h-4 w-4 mr-1.5', loading && 'animate-spin')} />
          Refresh
        </Button>

        <Button
          variant={autoRefresh ? 'default' : 'outline'}
          size="sm"
          onClick={() => setAutoRefresh((v) => !v)}
        >
          {autoRefresh
            ? <><Pause className="h-4 w-4 mr-1.5" /> Live</>
            : <><Play className="h-4 w-4 mr-1.5" /> Live</>}
        </Button>
      </div>

      {/* Log output */}
      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <div className="bg-[#0d1117] rounded-xl overflow-auto max-h-[65vh] font-mono text-xs">
            {error ? (
              <div className="p-6 text-red-400">{error}</div>
            ) : lines.length === 0 && !loading ? (
              <div className="p-6 text-gray-500">No log lines found.</div>
            ) : (
              <table className="w-full border-collapse">
                <tbody>
                  {lines.map((line, i) => (
                    <tr
                      key={i}
                      className={cn(
                        'border-b border-white/5 hover:bg-white/5 transition-colors',
                        line.level === 'ERROR' && 'bg-red-950/20',
                        line.level === 'WARNING' && 'bg-amber-950/10',
                      )}
                    >
                      <td className="pl-4 pr-2 py-0.5 select-none text-gray-600 text-right w-10 shrink-0">
                        {i + 1}
                      </td>
                      <td className={cn('pr-3 py-0.5 w-20 shrink-0 font-semibold', LEVEL_STYLES[line.level])}>
                        {line.level}
                      </td>
                      <td className="pr-4 py-0.5 text-gray-300 whitespace-pre-wrap break-all">
                        <HighlightedLine text={line.text} />
                      </td>
                    </tr>
                  ))}
                  <tr ref={bottomRef} />
                </tbody>
              </table>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
