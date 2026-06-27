'use client'
import { useEffect, useState } from 'react'
import { AlertTriangle, Search, FileWarning } from 'lucide-react'
import { apiFetch, fmtDate, fmtCurrency, statusColor } from '../../lib/api'

const SEV_COLORS: Record<string, string> = {
  critical: 'bg-red-200 text-red-800',
  error: 'bg-red-100 text-red-700',
  warning: 'bg-yellow-100 text-yellow-700',
  info: 'bg-blue-100 text-blue-700',
}

export default function ExceptionsPage() {
  const [exceptions, setExceptions] = useState<any[]>([])
  const [claims, setClaims] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<'exceptions'|'claims'>('exceptions')
  const [search, setSearch] = useState('')
  const [severityFilter, setSeverityFilter] = useState('')

  useEffect(() => {
    Promise.all([
      apiFetch('/ops/exceptions?limit=100').catch(() => ({ exceptions: [] })),
      apiFetch('/ops/claims?limit=100').catch(() => []),
    ]).then(([e, c]) => {
      setExceptions(e.exceptions || [])
      setClaims(Array.isArray(c) ? c : [])
      setLoading(false)
    })
  }, [])

  const filteredExc = exceptions.filter(e => {
    const matchSearch = !search ||
      e.exception_number?.toLowerCase().includes(search.toLowerCase()) ||
      e.exception_type?.toLowerCase().includes(search.toLowerCase())
    const matchSev = !severityFilter || e.severity === severityFilter
    return matchSearch && matchSev
  })

  const filteredClaims = claims.filter(c =>
    !search || c.claim_number?.toLowerCase().includes(search.toLowerCase())
  )

  const excSummary = {
    total: exceptions.length,
    blocking: exceptions.filter(e => e.is_blocking && e.status === 'open').length,
    critical: exceptions.filter(e => e.severity === 'critical').length,
    error: exceptions.filter(e => e.severity === 'error').length,
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <AlertTriangle className="text-red-500" size={24} /> Exceptions & Claims
        </h1>
        <p className="text-sm text-gray-500 mt-1">Manage shipment exceptions, freight claims, and recovery</p>
      </div>

      {/* Summary pills */}
      <div className="grid grid-cols-4 gap-3 mb-6">
        {[
          ['Total Open', excSummary.total, 'gray'],
          ['Blocking', excSummary.blocking, 'red'],
          ['Critical', excSummary.critical, 'red'],
          ['Errors', excSummary.error, 'orange'],
        ].map(([label, val, color]) => (
          <div key={label as string} className="bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{label}</p>
            <p className={`text-2xl font-bold text-${color}-600 mt-1`}>{val}</p>
          </div>
        ))}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 bg-gray-100 p-1 rounded-lg w-fit">
        <button onClick={() => setTab('exceptions')}
          className={`px-4 py-1.5 text-sm font-medium rounded-md ${tab === 'exceptions' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'}`}>
          Exceptions ({exceptions.length})
        </button>
        <button onClick={() => setTab('claims')}
          className={`px-4 py-1.5 text-sm font-medium rounded-md ${tab === 'claims' ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'}`}>
          Claims ({claims.length})
        </button>
      </div>

      <div className="flex gap-3 mb-4">
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder={tab === 'exceptions' ? 'Search exceptions...' : 'Search claims...'}
            className="pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        {tab === 'exceptions' && (
          <select value={severityFilter} onChange={e => setSeverityFilter(e.target.value)}
            className="text-sm border border-gray-200 rounded-lg px-3 py-2">
            <option value="">All Severities</option>
            {['critical','error','warning','info'].map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        )}
      </div>

      {tab === 'exceptions' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>{['Exception #','Type','Shipment','Severity','Blocking','Source','Status','Overdue'].map(h =>
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              )}</tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? <tr><td colSpan={8} className="text-center py-12 text-gray-400">Loading...</td></tr>
              : filteredExc.length === 0 ? <tr><td colSpan={8} className="text-center py-12 text-gray-400">No exceptions found</td></tr>
              : filteredExc.map((e: any) => (
                <tr key={e.exception_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs text-red-700">{e.exception_number}</td>
                  <td className="px-4 py-3 text-gray-600 capitalize text-xs">{e.exception_type?.replace(/_/g,' ')}</td>
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{e.shipment_number || '—'}</td>
                  <td className="px-4 py-3"><span className={`px-2 py-0.5 rounded-full text-xs font-medium ${SEV_COLORS[e.severity] || 'bg-gray-100 text-gray-600'}`}>{e.severity}</span></td>
                  <td className="px-4 py-3">{e.is_blocking ? <span className="text-red-600 font-medium text-xs">Yes</span> : <span className="text-gray-400 text-xs">No</span>}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs capitalize">{e.source}</td>
                  <td className="px-4 py-3"><span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(e.status)}`}>{e.status}</span></td>
                  <td className="px-4 py-3">{e.is_overdue ? <span className="text-red-600 text-xs font-medium">Yes</span> : <span className="text-gray-400 text-xs">—</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'claims' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>{['Claim #','Type','Shipment','Carrier','Claimed','Settled','Status'].map(h =>
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              )}</tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? <tr><td colSpan={7} className="text-center py-12 text-gray-400">Loading...</td></tr>
              : filteredClaims.length === 0 ? <tr><td colSpan={7} className="text-center py-12 text-gray-400">No claims found</td></tr>
              : filteredClaims.map((c: any) => (
                <tr key={c.claim_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-xs text-orange-700">{c.claim_number}</td>
                  <td className="px-4 py-3 capitalize text-gray-600 text-xs">{c.claim_type}</td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{c.shipment_number || '—'}</td>
                  <td className="px-4 py-3 text-gray-600">{c.carrier_name || '—'}</td>
                  <td className="px-4 py-3 font-medium text-red-600">{fmtCurrency(c.claim_amount || c.claimed_amount)}</td>
                  <td className="px-4 py-3 text-green-600">{c.settlement_amount ? fmtCurrency(c.settlement_amount) : '—'}</td>
                  <td className="px-4 py-3"><span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(c.status)}`}>{c.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
