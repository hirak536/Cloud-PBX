import { useEffect, useRef } from 'react'
import { Loader2 } from 'lucide-react'
import { Select } from '@/components/ui/select'

export const PAGE_SIZE_OPTIONS = [25, 50, 100, 200]
export const DEFAULT_PAGE_SIZE = 50

/**
 * Page-size selector. Drop next to a list's header/toolbar.
 *   <PageSizeSelector value={pageSize} onChange={setPageSize} />
 */
export function PageSizeSelector({ value, onChange, options = PAGE_SIZE_OPTIONS, className }) {
  return (
    <div className={`flex items-center gap-2 text-sm text-muted-foreground ${className || ''}`}>
      <span>Show</span>
      <Select
        value={String(value)}
        onChange={(e) => onChange(Number(e.target.value))}
        wrapperClassName="w-20"
      >
        {options.map((n) => <option key={n} value={n}>{n}</option>)}
      </Select>
      <span>per page</span>
    </div>
  )
}

/**
 * Infinite-scroll sentinel + footer. Place at the END of a scrollable list.
 * Calls onLoadMore when the sentinel scrolls into view.
 *
 *   <InfiniteScroll
 *     hasMore={hasMore} loadingMore={loadingMore}
 *     onLoadMore={loadMore} loaded={rows.length} total={total}
 *   />
 *
 * @param {string} [root] optional CSS selector / ref for the scroll container
 *                        (defaults to the viewport). Pass `rootRef` for a
 *                        scrollable dialog/panel.
 */
export function InfiniteScroll({
  hasMore,
  loadingMore,
  onLoadMore,
  loaded,
  total,
  rootRef = null,
  className,
}) {
  const sentinelRef = useRef(null)

  useEffect(() => {
    const sentinel = sentinelRef.current
    if (!sentinel || !hasMore) return
    const observer = new IntersectionObserver(
      (entries) => { if (entries[0].isIntersecting) onLoadMore() },
      { root: rootRef?.current || null, rootMargin: '200px' }
    )
    observer.observe(sentinel)
    return () => observer.disconnect()
  }, [hasMore, onLoadMore, rootRef])

  return (
    <div className={className}>
      <div ref={sentinelRef} aria-hidden className="h-px w-full" />
      <div className="py-3 text-center text-xs text-muted-foreground">
        {loadingMore ? (
          <span className="inline-flex items-center gap-2">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading…
          </span>
        ) : hasMore ? (
          <span>Scroll to load more</span>
        ) : total != null ? (
          <span>{(total || 0).toLocaleString()} {total === 1 ? 'item' : 'items'}</span>
        ) : null}
      </div>
    </div>
  )
}
