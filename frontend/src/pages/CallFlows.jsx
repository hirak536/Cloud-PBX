import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useParams, useLocation } from 'react-router-dom'
import { useSelector } from 'react-redux'
import { selectAuth } from '@/store'
import { canPerformAction } from '@/lib/permissions'
import {
  destinations as destinationsApi,
  extensions as extensionsApi,
  voicemails as voicemailsApi,
  ringGroups as ringGroupsApi,
  ivrMenus as ivrMenusApi,
  conferences as conferencesApi,
  workingHours as workingHoursApi,
  customDestinations as customDestinationsApi,
  callFlows as callFlowsApi,
} from '@/api'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Skeleton } from '@/components/ui/skeleton'
import DestinationPicker, { EMPTY_DEST } from '@/components/DestinationPicker'
import { useDestinationData } from '@/hooks/useDestinationData'
import { toast } from 'sonner'
import {
  Phone, PhoneForwarded, Users, Bot, Voicemail, Clock, GitBranch,
  PhoneOff, Mic, ExternalLink, Search, ChevronDown, ChevronRight,
  Hash, Zap, Radio, Plus, Pencil, Trash2, Loader2, Sun, Moon, ToggleLeft,
} from 'lucide-react'
import { cn } from '@/lib/utils'

// ── Node type config ──────────────────────────────────────────────────────────
// Each type has light-mode and dark-mode variants via Tailwind dark: prefix

