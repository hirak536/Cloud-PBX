import { useEffect, useState, useRef } from 'react'
import { Search, Loader2, X, ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

/**
 * ExtensionPicker
 * Props:
 *   value      - extension_uuid string
 *   onChange   - (extension_uuid) => void
 *   extensions - array from API
 *   loading    - bool
 *   placeholder - string
 */
export default function ExtensionPicker({
  value,
  onChange,
  extensions = [],
  loading = false,
  placeholder = 'Choose an extension…',
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
        ) : selected ? (
          <span className="flex items-center gap-2 min-w-0">
            <span className="font-mono font-bold text-blue-500 shrink-0">{selected.extension}</span>
            <span className="text-sm text-muted-foreground truncate">
              {selected.effective_caller_id_name || selected.description || ''}
            </span>
          </span>
        ) : (
          <span className="text-muted-foreground text-sm">{placeholder}</span>
        )}
        <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
      </button>

      {open && (
        <div className={cn("absolute z-50 w-full rounded-xl border border-border/60 bg-card shadow-2xl shadow-black/10 animate-dropdown-in", dropUp ? "bottom-full mb-1" : "mt-1")}>
          <div className="flex items-center gap-2 border-b px-3 py-2">
            <Search className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <input
              ref={inputRef}
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="Search extensions…"
              className="flex-1 text-sm bg-transparent outline-none placeholder:text-muted-foreground"
            />
            {query && (
              <button type="button" onClick={() => setQuery('')}>
                <X className="h-3 w-3 text-muted-foreground" />
              </button>
            )}
          </div>
          <div className="max-h-48 overflow-y-auto p-1">
            {filtered.length === 0 ? (
              <p className="px-3 py-3 text-sm text-muted-foreground text-center">No extensions found</p>
            ) : (
              filtered.map(e => (
                <button
                  key={e.extension_uuid}
                  type="button"
                  onClick={() => { onChange(e.extension_uuid); setOpen(false); setQuery('') }}
                  className={cn(
                    'w-full flex items-center gap-3 mx-1 px-3 py-2 rounded-lg hover:bg-muted text-left transition-colors text-sm',
                    value === e.extension_uuid && 'bg-muted',
                  )}
                >
                  <span className="font-mono font-bold text-blue-500 w-12 shrink-0">{e.extension}</span>
                  <span className="text-sm text-muted-foreground truncate">
                    {e.effective_caller_id_name || e.description || ''}
                  </span>
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
