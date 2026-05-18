import { useEffect, useState } from 'react'
import { tenants as tenantsApi, gateways as gatewaysApi } from '@/api'
import { useSelector } from 'react-redux'
import { selectTenant } from '@/store'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select } from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Loader2, Save, Mic, Building2, Bell, PhoneOutgoing,
  Printer, BarChart2, Shield, CheckCircle2, AlertCircle,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// Common timezones
const TIMEZONES = [
  'UTC',
  'America/New_York','America/Chicago','America/Denver','America/Los_Angeles',
  'America/Phoenix','America/Anchorage','America/Honolulu','America/Toronto',
  'America/Vancouver','America/Mexico_City','America/Bogota','America/Lima',
  'America/Sao_Paulo','America/Argentina/Buenos_Aires',
  'Europe/London','Europe/Dublin','Europe/Lisbon','Europe/Paris','Europe/Berlin',
  'Europe/Amsterdam','Europe/Brussels','Europe/Madrid','Europe/Rome',
  'Europe/Warsaw','Europe/Stockholm','Europe/Helsinki','Europe/Athens',
  'Europe/Istanbul','Europe/Moscow',
  'Africa/Cairo','Africa/Johannesburg','Africa/Lagos','Africa/Nairobi',
  'Asia/Dubai','Asia/Karachi','Asia/Kolkata','Asia/Dhaka','Asia/Bangkok',
  'Asia/Singapore','Asia/Shanghai','Asia/Tokyo','Asia/Seoul','Asia/Hong_Kong',
  'Asia/Jakarta','Asia/Taipei',
  'Australia/Sydney','Australia/Melbourne','Australia/Brisbane','Australia/Perth',
  'Pacific/Auckland','Pacific/Fiji',
]

// ── Reusable field wrapper ────────────────────────────────────────────────────
function Field({ label, hint, children, className }) {
  return (
    <div className={cn('space-y-1.5', className)}>
      {label && <Label className="text-sm font-medium">{label}</Label>}
      {children}
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
    </div>
  )
}

// ── Section card ─────────────────────────────────────────────────────────────
function Section({ icon: Icon, title, children }) {
  return (
    <div className="rounded-xl border bg-card shadow-sm overflow-hidden">
      <div className="flex items-center gap-2.5 px-5 py-3.5 border-b bg-muted/30">
        {Icon && <Icon className="h-4 w-4 text-primary" />}
        <h3 className="text-sm font-semibold tracking-wide">{title}</h3>
      </div>
      <div className="px-5 py-4 space-y-4">{children}</div>
    </div>
  )
}

// ── Toggle switch ─────────────────────────────────────────────────────────────
function Toggle({ checked, onChange, label, description }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div className="space-y-0.5 flex-1">
        {label && <p className="text-sm font-medium">{label}</p>}
        {description && <p className="text-xs text-muted-foreground leading-relaxed">{description}</p>}
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={onChange}
        className={cn(
          'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors mt-0.5',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          checked ? 'bg-primary' : 'bg-muted-foreground/25',
        )}
      >
        <span className={cn(
          'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow-lg ring-0 transition-transform',
          checked ? 'translate-x-5' : 'translate-x-0',
        )} />
      </button>
    </div>
  )
}

