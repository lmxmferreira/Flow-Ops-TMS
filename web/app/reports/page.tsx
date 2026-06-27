'use client'
import { useEffect, useState } from 'react'
import { BarChart3, TrendingUp, Package, Truck, DollarSign, PieChart } from 'lucide-react'
import { apiFetch, fmtCurrency } from '../../lib/api'

export default function ReportsPage() {
  const [operational, setOperational] = useState<any>(null)
  const [financial, setFinancial] = useState<any>(null)
  const [carrierPerf, setCarrierPerf] = useState<any[]>([])
  const [allocation, setAllocation] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<'operational'|'financial'|'carriers'|'allocation'>('operational')

  useEffect(() => {
    Promise.all([
      apiFetch('/platform/reports/operational').catch(() => null),
      apiFetch('/platform/reports/financial').catch(() => null),
      apiFetch('/platform/reports/carrier-performance').catch(() => []),
      apiFetch('/platform/reports/allocation').catch(() => []),
    ]).then(([o, f, c, a]) => {
      setOperational(o); setFinancial(f)
      setCarrierPerf(Array.isArray(c) ? c : [])
      setAllocation(Array.isArray(a) ? a : [])
      setLoading(false)
    })
  }, [])

  const TABS = [
    { key: 'operational', label: 'Operational', icon: Truck },
    { key: 'financial', label: 'Financial', icon: DollarSign },
    { key: 'carriers', label: 'Carrier Performance', icon: TrendingUp },
    { key: 'allocation', label: 'Cost Allocation', icon: PieChart },
  ]

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <BarChart3 className="text-orange-600" size={24} /> Reports & Analytics
        </h1>
        <p className="text-sm text-gray-500 mt-1">Operational, financial, carrier performance, and allocation reports</p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-lg w-fit flex-wrap">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key as any)}
            className={`flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${tab === t.key ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
            <t.icon size={13} /> {t.label}
          </button>
        ))}
      </div>

      {tab === 'operational' && operational && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          {/* Shipment Status */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-gray-800 mb-4">Shipments by Stage</h3>
            <div className="space-y-2">
              {Object.entries(operational.shipment_status || {}).map(([stage, count]: any) => (
                <div key={stage} className="flex items-center justify-between">
                  <span className="text-sm text-gray-600 capitalize">{stage.replace(/_/g,' ')}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-24 bg-gray-100 rounded-full h-1.5">
                      <div className="bg-blue-500 h-1.5 rounded-full" style={{ width: `${Math.min(count/10*100,100)}%` }} />
                    </div>
                    <span className="text-sm font-semibold text-gray-800 w-6 text-right">{count}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Tender Status */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-gray-800 mb-4">Tender Status</h3>
            <div className="space-y-2">
              {Object.entries(operational.tender_status || {}).map(([status, count]: any) => (
                <div key={status} className="flex items-center justify-between">
                  <span className="text-sm text-gray-600">{status}</span>
                  <span className="text-sm font-semibold text-gray-800">{count}</span>
                </div>
              ))}
              {Object.keys(operational.tender_status || {}).length === 0 && (
                <p className="text-xs text-gray-400">No tender data</p>
              )}
            </div>
          </div>

          {/* Exceptions */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-gray-800 mb-4">Open Exceptions</h3>
            <div className="space-y-2">
              {Object.entries(operational.open_exceptions || {}).map(([sev, count]: any) => (
                <div key={sev} className="flex items-center justify-between">
                  <span className={`px-2 py-0.5 text-xs rounded-full font-medium capitalize ${sev === 'critical' ? 'bg-red-200 text-red-800' : sev === 'error' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'}`}>{sev}</span>
                  <span className="text-sm font-semibold text-gray-800">{count}</span>
                </div>
              ))}
              {Object.keys(operational.open_exceptions || {}).length === 0 && (
                <p className="text-sm text-green-600 font-medium">✓ No open exceptions</p>
              )}
            </div>
          </div>
        </div>
      )}

      {tab === 'financial' && financial && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Revenue summary */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-gray-800 mb-4">Revenue Summary</h3>
            <div className="space-y-3">
              {[
                ['Total Billed', financial.reconciliation_summary?.total_billed],
                ['Total Cost', financial.reconciliation_summary?.total_carrier_cost],
                ['Total Margin', financial.reconciliation_summary?.total_markup],
              ].map(([label, val]) => (
                <div key={label as string} className="flex justify-between items-center border-b border-gray-50 pb-2">
                  <span className="text-sm text-gray-600">{label}</span>
                  <span className="text-sm font-semibold text-gray-900">{fmtCurrency(val)}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Invoice aging */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="text-sm font-semibold text-gray-800 mb-4">Invoice Aging</h3>
            <div className="space-y-2">
              {Object.entries(financial.invoice_aging || {}).map(([bucket, data]: any) => (
                <div key={bucket} className="flex justify-between items-center">
                  <span className="text-sm text-gray-600 capitalize">{bucket.replace(/_/g,' ')}</span>
                  <div className="text-right">
                    <span className="text-sm font-semibold text-gray-900">{data.count}</span>
                    <span className="text-xs text-gray-400 ml-1">({fmtCurrency(data.total)})</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Carrier costs */}
          <div className="bg-white rounded-xl border border-gray-200 p-5 lg:col-span-2">
            <h3 className="text-sm font-semibold text-gray-800 mb-4">Top Carrier Costs by Charge Code</h3>
            <div className="space-y-2">
              {(financial.carrier_costs_by_charge || []).map((c: any) => (
                <div key={c.charge_code} className="flex items-center gap-3">
                  <span className="font-mono text-xs text-gray-500 w-28 truncate">{c.charge_code || 'UNKNOWN'}</span>
                  <div className="flex-1 bg-gray-100 rounded-full h-2">
                    <div className="bg-blue-500 h-2 rounded-full" style={{ width: `${Math.min(parseFloat(c.total)/10000*100,100)}%` }} />
                  </div>
                  <span className="text-sm font-medium text-gray-700 w-24 text-right">{fmtCurrency(c.total)}</span>
                  <span className="text-xs text-gray-400 w-10">{c.count}x</span>
                </div>
              ))}
              {(financial.carrier_costs_by_charge || []).length === 0 && (
                <p className="text-xs text-gray-400">No cost data</p>
              )}
            </div>
          </div>
        </div>
      )}

      {tab === 'carriers' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>{['Carrier','SCAC','Acceptance','OTP','OTD','Invoice Acc.','Claims','Avg Score'].map(h =>
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              )}</tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? <tr><td colSpan={8} className="text-center py-12 text-gray-400">Loading...</td></tr>
              : carrierPerf.length === 0 ? <tr><td colSpan={8} className="text-center py-12 text-gray-400">No carrier performance data yet</td></tr>
              : carrierPerf.map((c: any) => (
                <tr key={c.carrier_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">{c.carrier_name}</td>
                  <td className="px-4 py-3 font-mono text-gray-500">{c.scac || '—'}</td>
                  {[c.avg_acceptance_pct, c.avg_otp_pct, c.avg_otd_pct, c.avg_invoice_accuracy].map((val, i) => (
                    <td key={i} className="px-4 py-3">
                      {val != null ? (
                        <span className={`font-medium ${parseFloat(val) >= 95 ? 'text-green-600' : parseFloat(val) >= 85 ? 'text-yellow-600' : 'text-red-600'}`}>
                          {parseFloat(val).toFixed(1)}%
                        </span>
                      ) : '—'}
                    </td>
                  ))}
                  <td className="px-4 py-3 text-gray-600">{c.total_claims || 0}</td>
                  <td className="px-4 py-3 font-semibold text-gray-900">{c.avg_score ? parseFloat(c.avg_score).toFixed(1) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'allocation' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>{['Type','Category','GL Code','Party Type','Basis','Lines','Total'].map(h =>
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              )}</tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? <tr><td colSpan={7} className="text-center py-12 text-gray-400">Loading...</td></tr>
              : allocation.length === 0 ? <tr><td colSpan={7} className="text-center py-12 text-gray-400">No allocation data</td></tr>
              : allocation.map((a: any, i) => (
                <tr key={i} className="hover:bg-gray-50">
                  <td className="px-4 py-3 capitalize text-gray-700">{a.allocation_type}</td>
                  <td className="px-4 py-3 text-gray-600">{a.charge_category || '—'}</td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{a.gl_account_code || '—'}</td>
                  <td className="px-4 py-3 text-gray-500 capitalize">{a.responsible_party_type || '—'}</td>
                  <td className="px-4 py-3 text-gray-500 capitalize">{a.allocation_basis || '—'}</td>
                  <td className="px-4 py-3 text-gray-700">{a.lines}</td>
                  <td className="px-4 py-3 font-medium">{fmtCurrency(a.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
