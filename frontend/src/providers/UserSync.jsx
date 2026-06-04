/**
 * UserSync — keeps the logged-in user's record fresh.
 *
 * Re-fetches /auth/me on every in-app navigation (route change) while
 * authenticated, so role / allowed_pages / tenant / fax-access changes made by
 * an admin take effect without a logout/login cycle. A short throttle prevents
 * hammering the endpoint on rapid navigations.
 */
import { useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { selectAuth } from '@/store'
import { refreshUserThunk } from '@/store/slices/authSlice'

const THROTTLE_MS = 5000

export default function UserSync() {
  const dispatch = useDispatch()
  const { pathname } = useLocation()
  const { isAuthenticated } = useSelector(selectAuth)
  const lastRef = useRef(0)

  useEffect(() => {
    if (!isAuthenticated) return
    const now = Date.now()
    if (now - lastRef.current < THROTTLE_MS) return
    lastRef.current = now
    dispatch(refreshUserThunk())
  }, [pathname, isAuthenticated, dispatch])

  return null
}
