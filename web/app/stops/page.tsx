'use client'
import { useEffect, useState } from 'react'
import { MapPin, Search } from 'lucide-react'
import { apiFetch, fmtDate, statusColor } from '../../lib/api'

export default function StopsPage() {
  const [stops, setStops] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  useEffect(() => {
    apiFetch('/shipment-stops/?limit=100').catch(() => apiFetch('/stops/?limit=100').catch(() => []))
      .then(d => { setStops(Array.isArray(d) ? d : d.data || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const filtered = stops.filter(s => !search || s.location_name?.toLowerCase().includes(search.toLowerCase()))

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><MapPin className="text-green-600" size={24}/> Stop Management</h1>
        <p className="text-sm text-gray-500 mt-1">Track stop activities, arrivals, departures, and confirmations</p>
      </div>
      <div className="relative max-w-xs mb-4">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"/>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search stops..." className="pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-blue-500"/>
      </div>
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>{['Stop #','Shipment','Location','Type','Planned Arrival','Actual Arrival','Status'].map(h => <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? <tr><td colSpan={7} className="text-center py-12 text-gray-400">Loading stops...</td></tr>
            : filtered.length === 0 ? <tr><td colSpan={7} className="text-center py-12 text-gray-400">No stops found</td></tr>
            : filtered.map((s: any) => (
              <tr key={s.shipment_stop_id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-mono text-xs text-green-700">{s.stop_sequence || '—'}</td>
                <td className="px-4 py-3 font-mono text-xs text-gray-500">{s.shipment_number || s.shipment_id?.slice(0,12) || '—'}</td>
                <td className="px-4 py-3 text-gray-700">{s.location_name || s.city || '—'}</td>
                <td className="px-4 py-3 capitalize text-gray-500">{s.stop_type || '—'}</td>
                <td className="px-4 py-3 text-gray-500">{fmtDate(s.planned_arrival_datetime || s.planned_arrival)}</td>
                <td className="px-4 py-3 text-gray-500">{s.actual_arrival_datetime ? fmtDate(s.actual_arrival_datetime) : '—'}</td>
                <td className="px-4 py-3"><span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(s.stop_status || 'pending')}`}>{s.stop_status || 'pending'}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
