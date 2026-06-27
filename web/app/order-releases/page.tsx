'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Layers, Search } from 'lucide-react'
import { apiFetch, fmtDate, fmtCurrency, statusColor } from '../../lib/api'

export default function OrderReleasesPage() {
  const [releases, setReleases] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  useEffect(() => {
    const params = new URLSearchParams({ limit: '100' })
    if (statusFilter) params.set('status', statusFilter)
    apiFetch(`/order-releases/?${params}`)
      .then(d => { setReleases(Array.isArray(d) ? d : d.data || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [statusFilter])

  const filtered = releases.filter(r =>
    !search ||
    r.release_number?.toLowerCase().includes(search.toLowerCase()) ||
    r.customer_name?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Layers className="text-blue-600" size={24} /> Order Releases
          </h1>
          <p className="text-sm text-gray-500 mt-1">Transportation order releases linked to PO lines</p>
        </div>
      </div>

      <div className="flex gap-3 mb-4">
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search release number..."
            className="pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="">All Statuses</option>
          {['open','planned','tendered','shipped','delivered','closed','canceled'].map(s => (
            <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
          ))}
        </select>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {['Release #', 'Customer', 'Origin', 'Destination', 'Pickup', 'Delivery', 'Mode', 'Weight', 'Status', ''].map(h => (
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={10} className="text-center py-12 text-gray-400">Loading releases...</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={10} className="text-center py-12 text-gray-400">No order releases found</td></tr>
            ) : filtered.map((r: any) => (
              <tr key={r.order_release_id} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3 font-mono font-medium text-blue-600">
                  <Link href={`/order-releases/${r.order_release_id}`}>{r.release_number}</Link>
                </td>
                <td className="px-4 py-3 text-gray-700">{r.customer_name || '—'}</td>
                <td className="px-4 py-3 text-gray-600 text-xs">{r.origin_location_name || r.origin_location_id?.slice(0,8) || '—'}</td>
                <td className="px-4 py-3 text-gray-600 text-xs">{r.destination_location_name || r.destination_location_id?.slice(0,8) || '—'}</td>
                <td className="px-4 py-3 text-gray-500">{fmtDate(r.requested_pickup_date)}</td>
                <td className="px-4 py-3 text-gray-500">{fmtDate(r.requested_delivery_date)}</td>
                <td className="px-4 py-3 text-gray-600 uppercase text-xs">{r.transport_mode || '—'}</td>
                <td className="px-4 py-3 text-gray-600">{r.total_weight ? `${r.total_weight} ${r.weight_uom || 'lbs'}` : '—'}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium capitalize ${statusColor(r.release_status)}`}>
                    {r.release_status?.replace(/_/g, ' ') || '—'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <Link href={`/order-releases/${r.order_release_id}`} className="text-blue-600 hover:underline text-xs">View →</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