export default function Tenants() {
  const { currentTenant } = useSelector(selectTenant)
  const [form, setForm] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')
  const [gateways, setGateways] = useState([])
  const [applyingRecording, setApplyingRecording] = useState(false)
  const [applyRecordingMsg, setApplyRecordingMsg] = useState('')

  useEffect(() => {
    if (!currentTenant?.tenant_uuid) return
    setLoading(true)
    setError('')
    Promise.all([
      tenantsApi.get(currentTenant.tenant_uuid),
      gatewaysApi.list().catch(() => ({ data: [] })),
    ]).then(([{ data: d }, { data: gw }]) => {
      setGateways(Array.isArray(gw) ? gw : gw.results || [])
      setForm({
        tenant_name:               d.tenant_name || '',
        tenant_code:               d.tenant_code || '',
        timezone:                  d.timezone || 'UTC',
        voicemail_timeout:         d.voicemail_timeout ?? 120,
        max_channels:              d.max_channels ?? '',
        max_extensions:            d.max_extensions ?? '',
        recording_enabled:         d.recording_enabled !== false,
        fax_gateway:               d.fax_gateway || '',
        default_gateway:           d.default_gateway || '',
        default_gateway_priority:  d.default_gateway_priority ?? 10,
        push_notifications_enabled: d.push_notifications_enabled || false,
        offline_poll_timeout:      d.offline_poll_timeout ?? 30,
      })
    }).catch(() => setError('Failed to load tenant settings.'))
      .finally(() => setLoading(false))
  }, [currentTenant?.tenant_uuid])

  const set = (key) => (e) => setForm(p => ({ ...p, [key]: e.target.value }))
  const tog = (key) => () => setForm(p => ({ ...p, [key]: !p[key] }))

  const handleSave = async () => {
    const timeout = parseInt(form.voicemail_timeout, 10)
    if (isNaN(timeout) || timeout < 10 || timeout > 3600) {
      setError('Voicemail timeout must be between 10 and 3600 seconds.')
      return
    }
    setSaving(true); setError(''); setSaved(false)
    try {
      await tenantsApi.update(currentTenant.tenant_uuid, {
        ...form,
        voicemail_timeout:        timeout,
        max_channels:             form.max_channels !== '' ? parseInt(form.max_channels, 10) : null,
        max_extensions:           form.max_extensions !== '' ? parseInt(form.max_extensions, 10) : null,
        fax_gateway:              form.fax_gateway || null,
        default_gateway:          form.default_gateway || null,
        default_gateway_priority: parseInt(form.default_gateway_priority, 10) || 10,
        offline_poll_timeout:     parseInt(form.offline_poll_timeout, 10) || 30,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 3000)
    } catch (err) {
      const d = err?.response?.data
      setError(typeof d === 'string' ? d : Object.values(d || {}).flat().join(' ') || 'Save failed.')
    } finally { setSaving(false) }
  }

  const handleApplyRecording = async () => {
    setApplyingRecording(true)
    setApplyRecordingMsg('')
    try {
      const { data } = await tenantsApi.applyRecording(currentTenant.tenant_uuid)
      setApplyRecordingMsg(data.detail || 'Done.')
      setTimeout(() => setApplyRecordingMsg(''), 4000)
    } catch {
      setApplyRecordingMsg('Failed to apply recording setting.')
    } finally {
      setApplyingRecording(false)
    }
  }

  if (!currentTenant) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center gap-3">
        <Building2 className="h-10 w-10 text-muted-foreground/40" />
        <p className="text-sm text-muted-foreground">No tenant selected. Use the tenant switcher in the sidebar.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">

      {/* ── Page header ── */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Tenant Settings</h2>
          <p className="text-sm text-muted-foreground mt-0.5">{currentTenant.tenant_name}</p>
        </div>
        <Button onClick={handleSave} disabled={saving || loading || !form} className="shrink-0">
          {saving
            ? <Loader2 className="h-4 w-4 animate-spin" />
            : saved
            ? <CheckCircle2 className="h-4 w-4 text-green-400" />
            : <Save className="h-4 w-4" />}
          {saved ? 'Saved!' : 'Save Settings'}
        </Button>
      </div>

      {/* ── Error banner ── */}
      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
          <span>{error}</span>
        </div>
      )}

      {loading || !form ? (
        <div className="space-y-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="rounded-xl border bg-card shadow-sm p-5 space-y-3">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-9 w-full" />
              <Skeleton className="h-9 w-full" />
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-4">

          {/* ── Row 1: General + Limits ── */}
          <div className="grid grid-cols-2 gap-4">

            <Section icon={Building2} title="General">
              <div className="grid grid-cols-2 gap-3">
                <Field label="Tenant Name" className="col-span-2">
                  <Input value={form.tenant_name} onChange={set('tenant_name')} />
                </Field>
                <Field label="Tenant Code" hint="Used in SIP usernames">
                  <Input value={form.tenant_code} onChange={set('tenant_code')} className="font-mono" />
                </Field>
                <Field label="Timezone">
                  <Select value={form.timezone} onChange={set('timezone')}>
                    {TIMEZONES.map(tz => (
                      <option key={tz} value={tz}>{tz}</option>
                    ))}
                  </Select>
                </Field>
              </div>
            </Section>

            <div className="space-y-4">
              <Section icon={Shield} title="Limits">
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Max Channels" hint="Blank = unlimited">
                    <Input type="number" placeholder="Unlimited" value={form.max_channels} onChange={set('max_channels')} />
                  </Field>
                  <Field label="Max Extensions" hint="Blank = unlimited">
                    <Input type="number" placeholder="Unlimited" value={form.max_extensions} onChange={set('max_extensions')} />
                  </Field>
                </div>
              </Section>

              <Section icon={BarChart2} title="Voicemail">
                <Field label="Max Recording Length" hint="Default: 120 s (2 min)">
                  <div className="flex items-center gap-2">
                    <Input type="number" min={10} max={3600} value={form.voicemail_timeout} onChange={set('voicemail_timeout')} className="max-w-[110px]" />
                    <span className="text-sm text-muted-foreground">seconds</span>
                  </div>
                </Field>
              </Section>
            </div>
          </div>

          {/* ── Row 2: Recording + Push Notifications ── */}
          <div className="grid grid-cols-2 gap-4">

            <Section icon={Mic} title="Call Recording">
              <Toggle
                checked={form.recording_enabled}
                onChange={tog('recording_enabled')}
                label="Record All Calls"
                description="Automatically record every inbound and outbound call for this tenant."
              />
              {form.recording_enabled && (
                <div className="rounded-lg border border-amber-200 bg-amber-50 dark:bg-amber-900/20 dark:border-amber-800 px-3 py-2 text-xs text-amber-800 dark:text-amber-300 flex items-start gap-2">
                  <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
                  <span>Consumes significant disk space. Ensure <code className="font-mono">RECORDINGS_BASE_PATH</code> is configured.</span>
                </div>
              )}
              <div className="flex items-center gap-2 pt-1 border-t">
                <Button variant="outline" size="sm" onClick={handleApplyRecording} disabled={applyingRecording}>
                  {applyingRecording ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Mic className="h-3.5 w-3.5" />}
                  Apply to all extensions
                </Button>
                {applyRecordingMsg && (
                  <span className={cn('text-xs font-medium',
                    applyRecordingMsg.toLowerCase().includes('fail') ? 'text-destructive' : 'text-green-600'
                  )}>{applyRecordingMsg}</span>
                )}
              </div>
            </Section>

            <Section icon={Bell} title="Mobile Push Notifications">
              <Toggle
                checked={form.push_notifications_enabled}
                onChange={tog('push_notifications_enabled')}
                label="Enable Push Notifications"
                description="Offline extensions will park with ringback and send a push webhook so the mobile app can wake up and register."
              />
              {form.push_notifications_enabled && (
                <Field label="Offline Wait Timeout" hint="How long to wait before forwarding. Default: 30 s.">
                  <div className="flex items-center gap-2">
                    <Input type="number" min={1} max={120} value={form.offline_poll_timeout} onChange={set('offline_poll_timeout')} className="max-w-[110px]" />
                    <span className="text-sm text-muted-foreground">seconds</span>
                  </div>
                </Field>
              )}
            </Section>
          </div>

          {/* ── Row 3: Outbound Gateway + Fax ── */}
          <div className="grid grid-cols-2 gap-4">

            <Section icon={PhoneOutgoing} title="Default Outbound Gateway">
              <div className="grid grid-cols-2 gap-3">
                <Field label="Gateway" hint="Used for outbound calls tenant-wide." className="col-span-2">
                  <Select value={form.default_gateway || ''} onChange={e => setForm(p => ({ ...p, default_gateway: e.target.value }))}>
                    <option value="">None (FreeSWITCH default)</option>
                    {gateways.map(g => <option key={g.gateway_uuid} value={g.gateway_uuid}>{g.gateway}</option>)}
                  </Select>
                </Field>
                <Field label="Priority" hint="Lower = higher priority">
                  <Input type="number" min={1} max={100} value={form.default_gateway_priority} onChange={set('default_gateway_priority')} />
                </Field>
              </div>
            </Section>

            <Section icon={Printer} title="Fax">
              <Field label="Default Fax Gateway" hint="Gateway for outbound fax. Applies tenant-wide.">
                <Select value={form.fax_gateway || ''} onChange={e => setForm(p => ({ ...p, fax_gateway: e.target.value }))}>
                  <option value="">None (use FreeSWITCH default)</option>
                  {gateways.map(g => <option key={g.gateway_uuid} value={g.gateway_uuid}>{g.gateway}</option>)}
                </Select>
              </Field>
            </Section>
          </div>

          {/* ── Save footer ── */}
          <div className="flex items-center justify-end gap-3 pt-1 pb-2">
            {saved && (
              <span className="flex items-center gap-1.5 text-sm text-green-600 font-medium">
                <CheckCircle2 className="h-4 w-4" /> Saved
              </span>
            )}
            <Button onClick={handleSave} disabled={saving}>
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
              Save Settings
            </Button>
          </div>

        </div>
      )}
    </div>
  )
}