const NODE_CONFIG = {
  did: {
    label: 'DID',
    icon: Radio,
    glow: 'shadow-[0_0_16px_2px_rgba(99,102,241,0.2)] dark:shadow-[0_0_16px_2px_rgba(99,102,241,0.4)]',
    border: 'border-indigo-300 dark:border-indigo-500/50',
    bg: 'bg-indigo-50 dark:bg-indigo-950/60',
    iconBg: 'bg-indigo-100 dark:bg-indigo-500/20',
    iconColor: 'text-indigo-600 dark:text-indigo-300',
    tagColor: 'text-indigo-500 dark:text-indigo-400',
    dotColor: 'bg-indigo-500 dark:bg-indigo-400',
    lineColor: '#6366f1',
  },
  extension: {
    label: 'Extension',
    icon: Hash,
    glow: 'shadow-[0_0_14px_2px_rgba(59,130,246,0.15)] dark:shadow-[0_0_14px_2px_rgba(59,130,246,0.35)]',
    border: 'border-blue-300 dark:border-blue-500/40',
    bg: 'bg-blue-50 dark:bg-blue-950/60',
    iconBg: 'bg-blue-100 dark:bg-blue-500/20',
    iconColor: 'text-blue-600 dark:text-blue-300',
    tagColor: 'text-blue-500 dark:text-blue-400',
    dotColor: 'bg-blue-500 dark:bg-blue-400',
    lineColor: '#3b82f6',
  },
  ivr_menu: {
    label: 'IVR Menu',
    icon: Bot,
    glow: 'shadow-[0_0_14px_2px_rgba(245,158,11,0.15)] dark:shadow-[0_0_14px_2px_rgba(245,158,11,0.35)]',
    border: 'border-amber-300 dark:border-amber-500/40',
    bg: 'bg-amber-50 dark:bg-amber-950/60',
    iconBg: 'bg-amber-100 dark:bg-amber-500/20',
    iconColor: 'text-amber-600 dark:text-amber-300',
    tagColor: 'text-amber-500 dark:text-amber-400',
    dotColor: 'bg-amber-500 dark:bg-amber-400',
    lineColor: '#f59e0b',
  },
  ring_group: {
    label: 'Ring Group',
    icon: Users,
    glow: 'shadow-[0_0_14px_2px_rgba(34,197,94,0.15)] dark:shadow-[0_0_14px_2px_rgba(34,197,94,0.35)]',
    border: 'border-emerald-300 dark:border-emerald-500/40',
    bg: 'bg-emerald-50 dark:bg-emerald-950/60',
    iconBg: 'bg-emerald-100 dark:bg-emerald-500/20',
    iconColor: 'text-emerald-600 dark:text-emerald-300',
    tagColor: 'text-emerald-500 dark:text-emerald-400',
    dotColor: 'bg-emerald-500 dark:bg-emerald-400',
    lineColor: '#22c55e',
  },
  voicemail: {
    label: 'Voicemail',
    icon: Voicemail,
    glow: 'shadow-[0_0_14px_2px_rgba(168,85,247,0.15)] dark:shadow-[0_0_14px_2px_rgba(168,85,247,0.35)]',
    border: 'border-purple-300 dark:border-purple-500/40',
    bg: 'bg-purple-50 dark:bg-purple-950/60',
    iconBg: 'bg-purple-100 dark:bg-purple-500/20',
    iconColor: 'text-purple-600 dark:text-purple-300',
    tagColor: 'text-purple-500 dark:text-purple-400',
    dotColor: 'bg-purple-500 dark:bg-purple-400',
    lineColor: '#a855f7',
  },
  conference: {
    label: 'Conference',
    icon: Mic,
    glow: 'shadow-[0_0_14px_2px_rgba(14,165,233,0.15)] dark:shadow-[0_0_14px_2px_rgba(14,165,233,0.35)]',
    border: 'border-sky-300 dark:border-sky-500/40',
    bg: 'bg-sky-50 dark:bg-sky-950/60',
    iconBg: 'bg-sky-100 dark:bg-sky-500/20',
    iconColor: 'text-sky-600 dark:text-sky-300',
    tagColor: 'text-sky-500 dark:text-sky-400',
    dotColor: 'bg-sky-500 dark:bg-sky-400',
    lineColor: '#0ea5e9',
  },
  working_hours: {
    label: 'Working Hours',
    icon: Clock,
    glow: 'shadow-[0_0_14px_2px_rgba(20,184,166,0.15)] dark:shadow-[0_0_14px_2px_rgba(20,184,166,0.35)]',
    border: 'border-teal-300 dark:border-teal-500/40',
    bg: 'bg-teal-50 dark:bg-teal-950/60',
    iconBg: 'bg-teal-100 dark:bg-teal-500/20',
    iconColor: 'text-teal-600 dark:text-teal-300',
    tagColor: 'text-teal-500 dark:text-teal-400',
    dotColor: 'bg-teal-500 dark:bg-teal-400',
    lineColor: '#14b8a6',
  },
  external: {
    label: 'External',
    icon: ExternalLink,
    glow: 'shadow-[0_0_14px_2px_rgba(100,116,139,0.1)] dark:shadow-[0_0_14px_2px_rgba(100,116,139,0.3)]',
    border: 'border-slate-300 dark:border-slate-500/40',
    bg: 'bg-slate-100 dark:bg-slate-900/60',
    iconBg: 'bg-slate-200 dark:bg-slate-500/20',
    iconColor: 'text-slate-600 dark:text-slate-300',
    tagColor: 'text-slate-500 dark:text-slate-400',
    dotColor: 'bg-slate-500 dark:bg-slate-400',
    lineColor: '#64748b',
  },
  call_forward: {
    label: 'Forward',
    icon: PhoneForwarded,
    glow: 'shadow-[0_0_14px_2px_rgba(249,115,22,0.15)] dark:shadow-[0_0_14px_2px_rgba(249,115,22,0.35)]',
    border: 'border-orange-300 dark:border-orange-500/40',
    bg: 'bg-orange-50 dark:bg-orange-950/60',
    iconBg: 'bg-orange-100 dark:bg-orange-500/20',
    iconColor: 'text-orange-600 dark:text-orange-300',
    tagColor: 'text-orange-500 dark:text-orange-400',
    dotColor: 'bg-orange-500 dark:bg-orange-400',
    lineColor: '#f97316',
  },
  fax: {
    label: 'Fax',
    icon: Zap,
    glow: 'shadow-[0_0_14px_2px_rgba(249,115,22,0.12)] dark:shadow-[0_0_14px_2px_rgba(249,115,22,0.3)]',
    border: 'border-orange-300 dark:border-orange-500/40',
    bg: 'bg-orange-50 dark:bg-orange-950/60',
    iconBg: 'bg-orange-100 dark:bg-orange-500/20',
    iconColor: 'text-orange-600 dark:text-orange-300',
    tagColor: 'text-orange-500 dark:text-orange-400',
    dotColor: 'bg-orange-500 dark:bg-orange-400',
    lineColor: '#f97316',
  },
  hangup: {
    label: 'Hangup',
    icon: PhoneOff,
    glow: 'shadow-[0_0_14px_2px_rgba(239,68,68,0.15)] dark:shadow-[0_0_14px_2px_rgba(239,68,68,0.35)]',
    border: 'border-red-300 dark:border-red-500/40',
    bg: 'bg-red-50 dark:bg-red-950/60',
    iconBg: 'bg-red-100 dark:bg-red-500/20',
    iconColor: 'text-red-600 dark:text-red-300',
    tagColor: 'text-red-500 dark:text-red-400',
    dotColor: 'bg-red-500 dark:bg-red-400',
    lineColor: '#ef4444',
  },
  custom_destination: {
    label: 'Custom',
    icon: GitBranch,
    glow: 'shadow-[0_0_14px_2px_rgba(139,92,246,0.15)] dark:shadow-[0_0_14px_2px_rgba(139,92,246,0.35)]',
    border: 'border-violet-300 dark:border-violet-500/40',
    bg: 'bg-violet-50 dark:bg-violet-950/60',
    iconBg: 'bg-violet-100 dark:bg-violet-500/20',
    iconColor: 'text-violet-600 dark:text-violet-300',
    tagColor: 'text-violet-500 dark:text-violet-400',
    dotColor: 'bg-violet-500 dark:bg-violet-400',
    lineColor: '#8b5cf6',
  },
}

// ── Lookup builder ────────────────────────────────────────────────────────────

