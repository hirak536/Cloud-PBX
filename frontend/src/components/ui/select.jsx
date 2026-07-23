import { cn } from '@/lib/utils'
import { Check, ChevronDown } from 'lucide-react'
import { Children, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'

function parseOptions(children) {
  const options = []
  Children.forEach(children, child => {
    if (!child) return
    if (child.type === 'option') {
      options.push({ value: String(child.props.value ?? ''), label: child.props.children })
    } else if (child.type === 'optgroup') {
      Children.forEach(child.props.children, opt => {
        if (opt?.type === 'option') {
          options.push({ value: String(opt.props.value ?? ''), label: opt.props.children, group: child.props.label })
        }
      })
    }
  })
  return options
}

export function Select({ className, wrapperClassName, children, value, onChange, disabled, ...props }) {
  const [open, setOpen] = useState(false)
  const [dropUp, setDropUp] = useState(false)
  const [rect, setRect] = useState(null)
  const ref = useRef(null)
  const listRef = useRef(null)
  const menuRef = useRef(null)

  const options = parseOptions(children)
  const selected = options.find(o => String(o.value) === String(value ?? ''))

  // Close on outside click (account for the portalled menu living outside `ref`)
  useEffect(() => {
    if (!open) return
    const handler = (e) => {
      if (ref.current?.contains(e.target)) return
      if (menuRef.current?.contains(e.target)) return
      setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [open])

  // Track the trigger position so the portalled menu can align to it, and keep
  // it in sync while scrolling/resizing.
  useEffect(() => {
    if (!open) return
    const measure = () => {
      if (!ref.current) return
      const r = ref.current.getBoundingClientRect()
      setRect(r)
      setDropUp(r.bottom + 240 > window.innerHeight && r.top > 240)
    }
    measure()
    window.addEventListener('scroll', measure, true)
    window.addEventListener('resize', measure)
    return () => {
      window.removeEventListener('scroll', measure, true)
      window.removeEventListener('resize', measure)
    }
  }, [open])

  const handleOpen = () => {
    if (disabled) return
    setOpen(v => !v)
  }

  const handleSelect = (val) => {
    if (onChange) onChange({ target: { value: val } })
    setOpen(false)
  }

  // Keyboard navigation
  const handleKeyDown = (e) => {
    if (disabled) return
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); handleOpen() }
    if (e.key === 'Escape') setOpen(false)
    if (e.key === 'ArrowDown' && open) {
      e.preventDefault()
      const idx = options.findIndex(o => o.value === String(value ?? ''))
      const next = options[Math.min(idx + 1, options.length - 1)]
      if (next) handleSelect(next.value)
    }
    if (e.key === 'ArrowUp' && open) {
      e.preventDefault()
      const idx = options.findIndex(o => o.value === String(value ?? ''))
      const prev = options[Math.max(idx - 1, 0)]
      if (prev) handleSelect(prev.value)
    }
  }

  return (
    <div ref={ref} className={cn('relative', wrapperClassName ?? 'w-full')}>
      <button
        type="button"
        onClick={handleOpen}
        onKeyDown={handleKeyDown}
        disabled={disabled}
        className={cn(
          'flex h-9 w-full items-center justify-between gap-2 rounded-xl border border-input bg-background px-3 py-1 pr-8 text-sm shadow-sm text-left',
          'transition-all duration-150',
          'hover:border-primary/40',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 focus-visible:border-primary/60',
          'disabled:cursor-not-allowed disabled:opacity-50 disabled:bg-muted/30',
          open && 'border-primary/60 ring-2 ring-primary/40',
          className
        )}
        {...props}
      >
        <span className="truncate min-w-0">
          {selected ? selected.label : <span className="text-muted-foreground">—</span>}
        </span>
        <ChevronDown className={cn('pointer-events-none absolute right-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground transition-transform duration-150', open && 'rotate-180')} />
      </button>

      {open && rect && createPortal(
        <div
          ref={menuRef}
          style={{
            position: 'fixed',
            left: rect.left,
            width: rect.width,
            ...(dropUp
              ? { bottom: window.innerHeight - rect.top + 4 }
              : { top: rect.bottom + 4 }),
          }}
          className={cn(
            'z-[60] min-w-[8rem] overflow-auto rounded-xl border border-border/60 bg-card shadow-2xl shadow-black/10 animate-dropdown-in',
            'max-h-60 py-1',
          )}
        >
          {options.map((opt, i) => (
            <button
              key={i}
              type="button"
              onClick={() => handleSelect(opt.value)}
              className={cn(
                'flex w-full items-center gap-2 px-3 py-1.5 text-sm text-left transition-colors',
                'hover:bg-muted',
                String(opt.value) === String(value ?? '') && 'bg-primary/10 text-primary font-medium'
              )}
            >
              <span className="flex-1 truncate">{opt.label}</span>
              {String(opt.value) === String(value ?? '') && <Check className="h-3.5 w-3.5 shrink-0" />}
            </button>
          ))}
        </div>,
        document.body
      )}
    </div>
  )
}
