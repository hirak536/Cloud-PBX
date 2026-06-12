import { useDebounce } from '@/hooks/useDebounce'
import { useEffect, useState, useCallback, useRef, useMemo } from 'react'
import { recordings as api } from '@/api'
import { formatDate } from '@/lib/utils'
import { useInfiniteList } from '@/hooks/useInfiniteList'
import { InfiniteScroll, PageSizeSelector, DEFAULT_PAGE_SIZE } from '@/components/InfiniteScroll'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Search, FileAudio, Download, Play, Pause, Loader2,
  PhoneIncoming, PhoneOutgoing, Phone, RefreshCw,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// ── Audio player ──────────────────────────────────────────────────────────────

function AudioPlayer({ recordingId }) {
  const [blobUrl, setBlobUrl]         = useState(null)
  const [loading, setLoading]         = useState(false)
  const [playing, setPlaying]         = useState(false)
  const [progress, setProgress]       = useState(0)
  const [duration, setDuration]       = useState(0)
  const [downloading, setDownloading] = useState(false)
  const audioRef = useRef(null)

  const ensureLoaded = async () => {
    if (blobUrl) return blobUrl
    setLoading(true)
    try {
      const { data } = await api.streamRecording(recordingId)
      const url = URL.createObjectURL(data)
      setBlobUrl(url)
      return url
    } catch {
      return null
    } finally {
      setLoading(false)
    }
  }

  const togglePlay = async () => {
    const url = await ensureLoaded()
    if (!url) return
    const audio = audioRef.current
    if (!audio) return
    playing ? audio.pause() : audio.play()
  }

  useEffect(() => {
    if (blobUrl && audioRef.current) audioRef.current.play()
  }, [blobUrl])

  const handleDownload = async () => {
    setDownloading(true)
    try {
      const { data } = await api.downloadRecording(recordingId)
      const url = URL.createObjectURL(data)
      const a = document.createElement('a')
      a.href = url
      a.download = `recording-${recordingId}.wav`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setDownloading(false)
    }
  }

  const fmt = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s % 60)).padStart(2, '0')}`

  return (
    <div className="flex items-center gap-2 min-w-0">
      <button
        onClick={togglePlay}
        disabled={loading}
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground hover:bg-primary/90 disabled:opacity-50 transition-colors"
      >
        {loading
          ? <Loader2 className="h-3.5 w-3.5 animate-spin" />
          : playing
            ? <Pause className="h-3.5 w-3.5" />
            : <Play className="h-3.5 w-3.5 ml-0.5" />}
      </button>

      {blobUrl && (
        <div className="flex items-center gap-1.5 flex-1 min-w-0">
          <span className="text-[10px] text-muted-foreground tabular-nums w-7 shrink-0">{fmt(progress)}</span>
          <input
            type="range" min={0} max={duration || 1} value={progress} step={0.1}
            onChange={e => { if (audioRef.current) audioRef.current.currentTime = e.target.value }}
            className="flex-1 h-1 accent-primary cursor-pointer min-w-0"
          />
          <span className="text-[10px] text-muted-foreground tabular-nums w-7 shrink-0 text-right">{fmt(duration)}</span>
        </div>
      )}

      <button
        onClick={handleDownload}
        disabled={downloading}
        title="Download"
        className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md hover:bg-muted text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
      >
        {downloading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
      </button>

      {blobUrl && (
        <audio
          ref={audioRef}
          src={blobUrl}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onEnded={() => { setPlaying(false); setProgress(0) }}
          onTimeUpdate={() => setProgress(audioRef.current?.currentTime ?? 0)}
          onLoadedMetadata={() => setDuration(audioRef.current?.duration ?? 0)}
          className="hidden"
        />
      )}
    </div>
  )
}

// ── Direction badge ───────────────────────────────────────────────────────────

function DirBadge({ direction }) {
  if (!direction) return <span className="text-muted-foreground text-xs">—</span>
  const map = {
    inbound:  { Icon: PhoneIncoming, cls: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400', label: 'In' },
    outbound: { Icon: PhoneOutgoing, cls: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',     label: 'Out' },
    local:    { Icon: Phone,         cls: 'bg-muted text-muted-foreground',                                        label: 'Local' },
  }
  const { Icon, cls, label } = map[direction.toLowerCase()] ?? { Icon: Phone, cls: 'bg-muted text-muted-foreground', label: direction }
  return (
    <span className={cn('inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-semibold', cls)}>
      <Icon className="h-2.5 w-2.5" />{label}
    </span>
  )
}

function fmtDur(s) {
  if (!s) return '—'
  const m = Math.floor(s / 60), sec = s % 60
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function CallRecordings() {
  const [search, setSearch]       = useState('')
  const [pageSize, setPageSize]   = useState(DEFAULT_PAGE_SIZE)
  const [syncing, setSyncing]     = useState(false)
  const debouncedSearch = useDebounce(search, 300)

  const params = useMemo(() => ({
    ...(debouncedSearch ? { search: debouncedSearch } : {}),
    ordering: '-call_recording_start_stamp',
  }), [debouncedSearch])

  const {
    rows, total: count, loading, loadingMore, hasMore, loadMore, reload,
  } = useInfiniteList(api.callRecordings, { params, pageSize })

  const handleSync = async () => {
    setSyncing(true)
    try {
      await api.syncCallRecordings()
      await reload()
    } finally {
      setSyncing(false)
    }
  }

  return (
    <div className="space-y-4">

      {/* Toolbar */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search by number…"
            className="pl-8 h-9"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        {!loading && (
          <span className="text-sm text-muted-foreground shrink-0">{count} recording{count !== 1 ? 's' : ''}</span>
        )}
        <PageSizeSelector value={pageSize} onChange={setPageSize} />
        <Button variant="outline" size="sm" onClick={handleSync} disabled={syncing}>
          {syncing ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
          <span className="ml-1.5">{syncing ? 'Syncing…' : 'Sync'}</span>
        </Button>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <div className="min-w-[560px]">
            <div className="grid grid-cols-[130px_1fr_1fr_56px_68px_minmax(160px,1fr)] gap-3 px-4 py-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground bg-muted/30 border-b">
              <span>Date</span><span>Caller</span><span>Destination</span><span>Dir</span><span>Duration</span><span>Player</span>
            </div>

            {loading ? (
              <div className="divide-y">
                {[...Array(8)].map((_, i) => (
                  <div key={i} className="grid grid-cols-[130px_1fr_1fr_56px_68px_minmax(160px,1fr)] gap-3 px-4 py-3 items-center">
                    {[...Array(6)].map((_, j) => <Skeleton key={j} className="h-4 w-full" />)}
                  </div>
                ))}
              </div>
            ) : rows.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-16 text-muted-foreground">
                <FileAudio className="h-10 w-10 opacity-20" />
                <p className="text-sm">{search ? 'No recordings match your search.' : 'No call recordings found.'}</p>
              </div>
            ) : (
              <div className="divide-y">
                {rows.map(r => (
                  <div key={r.call_recording_uuid}
                    className="grid grid-cols-[130px_1fr_1fr_56px_68px_minmax(160px,1fr)] gap-3 px-4 py-2.5 items-center hover:bg-muted/30 transition-colors">
                    <span className="text-xs text-muted-foreground tabular-nums">
                      {r.call_recording_start_stamp ? formatDate(r.call_recording_start_stamp) : '—'}
                    </span>
                    <div className="min-w-0">
                      <p className="font-mono text-sm truncate">{r.call_recording_caller_id_number || '—'}</p>
                      {r.call_recording_caller_id_name && (
                        <p className="text-[10px] text-muted-foreground truncate">{r.call_recording_caller_id_name}</p>
                      )}
                    </div>
                    <span className="font-mono text-sm truncate">{r.call_recording_destination_number || '—'}</span>
                    <span><DirBadge direction={r.direction} /></span>
                    <span className="text-xs tabular-nums">{fmtDur(r.call_recording_duration)}</span>
                    <AudioPlayer recordingId={r.call_recording_uuid} />
                  </div>
                ))}
              </div>
            )}
          </div>

          {!loading && rows.length > 0 && (
            <InfiniteScroll
              hasMore={hasMore}
              loadingMore={loadingMore}
              onLoadMore={loadMore}
              loaded={rows.length}
              total={count}
            />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
