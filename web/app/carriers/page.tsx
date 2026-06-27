'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Users, Search, Star, Award } from 'lucide-react'
import { apiFetch, statusColor } from '../../lib/api'

export default function CarriersPage() {
  const [carriers, setCarriers] = useState<any[]>([])
  const [scorecards, setScorecards] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [tab, setTab] = useState<'carriers' | 'scorecards'>('carriers')

  useEffect(() => {
    Promise.all([
      apiFetch('/carrier-mgmt/carriers').catch(() => []),
      apiFetch('/carrier-mgmt/scorecards').catch(() => []),
    ]).then(([c, s]) => {
      setCarriers(Array.isArray(c) ? c : [])
      setScorecards(Array.isArray(s) ? s : [])
      setLoading(false)
    })
  }, [])

  const filteredCarriers = carriers.filter(c =>
    !search || c.carrier_name?.toLowerCase().includes(search.toLowerCase()) ||
    c.scac?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Users className="text-blue-600" size={24} /> Carrier Management
          </h1>
          <p className="text-sm text-gray-500 mt-1">Manage carriers, tenders, and performance scorecards</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 bg-gray-100 p-1 rounded-lg w-fit">
        {(['carriers', 'scorecards'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${tab === t ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === 'carriers' && (
        <>
          <div className="relative max-w-xs mb-4">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Search carriers..."
              className="pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {['Carrier', 'SCAC', 'DOT #', 'MC #', 'Mode', 'Service Area', 'Status', ''].map(h => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {loading ? (
                  <tr><td colSpan={8} className="text-center py-12 text-gray-400">Loading carriers...</td></tr>
                ) : filteredCarriers.length === 0 ? (
                  <tr><td colSpan={8} className="text-center py-12 text-gray-400">No carriers found</td></tr>
                ) : filteredCarriers.map((c: any) => (
                  <tr key={c.carrier_id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-medium text-gray-900">{c.carrier_name || c.party_name || '—'}</td>
                    <td className="px-4 py-3 font-mono text-gray-600">{c.scac || '—'}</td>
                    <td className="px-4 py-3 text-gray-500">{c.dot_number || '—'}</td>
                    <td className="px-4 py-3 text-gray-500">{c.mc_number || '—'}</td>
                    <td className="px-4 py-3 text-gray-600 uppercase text-xs">{c.primary_mode || '—'}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{c.service_area || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusColor(c.status || 'active')}`}>
                        {c.status || 'active'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <Link href={`/carriers/${c.carrier_id}`} className="text-blue-600 hover:underline text-xs">View →</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === 'scorecards' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {loading ? (
            <p className="text-gray-400 text-sm">Loading scorecards...</p>
          ) : scorecards.length === 0 ? (
            <p className="text-gray-400 text-sm col-span-3">No scorecard data yet</p>
          ) : scorecards.map((sc: any) => (
            <div key={sc.carrier_id} className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-gray-900 text-sm">{sc.carrier_name || sc.carrier_id?.slice(0,8)}</h3>
                <div className="flex items-center gap-1 text-amber-500">
                  <Star size={14} fill="currentColor" />
                  <span className="text-sm font-bold">{sc.total_score?.toFixed(1) || '—'}</span>
                </div>
              </div>
              <div className="space-y-2">
                {[
                  ['Acceptance', sc.tender_acceptance_pct, '%'],
                  ['On-Time Pickup', sc.on_time_pickup_pct, '%'],
                  ['On-Time Delivery', sc.on_time_delivery_pct, '%'],
                  ['Invoice Accuracy', sc.invoice_accuracy_pct, '%'],
                  ['Claims Count', sc.claims_count, ''],
                ].map(([label, val, unit]) => (
                  <div key={label as string} className="flex items-center justify-between text-xs">
                    <span className="text-gray-500">{label}</span>
                    <span className="font-medium text-gray-800">{val !== null && val !== undefined ? `${val}${unit}` : '—'}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
