/**
 * ThemeSync — keeps <html class="dark"> in sync with Redux theme state.
 * Supports 'light', 'dark', and 'system' (follows OS preference).
 * Rendered once at the app root.
 */
import { useEffect } from 'react'
import { useSelector } from 'react-redux'
import { selectTheme } from '@/store'

export default function ThemeSync() {
  const theme = useSelector(selectTheme)

  useEffect(() => {
    const apply = (isDark) => document.documentElement.classList.toggle('dark', isDark)

    if (theme === 'system') {
      const mq = window.matchMedia('(prefers-color-scheme: dark)')
      apply(mq.matches)
      const handler = (e) => apply(e.matches)
      mq.addEventListener('change', handler)
      return () => mq.removeEventListener('change', handler)
    }

    apply(theme === 'dark')
  }, [theme])

  return null
}
