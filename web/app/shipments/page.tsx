'use client'
import { useEffect, useState, useCallback } from 'react'
import Link from 'next/link'
import { api } from '../lib/api'
import {
  Search, Package, MapPin, Truck, Calendar,
  RefreshCw, ChevronLeft, ChevronRight, FileText
} from 'lucide-react'

interface Shipment {
  shipment_id: string
  shipment_number: string
  status_code: string
  status_name: string
  carrier_name: string
  origin_name: string
  origin_city: string
  origin_state: string
  destination_name: string
  destination_city: string
  destination_state: string
  transport_mode: string
  planned_pickup_datetime: string | null
  planned_delivery_datetime: string | null
  total_weight: number | null
  created_at: string
  po_number: string | null
  po_id: string | null
  po_count: number
}

interface StatusOption { status_code: string; status_name: string }

const STATUS_COLORS: Record<string, string> = {
  DRAFT:       'bg-gray-100 text-gray-700',
  PLANNED:     'bg-blue-100 text-blue-700',
  TENDERED:    'bg-yellow-100 text-yellow-700',
  CONFIRMED:   'bg-indigo-100 text-indigo-700',
  IN_TRANSIT:  'bg-orange-100 text-orange-700',
  DELIVERED:   'bg-green-100 text-green-700',
  CANCELLED:   'bg-red-100 text-red-700',
  EXCEPTION:   'bg-red-200 text-red-800',
  UNKNOWN:     'bg-gray-100 text-gray-500',
}
const sc = (code: string) => STATUS_COLORS[code] ?? STATUS_COLORS.UNKNOWN