function buildLookup(data) {
  const lk = {}
  const index = (type, items, keyFn, labelFn) => {
    lk[type] = {}
    items.forEach(item => { lk[type][keyFn(item)] = labelFn(item) })
  }
  index('extension',    data.extensions,    i => i.extension_uuid,     i => ({ name: i.effective_caller_id_name ? `${i.extension} – ${i.effective_caller_id_name}` : i.extension, ext: i.extension }))
  index('voicemail',    data.voicemails,     i => i.voicemail_id,       i => ({ name: i.voicemail_name || i.voicemail_id }))
  index('ring_group',   data.ringGroups,     i => i.ring_group_uuid,    i => ({ name: i.ring_group_name, ext: i.ring_group_extension, timeout_type: i.ring_group_timeout_type, timeout_uuid: i.ring_group_timeout_target_uuid, timeout_ext_number: i.ring_group_timeout_external_number }))
  index('ivr_menu',     data.ivrMenus,       i => i.ivr_menu_uuid,      i => ({ name: i.ivr_menu_name, options: i.options || [] }))
  index('conference',   data.conferences,    i => i.conference_uuid,    i => ({ name: i.conference_name }))
  index('working_hours',data.workingHours,   i => i.working_hours_uuid, i => ({ name: i.working_hours_name, open_dest_type: i.open_dest_type, open_dest_target_uuid: i.open_dest_target_uuid, open_dest_external_number: i.open_dest_external_number, closed_dest_type: i.closed_dest_type, closed_dest_target_uuid: i.closed_dest_target_uuid, closed_dest_external_number: i.closed_dest_external_number }))
  index('custom_destination', data.customDestinations, i => i.custom_destination_uuid, i => ({ name: i.name, dest_type: i.dest_type, dest_target_uuid: i.dest_target_uuid, dest_external_number: i.dest_external_number }))
  return lk
}

function buildNode(type, uuid, externalNumber, lookup) {
  if (!type) return null
  if (type === 'hangup') return { type: 'hangup', label: 'Hang Up' }
  if (type === 'external' || type === 'call_forward') return { type, label: externalNumber || 'External Number' }
  if (type === 'voicemail' && uuid) {
    const ext = lookup.extension?.[uuid]
    return { type: 'voicemail', uuid, label: ext ? `VM – ${ext.ext || ext.name}` : 'Voicemail' }
  }
  if (!uuid) {
    if (type === 'fax') return { type: 'fax', label: 'Fax Box' }
    return { type, label: NODE_CONFIG[type]?.label || type }
  }
  const entry = lookup[type]?.[uuid]
  if (!entry) return { type, uuid: String(uuid), label: NODE_CONFIG[type]?.label || type }
  return { type, uuid: String(uuid), label: entry.name || String(uuid).slice(0, 8), sublabel: type === 'ring_group' && entry.ext ? `Ext ${entry.ext}` : undefined }
}

// ── Flow Node ─────────────────────────────────────────────────────────────────

function FlowNode({ type, label, sublabel }) {
  const cfg = NODE_CONFIG[type] || NODE_CONFIG.extension
  const Icon = cfg.icon
  return (
    <div className={cn(
      'relative flex items-center gap-3 rounded-2xl border px-4 py-3 backdrop-blur-sm',
      'transition-all duration-200 hover:scale-[1.02] cursor-default',
      cfg.bg, cfg.border, cfg.glow,
    )}>
      {/* Animated status dot */}
      <span className={cn(
        'absolute -top-1 -right-1 h-2.5 w-2.5 rounded-full border-2 border-background',
        cfg.dotColor,
        type !== 'hangup' && 'animate-pulse',
      )} />

      {/* Icon */}
      <div className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-xl', cfg.iconBg)}>
        <Icon className={cn('h-4 w-4', cfg.iconColor)} />
      </div>

      {/* Text */}
      <div className="min-w-0">
        <div className={cn('text-[9px] font-bold uppercase tracking-[0.12em] mb-0.5', cfg.tagColor)}>
          {cfg.label}
        </div>
        <div className="text-sm font-semibold text-foreground leading-tight truncate max-w-[200px]" title={label}>
          {label}
        </div>
        {sublabel && (
          <div className="text-[11px] text-muted-foreground mt-0.5 font-mono">{sublabel}</div>
        )}
      </div>
    </div>
  )
}

// ── Animated connector (single straight line) ─────────────────────────────────

let _connId = 0
function Connector({ label, color = '#6366f1', dashed = true }) {
  const pathId = `cp${++_connId}`
  return (
    <div className="flex flex-col items-center" style={{ zIndex: 1 }}>
      <svg width="2" height="28" className="overflow-visible">
        <line x1="1" y1="0" x2="1" y2="28" stroke={color} strokeWidth="1.5"
          strokeDasharray={dashed ? '4 3' : 'none'} opacity="0.6" />
        <circle r="2.5" fill={color} opacity="0.9">
          <animateMotion dur="1.2s" repeatCount="indefinite">
            <mpath xlinkHref={`#${pathId}`} />
          </animateMotion>
        </circle>
        <path id={pathId} d="M1,0 L1,28" fill="none" />
      </svg>

      {label && (
        <div
          className="text-[9px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full border my-0.5"
          style={{ color, borderColor: `${color}66`, background: `${color}18` }}
        >
          {label}
        </div>
      )}

      <svg width="10" height="6" viewBox="0 0 10 6">
        <polygon points="5,6 0,0 10,0" fill={color} opacity="0.7" />
      </svg>
    </div>
  )
}

