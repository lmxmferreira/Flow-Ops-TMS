'use client'
import { useEffect, useState } from 'react'
import { BarChart3, TrendingUp, BookOpen, RefreshCw } from 'lucide-react'
import { apiFetch, fmtDate, fmtCurrency } from '../../lib/api'

export default function FinancialsPage() {
  const [accruals, setAccruals] = useState<any[]>([])
  const [periods, setPeriods] = useState<any[]>([])
  const [rates, setRates] = useState<any[]>([])
  const [approvals, setApprovals] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<'accruals'|'periods'|'rates'|'approvals'>('accruals')
  const [reconShipmentId, setReconShipmentId] = useState('')
  const [reconResult, setReconResult] = useState<any>(null)
  const [reconLoading, setReconLoading] = useState(false)

  useEffect(() => {
    Promise.all([
      apiFetch('/financials/accruals?limit=50').catch(() => []),
      apiFetch('/financials/periods').catch(() => []),
      apiFetch('/financials/exchange-rates').catch(() => []),
      apiFetch('/financials/approvals?status=pending').catch(() => []),
    ]).then(([a, p, r, ap]) => {
      setAccruals(Array.isArray(a) ? a : [])
      setPeriods(Array.isArray(p) ? p : [])
      setRates(Array.isArray(r) ? r : [])
      setApprovals(Array.isArray(ap) ? ap : [])
      setLoading(false)
    })
  }, [])

  async function runReconciliation() {
    if (!reconShipmentId.trim()) return
    setReconLoading(true)
    try {
      const r = await apiFetch(`/financials/reconcile/${reconShipmentId.trim()}`, { method: 'POST' })
      setReconResult(r)
    } catch {
      setReconResult({ error: 'Reconciliation failed' })
    } finally {
      setReconLoading(false)
    }
  }

  const TABS = [
    { key: 'accruals', label: `Accruals (${accruals.length})` },
    { key: 'periods', label: 'Financial Periods' },
    { key: 'rates', label: 'Exchange Rates' },
    { key: 'approvals', label: `Pending Approvals (${approvals.length})` },
  ]

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <BookOpen className="text-teal-600" size={24} /> Accruals & Financial Controls
        </h1>
        <p className="text-sm text-gray-500 mt-1">Freight accruals, GL distributions, periods, currency, and financial approvals</p>
      </div>

      {/* Reconciliation tool */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
        <h3 className="text-sm font-semibold text-gray-800 mb-2 flex items-center gap-2">
          <RefreshCw size={14} className="text-teal-600" /> Financial Reconciliation
        </h3>
        <p className="text-xs text-gray-500 mb-3">Run reconciliation across planned, accrued, actual, billed, and paid for a shipment.</p>
        <div className="flex gap-2 mb-3">
          <input value={reconShipmentId} onChange={e => setReconShipmentId(e.target.value)}
            placeholder="Shipment ID (UUID)..."
            className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-teal-500" />
          <button onClick={runReconciliation} disabled={reconLoading || !reconShipmentId.trim()}
            className="px-4 py-2 bg-teal-600 text-white text-sm font-medium rounded-lg hover:bg-teal-700 disabled:opacity-50">
            {reconLoading ? 'Running...' : 'Reconcile'}
          </button>
        </div>
        {reconResult && !reconResult.error && (
          <div className="grid grid-cols-3 lg:grid-cols-5 gap-2 mt-3">
            {[
              ['Planned', reconResult.planned_cost],
              ['Accrued', reconResult.accrued_cost],
              ['Actual', reconResult.actual_carrier_cost],
              ['Billed', reconResult.client_bill_amount],
              ['Received', reconResult.received_amount],
            ].map(([label, val]) => (
              <div key={label as string} className="bg-gray-50 p-2 rounded-lg text-center">
                <p className="text-xs text-gray-500">{label}</p>
                <p className="text-sm font-bold text-gray-900 mt-0.5">{fmtCurrency(val)}</p>
              </div>
            ))}
            <div className={`p-2 rounded-lg text-center col-span-3 lg:col-span-5 ${reconResult.is_reconciled ? 'bg-green-50' : 'bg-yellow-50'}`}>
              <p className="text-xs font-medium">{reconResult.is_reconciled ? '✅ Reconciled' : `⚠ Variances: ${JSON.stringify(reconResult.variances)}`}</p>
              <p className="text-sm font-bold mt-0.5">Margin: {fmtCurrency(reconResult.gross_margin)} ({reconResult.margin_pct}%)</p>
            </div>
          </div>
        )}
        {reconResult?.error && <p className="text-red-600 text-xs mt-2">{reconResult.error}</p>}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 bg-gray-100 p-1 rounded-lg w-fit flex-wrap">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key as any)}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${tab === t.key ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'accruals' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>{['Accrual #','Shipment','Milestone','Level','Amount','GL Code','Status'].map(h =>
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              )}</tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? <tr><td colSpan={7} className="text-center py-12 text-gray-400">Loading...</td></tr>
              : accruals.length === 0 ? <tr><td colSpan={7} className="text-center py-12 text-gray-400">No accruals found</td></tr>
              : accruals.map((a: any) => (
                <tr key={a.accrual_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs text-teal-700">{a.accrual_number}</td>
                  <td className="px-4 py-3 text-gray-600 text-xs">{a.shipment_number || a.shipment_id?.slice(0,8) || '—'}</td>
                  <td className="px-4 py-3 capitalize text-gray-600">{a.accrual_milestone?.replace(/_/g,' ') || '—'}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{a.accrual_level}</td>
                  <td className="px-4 py-3 font-medium">{fmtCurrency(a.accrual_amount)}</td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{a.gl_account_code || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${a.status === 'open' ? 'bg-blue-100 text-blue-700' : a.status === 'reversed' ? 'bg-gray-100 text-gray-500' : 'bg-green-100 text-green-700'}`}>
                      {a.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'periods' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {periods.map((p: any) => (
            <div key={p.financial_period_id || p.period_id} className={`bg-white rounded-xl border p-4 ${p.close_status_id ? 'border-gray-200 opacity-60' : 'border-blue-200'}`}>
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-semibold text-gray-800">{p.period_code || p.period_name}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${p.close_status_id ? 'bg-gray-100 text-gray-500' : 'bg-green-100 text-green-700'}`}>
                  {p.close_status_id ? 'Closed' : 'Open'}
                </span>
              </div>
              <p className="text-xs text-gray-500">{fmtDate(p.period_start_date || p.start_date)} → {fmtDate(p.period_end_date || p.end_date)}</p>
            </div>
          ))}
          {periods.length === 0 && <p className="text-gray-400 text-sm col-span-4">No financial periods configured</p>}
        </div>
      )}

      {tab === 'rates' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>{['From','To','Rate','Date','Type','Source'].map(h =>
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              )}</tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {rates.length === 0 ? <tr><td colSpan={6} className="text-center py-12 text-gray-400">No exchange rates configured</td></tr>
              : rates.map((r: any) => (
                <tr key={r.exchange_rate_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-gray-700">{r.from_currency_code}</td>
                  <td className="px-4 py-3 font-mono text-gray-700">{r.to_currency_code}</td>
                  <td className="px-4 py-3 font-medium">{r.exchange_rate}</td>
                  <td className="px-4 py-3 text-gray-500">{fmtDate(r.rate_date)}</td>
                  <td className="px-4 py-3 text-gray-500 capitalize">{r.rate_type}</td>
                  <td className="px-4 py-3 text-gray-500">{r.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'approvals' && (
        <div className="space-y-3">
          {approvals.length === 0 ? (
            <div className="bg-white rounded-xl border border-gray-200 p-8 text-center">
              <p className="text-gray-400 text-sm">No pending financial approvals</p>
            </div>
          ) : approvals.map((a: any) => (
            <div key={a.approval_id} className="bg-white rounded-xl border border-gray-200 p-4 flex items-center justify-between">
              <div>
                <p className="text-sm font-semibold text-gray-800">{a.approval_type?.replace(/_/g,' ')}</p>
                <p className="text-xs text-gray-500 mt-0.5">{a.entity_type} · Requested by {a.requested_by}</p>
                {a.amount && <p className="text-xs text-gray-600 mt-0.5">Amount: {fmtCurrency(a.amount)}</p>}
              </div>
              <div className="flex gap-2">
                <button onClick={() => apiFetch(`/financials/approvals/${a.approval_id}`, { method: 'PATCH', body: JSON.stringify({ action: 'approve' }) })}
                  className="px-3 py-1.5 bg-green-600 text-white text-xs font-medium rounded-lg hover:bg-green-700">
                  Approve
                </button>
                <button onClick={() => apiFetch(`/financials/approvals/${a.approval_id}`, { method: 'PATCH', body: JSON.stringify({ action: 'reject', reason: 'Rejected via UI' }) })}
                  className="px-3 py-1.5 bg-red-100 text-red-700 text-xs font-medium rounded-lg hover:bg-red-200">
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
