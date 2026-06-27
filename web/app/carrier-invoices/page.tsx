'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Receipt, Plus, Search, Filter, AlertTriangle, CheckCircle, Clock, XCircle } from 'lucide-react'

const API = process.env.NEXT_PUBLIC_API_URL

function statusBadge(status: string) {
  const map: Record<string, string> = {
    received: 'bg-gray-100 text-gray-700',
    pending_validation: 'bg-yellow-100 text-yellow-700',
    matched: 'bg-green-100 text-green-700',
    exception: 'bg-red-100 text-red-700',
    disputed: 'bg-orange-100 text-orange-700',
    approved: 'bg-blue-100 text-blue-700',
    paid: 'bg-emerald-100 text-emerald-700',
    canceled: 'bg-gray-100 text-gray-500',
  }
  return map[status] || 'bg-gray-100 text-gray-600'
}

export default function CarrierInvoicesPage() {
  const [invoices, setInvoices] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [aging, setAging] = useState<any>(null)

  useEffect(() => {
    const token = localStorage.getItem('tms_token')
    const params = new URLSearchParams()
    if (statusFilter) params.set('status', statusFilter)
    Promise.all([
      fetch(`${API}/carrier-invoices/?${params}`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json()),
      fetch(`${API}/carrier-invoices/reports/aging`, { headers: { Authorization: `Bearer ${token}` } }).then(r => r.json()),
    ]).then(([inv, ag]) => {
      setInvoices(Array.isArray(inv) ? inv : [])
      setAging(ag)
      setLoading(false)
    })
  }, [statusFilter])

  const filtered = invoices.filter(i =>
    !search || i.carrier_invoice_number?.toLowerCase().includes(search.toLowerCase()) ||
    i.carrier_name?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Receipt className="text-blue-600" size={24} /> Carrier Invoices
          </h1>
          <p className="text-sm text-gray-500 mt-1">Receive, match, approve and pay carrier invoices</p>
        </div>
        <Link href="/carrier-invoices/new"
          className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-blue-700">
          <Plus size={16} /> New Invoice
        </Link>
      </div>

      {/* Aging KPIs */}
      {aging && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">Outstanding</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">${aging.total_outstanding?.toLocaleString('en-US', {minimumFractionDigits:2})}</p>
            <p className="text-xs text-gray-400 mt-1">{aging.invoice_count} invoices</p>
          </div>
          {Object.entries(aging.aging_summary || {}).map(([bucket, data]: any) => (
            <div key={bucket} className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">{bucket.replace(/_/g,' ')}</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">{data.count}</p>
              <p className="text-xs text-gray-400 mt-1">${data.total?.toLocaleString('en-US', {minimumFractionDigits:2})}</p>
            </div>
          ))}
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search invoices..." className="pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="">All Statuses</option>
          {['received','pending_validation','matched','exception','disputed','approved','paid','canceled'].map(s => (
            <option key={s} value={s}>{s.replace(/_/g,' ')}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {['Invoice #','Carrier','Invoice Date','Due Date','Amount','Status','Days Overdue',''].map(h => (
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={8} className="text-center py-12 text-gray-400">Loading invoices...</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={8} className="text-center py-12 text-gray-400">No invoices found</td></tr>
            ) : filtered.map((inv: any) => (
              <tr key={inv.carrier_invoice_id} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3 font-mono font-medium text-blue-600">
                  <Link href={`/carrier-invoices/${inv.carrier_invoice_id}`}>{inv.carrier_invoice_number}</Link>
                </td>
                <td className="px-4 py-3 text-gray-700">{inv.carrier_name}</td>
                <td className="px-4 py-3 text-gray-600">{inv.invoice_date}</td>
                <td className="px-4 py-3 text-gray-600">{inv.due_date || '—'}</td>
                <td className="px-4 py-3 font-medium">${parseFloat(inv.invoice_total_amount||0).toLocaleString('en-US',{minimumFractionDigits:2})}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium capitalize ${statusBadge(inv.status)}`}>
                    {inv.status?.replace(/_/g,' ')}
                  </span>
                </td>
                <td className="px-4 py-3">
                  {inv.days_overdue > 0 ? (
                    <span className="text-red-600 font-medium">{inv.days_overdue}d</span>
                  ) : inv.days_overdue < 0 ? (
                    <span className="text-green-600">{Math.abs(inv.days_overdue)}d early</span>
                  ) : '—'}
                </td>
                <td className="px-4 py-3">
                  <Link href={`/carrier-invoices/${inv.carrier_invoice_id}`} className="text-blue-600 hover:underline text-xs">View →</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
