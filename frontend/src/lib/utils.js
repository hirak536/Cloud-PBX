import { clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs) {
  return twMerge(clsx(inputs))
}

export function formatDuration(seconds) {
  if (!seconds) return '0:00'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function formatDate(str) {
  if (!str) return '—'
  // Ensure the string is treated as UTC (append Z if no timezone info present)
  const normalized = /[Zz]|[+-]\d{2}:?\d{2}$/.test(str) ? str : str.replace(' ', 'T') + 'Z'
  return new Date(normalized).toLocaleString()
}
