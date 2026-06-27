'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Activity, Search, MapPin, Calendar, Package, ChevronRight } from 'lucide-react'

const API = process.env.NEXT_PUBLIC_API_URL

const STATUS_COLORS: Record<string, string> = {
  DRAFT:      'bg-gray-100 text-gray-600',
  READY:      'bg-blue-100 text-blue-700',
  PLANNED:    'bg-purple-100 text-purple-700',
  IN_TRANSIT: 'bg-indigo-100 text-indigo-700',
  DELIVERED:  'bg-green-100 text-green-700',
  CANCELLED:  'bg-red-100 text-red-600',
  CLOSED:     'bg-gray-100 text-gray-500',
}

const PRIORITY_COLORS: Record<string, string> = {
  High:   'text-red-600 font-semibold',
  Medium: 'text-amber-600',
  Low:    'text-gray-400',
}

export default function OrderReleasesPage() {
  const [releases, setReleases] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(0)
  const limit = 20

  useEffect(() => {
    const token = localStorage.getItem('tms_token')
    const params = new URLSearchParams({ limit: String(limit), offset: String(page * limit) })
    if (status) params.set('status', status)
    if (search) params.set('search', search)
    setLoading(true)
    fetch(`${API}/order-releases/?${params}`, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => r.json())
      .then(d => { setReleases(d.data || []); setTotal(d.total || 0); setLoading(false) })
  }, [search, status, page])

  const totalPages = Math.ceil(total / limit)

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Activity className="text-blue-600" size={24} /> Order Releases
          </h1>
          <p className="text-sm text-gray-500 mt-1">{total} release{total !== 1 ? 's' : ''} — linked to POs and shipments</p>
        </div>
      </div>
      <div className="flex gap-3 mb-5">
        <div className="relative flex-1 max-w-sm">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={search} onChange={e => { setSearch(e.target.value); setPage(0) }}
            placeholder="Search by release #, PO, customer..."
            className="pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <select value={status} onChange={e => { setStatus(e.target.value); setPage(0) }}
          className="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="">All Statuses</option>
          {['DRAFT','READY','PLANNED','IN_TRANSIT','DELIVERED','CANCELLED','CLOSED'].map(s => (
            <option key={s} value={s}>{s.replace('_', ' ')}</option>
          ))}
        </select>
      </div>
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {['Release #','PO','Customer','Route','Ship Date','Mode','Lines','Priority','Status',''].map(h => (
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={10} className="text-center py-12 text-gray-400">Loading...</td></tr>
            ) : releases.length === 0 ? (
              <tr><td colSpan={10} className="text-center py-12 text-gray-400">No releases found</td></tr>
            ) : releases.map((r: any) => (
              <tr key={r.order_release_id} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3">
                  <Link href={`/order-releases/${r.order_release_id}`} className="font-mono font-semibold text-blue-600 hover:underline">
                    {r.order_release_number}
                  </Link>
                </td>
                <td className="px-4 py-3">
                  {r.po_id ? (
                    <Link href={`/purchase-orders/${r.po_id}`} className="text-gray-600 hover:text-blue-600 font-mono text-xs">{r.po_number}</Link>
                  ) : <span className="text-gray-400">—</span>}
                </td>
                <td className="px-4 py-3 text-gray-700">{r.customer_name || '—'}</td>
                <td className="px-4 py-3">
                  <div className="flex items-center gap-1 text-xs text-gray-500">
                    <MapPin size={11} className="text-gray-400 shrink-0" />
                    {r.shipper_city}, {r.shipper_state} → {r.consignee_city}, {r.consignee_state}
                  </div>
                </td>
                <td className="px-4 py-3 text-xs text-gray-500">
                  {r.requested_ship_date ? new Date(r.requested_ship_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '—'}
                </td>
                <td className="px-4 py-3 text-gray-600 text-xs">{r.transport_mode || '—'}</td>
                <td className="px-4 py-3 text-xs text-gray-600">{r.line_count ?? '—'}</td>
                <td className="px-4 py-3">
                  <span className={`text-xs ${PRIORITY_COLORS[r.priority] || 'text-gray-500'}`}>{r.priority || '—'}</span>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${STATUS_COLORS[r.status_code] || 'bg-gray-100 text-gray-600'}`}>
                    {r.status_name || r.status_code}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <Link href={`/order-releases/${r.order_release_id}`} className="text-gray-400 hover:text-blue-600">
                    <ChevronRight size={16} />
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {totalPages > 1 && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-gray-100 bg-gray-50">
            <p className="text-xs text-gray-500">Showing {page * limit + 1}–{Math.min((page + 1) * limit, total)} of {total}</p>
            <div className="flex gap-2">
              <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
                className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-white">Previous</button>
              <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}
                className="px-3 py-1.5 text-xs border border-gray-200 rounded-lg disabled:opacity-40 hover:bg-white">Next</button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