// ── T-branch layout — CSS borders for the horizontal bar ─────────────────────
//
// Structure (each branch column):
//
//        [parent node]
//             │  ← stem (short vertical line, centred)
//   ┌─────────┼─────────┐  ← horizontal bar spans between first & last col
//   │                   │  ← drop (vertical, coloured per branch)
// [Open]             [Closed]
//   ↓                   ↓
// [child]            [child]
//
// We achieve this purely with CSS:
//  - each column has a top border on its "cap" div — left col: border-right only,
//    right col: border-left only, middle cols: both sides.
//  - The drop is just a short vertical line before the label/arrow.

function BranchConnector({ branches, lookup, depth, visited }) {
  return (
    <div className="flex flex-col items-center">
      {/* Short stem from parent to the horizontal bar level */}
      <div className="w-px h-5 bg-border/60" />

      {/* Branch row */}
      <div className="flex items-start">
        {branches.map((b, i) => {
          const isFirst  = i === 0
          const isLast   = i === branches.length - 1
          const isOnly   = branches.length === 1

          // Cap div draws the horizontal bar via top-border
          const capBorder = isOnly
            ? 'border-t-0'
            : isFirst
              ? 'border-t border-r border-border/50 rounded-tr-sm'
              : isLast
                ? 'border-t border-l border-border/50 rounded-tl-sm'
                : 'border-t border-l border-r border-border/50'

          return (
            <div key={i} className="flex flex-col items-center px-6">
              {/* Cap: horizontal bar segment */}
              <div className={cn('w-full h-5', capBorder)} />

              {/* Drop line in branch colour */}
              <div className="w-px h-4" style={{ backgroundColor: b.color, opacity: 0.5 }} />

              {/* Label badge */}
              {b.label && (
                <div
                  className="text-[9px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-full border mb-1"
                  style={{ color: b.color, borderColor: `${b.color}55`, background: `${b.color}15` }}
                >
                  {b.label}
                </div>
              )}

              {/* Arrowhead */}
              <svg width="10" height="6" viewBox="0 0 10 6" className="mb-2">
                <polygon points="5,6 0,0 10,0" fill={b.color} opacity="0.7" />
              </svg>

              {/* Child subtree */}
              <NodeTree node={b.node} lookup={lookup} depth={depth} visited={visited} />
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ── Recursive node tree ───────────────────────────────────────────────────────

function NodeTree({ node, lookup, depth = 0, visited = new Set() }) {
  if (!node || depth > 6) return null

  const { type, uuid, label, sublabel } = node
  const cfg = NODE_CONFIG[type] || NODE_CONFIG.extension

  const nodeKey = `${type}:${uuid}`
  if (uuid && visited.has(nodeKey)) {
    return (
      <div className="rounded-xl border border-dashed border-border px-3 py-2 text-[11px] text-muted-foreground">
        ↩ {label} (loop)
      </div>
    )
  }
  const newVisited = new Set(visited)
  if (uuid) newVisited.add(nodeKey)

  let branches = []

  if (type === 'working_hours' && uuid) {
    const wh = lookup.working_hours?.[uuid]
    if (wh) {
      const openNode   = wh.open_dest_type   ? buildNode(wh.open_dest_type,   wh.open_dest_target_uuid,   wh.open_dest_external_number,   lookup) : null
      const closedNode = wh.closed_dest_type ? buildNode(wh.closed_dest_type, wh.closed_dest_target_uuid, wh.closed_dest_external_number, lookup) : null
      if (openNode)   branches.push({ label: 'Open',   node: openNode,   color: '#22c55e' })
      if (closedNode) branches.push({ label: 'Closed', node: closedNode, color: '#64748b' })
    }
  } else if (type === 'ivr_menu' && uuid) {
    const ivr = lookup.ivr_menu?.[uuid]
    if (ivr?.options?.length) {
      ivr.options.slice(0, 9).forEach(opt => {
        if (opt.ivr_menu_option_dest_type) {
          const child = buildNode(opt.ivr_menu_option_dest_type, opt.ivr_menu_option_dest_target_uuid, opt.ivr_menu_option_dest_external_number, lookup)
          if (child) branches.push({ label: `Press ${opt.ivr_menu_option_digits}`, node: child, color: '#f59e0b' })
        }
      })
    }
  } else if (type === 'ring_group' && uuid) {
    const rg = lookup.ring_group?.[uuid]
    if (rg?.timeout_type) {
      const tn = buildNode(rg.timeout_type, rg.timeout_uuid, rg.timeout_ext_number, lookup)
      if (tn) branches.push({ label: 'Timeout', node: tn, color: '#f97316' })
    }
  } else if (type === 'custom_destination' && uuid) {
    const cd = lookup.custom_destination?.[uuid]
    if (cd?.dest_type) {
      const child = buildNode(cd.dest_type, cd.dest_target_uuid, cd.dest_external_number, lookup)
      if (child) branches.push({ label: null, node: child, color: cfg.lineColor })
    }
  }

  return (
    <div className="flex flex-col items-center">
      <FlowNode type={type} label={label} sublabel={sublabel} />

      {branches.length === 1 && (
        <div className="flex flex-col items-center">
          <Connector label={branches[0].label} color={branches[0].color} />
          <NodeTree node={branches[0].node} lookup={lookup} depth={depth + 1} visited={newVisited} />
        </div>
      )}

      {branches.length > 1 && (
        <BranchConnector branches={branches} lookup={lookup} depth={depth + 1} visited={newVisited} />
      )}
    </div>
  )
}

// ── DID Flow Card ─────────────────────────────────────────────────────────────

function DidFlowCard({ did, lookup }) {
  const [expanded, setExpanded] = useState(true)

  return (
    <div className="rounded-2xl border border-border bg-card overflow-hidden shadow-sm">
      {/* Header */}
      <button
        className="w-full flex items-center justify-between gap-3 px-5 py-4 hover:bg-muted/40 transition-colors"
        onClick={() => setExpanded(e => !e)}
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className={cn(
            'flex h-9 w-9 shrink-0 items-center justify-center rounded-xl',
            'bg-indigo-100 dark:bg-indigo-500/15',
            'border border-indigo-200 dark:border-indigo-500/30',
            'shadow-[0_0_12px_1px_rgba(99,102,241,0.15)] dark:shadow-[0_0_12px_1px_rgba(99,102,241,0.3)]',
          )}>
            <Radio className="h-4 w-4 text-indigo-600 dark:text-indigo-300" />
          </div>
          <div className="text-left min-w-0">
            <div className="font-semibold text-sm text-foreground truncate">
              {did.destination_name || did.destination_number}
            </div>
            <div className="text-xs text-muted-foreground font-mono tracking-wide">
              {did.destination_number}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          {!did.destination_enabled && (
            <span className="text-[10px] px-2 py-0.5 rounded-full bg-muted text-muted-foreground font-medium border border-border">
              Disabled
            </span>
          )}
          <div className="flex h-6 w-6 items-center justify-center rounded-lg text-muted-foreground">
            {expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
          </div>
        </div>
      </button>

      {/* Flow canvas */}
      {expanded && (
        <div className={cn(
          'border-t border-border',
          'bg-gradient-to-b from-indigo-50/60 to-transparent',
          'dark:from-indigo-950/20 dark:to-transparent',
        )}>
          <div className="overflow-x-auto">
            <div className="p-8 flex flex-col items-center min-w-fit">
              <FlowNode
                type="did"
                label={did.destination_name || did.destination_number}
                sublabel={did.destination_name ? did.destination_number : null}
              />

              {did.actions?.length > 0 ? (
                did.actions.map((action, idx) => {
                  const node = buildNode(action.dest_type, action.dest_target_uuid, action.dest_external_number, lookup)
                  if (!node) return null
                  const nodeCfg = NODE_CONFIG[action.dest_type] || NODE_CONFIG.extension
                  return (
                    <div key={idx} className="flex flex-col items-center">
                      <Connector label={idx > 0 ? 'Fallback' : null} color={nodeCfg.lineColor} />
                      <NodeTree node={node} lookup={lookup} depth={1} visited={new Set()} />
                    </div>
                  )
                })
              ) : did.dest_type ? (
                (() => {
                  const node = buildNode(did.dest_type, did.dest_target_uuid, did.dest_external_number, lookup)
                  if (!node) return null
                  const nodeCfg = NODE_CONFIG[did.dest_type] || NODE_CONFIG.extension
                  return (
                    <div className="flex flex-col items-center">
                      <Connector color={nodeCfg.lineColor} />
                      <NodeTree node={node} lookup={lookup} depth={1} visited={new Set()} />
                    </div>
                  )
                })()
              ) : (
                <div className="flex flex-col items-center">
                  <Connector color="#94a3b8" />
                  <div className="rounded-xl border border-dashed border-border px-4 py-2.5 text-xs text-muted-foreground">
                    No destination configured
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Skeleton loader ───────────────────────────────────────────────────────────

function FlowSkeleton() {
  return (
    <div className="flex flex-col gap-3">
      {[1, 2, 3].map(i => (
        <div key={i} className="rounded-2xl border border-border bg-card overflow-hidden">
          <div className="flex items-center gap-3 px-5 py-4">
            <div className="h-9 w-9 rounded-xl bg-muted animate-pulse" />
            <div className="flex-1 space-y-1.5">
              <div className="h-3.5 w-40 rounded bg-muted animate-pulse" />
              <div className="h-2.5 w-28 rounded bg-muted/60 animate-pulse" />
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

// ── Day/Night Switch form dialog ──────────────────────────────────────────────

const EMPTY_CF_FORM = {
  call_flow_name: '',
  call_flow_extension: '',
  call_flow_feature_code: '',
  call_flow_description: '',
  call_flow_enabled: true,
  day_dest:   { ...EMPTY_DEST },
  night_dest: { ...EMPTY_DEST },
}

function cfToForm(cf) {
  return {
    call_flow_name:        cf.call_flow_name        || '',
    call_flow_extension:   cf.call_flow_extension   || '',
    call_flow_feature_code: cf.call_flow_feature_code || '',
    call_flow_description: cf.call_flow_description || '',
    call_flow_enabled:     cf.call_flow_enabled !== false,
    day_dest: {
      type:            cf.day_dest_type            || '',
      target_uuid:     cf.day_dest_target_uuid     || '',
      external_number: cf.day_dest_external_number || '',
    },
    night_dest: {
      type:            cf.night_dest_type            || '',
      target_uuid:     cf.night_dest_target_uuid     || '',
      external_number: cf.night_dest_external_number || '',
    },
  }
}

function formToPayload(f) {
  return {
    call_flow_name:           f.call_flow_name,
    call_flow_extension:      f.call_flow_extension,
    call_flow_feature_code:   f.call_flow_feature_code,
    call_flow_description:    f.call_flow_description,
    call_flow_enabled:        f.call_flow_enabled,
    day_dest_type:            f.day_dest.type            || '',
    day_dest_target_uuid:     f.day_dest.target_uuid     || null,
    day_dest_external_number: f.day_dest.external_number || '',
    night_dest_type:            f.night_dest.type            || '',
    night_dest_target_uuid:     f.night_dest.target_uuid     || null,
    night_dest_external_number: f.night_dest.external_number || '',
  }
}

function CfDialog({ onClose, editItem, onSaved }) {
  const [form, setForm]       = useState(EMPTY_CF_FORM)
  const [saving, setSaving]   = useState(false)
  const { destData, destLoading, destSearchLoading, loadDestData, searchDestData } = useDestinationData()

  useEffect(() => {
    setForm(editItem ? cfToForm(editItem) : { ...EMPTY_CF_FORM, day_dest: { ...EMPTY_DEST }, night_dest: { ...EMPTY_DEST } })
    loadDestData()
  }, [editItem])

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSave = async () => {
    if (!form.call_flow_name.trim()) { toast.error('Name is required'); return }
    setSaving(true)
    try {
      const payload = formToPayload(form)
      if (editItem) {
        await callFlowsApi.update(editItem.call_flow_uuid, payload)
        toast.success('Day/night switch updated')
      } else {
        await callFlowsApi.create(payload)
        toast.success('Day/night switch created')
      }
      onSaved()
    } catch { toast.error('Save failed') }
    finally { setSaving(false) }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={onClose} className="-ml-2 gap-1">
          ← Call Flows
        </Button>
        <span className="text-muted-foreground">/</span>
        <h1 className="text-lg font-semibold">{editItem ? 'Edit' : 'New'} Day/Night Switch</h1>
      </div>

      <Card>
        <div className="space-y-4 px-6 py-5">
          {/* Name */}
          <div className="space-y-1.5">
            <Label>Name <span className="text-destructive">*</span></Label>
            <Input value={form.call_flow_name} onChange={e => set('call_flow_name', e.target.value)} placeholder="e.g. Office Hours Switch" />
          </div>

          <div className="grid grid-cols-2 gap-3">
            {/* Extension */}
            <div className="space-y-1.5">
              <Label>Routing Extension</Label>
              <Input value={form.call_flow_extension} onChange={e => set('call_flow_extension', e.target.value)} placeholder="e.g. 7000" />
              <p className="text-[11px] text-muted-foreground">DIDs transfer here to check day/night status</p>
            </div>
            {/* Feature code */}
            <div className="space-y-1.5">
              <Label>Feature Code</Label>
              <Input value={form.call_flow_feature_code} onChange={e => set('call_flow_feature_code', e.target.value)} placeholder="e.g. *23" />
              <p className="text-[11px] text-muted-foreground">Dial to toggle between day and night</p>
            </div>
          </div>

          {/* Day destination */}
          <div className="space-y-1.5">
            <Label className="flex items-center gap-1.5">
              <Sun className="h-3.5 w-3.5 text-amber-500" /> Day Destination
            </Label>
            {destLoading
              ? <div className="h-9 rounded-md bg-muted animate-pulse" />
              : <DestinationPicker value={form.day_dest} onChange={v => set('day_dest', v)} data={destData} searchLoading={destSearchLoading} onSearch={searchDestData} />
            }
          </div>

          {/* Night destination */}
          <div className="space-y-1.5">
            <Label className="flex items-center gap-1.5">
              <Moon className="h-3.5 w-3.5 text-indigo-500" /> Night Destination
            </Label>
            {destLoading
              ? <div className="h-9 rounded-md bg-muted animate-pulse" />
              : <DestinationPicker value={form.night_dest} onChange={v => set('night_dest', v)} data={destData} searchLoading={destSearchLoading} onSearch={searchDestData} />
            }
          </div>

          {/* Description */}
          <div className="space-y-1.5">
            <Label>Description</Label>
            <Input value={form.call_flow_description} onChange={e => set('call_flow_description', e.target.value)} placeholder="Optional notes" />
          </div>

          {/* Enabled */}
          <div className="flex items-center gap-2">
            <input type="checkbox" id="cf-enabled" checked={form.call_flow_enabled}
              onChange={e => set('call_flow_enabled', e.target.checked)}
              className="h-4 w-4 rounded border-border accent-primary" />
            <Label htmlFor="cf-enabled">Enabled</Label>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={onClose}>Cancel</Button>
            <Button size="sm" onClick={handleSave} disabled={saving}>
              {saving && <Loader2 className="h-3.5 w-3.5 animate-spin mr-1.5" />}
              {editItem ? 'Update' : 'Create'}
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}

// ── Day/Night Switches management section ─────────────────────────────────────

function DayNightSection() {
  const navigate = useNavigate()
  const { id: editParamId } = useParams()
  const location = useLocation()
  const isCreate   = location.pathname.endsWith('/call-flows/new')
  const routeId    = editParamId
  const editorOpen = isCreate || routeId !== undefined

  const { user: authUser } = useSelector(selectAuth)
  const canAdd    = canPerformAction(authUser, 'call-flows', 'add')
  const canEdit   = canPerformAction(authUser, 'call-flows', 'edit')
  const canDelete = canPerformAction(authUser, 'call-flows', 'delete')

  const [switches, setSwitches]   = useState([])
  const [loading, setLoading]     = useState(true)
  const [toggling, setToggling]   = useState(null)
  const [deleting, setDeleting]   = useState(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const { data } = await callFlowsApi.list({ page_size: 200 })
      setSwitches(Array.isArray(data) ? data : data.results || [])
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  const handleToggle = async (cf) => {
    setToggling(cf.call_flow_uuid)
    try {
      const { data } = await callFlowsApi.toggle(cf.call_flow_uuid)
      setSwitches(s => s.map(x => x.call_flow_uuid === cf.call_flow_uuid
        ? { ...x, call_flow_status: data.status } : x))
    } catch { toast.error('Toggle failed') }
    finally { setToggling(null) }
  }

  const handleDelete = async (cf) => {
    if (!confirm(`Delete "${cf.call_flow_name}"?`)) return
    setDeleting(cf.call_flow_uuid)
    try {
      await callFlowsApi.delete(cf.call_flow_uuid)
      toast.success('Deleted')
      load()
    } catch { toast.error('Delete failed') }
    finally { setDeleting(null) }
  }

  const openEdit    = (cf) => navigate(`/call-flows/${cf.call_flow_uuid}/edit`)
  const openNew     = ()   => navigate('/call-flows/new')
  const closeEditor = ()   => navigate('/call-flows')

  // ── Full-page editor (routed) ──────────────────────────────────────────────
  if (editorOpen) {
    const editItem = isCreate
      ? null
      : (switches.find(x => x.call_flow_uuid === routeId) || { call_flow_uuid: routeId })
    return (
      <CfDialog
        editItem={editItem}
        onClose={closeEditor}
        onSaved={() => { load(); closeEditor() }}
      />
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ToggleLeft className="h-4 w-4 text-amber-500" />
          <h2 className="text-sm font-semibold text-foreground">Day/Night Switches</h2>
        </div>
        {canAdd && (<Button size="sm" onClick={openNew} className="h-7 text-xs gap-1">
          <Plus className="h-3.5 w-3.5" /> New Switch
        </Button>)}
      </div>

      <Card>
        <CardContent className="p-0 overflow-x-auto">
          <Table className="min-w-[600px]">
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Ext</TableHead>
                <TableHead>Feature Code</TableHead>
                <TableHead>Day Dest</TableHead>
                <TableHead>Night Dest</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="w-20" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {loading ? (
                [...Array(3)].map((_, i) => (
                  <TableRow key={i}>
                    {[...Array(7)].map((_, j) => (
                      <TableCell key={j}><Skeleton className="h-4 w-full" /></TableCell>
                    ))}
                  </TableRow>
                ))
              ) : switches.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="py-12 text-center text-sm text-muted-foreground">
                    No day/night switches configured.
                  </TableCell>
                </TableRow>
              ) : (
                switches.map(cf => {
                  const isDay     = cf.call_flow_status === 'true'
                  const isToggling = toggling === cf.call_flow_uuid
                  const isDeleting = deleting === cf.call_flow_uuid
                  return (
                    <TableRow key={cf.call_flow_uuid}>
                      <TableCell className="font-medium">{cf.call_flow_name}</TableCell>
                      <TableCell className="font-mono text-sm">{cf.call_flow_extension || '—'}</TableCell>
                      <TableCell className="font-mono text-sm">{cf.call_flow_feature_code || '—'}</TableCell>
                      <TableCell>
                        {cf.day_dest_type
                          ? <Badge variant="outline" className="text-amber-600 border-amber-300 bg-amber-50 dark:bg-amber-900/20 gap-1 text-[11px]">
                              <Sun className="h-2.5 w-2.5" />{cf.day_dest_type.replace('_', ' ')}
                            </Badge>
                          : <span className="text-muted-foreground text-xs">—</span>
                        }
                      </TableCell>
                      <TableCell>
                        {cf.night_dest_type
                          ? <Badge variant="outline" className="text-indigo-600 border-indigo-300 bg-indigo-50 dark:bg-indigo-900/20 gap-1 text-[11px]">
                              <Moon className="h-2.5 w-2.5" />{cf.night_dest_type.replace('_', ' ')}
                            </Badge>
                          : <span className="text-muted-foreground text-xs">—</span>
                        }
                      </TableCell>
                      <TableCell>
                        <button
                          onClick={() => handleToggle(cf)}
                          disabled={isToggling}
                          className={cn(
                            'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold transition-colors',
                            isDay
                              ? 'bg-amber-100 text-amber-700 hover:bg-amber-200 dark:bg-amber-900/30 dark:text-amber-400'
                              : 'bg-indigo-100 text-indigo-700 hover:bg-indigo-200 dark:bg-indigo-900/30 dark:text-indigo-400',
                            isToggling && 'opacity-50 cursor-wait',
                          )}
                        >
                          {isToggling
                            ? <Loader2 className="h-3 w-3 animate-spin" />
                            : isDay ? <Sun className="h-3 w-3" /> : <Moon className="h-3 w-3" />
                          }
                          {isDay ? 'Day' : 'Night'}
                        </button>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1 justify-end">
                          {canEdit && (<Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => openEdit(cf)}>
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>)}
                          {canDelete && (<Button variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:text-destructive"
                            disabled={isDeleting} onClick={() => handleDelete(cf)}>
                            {isDeleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
                          </Button>)}
                        </div>
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function CallFlows() {
  const [loading, setLoading] = useState(true)
  const [dids, setDids]       = useState([])
  const [lookup, setLookup]   = useState({})
  const [search, setSearch]   = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [didsRes, extRes, vmRes, rgRes, ivrRes, confRes, whRes, cdRes] = await Promise.all([
        destinationsApi.list({ page_size: 200 }),
        extensionsApi.list({ page_size: 500 }),
        voicemailsApi.list({ page_size: 500 }),
        ringGroupsApi.list({ page_size: 200 }),
        ivrMenusApi.list({ page_size: 200 }),
        conferencesApi.list({ page_size: 200 }),
        workingHoursApi.list({ page_size: 200 }),
        customDestinationsApi.list({ page_size: 200 }),
      ])
      const get = r => r?.data?.results ?? r?.data ?? []
      setLookup(buildLookup({
        extensions: get(extRes), voicemails: get(vmRes), ringGroups: get(rgRes),
        ivrMenus: get(ivrRes), conferences: get(confRes), workingHours: get(whRes),
        customDestinations: get(cdRes),
      }))
      setDids(get(didsRes))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  const filtered = dids.filter(d => {
    if (!search) return true
    const q = search.toLowerCase()
    return d.destination_number?.toLowerCase().includes(q) || d.destination_name?.toLowerCase().includes(q)
  })

  return (
    <div className="flex flex-col gap-5 p-5 max-w-full">

      {/* Header */}
      <div className="flex items-center gap-3">
        <div className={cn(
          'flex h-10 w-10 items-center justify-center rounded-2xl',
          'bg-indigo-100 dark:bg-indigo-500/15',
          'border border-indigo-200 dark:border-indigo-500/25',
          'shadow-[0_0_20px_2px_rgba(99,102,241,0.12)] dark:shadow-[0_0_20px_2px_rgba(99,102,241,0.25)]',
        )}>
          <GitBranch className="h-5 w-5 text-indigo-600 dark:text-indigo-300" />
        </div>
        <div>
          <h1 className="text-lg font-bold text-foreground tracking-tight">Call Flows</h1>
          <p className="text-xs text-muted-foreground">Day/night switches and inbound routing diagram</p>
        </div>
      </div>

      {/* Day/Night switches management */}
      <DayNightSection />

      {/* Divider */}
      <div className="flex items-center gap-3">
        <div className="h-px flex-1 bg-border" />
        <span className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">Inbound Flow Diagram</span>
        <div className="h-px flex-1 bg-border" />
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-1.5">
        {Object.entries(NODE_CONFIG).filter(([k]) => k !== 'did').map(([type, cfg]) => {
          const Icon = cfg.icon
          return (
            <div
              key={type}
              className="flex items-center gap-1.5 rounded-lg px-2 py-1 border border-border bg-card text-[10px] font-medium"
            >
              <Icon className={cn('h-3 w-3', cfg.iconColor)} />
              <span className={cfg.tagColor}>{cfg.label}</span>
            </div>
          )
        })}
      </div>

      {/* DID search */}
      <div className="relative w-56">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
        <Input
          placeholder="Search DIDs..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="pl-8 h-8 text-sm"
        />
      </div>

      {/* Content */}
      {loading ? (
        <FlowSkeleton />
      ) : filtered.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-24 gap-3">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted border border-border">
            <Phone className="h-6 w-6 text-muted-foreground/40" />
          </div>
          <p className="text-sm text-muted-foreground">
            {search ? 'No DIDs match your search.' : 'No DIDs configured yet.'}
          </p>
        </div>
      ) : (
        <div className="flex flex-col gap-3">
          {filtered.map(did => (
            <DidFlowCard key={did.destination_uuid} did={did} lookup={lookup} />
          ))}
        </div>
      )}
    </div>
  )
}
