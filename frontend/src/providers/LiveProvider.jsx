/**
 * LiveProvider — manages the single global WebSocket connection.
 * Replaces useLiveStore.connect/disconnect from Zustand.
 * Dispatches liveSlice actions on every WS message.
 */
import { useEffect, useRef } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { selectAuth } from '@/store'
import { selectTenant } from '@/store'
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
  const { currentTenant } = useSelector(selectTenant)
  const wsRef = useRef(null)
  const timerRef = useRef(null)

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

    // Each effect run gets its own "alive" flag so onclose callbacks from a
    // previous run never schedule reconnects into the new run's closure.
    let alive = true

    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    const tenantParam = currentTenant?.tenant_uuid ? `&tenant=${currentTenant.tenant_uuid}` : ''

    function connect() {
      if (!alive) return
      const ws = new WebSocket(`${proto}://${location.host}/ws/operator-panel/?token=${accessToken}${tenantParam}`)
      wsRef.current = ws

      ws.onopen = () => {
        dispatch(setWsConnected(true))
      }

      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data)
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

      ws.onclose = () => {
        dispatch(setWsConnected(false))
        wsRef.current = null
        if (alive) {
          timerRef.current = setTimeout(connect, 4000)
        }
      }

      ws.onerror = (e) => { console.error('[LiveProvider] WS error', e); ws.close() }
    }

    connect()

    return () => {
      alive = false
      clearTimeout(timerRef.current)
      if (wsRef.current) {
        try { wsRef.current.onclose = null; wsRef.current.close() } catch {}
        wsRef.current = null
      }
      dispatch(setWsConnected(false))
    }
  }, [isAuthenticated, accessToken, currentTenant?.tenant_uuid])

  return null
}
