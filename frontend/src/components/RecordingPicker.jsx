import { useEffect, useState, useRef } from 'react'
import { Search, Loader2, X, ChevronDown, Music } from 'lucide-react'
import { cn } from '@/lib/utils'
import { recordings as recordingsApi } from '@/api'
import AudioPlayer from '@/components/AudioPlayer'

/**
 * RecordingPicker
 * Props:
 *   value      - recording_filename string
 *   onChange   - (recording_filename) => void
 *   recordings - array from API
 *   loading    - bool
 *   placeholder - string
 */
export default function RecordingPicker({
  value,
  onChange,
  recordings = [],
  loading = false,
  placeholder = 'Select recording…',
}) {
  const [open, setOpen]     = useState(false)
  const [dropUp, setDropUp] = useState(false)
  const [query, setQuery]   = useState('')
  const containerRef        = useRef(null)
  const inputRef            = useRef(null)

  const toggleOpen = () => {
    if (!open && containerRef.current) {
      const rect = containerRef.current.getBoundingClientRect()
      setDropUp(rect.bottom + 320 > window.innerHeight)
    }
    setOpen(o => !o)
  }

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
  const filtered = !q ? recordings : recordings.filter(r =>
    r.recording_name.toLowerCase().includes(q) ||
    r.recording_filename.toLowerCase().includes(q)
  )

  const selectedRec  = recordings.find(r => r.recording_filename === value)
  const displayName  = selectedRec?.recording_name || (value ? value : null)

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={toggleOpen}
        className={cn(
          'flex h-9 w-full items-center justify-between gap-2 rounded-xl border border-input bg-background px-3 py-1 text-sm shadow-sm',
          'hover:border-ring/60 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring transition-colors',
        )}
      >
        {loading ? (
          <span className="flex items-center gap-2 text-muted-foreground text-xs">
            <Loader2 className="h-3 w-3 animate-spin" /> Loading…
          </span>
        ) : displayName ? (
          <span className="flex items-center gap-2 min-w-0">
            <Music className="h-3.5 w-3.5 shrink-0 text-indigo-500" />
            <span className="truncate text-sm">{displayName}</span>
          </span>
        ) : (
          <span className="text-muted-foreground text-sm">{placeholder}</span>
        )}
        <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      </button>

      {open && (
        <div className={cn("absolute z-50 w-full min-w-[280px] rounded-xl border border-border/60 bg-card shadow-2xl shadow-black/10 animate-dropdown-in", dropUp ? "bottom-full mb-1" : "mt-1")}>
          <div className="flex items-center gap-2 border-b px-3 py-2">
            <Search className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <input
              ref={inputRef}
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search recordings…"
              className="flex-1 text-sm bg-transparent outline-none placeholder:text-muted-foreground"
            />
            {query && (
              <button type="button" onClick={() => setQuery('')}>
                <X className="h-3 w-3 text-muted-foreground" />
              </button>
            )}
          </div>
          <div className="max-h-52 overflow-y-auto py-1">
            {loading ? (
              <div className="flex items-center justify-center py-4 gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading recordings…
              </div>
            ) : filtered.length === 0 ? (
              <p className="px-3 py-4 text-sm text-muted-foreground text-center">
                {q ? `No results for "${query}"` : 'No recordings found'}
              </p>
            ) : (
              filtered.map(r => (
                <div
                  key={r.recording_uuid}
                  className={cn(
                    'flex flex-col mx-1 px-3 py-2 rounded-lg hover:bg-muted transition-colors',
                    value === r.recording_filename && 'bg-muted',
                  )}
                >
                  <button
                    type="button"
                    onClick={() => { onChange(r.recording_filename); setOpen(false); setQuery('') }}
                    className="flex items-center gap-3 text-left w-full mb-1"
                  >
                    <Music className="h-3.5 w-3.5 shrink-0 text-indigo-500" />
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{r.recording_name}</p>
                      <p className="text-xs text-muted-foreground truncate font-mono">{r.recording_filename}</p>
                    </div>
                  </button>
                  <div onClick={e => e.stopPropagation()}>
                    <AudioPlayer fetchAudio={() => recordingsApi.streamMediaFile(r.recording_uuid)} />
                  </div>
                </div>
              ))
            )}
            {value && (
              <div className="border-t mt-1 pt-1">
                <button
                  type="button"
                  onClick={() => { onChange(''); setOpen(false) }}
                  className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-muted text-left transition-colors"
                >
                  <X className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                  <span className="text-sm text-muted-foreground">Clear</span>
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
