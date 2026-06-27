'use client'
import { useEffect, useState } from 'react'
import { Globe, RefreshCw, AlertCircle, CheckCircle, Clock } from 'lucide-react'
import { apiFetch, statusColor } from '../../lib/api'

const STATUS_COLORS: Record<string, string> = {
  received: 'bg-gray-100 text-gray-600',
  processing: 'bg-blue-100 text-blue-700',
  completed: 'bg-green-100 text-green-700',
  failed: 'bg-red-100 text-red-700',
  retrying: 'bg-yellow-100 text-yellow-700',
  rejected: 'bg-orange-100 text-orange-700',
  duplicate: 'bg-purple-100 text-purple-700',
}

export default function IntegrationPage() {
  const [transactions, setTransactions] = useState<any[]>([])
  const [summary, setSummary] = useState<any>({})
  const [loading, setLoading] = useState(true)
  const [typeFilter, setTypeFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [directionFilter, setDirectionFilter] = useState('')

  function fetchData() {
    const params = new URLSearchParams({ limit: '100' })
    if (typeFilter) params.set('integration_type', typeFilter)
    if (statusFilter) params.set('status', statusFilter)
    if (directionFilter) params.set('direction', directionFilter)
    setLoading(true)
    apiFetch(`/platform/integration/transactions?${params}`)
      .then(d => {
        setTransactions(d.transactions || [])
        setSummary(d.last_24h_summary || {})
        setLoading(false)
      }).catch(() => setLoading(false))
  }

  useEffect(() => { fetchData() }, [typeFilter, statusFilter, directionFilter])

  const totalFailed = Object.entries(summary).filter(([k]) => k === 'failed').reduce((a, [_, v]: any) => a + v, 0)

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Globe className="text-blue-600" size={24} /> Integration
          </h1>
          <p className="text-sm text-gray-500 mt-1">Monitor ERP, WMS, carrier, and payment integrations</p>
        </div>
        <button onClick={fetchData} className="flex items-center gap-2 text-sm text-gray-600 hover:text-gray-900 border border-gray-200 px-3 py-2 rounded-lg hover:bg-gray-50">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* 24h Summary */}
      <div className="grid grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
        {Object.entries(summary).map(([status, count]: any) => (
          <div key={status} className={`bg-white rounded-xl border p-3 text-center ${status === 'failed' && count > 0 ? 'border-red-200' : 'border-gray-200'}`}>
            <p className="text-xs text-gray-500 capitalize">{status}</p>
            <p className={`text-2xl font-bold mt-1 ${status === 'failed' && count > 0 ? 'text-red-600' : 'text-gray-900'}`}>{count}</p>
          </div>
        ))}
        {Object.keys(summary).length === 0 && (
          <div className="col-span-6 bg-white rounded-xl border border-gray-200 p-6 text-center text-sm text-gray-400">
            No integration transactions in last 24 hours
          </div>
        )}
      </div>

      {totalFailed > 0 && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 mb-4 flex items-center gap-3">
          <AlertCircle size={16} className="text-red-600 flex-shrink-0" />
          <p className="text-sm text-red-700">{totalFailed} failed integration transaction(s) in the last 24 hours. Review and retry below.</p>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <select value={directionFilter} onChange={e => setDirectionFilter(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-2">
          <option value="">All Directions</option>
          <option value="inbound">Inbound</option>
          <option value="outbound">Outbound</option>
        </select>
        <select value={typeFilter} onChange={e => setTypeFilter(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-2">
          <option value="">All Types</option>
          {['erp_po','erp_ap','erp_ar','wms','carrier_edi','carrier_api','visibility','tax','telematics','payment','parcel'].map(t => (
            <option key={t} value={t}>{t.replace(/_/g,' ').toUpperCase()}</option>
          ))}
        </select>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-2">
          <option value="">All Statuses</option>
          {Object.keys(STATUS_COLORS).map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>{['Transaction #','Direction','Type','Message Type','Entity','Status','Retries','Processed',''].map(h =>
              <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
            )}</tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? <tr><td colSpan={9} className="text-center py-12 text-gray-400">Loading...</td></tr>
            : transactions.length === 0 ? <tr><td colSpan={9} className="text-center py-12 text-gray-400">No integration transactions found</td></tr>
            : transactions.map((t: any) => (
              <tr key={t.transaction_id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-mono text-xs text-blue-700">{t.transaction_number || t.transaction_id?.slice(0,12)}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${t.direction === 'inbound' ? 'bg-blue-100 text-blue-700' : 'bg-purple-100 text-purple-700'}`}>
                    {t.direction}
                  </span>
                </td>
                <td className="px-4 py-3 text-gray-600 uppercase text-xs">{t.integration_type?.replace(/_/g,' ')}</td>
                <td className="px-4 py-3 font-mono text-xs text-gray-500">{t.message_type || '—'}</td>
                <td className="px-4 py-3 text-gray-500 text-xs">{t.entity_type || '—'}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[t.status] || 'bg-gray-100 text-gray-600'}`}>{t.status}</span>
                </td>
                <td className="px-4 py-3 text-gray-500">{t.retry_count || 0}</td>
                <td className="px-4 py-3 text-gray-500 text-xs">{t.processed_at ? new Date(t.processed_at).toLocaleString() : '—'}</td>
                <td className="px-4 py-3">
                  {t.status === 'failed' && (
                    <button
                      onClick={() => apiFetch('/platform/integration/retry', { method: 'POST', body: JSON.stringify({ transaction_ids: [t.transaction_id] }) })}
                      className="text-xs text-blue-600 hover:underline">
                      Retry
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
