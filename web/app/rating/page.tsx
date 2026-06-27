'use client'
import { useEffect, useState } from 'react'
import { DollarSign, Calculator, Search } from 'lucide-react'
import { apiFetch, fmtCurrency } from '../../lib/api'

export default function RatingPage() {
  const [ratecards, setRatecards] = useState<any[]>([])
  const [costs, setCosts] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<'ratecards'|'costs'>('ratecards')
  const [rateForm, setRateForm] = useState({ shipment_id: '', carrier_id: '' })
  const [rateResult, setRateResult] = useState<any>(null)
  const [rateLoading, setRateLoading] = useState(false)

  useEffect(() => {
    Promise.all([
      apiFetch('/carrier-mgmt/carriers?limit=50').catch(() => []),
      apiFetch('/shipments/?limit=20').catch(() => []),
    ]).then(([r, c]) => {
      setRatecards(Array.isArray(r) ? r : [])
      setCosts(Array.isArray(c) ? c : [])
      setLoading(false)
    })
  }, [])

  async function runRating() {
    if (!rateForm.shipment_id) return
    setRateLoading(true)
    try {
      const result = await apiFetch(`/shipments/${rateForm.shipment_id}`)
      setRateResult(result)
    } catch {
      setRateResult({ error: 'Rating failed' })
    } finally {
      setRateLoading(false)
    }
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <DollarSign className="text-green-600" size={24} /> Rating & Cost Calculation
        </h1>
        <p className="text-sm text-gray-500 mt-1">Rate cards, shipment costing, and cost lookups</p>
      </div>

      {/* Quick Rate Lookup */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
        <h3 className="text-sm font-semibold text-gray-800 mb-3 flex items-center gap-2">
          <Calculator size={14} className="text-green-600" /> View Shipment Costs
        </h3>
        <div className="flex gap-2">
          <input value={rateForm.shipment_id} onChange={e => setRateForm({...rateForm, shipment_id: e.target.value})}
            placeholder="Shipment ID (UUID)..."
            className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-green-500" />
          <button onClick={runRating} disabled={rateLoading || !rateForm.shipment_id}
            className="px-4 py-2 bg-green-600 text-white text-sm font-medium rounded-lg hover:bg-green-700 disabled:opacity-50">
            {rateLoading ? 'Loading...' : 'Get Costs'}
          </button>
        </div>
        {rateResult && !rateResult.error && (
          <div className="mt-3 space-y-1.5">
            {(Array.isArray(rateResult) ? rateResult : []).map((cost: any, i: number) => (
              <div key={i} className="flex items-center justify-between text-xs bg-gray-50 px-3 py-2 rounded-lg">
                <span className="font-mono text-gray-600">{cost.charge_code}</span>
                <span className="font-medium text-gray-900">{fmtCurrency(cost.amount)}</span>
              </div>
            ))}
          </div>
        )}
        {rateResult?.error && <p className="text-red-600 text-xs mt-2">{rateResult.error}</p>}
      </div>

      <div className="flex gap-1 mb-4 bg-gray-100 p-1 rounded-lg w-fit">
        <button onClick={() => setTab('ratecards')}
          className={`px-4 py-1.5 text-sm font-medium rounded-md ${tab === 'ratecards' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'}`}>
          Rate Cards ({ratecards.length})
        </button>
        <button onClick={() => setTab('costs')}
          className={`px-4 py-1.5 text-sm font-medium rounded-md ${tab === 'costs' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'}`}>
          Shipment Costs ({costs.length})
        </button>
      </div>

      {tab === 'ratecards' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>{['Carrier','Lane','Mode','Charge Code','Base Rate','Per Unit','Effective','Expiry'].map(h =>
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              )}</tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? <tr><td colSpan={8} className="text-center py-12 text-gray-400">Loading...</td></tr>
              : ratecards.length === 0 ? <tr><td colSpan={8} className="text-center py-12 text-gray-400">No rate cards found</td></tr>
              : ratecards.map((r: any, i) => (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-4 py-3 text-gray-700">{r.carrier_name || '—'}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{[r.origin_zone, r.destination_zone].filter(Boolean).join(' → ') || '—'}</td>
                  <td className="px-4 py-3 uppercase text-xs text-gray-500">{r.transport_mode || '—'}</td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{r.charge_code || '—'}</td>
                  <td className="px-4 py-3 font-medium">{r.base_rate ? fmtCurrency(r.base_rate) : '—'}</td>
                  <td className="px-4 py-3 text-gray-500">{r.rate_per_unit ? `${fmtCurrency(r.rate_per_unit)}/${r.rate_uom || 'unit'}` : '—'}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{r.effective_date || '—'}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{r.expiry_date || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'costs' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>{['Shipment','Charge Code','Amount','Cost Type','Currency'].map(h =>
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              )}</tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? <tr><td colSpan={5} className="text-center py-12 text-gray-400">Loading...</td></tr>
              : costs.length === 0 ? <tr><td colSpan={5} className="text-center py-12 text-gray-400">No cost data found</td></tr>
              : costs.map((c: any) => (
                <tr key={c.cost_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{c.shipment_id?.slice(0,12)}...</td>
                  <td className="px-4 py-3 font-mono text-sm text-gray-700">{c.charge_code}</td>
                  <td className="px-4 py-3 font-medium">{fmtCurrency(c.amount)}</td>
                  <td className="px-4 py-3 capitalize text-gray-500">{c.cost_type || '—'}</td>
                  <td className="px-4 py-3 text-gray-500">{c.currency || 'USD'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
