'use client'
import { useEffect, useState } from 'react'
import { ClipboardCheck, Search, CheckCircle, AlertTriangle, XCircle, Clock } from 'lucide-react'
import { apiFetch, fmtCurrency, statusColor } from '../../lib/api'

export default function FreightAuditPage() {
  const [summary, setSummary] = useState<any>(null)
  const [tolerances, setTolerances] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [auditInvoiceId, setAuditInvoiceId] = useState('')
  const [auditResult, setAuditResult] = useState<any>(null)
  const [auditLoading, setAuditLoading] = useState(false)

  useEffect(() => {
    Promise.all([
      apiFetch('/audit/reports/summary').catch(() => null),
      apiFetch('/audit/tolerances').catch(() => []),
    ]).then(([s, t]) => {
      setSummary(s); setTolerances(Array.isArray(t) ? t : [])
      setLoading(false)
    })
  }, [])

  async function runAudit() {
    if (!auditInvoiceId.trim()) return
    setAuditLoading(true); setAuditResult(null)
    try {
      const result = await apiFetch('/audit/run', {
        method: 'POST',
        body: JSON.stringify({ invoice_id: auditInvoiceId.trim(), audit_type: 'auto' }),
      })
      setAuditResult(result)
    } catch (e) {
      setAuditResult({ error: 'Audit failed — check invoice ID' })
    } finally {
      setAuditLoading(false)
    }
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <ClipboardCheck className="text-emerald-600" size={24} /> Freight Audit
        </h1>
        <p className="text-sm text-gray-500 mt-1">Auto-audit carrier invoices, manage exceptions, disputes and payments</p>
      </div>

      {/* KPI Cards */}
      {!loading && summary && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Open Disputes</p>
            <p className="text-3xl font-bold text-gray-900 mt-1">{summary.dispute_summary?.open_disputes || 0}</p>
            <p className="text-xs text-gray-400 mt-1">{fmtCurrency(summary.dispute_summary?.total_disputed)} disputed</p>
          </div>
          {Object.entries(summary.variance_by_type || {}).slice(0,3).map(([type, data]: any) => (
            <div key={type} className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{type.replace(/_/g,' ')}</p>
              <p className="text-3xl font-bold text-red-600 mt-1">{data.count}</p>
              <p className="text-xs text-gray-400 mt-1">{fmtCurrency(data.total)} variance</p>
            </div>
          ))}
          {Object.entries(summary.payment_status || {}).slice(0,1).map(([status, data]: any) => (
            <div key={status} className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Payment: {status}</p>
              <p className="text-3xl font-bold text-gray-900 mt-1">{data.count}</p>
              <p className="text-xs text-gray-400 mt-1">{fmtCurrency(data.total)}</p>
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        {/* Run Audit */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-800 mb-3">Run Freight Audit</h3>
          <p className="text-xs text-gray-500 mb-3">Enter a carrier invoice ID to run automated audit against contracted rates and tolerances.</p>
          <div className="flex gap-2">
            <input value={auditInvoiceId} onChange={e => setAuditInvoiceId(e.target.value)}
              placeholder="Carrier invoice ID (UUID)..."
              className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
            <button onClick={runAudit} disabled={auditLoading || !auditInvoiceId.trim()}
              className="px-4 py-2 bg-emerald-600 text-white text-sm font-medium rounded-lg hover:bg-emerald-700 disabled:opacity-50 transition-colors">
              {auditLoading ? 'Running...' : 'Run Audit'}
            </button>
          </div>

          {auditResult && (
            <div className="mt-4 p-3 bg-gray-50 rounded-lg text-xs space-y-1.5">
              {auditResult.error ? (
                <p className="text-red-600">{auditResult.error}</p>
              ) : (
                <>
                  <div className="flex justify-between"><span className="text-gray-500">Invoice</span><span className="font-medium">{auditResult.invoice_number}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Lines audited</span><span className="font-medium">{auditResult.lines_audited}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Auto-approved</span><span className="font-medium text-green-600">{auditResult.auto_approved}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Exceptions</span><span className="font-medium text-red-600">{auditResult.exceptions}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Result</span>
                    <span className={`font-semibold ${auditResult.new_status === 'matched' ? 'text-green-600' : 'text-red-600'}`}>
                      {auditResult.new_status?.toUpperCase()}
                    </span>
                  </div>
                </>
              )}
            </div>
          )}
        </div>

        {/* Tolerances */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-800 mb-3">Audit Tolerances</h3>
          <div className="space-y-2">
            {tolerances.length === 0 ? (
              <p className="text-xs text-gray-400">No tolerances configured</p>
            ) : tolerances.map((t: any) => (
              <div key={t.tolerance_id} className="flex items-center justify-between py-1.5 border-b border-gray-50 last:border-0">
                <span className="text-sm text-gray-700">{t.tolerance_name}</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono text-gray-500 bg-gray-50 px-2 py-0.5 rounded">
                    {t.use_pct ? `${t.variance_pct}%` : `$${t.variance_amount}`}
                  </span>
                  {t.auto_approve && <CheckCircle size={12} className="text-green-500" />}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Invoice Aging */}
      {summary?.invoice_aging && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h3 className="text-sm font-semibold text-gray-800 mb-4">Invoice Aging</h3>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            {Object.entries(summary.invoice_aging).map(([bucket, data]: any) => (
              <div key={bucket} className={`p-3 rounded-lg border ${bucket.includes('over') ? 'border-red-200 bg-red-50' : bucket.includes('61') ? 'border-orange-200 bg-orange-50' : 'border-gray-200 bg-gray-50'}`}>
                <p className="text-xs text-gray-500 capitalize">{bucket.replace(/_/g,' ')}</p>
                <p className="text-xl font-bold text-gray-900 mt-1">{data.count}</p>
                <p className="text-xs text-gray-400">{fmtCurrency(data.total)}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
