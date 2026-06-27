'use client'
import { useEffect, useState } from 'react'
import { Layers, CheckCircle, AlertTriangle, RefreshCw, Search } from 'lucide-react'

const API = process.env.NEXT_PUBLIC_API_URL

export default function AllocationPage() {
  const [rules, setRules] = useState<any[]>([])
  const [shipments, setShipments] = useState<any[]>([])
  const [selected, setSelected] = useState('')
  const [result, setResult] = useState<any>(null)
  const [validation, setValidation] = useState<any>(null)
  const [versions, setVersions] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [rulesLoading, setRulesLoading] = useState(true)

  const token = () => localStorage.getItem('tms_token')

  useEffect(() => {
    Promise.all([
      fetch(`${API}/allocation/rules`, { headers: { Authorization: `Bearer ${token()}` } }).then(r => r.json()),
      fetch(`${API}/shipments/?limit=20`, { headers: { Authorization: `Bearer ${token()}` } }).then(r => r.json()),
    ]).then(([r, s]) => {
      setRules(Array.isArray(r) ? r : [])
      setShipments(s.data || [])
      setRulesLoading(false)
    })
  }, [])

  const calculate = async () => {
    if (!selected) return
    setLoading(true)
    const [res, val, ver] = await Promise.all([
      fetch(`${API}/allocation/calculate/${selected}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token()}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ allocation_basis: 'rule_based', allocation_levels: ['po_line'], replace_existing: true }),
      }).then(r => r.json()),
      fetch(`${API}/allocation/validate/${selected}`, { headers: { Authorization: `Bearer ${token()}` } }).then(r => r.json()),
      fetch(`${API}/allocation/versions/${selected}`, { headers: { Authorization: `Bearer ${token()}` } }).then(r => r.json()),
    ])
    setResult(res)
    setValidation(val)
    setVersions(ver.versions || [])
    setLoading(false)
  }

  const METHOD_COLOR: Record<string, string> = {
    weight: 'bg-blue-100 text-blue-700', equal: 'bg-purple-100 text-purple-700',
    value: 'bg-green-100 text-green-700', volume: 'bg-indigo-100 text-indigo-700',
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Layers className="text-blue-600" size={24} /> Cost Allocation
        </h1>
        <p className="text-sm text-gray-500 mt-1">Allocate shipment costs to PO lines, customers, cost centers, and GL accounts</p>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Left: calculate */}
        <div className="col-span-2 space-y-4">
          {/* Calculate panel */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">Calculate Allocation</h2>
            <div className="flex gap-3 mb-4">
              <select value={selected} onChange={e => setSelected(e.target.value)}
                className="flex-1 text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
                <option value="">Select shipment...</option>
                {shipments.map((s: any) => (
                  <option key={s.shipment_id} value={s.shipment_id}>{s.shipment_number} — {s.carrier_name}</option>
                ))}
              </select>
              <button onClick={calculate} disabled={!selected || loading}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50">
                <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
                {loading ? 'Calculating...' : 'Calculate'}
              </button>
            </div>

            {/* Result */}
            {result && (
              <div>
                <div className="flex items-center gap-3 mb-3">
                  {result.is_balanced
                    ? <CheckCircle size={18} className="text-green-500" />
                    : <AlertTriangle size={18} className="text-red-500" />}
                  <span className={`text-sm font-semibold ${result.is_balanced ? 'text-green-700' : 'text-red-700'}`}>
                    {result.is_balanced ? 'Balanced' : 'Out of Balance'}
                  </span>
                  <span className="text-xs text-gray-500 ml-auto">Version {result.version}</span>
                </div>
                <div className="grid grid-cols-3 gap-4 mb-4">
                  {[
                    ['Source Total', `$${result.total_source?.toFixed(2)}`],
                    ['Allocated', `$${result.total_allocated?.toFixed(2)}`],
                    ['Variance', `$${result.variance?.toFixed(2)}`],
                  ].map(([k,v]) => (
                    <div key={k} className="bg-gray-50 rounded-lg p-3">
                      <p className="text-xs text-gray-500">{k}</p>
                      <p className="text-lg font-bold text-gray-900 mt-1">{v}</p>
                    </div>
                  ))}
                </div>
                <table className="w-full text-xs">
                  <thead><tr className="border-b border-gray-100">
                    {['Charge','Category','Method','Entity','%','Amount','GL'].map(h => (
                      <th key={h} className="text-left py-1.5 text-gray-500 font-semibold">{h}</th>
                    ))}
                  </tr></thead>
                  <tbody className="divide-y divide-gray-50">
                    {(result.allocations || []).map((a: any, i: number) => (
                      <tr key={i} className="hover:bg-gray-50">
                        <td className="py-1.5 font-mono">{a.charge_code}</td>
                        <td className="py-1.5 capitalize">{a.charge_category}</td>
                        <td className="py-1.5">
                          <span className={`px-1.5 py-0.5 rounded text-xs ${METHOD_COLOR[a.method] || 'bg-gray-100 text-gray-600'}`}>{a.method}</span>
                        </td>
                        <td className="py-1.5 capitalize">{a.entity_type}</td>
                        <td className="py-1.5">{a.pct?.toFixed(1)}%</td>
                        <td className="py-1.5 font-medium">${a.amount?.toFixed(2)}</td>
                        <td className="py-1.5 font-mono text-gray-500">{a.gl_account || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Validation */}
          {validation && (
            <div className={`rounded-xl border p-4 ${validation.is_valid ? 'bg-green-50 border-green-200' : 'bg-red-50 border-red-200'}`}>
              <div className="flex items-center gap-2 mb-2">
                {validation.is_valid
                  ? <CheckCircle size={16} className="text-green-500" />
                  : <AlertTriangle size={16} className="text-red-500" />}
                <span className={`text-sm font-semibold ${validation.is_valid ? 'text-green-700' : 'text-red-700'}`}>
                  {validation.is_valid ? 'Allocation Valid — Ready for Approval' : 'Allocation Invalid'}
                </span>
              </div>
              {validation.issues?.map((issue: string, i: number) => (
                <p key={i} className="text-xs text-red-700 mt-1">• {issue}</p>
              ))}
              <div className="flex gap-4 mt-2 text-xs text-gray-600">
                <span>{validation.cost_line_count} cost lines</span>
                <span>{validation.allocation_count} allocations</span>
                <span>Variance: ${validation.variance?.toFixed(2)}</span>
              </div>
            </div>
          )}

          {/* Version history */}
          {versions.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h2 className="text-sm font-semibold text-gray-700 mb-3">Version History</h2>
              <div className="space-y-2">
                {versions.map((v: any) => (
                  <div key={v.version_id} className="flex items-center gap-3 text-xs">
                    <span className="font-medium text-gray-700">v{v.version_number}</span>
                    <span className="text-gray-500 capitalize">{v.triggered_by}</span>
                    <span className="text-gray-500">${v.total_allocated?.toFixed(2)} allocated</span>
                    {v.is_balanced
                      ? <span className="text-green-600">✓ Balanced</span>
                      : <span className="text-red-600">✗ Unbalanced</span>}
                    <span className="text-gray-400 ml-auto">{new Date(v.created_at).toLocaleString()}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Right: rules */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Allocation Rules ({rules.length})</h2>
          <div className="space-y-3">
            {rulesLoading ? <p className="text-xs text-gray-400">Loading...</p> :
              rules.map((r: any) => (
                <div key={r.rule_id} className="border border-gray-100 rounded-lg p-3">
                  <p className="text-xs font-semibold text-gray-800">{r.rule_name}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className={`px-1.5 py-0.5 rounded text-xs ${METHOD_COLOR[r.allocation_method] || 'bg-gray-100 text-gray-600'}`}>{r.allocation_method}</span>
                    <span className="text-xs text-gray-500 capitalize">{r.allocation_level}</span>
                    {r.charge_category && <span className="text-xs text-gray-400">· {r.charge_category}</span>}
                  </div>
                </div>
              ))}
          </div>
        </div>
      </div>
    </div>
  )
}
