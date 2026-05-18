/**
 * LiveProvider — manages the single global WebSocket connection.
 * Replaces useLiveStore.connect/disconnect from Zustand.
 * Dispatches liveSlice actions on every WS message.
 */
import { useEffect, useRef } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { selectAuth } from '@/store'
import {
  setWsConnected,
  setActiveCalls,
  setRegistrations,
  setSystemMetrics,
  setFsStatus,
  setDbStatus,
  setExtSnapshot,
  updateExtStatus,
} from '@/store/slices/liveSlice'

export default function LiveProvider() {
  const dispatch = useDispatch()
  const { isAuthenticated, accessToken } = useSelector(selectAuth)
  const wsRef = useRef(null)
  const timerRef = useRef(null)
  const destroyedRef = useRef(false)

  useEffect(() => {
    if (!isAuthenticated || !accessToken) {
      // Clean up if logged out
      if (wsRef.current) {
        try { wsRef.current.onclose = null; wsRef.current.close() } catch {}
        wsRef.current = null
      }
      clearTimeout(timerRef.current)
      dispatch(setWsConnected(false))
      return
    }

    destroyedRef.current = false

    function connect() {
      if (destroyedRef.current) return
      const proto = location.protocol === 'https:' ? 'wss' : 'ws'
      const ws = new WebSocket(`${proto}://${location.host}/ws/operator-panel/?token=${accessToken}`)
      wsRef.current = ws

      ws.onopen = () => {
        // console.log('[LiveProvider] WS connected')
        dispatch(setWsConnected(true))
      }

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
          // console.log('[LiveProvider] msg:', msg.type, msg)
          switch (msg.type) {
            case 'active_calls_update':
              dispatch(setActiveCalls(msg.calls || []))
              break
            case 'registrations_update':
              dispatch(setRegistrations(msg.registrations || []))
              break
            case 'system_metrics':
              dispatch(setSystemMetrics(msg.metrics || msg.data || null))
              break
            case 'freeswitch_status':
              dispatch(setFsStatus(msg.status || msg.data || null))
              break
            case 'db_status':
              dispatch(setDbStatus(msg.status || msg.data || null))
              break
            case 'extension_status_snapshot':
              dispatch(setExtSnapshot(msg.extensions || {}))
              break
            case 'extension_status_update':
              if (msg.extension) dispatch(updateExtStatus({ extension: msg.extension, status: msg.status }))
              break
          }
        } catch {}
      }

      ws.onclose = (e) => {
        // console.log('[LiveProvider] WS closed', e.code, e.reason)
        dispatch(setWsConnected(false))
        wsRef.current = null
        if (!destroyedRef.current) {
          timerRef.current = setTimeout(connect, 4000)
        }
      }

      ws.onerror = (e) => { console.error('[LiveProvider] WS error', e); ws.close() }
    }

    connect()

    return () => {
      destroyedRef.current = true
      clearTimeout(timerRef.current)
      if (wsRef.current) {
        try { wsRef.current.onclose = null; wsRef.current.close() } catch {}
        wsRef.current = null
      }
      dispatch(setWsConnected(false))
    }
  }, [isAuthenticated, accessToken])

  return null
}
