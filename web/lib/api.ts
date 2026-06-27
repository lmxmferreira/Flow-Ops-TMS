// lib/api.ts — shared API client for Flow Ops TMS

export const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1'

export function token() {
  if (typeof window === 'undefined') return ''
  return localStorage.getItem('tms_token') || ''
}

export function authHeaders() {
  return { Authorization: `Bearer ${token()}`, 'Content-Type': 'application/json' }
}

export async function apiFetch(path: string, options?: RequestInit) {
  const res = await fetch(`${API}${path}`, {
    ...options,
    headers: { ...authHeaders(), ...(options?.headers || {}) },
  })
  if (res.status === 401) {
    localStorage.removeItem('tms_token')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
  if (!res.ok) throw new Error(`API error ${res.status}`)
  return res.json()
}

export async function apiPost(path: string, body: any) {
  return apiFetch(path, { method: 'POST', body: JSON.stringify(body) })
}

export async function apiPatch(path: string, body: any) {
  return apiFetch(path, { method: 'PATCH', body: JSON.stringify(body) })
}

// Format helpers
export const fmtCurrency = (n: any) =>
  `$${parseFloat(n || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`

export const fmtDate = (d: any) => d ? new Date(d).toLocaleDateString() : '—'

export const fmtDateTime = (d: any) => d ? new Date(d).toLocaleString() : '—'

export function statusColor(status: string, map?: Record<string, string>) {
  const defaults: Record<string, string> = {
    active: 'bg-green-100 text-green-700',
    open: 'bg-blue-100 text-blue-700',
    pending: 'bg-yellow-100 text-yellow-700',
    closed: 'bg-gray-100 text-gray-500',
    draft: 'bg-gray-100 text-gray-600',
    approved: 'bg-green-100 text-green-700',
    rejected: 'bg-red-100 text-red-700',
    paid: 'bg-emerald-100 text-emerald-700',
    disputed: 'bg-orange-100 text-orange-700',
    exception: 'bg-red-100 text-red-700',
    matched: 'bg-green-100 text-green-700',
    sent: 'bg-blue-100 text-blue-700',
    cancelled: 'bg-gray-100 text-gray-500',
    canceled: 'bg-gray-100 text-gray-500',
    in_transit: 'bg-indigo-100 text-indigo-700',
    delivered: 'bg-emerald-100 text-emerald-700',
    dispatched: 'bg-blue-100 text-blue-700',
    received: 'bg-purple-100 text-purple-700',
    exported: 'bg-teal-100 text-teal-700',
    overridden: 'bg-orange-100 text-orange-700',
    resolved: 'bg-green-100 text-green-700',
    escalated: 'bg-red-100 text-red-700',
    confirmed: 'bg-green-100 text-green-700',
    warning: 'bg-yellow-100 text-yellow-700',
    error: 'bg-red-100 text-red-700',
    critical: 'bg-red-200 text-red-800',
    ...map,
  }
  return defaults[status] || 'bg-gray-100 text-gray-600'
}
