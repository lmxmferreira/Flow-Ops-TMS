'use client'
import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import {
  Search, Filter, ChevronLeft, ChevronRight,
  AlertTriangle, Package, ArrowUpDown, X
} from 'lucide-react'
import { api } from '../lib/api'

// ── Types ─────────────────────────────────────────────────────────────

interface PO {
  purchase_order_id: string
  purchase_order_number: string
  source_reference: string
  po_type: string
  status_code: string
  status_name: string
  supplier_name: string
  buyer_name: string
  ship_from_name: string
  ship_from_city: string
  ship_from_state: string
  ship_to_name: string
  ship_to_city: string
  ship_to_state: string
  requested_ship_date: string | null
  requested_delivery_date: string | null
  incoterm: string
  freight_terms: string
  currency: string
  payment_terms: string
  priority: string
  hold_flag: boolean
  hold_reason: string
  version_number: number
  business_unit: string
  project: string
  cost_center: string
  source_system: string
  created_at: string
  updated_at: string
  line_count: number
}

// ── Helpers ───────────────────────────────────────────────────────────

const STATUS_STYLES: Record<string, string> = {
  DRAFT:              'bg-gray-100 text-gray-600',
  RECEIVED:           'bg-blue-50 text-blue-700',
  VALIDATED:          'bg-cyan-50 text-cyan-700',
  ON_HOLD:            'bg-yellow-50 text-yellow-700',
  PARTIALLY_RELEASED: 'bg-purple-50 text-purple-700',
  FULLY_RELEASED:     'bg-indigo-50 text-indigo-700',
  SHIPPED:            'bg-orange-50 text-orange-700',
  PARTIALLY_RECEIVED: 'bg-lime-50 text-lime-700',
  CLOSED:             'bg-green-50 text-green-700',
  CANCELED:           'bg-red-50 text-red-700',
  EXCEPTION:          'bg-rose-100 text-rose-700',
}

