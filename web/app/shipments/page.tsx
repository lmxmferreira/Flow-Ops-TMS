'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Truck, Search, MapPin } from 'lucide-react'
import { apiFetch, fmtDate, fmtCurrency, statusColor } from '../../lib/api'

const STAGE_COLORS: Record<string, string> = {
  planned: 'bg-gray-100 text-gray-600',
  dispatched: 'bg-blue-100 text-blue-700',
  in_transit: 'bg-indigo-100 text-indigo-700',
  delivered: 'bg-green-100 text-green-700',
  accepted: 'bg-purple-100 text-purple-700',
  exception: 'bg-red-100 text-red-700',
  closed: 'bg-gray-50 text-gray-400',
  costed: 'bg-teal-100 text-teal-700',
}

export default function ShipmentsPage() {
  const [shipments, setShipments] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [stageFilter, setStageFilter] = useState('')

  useEffect(() => {
    apiFetch(`/shipments/?limit=100`)
      .then(d => { setShipments(d.data || d || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const filtered = shipments.filter(s => {
    const matchSearch = !search ||
      s.shipment_number?.toLowerCase().includes(search.toLowerCase()) ||
      s.carrier_name?.toLowerCase().includes(search.toLowerCase()) ||
      s.customer_name?.toLowerCase().includes(search.toLowerCase())
    const matchStage = !stageFilter || s.current_stage === stageFilter
    return matchSearch && matchStage
  })

  const stages = [...new Set(shipments.map(s => s.current_stage).filter(Boolean))]

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Truck className="text-blue-600" size={24} /> Shipments
          </h1>
          <p className="text-sm text-gray-500 mt-1">Plan, dispatch, and track all shipments</p>
        </div>
      </div>

      {/* Stage summary pills */}
      <div className="flex gap-2 mb-4 flex-wrap">
        <button onClick={() => setStageFilter('')}
          className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${!stageFilter ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'}`}>
          All ({shipments.length})
        </button>
        {stages.map(s => (
          <button key={s} onClick={() => setStageFilter(s === stageFilter ? '' : s)}
            className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${stageFilter === s ? 'bg-blue-600 text-white' : `${STAGE_COLORS[s] || 'bg-gray-100 text-gray-600'} hover:opacity-80`}`}>
            {s.replace(/_/g, ' ')} ({shipments.filter(sh => sh.current_stage === s).length})
          </button>
        ))}
      </div>

      <div className="flex gap-3 mb-4">
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search shipments..."
            className="pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {['Shipment #', 'Carrier', 'Customer', 'Origin → Dest', 'Pickup', 'Delivery', 'Cost', 'Stage', ''].map(h => (
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={9} className="text-center py-12 text-gray-400">Loading shipments...</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={9} className="text-center py-12 text-gray-400">No shipments found</td></tr>
            ) : filtered.map((s: any) => (
              <tr key={s.shipment_id} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3 font-mono font-medium text-blue-600">
                  <Link href={`/shipments/${s.shipment_id}`}>{s.shipment_number}</Link>
                </td>
                <td className="px-4 py-3 text-gray-700">{s.carrier_name || '—'}</td>
                <td className="px-4 py-3 text-gray-600">{s.customer_name || '—'}</td>
                <td className="px-4 py-3 text-gray-500 text-xs">
                  <div className="flex items-center gap-1">
                    <MapPin size={10} className="text-gray-400" />
                    {[s.origin_city, s.destination_city].filter(Boolean).join(' → ') || '—'}
                  </div>
                </td>
                <td className="px-4 py-3 text-gray-500">{fmtDate(s.planned_pickup_date)}</td>
                <td className="px-4 py-3 text-gray-500">{fmtDate(s.planned_delivery_date)}</td>
                <td className="px-4 py-3 font-medium">{s.total_cost ? fmtCurrency(s.total_cost) : '—'}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${STAGE_COLORS[s.current_stage] || 'bg-gray-100 text-gray-500'}`}>
                    {s.current_stage?.replace(/_/g, ' ') || 'planned'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <Link href={`/shipments/${s.shipment_id}`} className="text-blue-600 hover:underline text-xs">View →</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
