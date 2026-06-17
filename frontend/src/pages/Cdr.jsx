import { useDebounce } from '@/hooks/useDebounce'
import { useInfiniteList } from '@/hooks/useInfiniteList'
import { InfiniteScroll, PageSizeSelector, DEFAULT_PAGE_SIZE } from '@/components/InfiniteScroll'
import { useEffect, useMemo, useState, useCallback } from 'react'
import { cdr as cdrApi, voicemails as voicemailsApi, ivrMenus as ivrMenusApi, ringGroups as ringGroupsApi, workingHours as workingHoursApi } from '@/api'
import { useSelector } from 'react-redux'
import { selectAuth } from '@/store'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import { formatDuration, formatDate } from '@/lib/utils'
import { Select } from '@/components/ui/select'
import {
  Search, ChevronDown, ChevronRight, ChevronUp, Download,
  Phone, PhoneIncoming, PhoneOutgoing,
  Voicemail, GitBranch, Clock, Mic,
  PhoneCall, PhoneMissed, PhoneOff,
  Network, FileDown, Info,
} from 'lucide-react'

// ─── Leg grouping ─────────────────────────────────────────────────────────────
// A-leg: leg === 'a', B-legs match where B.bridge_uuid === A.call_uuid
// When multiple B-legs exist (forked dial to multiple registered devices),
// each B-leg gets its own row in the table so declined/answered devices are visible separately.
function groupLegs(list) {
  const used = new Set()
  const groups = []

  for (const row of list) {
    if (used.has(row.xml_cdr_uuid)) continue
    if (row.leg === 'b') continue
    const bLegs = row.call_uuid
      ? list.filter((r) => r.leg === 'b' && r.bridge_uuid === row.call_uuid && !used.has(r.xml_cdr_uuid))
      : []
    used.add(row.xml_cdr_uuid)
    bLegs.forEach((b) => used.add(b.xml_cdr_uuid))

    if (bLegs.length === 0) {
      groups.push({ aLeg: row, bLeg: null, bLegs: [] })
    } else {
      // One row per B-leg so each device (answered/declined) appears separately
      for (const b of bLegs) {
        groups.push({ aLeg: row, bLeg: b, bLegs: [b] })
      }
    }
  }

  // Unmatched B-legs shown as standalone
  for (const row of list) {
    if (!used.has(row.xml_cdr_uuid)) {
      groups.push({ aLeg: row, bLeg: null, bLegs: [] })
    }
  }
  return groups
}

// ─── Badges ───────────────────────────────────────────────────────────────────
function HangupBadge({ cause }) {
  if (!cause) return <Badge variant="secondary">—</Badge>
  if (cause === 'NORMAL_CLEARING') return <Badge variant="success">Answered</Badge>
  if (cause === 'NO_ANSWER') return <Badge variant="warning">No Answer</Badge>
  if (cause === 'USER_BUSY') return <Badge variant="warning">Busy</Badge>
  if (cause === 'ORIGINATOR_CANCEL') return <Badge variant="secondary">Cancelled</Badge>
  if (cause === 'USER_NOT_REGISTERED') return <Badge variant="warning">Offline</Badge>
  return <Badge variant="secondary">{cause.replace(/_/g, ' ')}</Badge>
}

function StatusBadge({ status }) {
  if (!status) return <Badge variant="secondary">—</Badge>
  if (status === 'ANSWERED') return <Badge variant="success">Answered</Badge>
  if (status === 'MISSED') return <Badge variant="destructive">Missed</Badge>
  if (status === 'NO_ANSWER') return <Badge variant="warning">No Answer</Badge>
  if (status === 'BUSY') return <Badge variant="warning">Busy</Badge>
  if (status === 'WENT_TO_VOICEMAIL') return <Badge variant="outline" className="text-orange-500 border-orange-300">Voicemail</Badge>
  if (status === 'FAILED') return <Badge variant="destructive">Failed</Badge>
  if (status === 'CONGESTION') return <Badge variant="warning">Congestion</Badge>
  return <Badge variant="secondary">{status.replace(/_/g, ' ')}</Badge>
}

function DirectionIcon({ direction, context }) {
  if (direction === 'outbound')
    return <span className="flex items-center gap-1 text-xs text-blue-500"><PhoneOutgoing className="h-3.5 w-3.5" /> Out</span>
  if (direction === 'local')
    return <span className="flex items-center gap-1 text-xs text-purple-500"><Phone className="h-3.5 w-3.5" /> Local</span>
  if (context === 'public')
    return <span className="flex items-center gap-1 text-xs text-amber-500"><PhoneIncoming className="h-3.5 w-3.5" /> GW In</span>
  return <span className="flex items-center gap-1 text-xs text-green-600"><PhoneIncoming className="h-3.5 w-3.5" /> In</span>
}

// Detect voicemail calls regardless of which last_app FreeSWITCH reports:
//   - last_app=voicemail (standard)
//   - last_app=speak with TTS arg (flite|kal|...) — greeting was last action
//   - last_app=record with /voicemail/ in path — recording was last action
function isVoicemailCall(last_app, last_arg) {
  const app = (last_app || '').toLowerCase()
  const arg = last_arg || ''
  return app === 'voicemail' ||
    (app === 'speak' && arg.includes('|')) ||
    (app === 'record' && arg.includes('/voicemail/')) ||
    (app === 'system' && arg.includes('voicemail-messages/ingest')) ||
    (app === 'phrase' && arg.includes('voicemail'))
}

// ─── Call flow timeline ───────────────────────────────────────────────────────
// Strip the tenant suffix ("115-IHS" -> "115") for display.
function memberLabel(b) {
  const raw = b.extension_number || b.destination_number || ''
  return raw.replace(/-[^-]+$/, '') || '?'
}

