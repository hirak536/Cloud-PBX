import { useEffect, useRef } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { toast } from 'sonner'
import { selectAuth } from '@/store'
import { logoutThunk } from '@/store/slices/authSlice'
import { broadcastLogout } from '@/api'

const IDLE_TIMEOUT_MS = 15 * 60 * 1000
const WARNING_MS = 60 * 1000
const ACTIVITY_KEY = 'auth:last-activity'
const ACTIVITY_THROTTLE_MS = 2000
const CHECK_INTERVAL_MS = 5000

const ACTIVITY_EVENTS = ['mousedown', 'mousemove', 'keydown', 'wheel', 'touchstart', 'scroll', 'click']

export default function IdleLogout() {
  const dispatch = useDispatch()
  const { isAuthenticated } = useSelector(selectAuth)
  const warnedRef = useRef(false)
  const lastWriteRef = useRef(0)

  useEffect(() => {
    if (!isAuthenticated) return

    const now = Date.now()
    try { localStorage.setItem(ACTIVITY_KEY, String(now)) } catch {}
    lastWriteRef.current = now
    warnedRef.current = false

    const markActivity = () => {
      const t = Date.now()
      if (t - lastWriteRef.current < ACTIVITY_THROTTLE_MS) return
      lastWriteRef.current = t
      try { localStorage.setItem(ACTIVITY_KEY, String(t)) } catch {}
      if (warnedRef.current) {
        warnedRef.current = false
        toast.dismiss('idle-warning')
      }
    }

    const onStorage = (e) => {
      // Another tab updated activity — reset our warning state
      if (e.key === ACTIVITY_KEY && warnedRef.current) {
        warnedRef.current = false
        toast.dismiss('idle-warning')
      }
    }

    ACTIVITY_EVENTS.forEach((ev) => window.addEventListener(ev, markActivity, { passive: true }))
    window.addEventListener('storage', onStorage)

    const interval = setInterval(() => {
      let last = lastWriteRef.current
      try {
        const raw = localStorage.getItem(ACTIVITY_KEY)
        const parsed = parseInt(raw, 10)
        if (!Number.isNaN(parsed)) last = Math.max(last, parsed)
      } catch {}
      const idle = Date.now() - last

      if (idle >= IDLE_TIMEOUT_MS) {
        toast.dismiss('idle-warning')
        toast.info('Logged out due to 15 minutes of inactivity')
        broadcastLogout()
        dispatch(logoutThunk())
      } else if (idle >= IDLE_TIMEOUT_MS - WARNING_MS && !warnedRef.current) {
        warnedRef.current = true
        toast.warning('You will be logged out in 1 minute due to inactivity', {
          id: 'idle-warning',
          duration: WARNING_MS,
        })
      }
    }, CHECK_INTERVAL_MS)

    return () => {
      ACTIVITY_EVENTS.forEach((ev) => window.removeEventListener(ev, markActivity))
      window.removeEventListener('storage', onStorage)
      clearInterval(interval)
      toast.dismiss('idle-warning')
    }
  }, [isAuthenticated, dispatch])

  return null
}
