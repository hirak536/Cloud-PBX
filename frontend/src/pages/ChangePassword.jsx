import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDispatch, useSelector } from 'react-redux'
import { setUser } from '@/store/slices/authSlice'
import { selectAuth } from '@/store'
import { auth as authApi } from '@/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { KeyRound, Loader2, Eye, EyeOff, Check } from 'lucide-react'

const rules = [
  { label: 'Uppercase letter (A-Z)', test: (v) => /[A-Z]/.test(v) },
  { label: 'Lowercase letter (a-z)', test: (v) => /[a-z]/.test(v) },
  { label: 'Digit (0-9)',            test: (v) => /[0-9]/.test(v) },
  { label: 'Special character (!@#$…)', test: (v) => /[^A-Za-z0-9]/.test(v) },
  { label: 'At least 8 characters',  test: (v) => v.length >= 8 },
]

export default function ChangePassword() {
  const [form, setForm] = useState({ new_password: '', confirm_password: '' })
  const [showNew, setShowNew] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')
  const navigate = useNavigate()
  const dispatch = useDispatch()
  const { isAuthenticated } = useSelector(selectAuth)

  if (!isAuthenticated) {
    navigate('/login', { replace: true })
    return null
  }

  const f = (key) => (e) => setForm((p) => ({ ...p, [key]: e.target.value }))

  const allRulesPassed = rules.every((r) => r.test(form.new_password))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!allRulesPassed) {
      setError('Password does not meet the requirements below.')
      return
    }
    if (form.new_password !== form.confirm_password) {
      setError('Passwords do not match.')
      return
    }
    setLoading(true)
    setError('')
    try {
      await authApi.changePassword({
        new_password: form.new_password,
        confirm_password: form.confirm_password,
      })
      setSuccess('Password changed successfully. Redirecting…')
      // Refresh user data from backend so must_change_password becomes false
      const { data } = await authApi.me()
      dispatch(setUser(data))
      setTimeout(() => navigate('/', { replace: true }), 1200)
    } catch (err) {
      setError(err?.response?.data?.detail || 'Failed to change password.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex flex-col items-center gap-2">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-primary/10">
            <KeyRound className="h-6 w-6 text-primary" />
          </div>
          <h2 className="text-2xl font-bold">Set a new password</h2>
          <p className="text-sm text-muted-foreground text-center">
            Your account requires a password change before continuing.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="rounded-lg border border-destructive/30 bg-destructive/8 px-4 py-3 text-sm text-destructive">
              {error}
            </div>
          )}
          {success && (
            <div className="rounded-lg border border-primary/30 bg-primary/8 px-4 py-3 text-sm text-primary">
              {success}
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="new_password">New password</Label>
            <div className="relative">
              <Input
                id="new_password"
                type={showNew ? 'text' : 'password'}
                placeholder="At least 8 characters"
                autoComplete="new-password"
                value={form.new_password}
                onChange={f('new_password')}
                disabled={loading}
                className="pr-10"
              />
              <button type="button" tabIndex={-1}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                onClick={() => setShowNew(!showNew)}>
                {showNew ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="confirm_password">Confirm new password</Label>
            <div className="relative">
              <Input
                id="confirm_password"
                type={showConfirm ? 'text' : 'password'}
                placeholder="Repeat password"
                autoComplete="new-password"
                value={form.confirm_password}
                onChange={f('confirm_password')}
                disabled={loading}
                className="pr-10"
              />
              <button type="button" tabIndex={-1}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                onClick={() => setShowConfirm(!showConfirm)}>
                {showConfirm ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>
          </div>

          <Button type="submit" className="w-full h-10" disabled={loading || !allRulesPassed}>
            {loading
              ? <><Loader2 className="h-4 w-4 animate-spin" /> Saving…</>
              : 'Set new password'}
          </Button>

          <ul className="space-y-1 rounded-lg border border-border bg-muted/40 px-4 py-3">
            {rules.map((rule) => {
              const passed = rule.test(form.new_password)
              return (
                <li key={rule.label} className="flex items-center gap-2 text-xs">
                  <span className={`flex h-4 w-4 items-center justify-center rounded-full border ${passed ? 'border-green-500 bg-green-500' : 'border-muted-foreground/40 bg-transparent'}`}>
                    {passed && <Check className="h-2.5 w-2.5 text-white" strokeWidth={3} />}
                  </span>
                  <span className={passed ? 'text-green-600 dark:text-green-400' : 'text-muted-foreground'}>
                    {rule.label}
                  </span>
                </li>
              )
            })}
          </ul>
        </form>
      </div>
    </div>
  )
}