function StatusBadge({ code, name }: { code: string; name: string }) {
  const cls = STATUS_STYLES[code] ?? 'bg-gray-100 text-gray-600'
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium whitespace-nowrap ${cls}`}>
      {name || code}
    </span>
  )
}

function fmt(date: string | null) {
  if (!date) return '—'
  return new Date(date).toLocaleDateString('en-CA') // YYYY-MM-DD
}

function fmtTs(ts: string) {
  return new Date(ts).toLocaleString('en-CA', { dateStyle: 'short', timeStyle: 'short' })
}

const STATUSES = [
  'DRAFT','RECEIVED','VALIDATED','ON_HOLD',
  'PARTIALLY_RELEASED','FULLY_RELEASED','SHIPPED',
  'PARTIALLY_RECEIVED','CLOSED','CANCELED','EXCEPTION',
]

// Column definitions
const COLUMNS = [
  { key: 'purchase_order_number', label: 'PO Number',         width: 'w-36' },
  { key: 'status_name',           label: 'Status',            width: 'w-36' },
  { key: 'supplier_name',         label: 'Supplier',          width: 'w-40' },
  { key: 'buyer_name',            label: 'Buyer',             width: 'w-36' },
  { key: 'po_type',               label: 'Type',              width: 'w-28' },
  { key: 'ship_from',             label: 'Ship From',         width: 'w-36' },
  { key: 'ship_to',               label: 'Ship To',           width: 'w-36' },
  { key: 'requested_ship_date',   label: 'Ship Date',         width: 'w-28' },
  { key: 'requested_delivery_date',label: 'Delivery Date',    width: 'w-28' },
  { key: 'incoterm',              label: 'Incoterms',         width: 'w-24' },
  { key: 'freight_terms',         label: 'Freight Terms',     width: 'w-28' },
  { key: 'currency',              label: 'Currency',          width: 'w-20' },
  { key: 'payment_terms',         label: 'Payment Terms',     width: 'w-28' },
  { key: 'priority',              label: 'Priority',          width: 'w-24' },
  { key: 'hold_flag',             label: 'On Hold',           width: 'w-20' },
  { key: 'hold_reason',           label: 'Hold Reason',       width: 'w-28' },
  { key: 'business_unit',         label: 'Business Unit',     width: 'w-32' },
  { key: 'project',               label: 'Project',           width: 'w-28' },
  { key: 'cost_center',           label: 'Cost Center',       width: 'w-28' },
  { key: 'source_system',         label: 'Source System',     width: 'w-28' },
  { key: 'source_reference',      label: 'Source Ref',        width: 'w-28' },
  { key: 'version_number',        label: 'Version',           width: 'w-20' },
  { key: 'line_count',            label: 'Lines',             width: 'w-16' },
  { key: 'created_at',            label: 'Created',           width: 'w-36' },
  { key: 'updated_at',            label: 'Updated',           width: 'w-36' },
]

// ── Page ──────────────────────────────────────────────────────────────

export default function PurchaseOrdersPage() {
  const router = useRouter()
  const [pos, setPos] = useState<PO[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Filters
  const [search, setSearch] = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [showFilters, setShowFilters] = useState(false)

  // Pagination
  const [page, setPage] = useState(0)
  const limit = 50

  // Column visibility
  const [hiddenCols, setHiddenCols] = useState<Set<string>>(new Set([
    'hold_reason','project','cost_center','source_system',
    'payment_terms','version_number','updated_at',
  ]))
  const [showColPicker, setShowColPicker] = useState(false)

  const visibleCols = COLUMNS.filter(c => !hiddenCols.has(c.key))

  const fetchPOs = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string> = {
        limit: String(limit),
        offset: String(page * limit),
      }
      if (search) params.search = search
      if (statusFilter) params.status = statusFilter
      const data = await api.purchaseOrders.list(params)
      setPos(data.data)
      setTotal(data.total)
    } catch {
      setError('Failed to load purchase orders.')
    } finally {
      setLoading(false)
    }
  }, [search, statusFilter, page])

  useEffect(() => { fetchPOs() }, [fetchPOs])

  function handleSearch(e: React.FormEvent) {
    e.preventDefault()
    setSearch(searchInput)
    setPage(0)
  }

  function clearFilters() {
    setSearch(''); setSearchInput(''); setStatusFilter(''); setPage(0)
  }

  const totalPages = Math.ceil(total / limit)
  const activeFilters = [search, statusFilter].filter(Boolean).length

  function toggleCol(key: string) {
    setHiddenCols(prev => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }

  function renderCell(po: PO, key: string) {
    switch (key) {
      case 'purchase_order_number':
        return (
          <span className="font-mono font-semibold text-blue-700 hover:underline cursor-pointer">
            {po.purchase_order_number}
          </span>
        )
      case 'status_name':
        return <StatusBadge code={po.status_code} name={po.status_name} />
      case 'ship_from':
        return (
          <span className="text-gray-600 text-xs">
            {[po.ship_from_name, po.ship_from_city, po.ship_from_state].filter(Boolean).join(', ') || '—'}
          </span>
        )
      case 'ship_to':
        return (
          <span className="text-gray-600 text-xs">
            {[po.ship_to_name, po.ship_to_city, po.ship_to_state].filter(Boolean).join(', ') || '—'}
          </span>
        )
      case 'requested_ship_date':
        return <span className="text-gray-600 text-xs">{fmt(po.requested_ship_date)}</span>
      case 'requested_delivery_date':
        return <span className="text-gray-600 text-xs">{fmt(po.requested_delivery_date)}</span>
      case 'created_at':
        return <span className="text-gray-500 text-xs">{fmtTs(po.created_at)}</span>
      case 'updated_at':
        return <span className="text-gray-500 text-xs">{fmtTs(po.updated_at)}</span>
      case 'hold_flag':
        return po.hold_flag
          ? <span className="inline-flex items-center gap-1 text-xs text-yellow-700"><AlertTriangle size={12} /> Yes</span>
          : <span className="text-gray-400 text-xs">No</span>
      case 'line_count':
        return (
          <span className="inline-flex items-center gap-1 text-xs text-gray-600">
            <Package size={11} /> {po.line_count}
          </span>
        )
      case 'currency':
        return <span className="font-mono text-xs text-gray-700">{po[key] || '—'}</span>
      case 'version_number':
        return <span className="text-gray-500 text-xs">v{po.version_number}</span>
      default: {
        const val = po[key as keyof PO]
        return <span className="text-gray-600 text-xs">{val != null && val !== '' ? String(val) : '—'}</span>
      }
    }
  }

  return (
    <div className="flex flex-col h-full bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-gray-900">Purchase Orders</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              {loading ? 'Loading…' : `${total.toLocaleString()} orders`}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {/* Column picker */}
            <div className="relative">
              <button
                onClick={() => setShowColPicker(v => !v)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-600 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                <ArrowUpDown size={14} /> Columns
              </button>
              {showColPicker && (
                <div className="absolute right-0 top-9 z-20 bg-white border border-gray-200 rounded-xl shadow-xl p-3 w-64 max-h-96 overflow-y-auto">
                  <p className="text-xs font-semibold text-gray-500 mb-2">Show / Hide Columns</p>
                  <div className="space-y-1">
                    {COLUMNS.map(col => (
                      <label key={col.key} className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer hover:bg-gray-50 px-1 py-0.5 rounded">
                        <input
                          type="checkbox"
                          checked={!hiddenCols.has(col.key)}
                          onChange={() => toggleCol(col.key)}
                          className="rounded"
                        />
                        {col.label}
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Filter toggle */}
            <button
              onClick={() => setShowFilters(v => !v)}
              className={`flex items-center gap-1.5 px-3 py-1.5 text-sm border rounded-lg transition ${
                showFilters || activeFilters > 0
                  ? 'bg-blue-50 text-blue-700 border-blue-300'
                  : 'text-gray-600 border-gray-300 hover:bg-gray-50'
              }`}
            >
              <Filter size={14} />
              Filters
              {activeFilters > 0 && (
                <span className="bg-blue-600 text-white text-xs rounded-full w-4 h-4 flex items-center justify-center">
                  {activeFilters}
                </span>
              )}
            </button>
          </div>
        </div>

        {/* Search + filters row */}
        <div className="mt-3 flex items-center gap-3">
          <form onSubmit={handleSearch} className="flex-1 flex gap-2">
            <div className="relative flex-1 max-w-sm">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                value={searchInput}
                onChange={e => setSearchInput(e.target.value)}
                placeholder="PO number, supplier, buyer, source ref…"
                className="w-full pl-9 pr-3 py-1.5 text-sm border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <button type="submit" className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              Search
            </button>
            {(search || statusFilter) && (
              <button type="button" onClick={clearFilters} className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
                <X size={14} /> Clear
              </button>
            )}
          </form>
        </div>

        {/* Expanded filters */}
        {showFilters && (
          <div className="mt-3 flex flex-wrap gap-3 pt-3 border-t border-gray-100">
            <div>
              <label className="block text-xs font-medium text-gray-500 mb-1">Status</label>
              <select
                value={statusFilter}
                onChange={e => { setStatusFilter(e.target.value); setPage(0) }}
                className="text-sm border border-gray-300 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All Statuses</option>
                {STATUSES.map(s => (
                  <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
                ))}
              </select>
            </div>
          </div>
        )}
      </div>

      {/* Table */}
      <div className="flex-1 overflow-auto">
        {error ? (
          <div className="flex items-center justify-center h-64 text-red-500">{error}</div>
        ) : loading ? (
          <div className="flex items-center justify-center h-64 text-gray-400">Loading purchase orders…</div>
        ) : pos.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-gray-400">
            <Package size={40} className="mb-3 opacity-30" />
            <p className="text-sm">No purchase orders found.</p>
            {(search || statusFilter) && (
              <button onClick={clearFilters} className="mt-2 text-sm text-blue-600 hover:underline">Clear filters</button>
            )}
          </div>
        ) : (
          <table className="w-full text-sm border-separate border-spacing-0">
            <thead className="sticky top-0 z-10">
              <tr>
                {visibleCols.map(col => (
                  <th
                    key={col.key}
                    className={`${col.width} text-left px-3 py-2.5 text-xs font-semibold text-gray-600 bg-white border-b border-gray-200 whitespace-nowrap`}
                  >
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {pos.map((po, idx) => (
                <tr
                  key={po.purchase_order_id}
                  onClick={() => router.push(`/purchase-orders/${po.purchase_order_id}`)}
                  className={`cursor-pointer hover:bg-blue-50 transition-colors ${
                    idx % 2 === 0 ? 'bg-white' : 'bg-gray-50/60'
                  } ${po.hold_flag ? 'border-l-2 border-yellow-400' : ''}`}
                >
                  {visibleCols.map(col => (
                    <td
                      key={col.key}
                      className="px-3 py-2 border-b border-gray-100 whitespace-nowrap max-w-xs truncate"
                    >
                      {renderCell(po, col.key)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Pagination */}
      {!loading && total > limit && (
        <div className="bg-white border-t border-gray-200 px-6 py-3 flex items-center justify-between">
          <p className="text-sm text-gray-500">
            Showing {page * limit + 1}–{Math.min((page + 1) * limit, total)} of {total.toLocaleString()}
          </p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(p => Math.max(0, p - 1))}
              disabled={page === 0}
              className="p-1.5 rounded-lg border border-gray-300 disabled:opacity-40 hover:bg-gray-50"
            >
              <ChevronLeft size={16} />
            </button>
            <span className="text-sm text-gray-600">
              Page {page + 1} of {totalPages}
            </span>
            <button
              onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1}
              className="p-1.5 rounded-lg border border-gray-300 disabled:opacity-40 hover:bg-gray-50"
            >
              <ChevronRight size={16} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