function buildCallFlow(row, vmName, bLeg, ivrMap = {}, rgMap = {}, whMap = {}, bLegs = []) {
  const steps = []

  steps.push({
    icon: row.direction === 'outbound' ? PhoneOutgoing : PhoneIncoming,
    label: row.direction === 'outbound' ? 'Outbound call initiated' : 'Inbound call received',
    detail: `${row.caller_id_number}${row.caller_id_name ? ` (${row.caller_id_name})` : ''} → ${row.destination_number}`,
    time: row.start_stamp,
    color: 'text-blue-500',
  })

  if (row.context) {
    steps.push({
      icon: GitBranch,
      label: 'Dialplan routing',
      detail: `Context: ${row.context}`,
      time: null,
      color: 'text-purple-500',
    })
  }

  if (row.waitsec > 0) {
    steps.push({
      icon: Clock,
      label: 'Waiting / ringing',
      detail: `Ring time: ${row.waitsec}s`,
      time: null,
      color: 'text-amber-500',
    })
  }

  // Ring-group / hunt fan-out: more than one member was dialed for this call.
  if (bLegs.length > 1) {
    const answered = bLegs.find(b => b.billsec > 0)
    const detail = bLegs
      .map(b => `${memberLabel(b)} (${b.billsec > 0 ? `${formatDuration(b.billsec)} ✓` : (b.hangup_cause || 'no answer').replace(/_/g, ' ').toLowerCase()})`)
      .join(', ')
    steps.push({
      icon: PhoneCall,
      label: `Rang ${bLegs.length} members${answered ? ` — ${memberLabel(answered)} answered` : ' — no answer'}`,
      detail,
      time: null,
      color: answered ? 'text-green-500' : 'text-amber-500',
    })
  }

  if (row.answer_stamp && row.billsec > 0) {
    steps.push({
      icon: Phone,
      label: 'Call answered',
      detail: `Connected at ${formatDate(row.answer_stamp)} · PDD: ${row.pdd_ms}ms`,
      time: row.answer_stamp,
      color: 'text-green-500',
    })
  }

  if (row.last_app) {
    const appMap = {
      bridge: {
        icon: PhoneCall, label: 'Bridged to extension', color: 'text-green-500',
        fmt: (arg) => {
          if (bLeg?.extension_number || bLeg?.destination_number) {
            const raw = bLeg.extension_number || bLeg.destination_number
            const ext = raw.replace(/-[^-]+$/, '')
            return `${ext}${bLeg.caller_id_name ? ` (${bLeg.caller_id_name})` : ''} — ${arg}`
          }
          return arg.replace(/^user\//, '').replace(/@.*$/, '')
        },
      },
      voicemail: {
        icon: Voicemail, label: 'Sent to voicemail', color: 'text-orange-500',
        fmt: (arg) => {
          const parts = arg.trim().split(/\s+/)
          const mailbox = parts[2] || parts[0] || arg
          return vmName ? `Mailbox: ${mailbox} — ${vmName}` : `Mailbox: ${mailbox}`
        },
      },
      transfer: {
        icon: GitBranch, label: 'Transferred', color: 'text-purple-500',
        fmt: (a) => {
          // format: "{extension} XML {context}"
          const ext = a?.split(' ')?.[0]
          if (!ext) return a
          if (rgMap[ext]) return `Ring Group: ${rgMap[ext]}`
          if (whMap[ext]) return `Working Hours: ${whMap[ext]}`
          return `Extension: ${ext}`
        },
      },
      ivr: {
        icon: PhoneCall, label: 'IVR Menu', color: 'text-cyan-500',
        fmt: (a) => {
          const name = ivrMap?.[a]
          return name ? `IVR: ${name}` : 'IVR Menu'
        },
      },
      // last_app=record with /voicemail/ path means call went to voicemail recording
      record: {
        icon: (arg) => arg.includes('/voicemail/') ? Voicemail : Mic,
        label: (arg) => arg.includes('/voicemail/') ? 'Sent to voicemail' : 'Recording started',
        color: (arg) => arg.includes('/voicemail/') ? 'text-orange-500' : 'text-red-500',
        fmt: (arg) => {
          if (!arg.includes('/voicemail/')) return arg
          return vmName ? `Mailbox: ${row.extension_number} — ${vmName}` : `Mailbox: ${row.extension_number}`
        },
      },
      playback: { icon: Phone, label: 'Playback', color: 'text-blue-400', fmt: (a) => a },
      system: {
        icon: (arg) => arg.includes('voicemail-messages/ingest') ? Voicemail : Phone,
        label: (arg) => arg.includes('voicemail-messages/ingest') ? 'Sent to voicemail' : 'System',
        color: (arg) => arg.includes('voicemail-messages/ingest') ? 'text-orange-500' : 'text-gray-500',
        fmt: (arg) => {
          if (arg.includes('voicemail-messages/ingest')) {
            const ext = (row.extension_number || '').replace(/-[^-]+$/, '')
            return vmName ? `Mailbox: ${ext} — ${vmName}` : `Mailbox: ${ext}`
          }
          return arg
        },
      },
      // last_app=speak with TTS arg (flite|kal|...) is a voicemail greeting
      speak: {
        icon: Voicemail,
        label: (arg) => arg.includes('|') ? 'Sent to voicemail' : 'speak',
        color: (arg) => arg.includes('|') ? 'text-orange-500' : 'text-gray-500',
        fmt: (arg) => {
          if (!arg.includes('|')) return arg
          const msg = arg.split('|').slice(2).join('|')
          return vmName ? `Mailbox: ${row.extension_number} — ${vmName}` : `Greeting: ${msg}`
        },
      },
    }
    const appEntry = appMap[row.last_app.toLowerCase()]
    const _arg = row.last_arg || ''
    const app = appEntry
      ? {
          icon: typeof appEntry.icon === 'function' ? appEntry.icon(_arg) : appEntry.icon,
          label: typeof appEntry.label === 'function' ? appEntry.label(_arg) : appEntry.label,
          color: typeof appEntry.color === 'function' ? appEntry.color(_arg) : appEntry.color,
          fmt: appEntry.fmt,
        }
      : { icon: GitBranch, label: row.last_app, color: 'text-gray-500', fmt: (a) => a }

    steps.push({
      icon: app.icon,
      label: app.label,
      detail: app.fmt(row.last_arg || ''),
      time: null,
      color: app.color,
    })
  }

  if (row.record_name) {
    steps.push({
      icon: Mic,
      label: 'Call recorded',
      detail: row.record_name,
      time: null,
      color: 'text-red-500',
    })
  }

  if (row.cc_queue) {
    steps.push({
      icon: PhoneCall,
      label: 'Call center queue',
      detail: `Queue: ${row.cc_queue}${row.cc_agent ? ` · Agent: ${row.cc_agent}` : ''}`,
      time: null,
      color: 'text-cyan-500',
    })
  }

  steps.push({
    icon: row.hangup_cause === 'NORMAL_CLEARING' ? PhoneOff : PhoneMissed,
    label: `Call ended — ${row.hangup_cause?.replace(/_/g, ' ') || 'Unknown'}`,
    detail: `Duration: ${formatDuration(row.duration)} · Billed: ${formatDuration(row.billsec)}`,
    time: row.end_stamp,
    color: row.hangup_cause === 'NORMAL_CLEARING' ? 'text-gray-400' : 'text-red-400',
  })

  return steps
}

// ─── Leg detail table ─────────────────────────────────────────────────────────
function LegDetail({ row, label }) {
  const fields = [
    ['UUID', row.xml_cdr_uuid?.slice(0, 8) + '…'],
    ['Call UUID', row.call_uuid?.toString().slice(0, 8) + '…'],
    ['Caller', row.caller_id_number],
    ['Caller Name', row.caller_id_name || '—'],
    ['Destination', row.destination_number],
    ['Extension', row.extension_number || '—'],
    ['Context', row.context || '—'],
    ['Direction', row.direction],
    ['Duration', formatDuration(row.duration)],
    ['Billsec', formatDuration(row.billsec)],
    ['Waitsec', row.waitsec ? `${row.waitsec}s` : '—'],
    ['PDD', row.pdd_ms ? `${row.pdd_ms}ms` : '—'],
    ['Last App', row.last_app || '—'],
    ['Last Arg', row.last_arg || '—'],
    ['Codec (R/W)', `${row.read_codec || '—'} / ${row.write_codec || '—'}`],
    ['Rate (R/W)', `${row.read_rate || '—'} / ${row.write_rate || '—'}`],
    ['Remote IP', row.remote_media_ip || '—'],
    ['Network Addr', row.network_addr || '—'],
    ['Bypass Media', row.bypass_media ? '✓ Yes' : 'No'],
    ['Hangup', `${row.hangup_cause || '—'} (Q.850 ${row.hangup_cause_q850 ?? 0})`],
    row.cc_queue && ['CC Queue', row.cc_queue],
    row.cc_agent && ['CC Agent', row.cc_agent],
    row.record_name && ['Recording', row.record_name],
    row.conference_name && ['Conference', row.conference_name],
    row.tenant_code && ['Tenant', row.tenant_code],
    row.domain_name && ['Domain', row.domain_name],
  ].filter(Boolean)

  return (
    <div>
      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">{label}</p>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        {fields.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-muted-foreground font-medium">{k}</dt>
            <dd className="font-mono truncate">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

// ─── Per-leg SIP / PCAP viewer ─────────────────────────────────────────────────
// Renders the tshark-style numbered frame summary per leg (First Leg, Second
// Leg 0..N), sliced from the rolling SIP capture by Call-ID. Each leg offers a
// "Download .pcap" of just that dialog (openable in sngrep/Wireshark).
function FrameTable({ frames }) {
  return (
    <pre className="text-[11px] leading-snug font-mono overflow-x-auto bg-background/60 rounded border p-2">
      {frames.map((f) => {
        const n = String(f.n).padStart(4, ' ')
        const t = f.time.toFixed(6).padStart(11, ' ')
        const len = f.length != null ? String(f.length) : ''
        return `${n}  ${t}  ${f.src} → ${f.dst}  ${f.proto} ${len} ${f.info}`
      }).join('\n')}
    </pre>
  )
}

function SipPcapView({ aLeg }) {
  const [state, setState] = useState({ loading: true, legs: null, captureEnabled: true, error: null })

  useEffect(() => {
    let alive = true
    setState({ loading: true, legs: null, captureEnabled: true, error: null })
    cdrApi.pcap(aLeg.xml_cdr_uuid)
      .then(({ data }) => alive && setState({
        loading: false, legs: data.legs || [],
        captureEnabled: data.capture_enabled !== false, error: null,
      }))
      .catch(() => alive && setState({ loading: false, legs: [], captureEnabled: true, error: 'Failed to load SIP capture' }))
    return () => { alive = false }
  }, [aLeg.xml_cdr_uuid])

  const download = async (legUuid) => {
    try {
      const { data } = await cdrApi.pcapDownload(aLeg.xml_cdr_uuid, legUuid)
      const url = URL.createObjectURL(new Blob([data], { type: 'application/vnd.tcpdump.pcap' }))
      const a = document.createElement('a')
      a.href = url
      a.download = `leg-${legUuid.slice(0, 8)}.pcap`
      a.click()
      URL.revokeObjectURL(url)
    } catch { /* nothing captured / not authorized */ }
  }

  if (state.loading) {
    return <div className="px-4 py-3 text-xs text-muted-foreground">Slicing SIP capture…</div>
  }
  if (state.error) {
    return <div className="px-4 py-3 text-xs text-destructive">{state.error}</div>
  }
  if (!state.captureEnabled) {
    return <div className="px-4 py-3 text-xs text-amber-600">SIP capture is not running on this server (sngrep/tcpdump unavailable).</div>
  }
  if (!state.legs.length) {
    return <div className="px-4 py-3 text-xs text-muted-foreground">No SIP legs for this call.</div>
  }

  return (
    <div className="px-3 py-2 space-y-4">
      {state.legs.map((leg) => (
        <div key={leg.leg_uuid}>
          <div className="flex items-center justify-between mb-1">
            <p className="text-xs font-semibold flex items-center gap-1.5">
              <Network className="h-3.5 w-3.5 text-cyan-500" />
              {leg.label} SIP decoded
              {leg.call_id && <span className="text-muted-foreground font-mono font-normal">· {leg.call_id}</span>}
            </p>
            {leg.available && (
              <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={() => download(leg.leg_uuid)}>
                <FileDown className="h-3.5 w-3.5 mr-1" /> Download .pcap
              </Button>
            )}
          </div>
          {leg.available && leg.frames.length
            ? <FrameTable frames={leg.frames} />
            : <p className="text-xs text-muted-foreground italic">{leg.reason || 'No packets captured.'}</p>}
        </div>
      ))}
    </div>
  )
}

// ─── Expanded row: plain per-leg table (one row per member rung) ───────────────
function LegsTable({ aLeg }) {
  const [legs, setLegs] = useState(null)

  useEffect(() => {
    setLegs(null)
    if (!aLeg.xml_cdr_uuid) return
    cdrApi.legs(aLeg.xml_cdr_uuid)
      .then(({ data }) => setLegs(Array.isArray(data) ? data : []))
      .catch(() => setLegs([]))
  }, [aLeg.xml_cdr_uuid])

  // Label the leg's destination as "<dialed number> » <member>". For a voicemail
  // leg show "» Voicemail <box>" instead of the device.
  function destLabel(leg) {
    const dialed = aLeg.destination_number || ''
    if (isVoicemailCall(leg.last_app, leg.last_arg)) {
      const raw = leg.extension_number || leg.destination_number || ''
      const box = raw.replace(/-[^-]+$/, '')
      return `${dialed} » Voicemail ${box}`
    }
    // Outbound: extension_number is the *calling* ext, not a callee — the leg is
    // just the dialed number, so show it plainly (no "» member").
    if (aLeg.direction === 'outbound') {
      return leg.destination_number || dialed
    }
    return `${dialed} » ${memberLabel(leg)}`
  }

  if (legs === null) {
    return <div className="px-4 py-3 text-xs text-muted-foreground">Loading legs…</div>
  }
  // No B-legs means nothing was rung/bridged (e.g. a call that went straight to
  // voicemail). The A-leg itself carries the call's outcome, so show it as the
  // single row instead of an empty-state message.
  const rows = legs.length === 0 ? [aLeg] : legs

  return (
    <div className="px-2 py-2">
      <Table className="min-w-[700px]">
        <TableHeader>
          <TableRow>
            <TableHead className="text-xs">Start</TableHead>
            <TableHead className="text-xs">CallerID</TableHead>
            <TableHead className="text-xs">Destination</TableHead>
            <TableHead className="text-xs">Duration</TableHead>
            <TableHead className="text-xs">Talk time</TableHead>
            <TableHead className="text-xs">Disposition</TableHead>
            <TableHead className="text-xs">Cost</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map(leg => (
            <TableRow key={leg.xml_cdr_uuid} className="hover:bg-muted/50">
              <TableCell className="text-xs whitespace-nowrap">{formatDate(leg.start_stamp)}</TableCell>
              <TableCell className="text-xs">
                {leg.caller_id_name ? `"${leg.caller_id_name}" ` : ''}&lt;{aLeg.caller_id_number || '—'}&gt;
              </TableCell>
              <TableCell className="text-xs font-mono">{destLabel(leg)}</TableCell>
              <TableCell className="text-xs">{formatDuration(leg.duration)}</TableCell>
              <TableCell className="text-xs">{formatDuration(leg.billsec)}</TableCell>
              <TableCell><StatusBadge status={leg.status} /></TableCell>
              <TableCell className="text-xs">0.00</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

// ─── Expanded row: tabbed Legs / SIP-PCAP view ─────────────────────────────────
function ExpandedDetail({ aLeg, bLeg, bLegs = [], isSuperAdmin }) {
  const [tab, setTab] = useState('legs')
  const tabs = [
    { key: 'legs', label: 'Legs' },
    { key: 'details', label: 'Details', icon: Info },
    { key: 'pcap', label: 'SIP / PCAP', icon: Network },
  ]
  return (
    <div className="bg-muted/30 border-t">
      <div className="flex gap-1 px-3 pt-2">
        {tabs.map(t => {
          const Icon = t.icon
          const active = tab === t.key
          return (
            <button
              key={t.key}
              onClick={(e) => { e.stopPropagation(); setTab(t.key) }}
              className={`flex items-center gap-1 text-xs px-3 py-1.5 rounded-t border-b-2 transition-colors ${
                active ? 'border-primary font-medium text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground'
              }`}
            >
              {Icon && <Icon className="h-3.5 w-3.5" />} {t.label}
            </button>
          )
        })}
      </div>
      {tab === 'details' && <CallDetail aLeg={aLeg} bLeg={bLeg} bLegs={bLegs} isSuperAdmin={isSuperAdmin} />}
      {tab === 'legs' && <LegsTable aLeg={aLeg} />}
      {tab === 'pcap' && <SipPcapView aLeg={aLeg} />}
    </div>
  )
}

// ─── Expanded row detail ──────────────────────────────────────────────────────
function CallDetail({ aLeg, bLeg, bLegs = [], isSuperAdmin }) {
  const [vmName, setVmName] = useState(null)
  const [ivrMap, setIvrMap] = useState({})
  const [rgMap, setRgMap] = useState({})
  const [whMap, setWhMap] = useState({})
  // B-legs (per-member fan-out) are not in the A-leg-only list query, so fetch
  // them on demand. Fall back to any bLegs already grouped from the page.
  const [fetchedLegs, setFetchedLegs] = useState(null)

  useEffect(() => {
    setFetchedLegs(null)
    if (!aLeg.xml_cdr_uuid) return
    cdrApi.legs(aLeg.xml_cdr_uuid)
      .then(({ data }) => setFetchedLegs(Array.isArray(data) ? data : []))
      .catch(() => setFetchedLegs([]))
  }, [aLeg.xml_cdr_uuid])

  // Prefer freshly fetched legs; fall back to legs grouped from the page.
  const allBLegs = (fetchedLegs && fetchedLegs.length) ? fetchedLegs : bLegs
  const primaryBLeg = bLeg
    || allBLegs.find(b => b.billsec > 0)
    || allBLegs[0]
    || null

  useEffect(() => {
    // Voicemail name
    if (isVoicemailCall(aLeg.last_app, aLeg.last_arg)) {
      const lastApp = aLeg.last_app?.toLowerCase()
      let mailbox = aLeg.extension_number
      // For standard voicemail app, mailbox is 3rd whitespace-separated token in last_arg
      if (lastApp === 'voicemail' && aLeg.last_arg) {
        mailbox = aLeg.last_arg.trim().split(/\s+/)[2] || mailbox
      }
      if (mailbox) {
        voicemailsApi.list({ voicemail_id: mailbox, page_size: 1 })
          .then(({ data }) => {
            const vm = Array.isArray(data) ? data[0] : data.results?.[0]
            if (vm?.voicemail_name) setVmName(vm.voicemail_name)
          }).catch(() => {})
      }
    }
    // Load all lookup maps for resolving names in call flow
    Promise.allSettled([
      ivrMenusApi.list({ page_size: 200 }),
      ringGroupsApi.list({ page_size: 200 }),
      workingHoursApi.list({ page_size: 200 }),
    ]).then(([ivr, rg, wh]) => {
      if (ivr.status === 'fulfilled') {
        const list = Array.isArray(ivr.value.data) ? ivr.value.data : ivr.value.data.results ?? []
        const map = {}
        list.forEach(m => { map[m.ivr_menu_uuid] = m.ivr_menu_name })
        setIvrMap(map)
      }
      if (rg.status === 'fulfilled') {
        const list = Array.isArray(rg.value.data) ? rg.value.data : rg.value.data.results ?? []
        const map = {}
        list.forEach(r => { map[r.ring_group_extension] = r.ring_group_name })
        setRgMap(map)
      }
      if (wh.status === 'fulfilled') {
        const list = Array.isArray(wh.value.data) ? wh.value.data : wh.value.data.results ?? []
        const map = {}
        list.forEach(w => { map[w.dialplan_extension] = w.working_hours_name })
        setWhMap(map)
      }
    })
  }, [aLeg.xml_cdr_uuid])

  const steps = buildCallFlow(aLeg, vmName, primaryBLeg, ivrMap, rgMap, whMap, allBLegs)

  return (
    <div className="px-4 py-3 space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Call flow timeline */}
        <div>
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Call Flow</p>
          <ol className="relative border-l border-border ml-2 space-y-3">
            {steps.map((step, i) => {
              const Icon = step.icon
              return (
                <li key={i} className="ml-4">
                  <span className={`absolute -left-2 flex h-4 w-4 items-center justify-center rounded-full bg-background border ${step.color}`}>
                    <Icon className="h-2.5 w-2.5" />
                  </span>
                  <p className="text-xs font-medium leading-none">{step.label}</p>
                  {step.detail && <p className="text-xs text-muted-foreground mt-0.5">{step.detail}</p>}
                  {step.time && <p className="text-xs text-muted-foreground/60 mt-0.5">{formatDate(step.time)}</p>}
                </li>
              )
            })}
          </ol>
        </div>

        {isSuperAdmin && (
          <LegDetail row={aLeg} label={allBLegs.length ? 'A-Leg (Caller)' : 'Technical Details'} />
        )}
      </div>

      {isSuperAdmin && allBLegs.length > 0 && (
        <div className="border-t pt-3 space-y-4">
          {allBLegs.map((b, idx) => (
            <div key={b.xml_cdr_uuid} className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <LegDetail row={b} label={bLegs.length > 1 ? `B-Leg ${idx + 1} (${b.destination_number || 'Callee'}) — ${b.hangup_cause || '?'}` : 'B-Leg (Callee)'} />
              <div>
                <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-2">Bridge Summary</p>
                <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
                  {[
                    ['A-leg UUID', aLeg.call_uuid?.toString().slice(0, 8) + '…'],
                    ['B-leg UUID', b.call_uuid?.toString().slice(0, 8) + '…'],
                    ['Bridge UUID', aLeg.bridge_uuid?.toString().slice(0, 8) + '…'],
                    ['A codec', `${aLeg.read_codec}/${aLeg.write_codec}`],
                    ['B codec', `${b.read_codec}/${b.write_codec}`],
                    ['A remote IP', aLeg.remote_media_ip || '—'],
                    ['B remote IP', b.remote_media_ip || '—'],
                    ['A PDD', aLeg.pdd_ms ? `${aLeg.pdd_ms}ms` : '—'],
                    ['B PDD', b.pdd_ms ? `${b.pdd_ms}ms` : '—'],
                    ['A duration', formatDuration(aLeg.duration)],
                    ['B duration', formatDuration(b.duration)],
                    ['Tenant', aLeg.tenant_code || '—'],
                    ['Domain', aLeg.domain_name || '—'],
                    ['Context', aLeg.context || b.context || '—'],
                    ['Bypass Media', (aLeg.bypass_media || b.bypass_media) ? '✓ Yes' : 'No'],
                  ].map(([k, v]) => (
                    <div key={k} className="contents">
                      <dt className="text-muted-foreground font-medium">{k}</dt>
                      <dd className="font-mono truncate">{v}</dd>
                    </div>
                  ))}
                </dl>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ─── Summary bar ──────────────────────────────────────────────────────────────
function SummaryBar({ summary }) {
  if (!summary) return null
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {[
        { label: 'Total Calls', value: summary.total_calls?.toLocaleString() ?? '—' },
        { label: 'Answered', value: summary.answered_calls?.toLocaleString() ?? '—' },
        { label: 'Missed', value: summary.missed_calls?.toLocaleString() ?? '—' },
        { label: 'Answer Rate', value: summary.answer_rate != null ? `${summary.answer_rate}%` : '—' },
      ].map(({ label, value }) => (
        <Card key={label}>
          <CardContent className="p-3">
            <p className="text-xs text-muted-foreground">{label}</p>
            <p className="text-lg font-semibold">{value}</p>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function Cdr() {
  const { user } = useSelector(selectAuth)
  const isSuperAdmin = user?.is_superuser === true

  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE)
  const [search, setSearch] = useState('')
  const debouncedSearch = useDebounce(search, 300)
  const [datePreset, setDatePreset] = useState('this_month')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [direction, setDirection] = useState('')
  const [hangupCause, setHangupCause] = useState('')
  const [ordering, setOrdering] = useState('-start_stamp')
  const [expanded, setExpanded] = useState(null)
  const [summary, setSummary] = useState(null)

  // Compute date range from preset
  const getPresetRange = useCallback(() => {
    const today = new Date()
    const fmt = (d) => d.toISOString().slice(0, 10)
    if (datePreset === 'this_week') {
      const mon = new Date(today); mon.setDate(today.getDate() - today.getDay() + 1)
      return { from: fmt(mon), to: fmt(today) }
    }
    if (datePreset === 'last_week') {
      const mon = new Date(today); mon.setDate(today.getDate() - today.getDay() - 6)
      const sun = new Date(mon); sun.setDate(mon.getDate() + 6)
      return { from: fmt(mon), to: fmt(sun) }
    }
    if (datePreset === 'this_month') {
      return { from: fmt(new Date(today.getFullYear(), today.getMonth(), 1)), to: fmt(today) }
    }
    if (datePreset === 'last_month') {
      const first = new Date(today.getFullYear(), today.getMonth() - 1, 1)
      const last = new Date(today.getFullYear(), today.getMonth(), 0)
      return { from: fmt(first), to: fmt(last) }
    }
    if (datePreset === 'this_year') {
      return { from: fmt(new Date(today.getFullYear(), 0, 1)), to: fmt(today) }
    }
    // custom — use manual dateFrom/dateTo
    return { from: dateFrom, to: dateTo }
  }, [datePreset, dateFrom, dateTo])

  // Build filter params (no page/page_size — useInfiniteList supplies those).
  // Memoised so its identity only changes when an actual filter value changes,
  // which is what drives the hook's auto-reset to page 1.
  const listParams = useMemo(() => {
    const { from, to } = getPresetRange()
    const params = { ordering }
    if (debouncedSearch) params.search = debouncedSearch
    if (from) params.start_stamp__gte = from
    if (to) params.start_stamp__lte = to + 'T23:59:59'
    if (direction) params.direction = direction
    if (hangupCause) params.hangup_cause = hangupCause
    return params
  }, [debouncedSearch, getPresetRange, direction, hangupCause, ordering])

  // Infinite-scroll loader — rows here are the raw (ungrouped) CDR legs.
  const {
    rows: rawRows,
    total,
    loading: initialLoading,
    loadingMore,
    hasMore,
    loadMore,
  } = useInfiniteList(cdrApi.list, { params: listParams, pageSize })

  // Leg-grouping applied to the full accumulated set of raw rows.
  const rows = useMemo(() => groupLegs(rawRows), [rawRows])

  // Summary follows the same filters (not paginated).
  useEffect(() => {
    let cancelled = false
    cdrApi.summary(listParams)
      .then(({ data }) => { if (!cancelled) setSummary(data) })
      .catch(() => {})
    return () => { cancelled = true }
  }, [listParams])

  // Collapse any expanded row when filters/page size change.
  useEffect(() => { setExpanded(null) }, [listParams, pageSize])

  const toggleExpand = (uuid) => setExpanded((prev) => prev === uuid ? null : uuid)

  const clearFilters = () => { setSearch(''); setDatePreset('this_month'); setDateFrom(''); setDateTo(''); setDirection(''); setHangupCause('') }

  const [exporting, setExporting] = useState(false)
  const handleExport = async () => {
    setExporting(true)
    try {
      const { from, to } = getPresetRange()
      const params = {}
      if (debouncedSearch) params.search = debouncedSearch
      if (from) params.start_stamp__gte = from
      if (to) params.start_stamp__lte = to + 'T23:59:59'
      if (direction) params.direction = direction
      if (hangupCause) params.hangup_cause = hangupCause
      const { data, headers } = await cdrApi.export(params)
      const url = URL.createObjectURL(new Blob([data], { type: 'text/csv' }))
      const a = document.createElement('a')
      a.href = url
      const cd = headers['content-disposition'] || ''
      const match = cd.match(/filename="?([^"]+)"?/)
      a.download = match ? match[1] : 'cdr.csv'
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setExporting(false)
    }
  }

  const toggleSort = (field) => {
    setOrdering((prev) => prev === `-${field}` ? field : `-${field}`)
  }

  const SortIcon = ({ field }) => {
    if (ordering === `-${field}`) return <ChevronDown className="inline h-3 w-3 ml-0.5" />
    if (ordering === field) return <ChevronUp className="inline h-3 w-3 ml-0.5" />
    return <ChevronDown className="inline h-3 w-3 ml-0.5 opacity-30" />
  }

  return (
    <div className="space-y-4">
      {/* Summary */}
      {!initialLoading && <SummaryBar summary={summary} />}

      {/* Filters */}
      {/* Mobile: search full-width on top, controls scroll horizontally below */}
      {/* Desktop: single row, search expands, controls fixed width */}
      <div className="flex flex-col gap-2 md:flex-row md:items-center md:gap-2">
        <div className="relative md:flex-1 md:min-w-0">
          <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search..."
            className="pl-7 h-9 text-sm w-full"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className="flex flex-nowrap items-center gap-2 overflow-x-auto pb-0.5">
          <Select wrapperClassName="w-36 shrink-0" value={datePreset} onChange={(e) => setDatePreset(e.target.value)}>
            <option value="this_week">This Week</option>
            <option value="last_week">Last Week</option>
            <option value="this_month">This Month</option>
            <option value="last_month">Last Month</option>
            <option value="this_year">This Year</option>
            <option value="custom">Custom Range</option>
          </Select>

          {datePreset === 'custom' && (
            <>
              <Input type="date" className="w-36 h-9 shrink-0" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
              <span className="text-muted-foreground text-sm shrink-0">–</span>
              <Input type="date" className="w-36 h-9 shrink-0" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
            </>
          )}

          <Select wrapperClassName="w-36 shrink-0" value={direction || 'all'} onChange={(e) => setDirection(e.target.value === 'all' ? '' : e.target.value)}>
            <option value="all">All Directions</option>
            <option value="inbound">Inbound</option>
            <option value="outbound">Outbound</option>
            <option value="local">Local</option>
          </Select>

          <Select wrapperClassName="w-36 shrink-0" value={hangupCause || 'all'} onChange={(e) => setHangupCause(e.target.value === 'all' ? '' : e.target.value)}>
            <option value="all">All Statuses</option>
            <option value="NORMAL_CLEARING">Answered</option>
            <option value="NO_ANSWER">No Answer</option>
            <option value="USER_BUSY">Busy</option>
            <option value="ORIGINATOR_CANCEL">Cancelled</option>
            <option value="USER_NOT_REGISTERED">Offline</option>
          </Select>

          {(search || direction || hangupCause || datePreset !== 'this_month' || dateFrom || dateTo) && (
            <Button variant="ghost" size="sm" className="h-9 px-3 shrink-0" onClick={clearFilters}>Clear</Button>
          )}

          <Button variant="outline" size="sm" className="h-9 px-3 shrink-0" onClick={handleExport} disabled={exporting}>
            <Download className="h-3.5 w-3.5 mr-1.5" />
            {exporting ? 'Exporting…' : 'Export CSV'}
          </Button>

          <PageSizeSelector value={pageSize} onChange={setPageSize} className="shrink-0 ml-auto" />

          {total > 0 && (
            <span className="text-sm text-muted-foreground whitespace-nowrap shrink-0">
              {rows.length.toLocaleString()} {rows.length === 1 ? 'call' : 'calls'}
              {hasMore && ` (loading…)`}
            </span>
          )}
        </div>
      </div>

      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <Table className="min-w-[800px]">
            <TableHeader>
              <TableRow>
                <TableHead className="w-6" />
                <TableHead className="cursor-pointer select-none whitespace-nowrap" onClick={() => toggleSort('start_stamp')}>
                  Date / Time <SortIcon field="start_stamp" />
                </TableHead>
                <TableHead>Direction</TableHead>
                <TableHead>Ext</TableHead>
                <TableHead>Caller</TableHead>
                <TableHead>Caller ID</TableHead>
                <TableHead>Destination</TableHead>
                <TableHead>Answered By</TableHead>
                <TableHead className="cursor-pointer select-none" onClick={() => toggleSort('duration')}>
                  Duration <SortIcon field="duration" />
                </TableHead>
                <TableHead className="cursor-pointer select-none" onClick={() => toggleSort('billsec')}>
                  Billsec <SortIcon field="billsec" />
                </TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {initialLoading ? (
                [...Array(10)].map((_, i) => (
                  <TableRow key={i}>
                    {[...Array(11)].map((_, j) => (
                      <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                    ))}
                  </TableRow>
                ))
              ) : rows.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={11} className="text-center py-10 text-muted-foreground">
                    No records found.
                  </TableCell>
                </TableRow>
              ) : (
                rows.map(({ aLeg, bLeg, bLegs }) => {
                  // Use B-leg uuid as row key when present — same A-leg may appear in multiple rows (forked dial)
                  const uuid = bLeg ? bLeg.xml_cdr_uuid : aLeg.xml_cdr_uuid
                  const isExpanded = expanded === uuid
                  const primary = aLeg
                  return (
                    <>
                      <TableRow
                        key={uuid}
                        className="cursor-pointer hover:bg-muted/50"
                        onClick={() => toggleExpand(uuid)}
                      >
                        <TableCell className="w-6 pr-0">
                          {isExpanded
                            ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
                            : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground whitespace-nowrap">
                          {formatDate(primary.start_stamp)}
                        </TableCell>
                        <TableCell>
                          <DirectionIcon direction={primary.direction} context={primary.context} />
                        </TableCell>
                        <TableCell className="font-mono text-sm font-medium">
                          {(() => {
                            const ext = primary.extension_number || ''
                            const looksLikeDid = ext.startsWith('+') || ext.replace(/\D/g, '').length > 6
                            if (primary.direction === 'inbound' && looksLikeDid && bLeg) {
                              // Each B-leg in a forked dial has its own extension_number (the specific device).
                              // caller_id_number on the B-leg is set to the dialled device by FreeSWITCH.
                              // Try: extension_number → caller_id_number → destination_number (each stripped of SIP suffix)
                              const candidates = [
                                bLeg.extension_number,
                                bLeg.caller_id_number,
                                bLeg.destination_number,
                              ]
                              for (const c of candidates) {
                                if (!c) continue
                                const stripped = c.replace(/-[^-]+$/, '')
                                // Only use if it looks like a short internal extension (not a DID)
                                if (stripped && !stripped.startsWith('+') && stripped.replace(/\D/g, '').length <= 6)
                                  return stripped
                              }
                            }
                            return ext.replace(/-[^-]+$/, '') || '—'
                          })()}
                        </TableCell>
                        <TableCell className="font-mono text-sm">
                          {primary.caller_id_number || '—'}
                        </TableCell>
                        <TableCell className="text-sm">
                          {primary.caller_id_name || '—'}
                        </TableCell>
                        <TableCell className="font-mono text-sm">
                          {primary.destination_number || '—'}
                        </TableCell>
                        <TableCell className="text-sm">
                          {(() => {
                            const app = primary.last_app?.toLowerCase()
                            if (app === 'bridge') {
                              if (primary.direction === 'inbound') {
                                const ext = primary.extension_number || ''
                                if (ext) return <span className="text-green-600 font-mono">Ext {ext.replace(/-[^-]+$/, '')}</span>
                              } else {
                                const dest = primary.destination_number || ''
                                if (dest) return <span className="text-blue-500 font-mono">{dest}</span>
                              }
                              return <span className="text-muted-foreground">—</span>
                            }
                            if (app === 'voicemail') {
                              const tokens = primary.last_arg?.trim().split(/\s+/) || []
                              const vmBox = (tokens.length >= 3 ? tokens[2] : '') || primary.extension_number || primary.destination_number || ''
                              return <span className="text-orange-500">VM {vmBox.replace(/-[^-]+$/, '')}</span>
                            }
                            if (isVoicemailCall(primary.last_app, primary.last_arg)) {
                              const raw = primary.extension_number || primary.destination_number || ''
                              const ext = raw.replace(/-[^-]+$/, '')
                              return <span className="text-orange-500">VM {ext}</span>
                            }
                            // Legacy Asterisk rows use last_app="Dial". If a real extension is
                            // recorded and the call connected, surface it the same as bridge.
                            if (primary.extension_number && primary.billsec > 0) {
                              if (primary.direction === 'inbound') {
                                const ext = primary.extension_number.replace(/-[^-]+$/, '')
                                return <span className="text-green-600 font-mono">Ext {ext}</span>
                              }
                              if (primary.destination_number) {
                                return <span className="text-blue-500 font-mono">{primary.destination_number}</span>
                              }
                            }
                            return <span className="text-muted-foreground">—</span>
                          })()}
                        </TableCell>
                        <TableCell>
                          <span className="font-mono text-sm">{formatDuration(primary.duration)}</span>
                        </TableCell>
                        <TableCell>
                          <span className="font-mono text-sm">{formatDuration(primary.billsec)}</span>
                        </TableCell>
                        <TableCell className="space-x-1">
                          <StatusBadge status={primary.status} />
                          {(primary.record_name || bLeg?.record_name) && (
                            <Badge variant="outline" className="text-xs text-red-500 border-red-300">
                              Recorded
                            </Badge>
                          )}
                        </TableCell>
                      </TableRow>

                      {isExpanded && (
                        <TableRow key={`${uuid}-detail`} className="hover:bg-transparent">
                          <TableCell colSpan={11} className="p-0">
                            <ExpandedDetail aLeg={aLeg} bLeg={bLeg} bLegs={bLegs} isSuperAdmin={isSuperAdmin} />
                          </TableCell>
                        </TableRow>
                      )}
                    </>
                  )
                })
              )}

              {/* Skeleton rows while loading more */}
              {loadingMore && (
                [...Array(5)].map((_, i) => (
                  <TableRow key={`skel-${i}`}>
                    {[...Array(11)].map((_, j) => (
                      <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                    ))}
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>

          {/* Infinite scroll — sentinel + footer */}
          {!initialLoading && rows.length > 0 && (
            <InfiniteScroll
              hasMore={hasMore}
              loadingMore={loadingMore}
              onLoadMore={loadMore}
              loaded={rows.length}
              total={total}
            />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
