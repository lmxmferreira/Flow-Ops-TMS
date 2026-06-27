'use client'
import { useEffect, useState } from 'react'
import { Calendar, Truck, MapPin, Clock } from 'lucide-react'
import { apiFetch, fmtDate, statusColor } from '../../lib/api'

export default function YardPage() {
  const [appointments, setAppointments] = useState<any[]>([])
  const [gateLog, setGateLog] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<'appointments'|'gate'>('appointments')
  const [dateFilter, setDateFilter] = useState(new Date().toISOString().slice(0,10))

  useEffect(() => {
    const params = new URLSearchParams({ limit: '50' })
    if (dateFilter) params.set('date', dateFilter)
    Promise.all([
      apiFetch(`/ops/appointments?${params}`).catch(() => []),
      apiFetch(`/ops/gate?limit=50`).catch(() => []),
    ]).then(([a, g]) => {
      setAppointments(Array.isArray(a) ? a : [])
      setGateLog(Array.isArray(g) ? g : [])
      setLoading(false)
    })
  }, [dateFilter])

  const APT_COLORS: Record<string, string> = {
    confirmed: 'bg-green-100 text-green-700',
    cancelled: 'bg-gray-100 text-gray-500',
    no_show: 'bg-red-100 text-red-700',
    completed: 'bg-blue-100 text-blue-700',
    rescheduled: 'bg-yellow-100 text-yellow-700',
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Calendar className="text-teal-600" size={24} /> Yard & Gate Management
        </h1>
        <p className="text-sm text-gray-500 mt-1">Appointments, dock scheduling, gate check-in/out, and yard inventory</p>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-3 mb-5">
        {[
          ['Appointments Today', appointments.length],
          ['No Shows', appointments.filter(a => a.no_show).length],
          ['Gate Transactions', gateLog.length],
        ].map(([label, val]) => (
          <div key={label as string} className="bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{label}</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">{val}</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex items-center gap-3 mb-4">
        <div className="flex gap-1 bg-gray-100 p-1 rounded-lg w-fit">
          {(['appointments', 'gate'] as const).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-1.5 text-sm font-medium rounded-md ${tab === t ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'}`}>
              {t.charAt(0).toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
        {tab === 'appointments' && (
          <input type="date" value={dateFilter} onChange={e => setDateFilter(e.target.value)}
            className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-teal-500" />
        )}
      </div>

      {tab === 'appointments' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>{['Apt #','Type','Location','Dock','Carrier','Scheduled','Duration','Arrival','Detention','Status'].map(h =>
                <th key={h} className="text-left px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              )}</tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? <tr><td colSpan={10} className="text-center py-12 text-gray-400">Loading...</td></tr>
              : appointments.length === 0 ? <tr><td colSpan={10} className="text-center py-12 text-gray-400">No appointments for this date</td></tr>
              : appointments.map((a: any) => (
                <tr key={a.appointment_id} className="hover:bg-gray-50">
                  <td className="px-3 py-3 font-mono text-xs text-teal-700">{a.appointment_number}</td>
                  <td className="px-3 py-3 capitalize text-gray-600 text-xs">{a.appointment_type}</td>
                  <td className="px-3 py-3 text-gray-500 text-xs">{a.location_name || '—'}</td>
                  <td className="px-3 py-3 font-mono text-xs text-gray-500">{a.dock_door_code || '—'}</td>
                  <td className="px-3 py-3 text-gray-600 text-xs">{a.carrier_name || '—'}</td>
                  <td className="px-3 py-3 text-gray-500 text-xs">{a.appointment_start_datetime ? new Date(a.appointment_start_datetime).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) : '—'}</td>
                  <td className="px-3 py-3 text-gray-500">{a.duration_minutes}m</td>
                  <td className="px-3 py-3 text-gray-500 text-xs">{a.actual_arrival ? new Date(a.actual_arrival).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) : '—'}</td>
                  <td className="px-3 py-3">{a.detention_minutes ? <span className="text-red-600 font-medium text-xs">{a.detention_minutes}m</span> : <span className="text-gray-400 text-xs">—</span>}</td>
                  <td className="px-3 py-3"><span className={`px-2 py-0.5 rounded-full text-xs font-medium ${APT_COLORS[a.status] || 'bg-gray-100 text-gray-600'}`}>{a.status || 'scheduled'}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'gate' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>{['Transaction #','Type','Carrier','Driver','Tractor','Trailer','Container','Seal','At','Empty'].map(h =>
                <th key={h} className="text-left px-3 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              )}</tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? <tr><td colSpan={10} className="text-center py-12 text-gray-400">Loading...</td></tr>
              : gateLog.length === 0 ? <tr><td colSpan={10} className="text-center py-12 text-gray-400">No gate transactions</td></tr>
              : gateLog.map((g: any) => (
                <tr key={g.gate_transaction_id} className="hover:bg-gray-50">
                  <td className="px-3 py-3 font-mono text-xs text-teal-700">{g.gate_transaction_number}</td>
                  <td className="px-3 py-3"><span className={`px-2 py-0.5 rounded-full text-xs font-medium ${g.transaction_type === 'check_in' ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>{g.transaction_type?.replace('_',' ')}</span></td>
                  <td className="px-3 py-3 text-gray-600 text-xs">{g.carrier_name || '—'}</td>
                  <td className="px-3 py-3 text-gray-600 text-xs">{g.driver_name || '—'}</td>
                  <td className="px-3 py-3 font-mono text-xs text-gray-500">{g.tractor_number || '—'}</td>
                  <td className="px-3 py-3 font-mono text-xs text-gray-500">{g.trailer_number || '—'}</td>
                  <td className="px-3 py-3 font-mono text-xs text-gray-500">{g.container_number || '—'}</td>
                  <td className="px-3 py-3 font-mono text-xs text-gray-500">{g.seal_number || '—'}</td>
                  <td className="px-3 py-3 text-gray-500 text-xs">{g.transaction_at ? new Date(g.transaction_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) : '—'}</td>
                  <td className="px-3 py-3">{g.is_empty ? <span className="text-xs text-gray-400">Empty</span> : <span className="text-xs text-blue-600">Loaded</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
