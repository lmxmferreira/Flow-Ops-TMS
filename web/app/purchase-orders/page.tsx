'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Package, Search, Filter, ChevronDown, Plus } from 'lucide-react'
import { apiFetch, fmtDate, fmtCurrency, statusColor } from '../../lib/api'

export default function PurchaseOrdersPage() {
  const [orders, setOrders] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  useEffect(() => {
    const params = new URLSearchParams({ limit: '100' })
    if (statusFilter) params.set('status', statusFilter)
    apiFetch(`/purchase-orders/?${params}`)
      .then(d => { setOrders(Array.isArray(d) ? d : d.data || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [statusFilter])

  const filtered = orders.filter(o =>
    !search ||
    o.purchase_order_number?.toLowerCase().includes(search.toLowerCase()) ||
    o.buyer_name?.toLowerCase().includes(search.toLowerCase()) ||
    o.supplier_name?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Package className="text-purple-600" size={24} /> Purchase Orders
          </h1>
          <p className="text-sm text-gray-500 mt-1">Manage PO headers and track through lifecycle</p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search PO number, buyer, supplier..."
            className="pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="">All Statuses</option>
          {['open','partially_released','fully_released','closed','canceled'].map(s => (
            <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
          ))}
        </select>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {['PO Number', 'Buyer', 'Supplier', 'Order Date', 'Required Date', 'Lines', 'Total', 'Status', ''].map(h => (
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={9} className="text-center py-12 text-gray-400">Loading purchase orders...</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={9} className="text-center py-12 text-gray-400">No purchase orders found</td></tr>
            ) : filtered.map((po: any) => (
              <tr key={po.purchase_order_id} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3 font-mono font-medium text-purple-600">
                  <Link href={`/purchase-orders/${po.purchase_order_id}`}>{po.purchase_order_number}</Link>
                </td>
                <td className="px-4 py-3 text-gray-700">{po.buyer_name || po.buyer_party_id?.slice(0,8) || '—'}</td>
                <td className="px-4 py-3 text-gray-600">{po.supplier_name || po.supplier_party_id?.slice(0,8) || '—'}</td>
                <td className="px-4 py-3 text-gray-500">{fmtDate(po.order_date)}</td>
                <td className="px-4 py-3 text-gray-500">{fmtDate(po.required_delivery_date)}</td>
                <td className="px-4 py-3 text-gray-600">{po.line_count || '—'}</td>
                <td className="px-4 py-3 font-medium">{po.total_po_value ? fmtCurrency(po.total_po_value) : '—'}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium capitalize ${statusColor(po.po_status)}`}>
                    {po.po_status?.replace(/_/g, ' ') || 'open'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <Link href={`/purchase-orders/${po.purchase_order_id}`} className="text-blue-600 hover:underline text-xs">View →</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
