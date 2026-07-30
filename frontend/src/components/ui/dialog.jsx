import { useEffect } from 'react'
import { X } from 'lucide-react'
import { cn } from '@/lib/utils'

export function Dialog({ open, onOpenChange, children }) {
  useEffect(() => {
    const handleKey = (e) => {
      if (e.key === 'Escape' && open) onOpenChange?.(false)
    }
    document.addEventListener('keydown', handleKey)
    return () => document.removeEventListener('keydown', handleKey)
  }, [open, onOpenChange])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Backdrop is intentionally NOT click-to-close: an accidental click outside
          would discard whatever the user had typed in the form. Dismissal is
          explicit only — the X button, a Cancel button, or the Escape key. */}
      <div className="fixed inset-0 bg-black/60 backdrop-blur-sm animate-overlay-in" />
      {children}
    </div>
  )
}

export function DialogContent({ className, children, ...props }) {
  return (
    <div
      className={cn(
        'relative z-50 w-full max-w-lg rounded-2xl border bg-card shadow-2xl shadow-black/20 animate-dialog-in',
        className
      )}
      {...props}
    >
      {children}
    </div>
  )
}

export function DialogHeader({ className, ...props }) {
  return (
    <div
      className={cn('flex flex-col space-y-1 px-6 pt-6 pb-4 border-b border-border/60', className)}
      {...props}
    />
  )
}

export function DialogFooter({ className, ...props }) {
  return (
    <div
      className={cn('flex flex-col-reverse sm:flex-row sm:justify-end gap-2 px-6 py-4 border-t border-border/60 bg-muted/30 rounded-b-2xl', className)}
      {...props}
    />
  )
}

export function DialogTitle({ className, ...props }) {
  return <h2 className={cn('text-lg font-semibold leading-none tracking-tight', className)} {...props} />
}

export function DialogDescription({ className, ...props }) {
  return <p className={cn('text-sm text-muted-foreground', className)} {...props} />
}

export function DialogClose({ onClose }) {
  return (
    <button
      onClick={onClose}
      className="absolute right-4 top-4 rounded-lg p-1.5 opacity-60 transition-all hover:opacity-100 hover:bg-muted focus:outline-none focus:ring-2 focus:ring-ring"
    >
      <X className="h-4 w-4" />
    </button>
  )
}
