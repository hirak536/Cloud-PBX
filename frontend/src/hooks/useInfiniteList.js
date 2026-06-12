import { useCallback, useEffect, useRef, useState } from 'react'

/**
 * Standard infinite-scroll list loader for DRF-paginated endpoints.
 *
 * Replaces per-page Prev/Next pagination across the app: fetches page 1, then
 * appends subsequent pages as the user scrolls (driven by <InfiniteScroll/>).
 * Supports a user-selectable page size.
 *
 * @param {(params) => Promise<{data}>} fetcher  API call, receives {page, page_size, ...params}.
 * @param {object}  options
 * @param {object}  options.params       Extra query params (filters/search). Changing these resets to page 1.
 * @param {number}  options.pageSize     Rows per page. Changing it resets to page 1.
 * @param {boolean} options.enabled      When false, skips loading (e.g. closed dialog). Default true.
 * @param {(data)=>Array} options.selectResults  Pull the array out of the response. Default: data.results || data.
 * @param {(data)=>number} options.selectCount    Pull the total count. Default: data.count || results.length.
 *
 * @returns {{rows, total, loading, loadingMore, hasMore, error, loadMore, reload, setRows}}
 */
export function useInfiniteList(fetcher, {
  params = {},
  pageSize = 50,
  enabled = true,
  selectResults = (d) => (Array.isArray(d) ? d : d.results || []),
  selectCount = (d, list) => (Array.isArray(d) ? list.length : d.count ?? list.length),
} = {}) {
  const [rows, setRows] = useState([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)        // initial / reset load
  const [loadingMore, setLoadingMore] = useState(false) // appending a page
  const [hasMore, setHasMore] = useState(false)
  const [error, setError] = useState(null)

  const pageRef = useRef(1)
  const loadingRef = useRef(false)
  // Serialize params so changing filters reliably triggers a reset.
  const paramsKey = JSON.stringify(params)

  const fetchPage = useCallback(async (pg) => {
    const { data } = await fetcher({ page: pg, page_size: pageSize, ...params })
    const list = selectResults(data)
    const count = selectCount(data, list)
    return { list, count }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fetcher, pageSize, paramsKey])

  const reload = useCallback(async () => {
    if (!enabled) return
    loadingRef.current = true
    setLoading(true)
    setError(null)
    try {
      const { list, count } = await fetchPage(1)
      setRows(list)
      setTotal(count)
      setHasMore(list.length === pageSize && list.length < count)
      pageRef.current = 2
    } catch (e) {
      setError(e)
      setRows([])
      setTotal(0)
      setHasMore(false)
    } finally {
      setLoading(false)
      loadingRef.current = false
    }
  }, [enabled, fetchPage, pageSize])

  const loadMore = useCallback(async () => {
    if (loadingRef.current || !hasMore || !enabled) return
    loadingRef.current = true
    setLoadingMore(true)
    try {
      const { list, count } = await fetchPage(pageRef.current)
      setRows((prev) => {
        const next = [...prev, ...list]
        setHasMore(list.length === pageSize && next.length < count)
        return next
      })
      setTotal(count)
      pageRef.current += 1
    } catch (e) {
      setError(e)
    } finally {
      setLoadingMore(false)
      loadingRef.current = false
    }
  }, [hasMore, enabled, fetchPage, pageSize])

  // Reset & reload whenever params, page size, or enabled change.
  useEffect(() => {
    if (enabled) reload()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsKey, pageSize, enabled])

  return { rows, total, loading, loadingMore, hasMore, error, loadMore, reload, setRows }
}