function fmtDate(dt: string | null) {
  if (!dt) return '—'
  return new Date(dt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}
function fmtLoc(name: string, city: string, state: string) {
  const place = [city, state].filter(Boolean).join(', ')
  return place || name || '—'
}

const PAGE_SIZE = 50

export default function ShipmentsPage() {
  const [shipments, setShipments]       = useState<Shipment[]>([])
  const [statuses, setStatuses]         = useState<StatusOption[]>([])
  const [total, setTotal]               = useState(0)
  const [page, setPage]                 = useState(0)
  const [search, setSearch]             = useState('')
  const [searchInput, setSearchInput]   = useState('')
  const [activeStatus, setActiveStatus] = useState('')
  const [loading, setLoading]           = useState(false)
  const [error, setError]               = useState('')

  const fetchShipments = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const params: Record<string, string> = {
        limit: String(PAGE_SIZE), offset: String(page * PAGE_SIZE),
      }
      if (search)       params.search = search
      if (activeStatus) params.status = activeStatus
      const res = await api.shipments.list(params)
      setShipments(res.data); setTotal(res.total)
    } catch { setError('Failed to load shipments.') }
    finally  { setLoading(false) }
  }, [search, activeStatus, page])

  useEffect(() => {
    api.shipments.listStatuses?.().then((r: { data: StatusOption[] }) => setStatuses(r.data)).catch(() => {})
  }, [])

  useEffect(() => { fetchShipments() }, [fetchShipments])

  useEffect(() => {
    const t = setTimeout(() => { setSearch(searchInput); setPage(0) }, 500)
    return () => clearTimeout(t)
  }, [searchInput])

  const totalPages = Math.ceil(total / PAGE_SIZE)

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Package className="text-blue-600" size={22} />
          <h1 className="text-xl font-semibold text-gray-800">Shipments</h1>
          <span className="text-sm text-gray-400">{total} total</span>
        </div>
        <button onClick={fetchShipments}
          className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-blue-600 transition-colors">
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white border-b px-6 py-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="relative w-full sm:w-80">
          <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input
            className="w-full pl-9 pr-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Search shipment #, PO#, location, carrier…"
            value={searchInput}
            onChange={e => setSearchInput(e.target.value)}
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <button onClick={() => { setActiveStatus(''); setPage(0) }}
            className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
              activeStatus === '' ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}>All</button>
          {(statuses.length > 0
            ? statuses
            : ['PLANNED','IN_TRANSIT','DELIVERED','EXCEPTION','CANCELLED'].map(c => ({ status_code: c, status_name: c.replace('_',' ') }))
          ).map(s => (
            <button key={s.status_code}
              onClick={() => { setActiveStatus(s.status_code); setPage(0) }}
              className={`px-3 py-1.5 rounded-full text-xs font-medium transition-colors ${
                activeStatus === s.status_code ? 'bg-blue-600 text-white' : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              }`}>{s.status_name}</button>
          ))}
        </div>
      </div>

      {/* Table */}
      <div className="px-6 py-4">
        {error && <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-600">{error}</div>}
        <div className="bg-white rounded-lg border overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 border-b text-left">
                  <th className="px-4 py-3 font-medium text-gray-600">Shipment #</th>
                  <th className="px-4 py-3 font-medium text-gray-600">PO #</th>
                  <th className="px-4 py-3 font-medium text-gray-600">Status</th>
                  <th className="px-4 py-3 font-medium text-gray-600">Origin</th>
                  <th className="px-4 py-3 font-medium text-gray-600">Destination</th>
                  <th className="px-4 py-3 font-medium text-gray-600">Carrier</th>
                  <th className="px-4 py-3 font-medium text-gray-600">Pickup</th>
                  <th className="px-4 py-3 font-medium text-gray-600">Delivery</th>
                </tr>
              </thead>
              <tbody>
                {loading && (
                  <tr><td colSpan={8} className="px-4 py-12 text-center text-gray-400">
                    <RefreshCw size={18} className="animate-spin inline mr-2" />Loading…
                  </td></tr>
                )}
                {!loading && shipments.length === 0 && (
                  <tr><td colSpan={8} className="px-4 py-12 text-center text-gray-400">
                    <Package size={32} className="mx-auto mb-2 opacity-30" />No shipments found
                  </td></tr>
                )}
                {!loading && shipments.map((s, i) => (
                  <tr key={s.shipment_id}
                    className={`border-b last:border-0 hover:bg-blue-50 transition-colors ${
                      i % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'
                    }`}>
                    {/* Shipment # — links to shipment detail */}
                    <td className="px-4 py-3">
                      <Link href={`/shipments/${s.shipment_id}`}
                        className="font-mono font-medium text-blue-700 hover:underline">
                        {s.shipment_number}
                      </Link>
                    </td>
                    {/* PO # — links to PO detail */}
                    <td className="px-4 py-3">
                      {s.po_id && s.po_number ? (
                        <div className="flex items-center gap-1">
                          <Link href={`/purchase-orders/${s.po_id}`}
                            className="flex items-center gap-1 font-mono text-xs text-indigo-700 hover:underline">
                            <FileText size={11} />
                            {s.po_number}
                          </Link>
                          {s.po_count > 1 && (
                            <span className="text-xs text-gray-400">+{s.po_count - 1}</span>
                          )}
                        </div>
                      ) : (
                        <span className="text-gray-300 text-xs">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${sc(s.status_code)}`}>
                        {s.status_name}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5 text-gray-700">
                        <MapPin size={13} className="text-gray-400 shrink-0" />
                        {fmtLoc(s.origin_name, s.origin_city, s.origin_state)}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5 text-gray-700">
                        <MapPin size={13} className="text-gray-400 shrink-0" />
                        {fmtLoc(s.destination_name, s.destination_city, s.destination_state)}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5 text-gray-700">
                        <Truck size={13} className="text-gray-400 shrink-0" />
                        {s.carrier_name}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5 text-gray-500">
                        <Calendar size={13} className="shrink-0" />
                        {fmtDate(s.planned_pickup_datetime)}
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1.5 text-gray-500">
                        <Calendar size={13} className="shrink-0" />
                        {fmtDate(s.planned_delivery_datetime)}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {totalPages > 1 && (
            <div className="px-4 py-3 border-t flex items-center justify-between text-sm text-gray-500">
              <span>Showing {page * PAGE_SIZE + 1}–{Math.min((page + 1) * PAGE_SIZE, total)} of {total}</span>
              <div className="flex gap-2">
                <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
                  className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-30"><ChevronLeft size={16} /></button>
                <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}
                  className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-30"><ChevronRight size={16} /></button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
