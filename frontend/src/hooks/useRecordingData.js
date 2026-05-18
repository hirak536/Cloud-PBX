import { useState, useRef, useCallback } from 'react'
import { recordings as recordingsApi } from '@/api'

/**
 * Lazy-loads tenant recordings once per component lifecycle.
 *
 * Usage:
 *   const { recordings, recLoading, loadRecordings } = useRecordingData()
 *   // call loadRecordings() when the dialog opens
 */
export function useRecordingData() {
  const loadedRef = useRef(false)
  const [recLoading, setRecLoading]   = useState(false)
  const [recordings, setRecordings]   = useState([])

  const loadRecordings = useCallback(async () => {
    if (loadedRef.current) return
    setRecLoading(true)
    try {
      const { data } = await recordingsApi.list({ page_size: 500 })
      setRecordings(Array.isArray(data) ? data : data.results || [])
      loadedRef.current = true
    } finally { setRecLoading(false) }
  }, [])

  return { recordings, recLoading, loadRecordings }
}
