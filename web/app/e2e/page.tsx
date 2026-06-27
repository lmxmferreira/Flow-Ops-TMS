'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { GitBranch, Search, AlertTriangle, CheckCircle, Clock, ChevronRight } from 'lucide-react'

const API = process.env.NEXT_PUBLIC_API_URL

export default function E2EPage() {
  const [searchRef, setSearchRef] = useState('')
  const [searchResult, setSearchResult] = useState<any>(null)
  const [exceptions, setExceptions] = useState<any>(null)
  const [shipments, setShipments] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [exLoading, setExLoading] = useState(true)

  const token = () => localStorage.getItem('tms_token')

  useEffect(() => {
    Promise.all([
      fetch(`${API}/e2e/exceptions?resolved=false&limit=10`, { headers: { Authorization: `Bearer ${token()}` } }).then(r => r.json()),
      fetch(`${API}/shipments/?limit=10`, { headers: { Authorization: `Bearer ${token()}` } }).then(r => r.json()),
    ]).then(([ex, shp]) => {
      setExceptions(ex)
      setShipments(shp.data || [])
      setExLoading(false)
    })
  }, [])

  const doSearch = async () => {
    if (!searchRef) return
    setLoading(true)
    const res = await fetch(`${API}/e2e/search?ref=${encodeURIComponent(searchRef)}`, {
      headers: { Authorization: `Bearer ${token()}` }
    }).then(r => r.json())
    setSearchResult(res)
    setLoading(false)
  }

  const STAGE_PCT: Record<string, number> = {
    planned: 10, released: 20, tendered: 30, accepted: 40,
    in_transit: 55, delivered: 70, costed: 80, allocated: 85,
    invoiced: 90, audited: 93, payment_approved: 96, billed: 98, closed: 100,
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <GitBranch className="text-blue-600" size={24} /> End-to-End Traceability
        </h1>
        <p className="text-sm text-gray-500 mt-1">Search any reference, view lifecycle, and manage exceptions</p>
      </div>

      {/* Universal search */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-3">Universal Reference Search</h2>
        <p className="text-xs text-gray-500 mb-3">Search by PO number, shipment number, BOL, PRO, tracking number, invoice number, or container</p>
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input value={searchRef} onChange={e => setSearchRef(e.target.value)}
              onKeyDown={e => e.key === 'Enter' && doSearch()}
              placeholder="SHP-2026-0001, BOL-2026-001, PRO-2026-001..."
              className="pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <button onClick={doSearch} disabled={loading}
            className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50">
            {loading ? 'Searching...' : 'Search'}
          </button>
        </div>

        {searchResult && (
          <div className="mt-4">
            <p className="text-xs text-gray-500 mb-2">{searchResult.total_matches} match{searchResult.total_matches !== 1 ? 'es' : ''} for "{searchResult.query}"</p>
            <div className="space-y-2">
              {searchResult.reference_matches?.map((m: any) => (
                <div key={m.ref_index_id || m.entity_id} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-800">{m.ref_number || m.shipment_number}</p>
                    <p className="text-xs text-gray-500 capitalize">{m.entity_type?.replace(/_/g,' ')} · {m.ref_type?.replace(/_/g,' ')}</p>
                  </div>
                  {m.entity_type === 'shipment' && (
                    <Link href={`/e2e/lifecycle/${m.entity_id}`} className="text-xs text-blue-600 hover:underline flex items-center gap-1">
                      Lifecycle <ChevronRight size={12} />
                    </Link>
                  )}
                </div>
              ))}
              {searchResult.asset_matches?.map((m: any) => (
                <div key={m.asset_id} className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-800">{m.asset_value}</p>
                    <p className="text-xs text-gray-500 capitalize">{m.asset_type?.replace(/_/g,' ')} on {m.shipment_number}</p>
                  </div>
                  <Link href={`/e2e/lifecycle/${m.shipment_id}`} className="text-xs text-blue-600 hover:underline flex items-center gap-1">
                    Lifecycle <ChevronRight size={12} />
                  </Link>
                </div>
              ))}
              {searchResult.total_matches === 0 && (
                <p className="text-sm text-gray-500 text-center py-4">No matches found</p>
              )}
            </div>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-6">
        {/* Shipment lifecycles */}
        <div>
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Shipment Lifecycles</h2>
          <div className="space-y-3">
            {shipments.map((s: any) => (
              <Link key={s.shipment_id} href={`/e2e/lifecycle/${s.shipment_id}`}
                className="block bg-white rounded-xl border border-gray-200 p-4 hover:border-blue-300 transition-colors">
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono font-medium text-blue-600">{s.shipment_number}</span>
                  <span className="text-xs text-gray-500 capitalize">{s.status_name}</span>
                </div>
                <p className="text-xs text-gray-500 mb-2">{s.origin_city} → {s.destination_city} · {s.carrier_name}</p>
                <div className="w-full bg-gray-100 rounded-full h-1.5">
                  <div className="bg-blue-500 h-1.5 rounded-full transition-all"
                    style={{ width: `${STAGE_PCT[s.status_code?.toLowerCase()] || 10}%` }} />
                </div>
              </Link>
            ))}
          </div>
        </div>

        {/* Exceptions */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-gray-700">Open Exceptions</h2>
            {exceptions?.total_open > 0 && (
              <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">{exceptions.total_open} open</span>
            )}
          </div>
          {exLoading ? (
            <p className="text-sm text-gray-400">Loading...</p>
          ) : exceptions?.exceptions?.length === 0 ? (
            <div className="bg-green-50 border border-green-200 rounded-xl p-6 text-center">
              <CheckCircle size={24} className="text-green-500 mx-auto mb-2" />
              <p className="text-sm text-green-700 font-medium">No open exceptions</p>
            </div>
          ) : (
            <div className="space-y-3">
              {exceptions?.exceptions?.map((ex: any) => (
                <div key={ex.exception_id} className="bg-white rounded-xl border border-gray-200 p-4">
                  <div className="flex items-start gap-3">
                    <AlertTriangle size={16} className={`mt-0.5 shrink-0 ${ex.severity === 'critical' ? 'text-red-500' : ex.severity === 'error' ? 'text-orange-500' : 'text-yellow-500'}`} />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-xs font-medium text-gray-700 capitalize">{ex.exception_type?.replace(/_/g,' ')}</span>
                        <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                          ex.severity === 'critical' ? 'bg-red-100 text-red-700' :
                          ex.severity === 'error' ? 'bg-orange-100 text-orange-700' :
                          'bg-yellow-100 text-yellow-700'}`}>{ex.severity}</span>
                      </div>
                      <p className="text-xs text-gray-600 truncate">{ex.description}</p>
                      {ex.shipment_number && (
                        <Link href={`/e2e/lifecycle/${ex.shipment_id}`} className="text-xs text-blue-600 hover:underline mt-1 block">
                          {ex.shipment_number}
                        </Link>
                      )}
                    </div>
                    <span className="text-xs text-gray-400">{new Date(ex.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
