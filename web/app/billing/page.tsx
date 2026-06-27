'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { CreditCard, Search, TrendingUp, DollarSign } from 'lucide-react'
import { apiFetch, fmtDate, fmtCurrency, statusColor } from '../../lib/api'

const BILL_STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-600',
  pending_approval: 'bg-yellow-100 text-yellow-700',
  approved: 'bg-blue-100 text-blue-700',
  sent: 'bg-indigo-100 text-indigo-700',
  disputed: 'bg-orange-100 text-orange-700',
  partially_paid: 'bg-teal-100 text-teal-700',
  paid: 'bg-green-100 text-green-700',
  canceled: 'bg-gray-100 text-gray-400',
  credited: 'bg-purple-100 text-purple-700',
}

export default function BillingPage() {
  const [bills, setBills] = useState<any[]>([])
  const [summary, setSummary] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  useEffect(() => {
    const params = new URLSearchParams({ limit: '100' })
    if (statusFilter) params.set('status', statusFilter)
    Promise.all([
      apiFetch(`/billing/?${params}`).catch(() => []),
      apiFetch('/billing/reports/summary').catch(() => null),
    ]).then(([b, s]) => {
      setBills(Array.isArray(b) ? b : [])
      setSummary(s)
      setLoading(false)
    })
  }, [statusFilter])

  const filtered = bills.filter(b =>
    !search ||
    b.client_bill_number?.toLowerCase().includes(search.toLowerCase()) ||
    b.customer_name?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <CreditCard className="text-indigo-600" size={24} /> Client Billing
          </h1>
          <p className="text-sm text-gray-500 mt-1">Generate, approve and track client bills and receivables</p>
        </div>
      </div>

      {/* Revenue KPIs */}
      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {[
            ['Total Billed', summary.revenue?.total_billed, 'green'],
            ['Total Paid', summary.revenue?.total_paid, 'blue'],
            ['Outstanding', summary.revenue?.total_outstanding, 'orange'],
            ['Margin', `${summary.margin?.overall_margin_pct?.toFixed(1)}%`, 'purple'],
          ].map(([label, val, color]) => (
            <div key={label as string} className="bg-white rounded-xl border border-gray-200 p-5">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{label}</p>
              <p className={`text-2xl font-bold mt-1 text-${color}-600`}>
                {typeof val === 'string' && val.includes('%') ? val : fmtCurrency(val)}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* AR Aging */}
      {summary?.ar_aging && Object.keys(summary.ar_aging).length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5 mb-4">
          <h3 className="text-sm font-semibold text-gray-800 mb-3">AR Aging</h3>
          <div className="grid grid-cols-3 lg:grid-cols-5 gap-3">
            {Object.entries(summary.ar_aging).map(([bucket, data]: any) => (
              <div key={bucket} className="text-center p-3 bg-gray-50 rounded-lg">
                <p className="text-xs text-gray-500 capitalize mb-1">{bucket.replace(/_/g,' ')}</p>
                <p className="text-xl font-bold text-gray-900">{data.count}</p>
                <p className="text-xs text-gray-400">{fmtCurrency(data.total)}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Filters + Table */}
      <div className="flex gap-3 mb-4">
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search bills..."
            className="pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none">
          <option value="">All Statuses</option>
          {Object.keys(BILL_STATUS_COLORS).map(s => (
            <option key={s} value={s}>{s.replace(/_/g,' ')}</option>
          ))}
        </select>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {['Bill #', 'Customer', 'Bill Date', 'Due Date', 'Amount', 'Paid', 'Outstanding', 'Status', ''].map(h => (
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={9} className="text-center py-12 text-gray-400">Loading bills...</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={9} className="text-center py-12 text-gray-400">No bills found</td></tr>
            ) : filtered.map((b: any) => (
              <tr key={b.client_bill_id} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3 font-mono font-medium text-indigo-600">
                  <Link href={`/billing/${b.client_bill_id}`}>{b.client_bill_number}</Link>
                </td>
                <td className="px-4 py-3 text-gray-700">{b.customer_name || '—'}</td>
                <td className="px-4 py-3 text-gray-500">{fmtDate(b.bill_date)}</td>
                <td className="px-4 py-3 text-gray-500">{fmtDate(b.due_date)}</td>
                <td className="px-4 py-3 font-medium">{fmtCurrency(b.total_bill_amount)}</td>
                <td className="px-4 py-3 text-green-600">{fmtCurrency(b.paid_amount)}</td>
                <td className="px-4 py-3 text-orange-600">{fmtCurrency(b.outstanding_amount)}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${BILL_STATUS_COLORS[b.status] || 'bg-gray-100 text-gray-600'}`}>
                    {b.status?.replace(/_/g,' ')}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <Link href={`/billing/${b.client_bill_id}`} className="text-blue-600 hover:underline text-xs">View →</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
