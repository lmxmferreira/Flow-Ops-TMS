'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Navigation, Search, MapPin, AlertTriangle, Clock, CheckCircle } from 'lucide-react'

const API = process.env.NEXT_PUBLIC_API_URL

const STAGE_COLOR: Record<string, string> = {
  planned: 'bg-gray-100 text-gray-600',
  dispatched: 'bg-blue-100 text-blue-700',
  in_transit: 'bg-indigo-100 text-indigo-700',
  delivered: 'bg-green-100 text-green-700',
  accepted: 'bg-purple-100 text-purple-700',
  exception: 'bg-red-100 text-red-700',
  closed: 'bg-gray-100 text-gray-500',
}

export default function ExecutionPage() {
  const [shipments, setShipments] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [alerts, setAlerts] = useState<any[]>([])

  useEffect(() => {
    const token = localStorage.getItem('tms_token')
    Promise.all([
      fetch(`${API}/shipments/?limit=50`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json()),
      fetch(`${API}/execution/alerts/dashboard`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json()),
    ]).then(([shp, al]) => {
      setShipments(shp.data || [])
      setAlerts(al.alerts || [])
      setLoading(false)
    })
  }, [])

  const filtered = shipments.filter(s =>
    !search || s.shipment_number?.toLowerCase().includes(search.toLowerCase()) ||
    s.carrier_name?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Navigation className="text-blue-600" size={24} /> Execution & Tracking
          </h1>
          <p className="text-sm text-gray-500 mt-1">Dispatch, track milestones, and manage exceptions</p>
        </div>
      </div>

      {/* Alert summary */}
      {alerts.length > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-6 flex items-start gap-3">
          <AlertTriangle size={18} className="text-red-500 mt-0.5 shrink-0" />
          <div>
            <p className="text-sm font-semibold text-red-800">{alerts.length} open exception{alerts.length !== 1 ? 's' : ''} require attention</p>
            <div className="flex flex-wrap gap-2 mt-2">
              {alerts.slice(0,3).map((a: any) => (
                <Link key={a.alert_id} href={`/execution/${a.shipment_id}`}
                  className="text-xs bg-white border border-red-200 rounded px-2 py-1 text-red-700 hover:bg-red-100">
                  {a.shipment_number} — {a.alert_type?.replace(/_/g,' ')}
                </Link>
              ))}
              {alerts.length > 3 && <span className="text-xs text-red-600">+{alerts.length-3} more</span>}
            </div>
          </div>
        </div>
      )}

      {/* Search */}
      <div className="relative max-w-sm mb-4">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input value={search} onChange={e => setSearch(e.target.value)}
          placeholder="Search shipments..." className="pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-blue-500" />
      </div>

      {/* Shipment execution table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {['Shipment','Carrier','Route','Stage','Last Event','ETA',''].map(h => (
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={7} className="text-center py-12 text-gray-400">Loading...</td></tr>
            ) : filtered.map((s: any) => (
              <tr key={s.shipment_id} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3 font-mono font-medium text-blue-600">
                  <Link href={`/execution/${s.shipment_id}`}>{s.shipment_number}</Link>
                </td>
                <td className="px-4 py-3 text-gray-700">{s.carrier_name || '—'}</td>
                <td className="px-4 py-3 text-gray-600 text-xs">
                  <div className="flex items-center gap-1">
                    <MapPin size={11} className="text-gray-400" />
                    {s.origin_city}, {s.origin_state} → {s.destination_city}, {s.destination_state}
                  </div>
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium capitalize ${STAGE_COLOR[s.status_code?.toLowerCase()] || 'bg-gray-100 text-gray-600'}`}>
                    {s.status_name || s.status_code || 'planned'}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-500 text-xs">—</td>
                <td className="px-4 py-3 text-gray-500 text-xs">
                  {s.planned_delivery_datetime ? new Date(s.planned_delivery_datetime).toLocaleDateString() : '—'}
                </td>
                <td className="px-4 py-3">
                  <Link href={`/execution/${s.shipment_id}`} className="text-blue-600 hover:underline text-xs">Track →</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
