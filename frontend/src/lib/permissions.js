// ── Page-based permissions ────────────────────────────────────────────────────
// Single source of truth for what each role may see/do.
// Role tiers (highest → lowest): superuser ⊃ admin ⊃ user.

export function roleOf(user) {
  if (user?.is_superuser) return 'superuser'
  if (user?.is_staff) return 'admin'
  return 'user'
}

// True if a user of `role` is allowed an item tagged with `requiredRole`.
// Untagged items (requiredRole falsy) are visible to everyone.
export function hasRole(role, requiredRole) {
  if (!requiredRole) return true
  if (requiredRole === 'superuser') return role === 'superuser'
  if (requiredRole === 'admin') return role === 'superuser' || role === 'admin'
  return true
}

// Minimum role required to access a given route path.
// Paths not listed are open to any authenticated user.
// Keep this in sync with the Sidebar nav `role` tags.
export const PAGE_ROLES = {
  'tenants':            'admin',
  'audit-log':          'admin',
  'super-users':        'superuser',
  'tenant-list':        'superuser',
  'domains':            'superuser',
  'gateways':           'superuser',
  'outbound-routes':    'superuser',
  'firewall':           'superuser',
  'global-active-calls':'superuser',
  'freeswitch':         'superuser',
  'freeswitch-log':     'superuser',
  'api-keys':           'superuser',
  'system-log':         'superuser',
  'admin-cdr':          'superuser',
  'admin-inventory':    'superuser',
}

// Which UC/PBX user roles a given role is allowed to create.
// superuser → can create admins + users; admin → users only.
export function creatableRoles(role) {
  if (role === 'superuser') return ['superuser', 'admin', 'user']
  if (role === 'admin') return ['user']
  return []
}

// ── Per-user page grants ───────────────────────────────────────────────────────
// Standard ('user') accounts only see pages explicitly granted to them via the
// user's `allowed_pages` list. Admins/superusers ignore this list and get full
// role-based access.
//
// GRANTABLE_PAGES is the catalog an admin can assign from — it is the set of
// pages NOT gated behind an admin/superuser role (i.e. not in PAGE_ROLES). The
// Dashboard (stored as 'dashboard', route '/') is grantable like any other page.
// Each entry's `path` is what gets stored in allowed_pages. Keep labels/groups in
// sync with the Sidebar.
export const GRANTABLE_PAGES = [
  { group: 'General', items: [
    { path: 'dashboard',           label: 'Dashboard' },
  ]},
  { group: 'Call Management', items: [
    { path: 'extensions',          label: 'Extensions' },
    { path: 'ring-groups',         label: 'Ring Groups' },
    { path: 'ivr-menus',           label: 'IVR Menus' },
    { path: 'call-flows',          label: 'Call Flows' },
    { path: 'destinations',        label: 'DIDs' },
    { path: 'custom-destinations', label: 'Custom Destinations' },
    { path: 'working-hours',       label: 'Working Hours' },
    { path: 'call-centers',        label: 'Call Centers' },
  ]},
  { group: 'Communication', items: [
    { path: 'voicemails',          label: 'Voicemails' },
    { path: 'voicemail-inbox',     label: 'Voicemail Inbox' },
    { path: 'conferences',         label: 'Conferences' },
    { path: 'call-parking',        label: 'Call Parking' },
    { path: 'fax',                 label: 'Fax' },
  ]},
  { group: 'System', items: [
    { path: 'media-files',         label: 'Media Files' },
    { path: 'dialplans',           label: 'Dialplans' },
    { path: 'devices',             label: 'Devices' },
  ]},
  { group: 'Reports', items: [
    { path: 'cdr',                 label: 'Call Detail Records' },
    { path: 'call-recordings',     label: 'Call Recordings' },
    { path: 'stats-report',        label: 'Stats Report' },
  ]},
  { group: 'Monitoring', items: [
    { path: 'active-calls',        label: 'Active Calls' },
    { path: 'registrations',       label: 'Peer Status' },
  ]},
]

// Flat list of all grantable page paths.
export const GRANTABLE_PATHS = GRANTABLE_PAGES.flatMap(g => g.items.map(i => i.path))

// ── Per-page action grants ─────────────────────────────────────────────────────
// Pages opted into action-level (view/add/edit/delete) control. Only these pages
// expose action checkboxes in the user editor and are enforced per-action on the
// backend (see core.permissions._PAGE_PERMISSION_PREFIXES). A page not listed
// here keeps page-level-only behavior: access to the page implies all actions.
// Keys must match the page path stored in allowed_pages.
export const ACTIONS = ['view', 'add', 'edit', 'delete']

export const ACTION_LABELS = {
  view:   'View',
  add:    'Create',
  edit:   'Edit',
  delete: 'Delete',
}

export const ACTION_CONTROLLED_PAGES = [
  'extensions',
  'ring-groups',
  'ivr-menus',
  'call-flows',
  'destinations',
  'voicemails',
  'call-centers',
  'conferences',
  'working-hours',
]

// True if `user` may perform `action` ('view'|'add'|'edit'|'delete') on `page`.
// - Superusers and admins (any is_staff) bypass — full access, like allowed_pages.
// - For pages NOT under action control, access to the page implies all actions.
// - For standard users on an action-controlled page, the action must be present
//   in allowed_actions[page].
export function canPerformAction(user, page, action) {
  if (roleOf(user) !== 'user') return true
  if (!ACTION_CONTROLLED_PAGES.includes(page)) return true
  const grants = user?.allowed_actions && typeof user.allowed_actions === 'object'
    ? user.allowed_actions
    : {}
  const allowed = Array.isArray(grants[page]) ? grants[page] : []
  return allowed.includes(action)
}

// True if `user` may access the route identified by `page` (path without slash).
// - Role-gated pages (in PAGE_ROLES) use the role tier check.
// - For standard users, other pages require an explicit grant in allowed_pages.
// - Admins/superusers always pass non-role-gated pages.
export function canAccessPage(user, page) {
  const role = roleOf(user)
  const required = PAGE_ROLES[page]
  if (required) return hasRole(role, required)
  if (role !== 'user') return true
  // Standard user: only granted pages. The Dashboard ('dashboard') is gated like
  // any other page — it must be explicitly granted.
  const granted = Array.isArray(user?.allowed_pages) ? user.allowed_pages : []
  return granted.includes(page)
}

// Resolve a route path (e.g. '/', '/fax') to its page key used in allowed_pages.
// The root route maps to the 'dashboard' grant key.
export function pageKeyOf(routePath) {
  const stripped = routePath.replace(/^\//, '')
  return stripped === '' ? 'dashboard' : stripped
}

// The path a user should land on after login or when bounced from a denied page.
// Prefers the Dashboard when granted, otherwise the first page the user can see.
// Falls back to '/' (which itself may be denied, but avoids an undefined target).
export function landingPath(user) {
  if (roleOf(user) !== 'user') return '/'
  if (canAccessPage(user, 'dashboard')) return '/'
  const granted = Array.isArray(user?.allowed_pages) ? user.allowed_pages : []
  const first = GRANTABLE_PATHS.find(p => p !== 'dashboard' && granted.includes(p))
  return first ? `/${first}` : '/'
}
