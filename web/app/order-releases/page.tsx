'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Layers, Search, Plus, X, ChevronDown, Truck, Tag, Trash2, CheckSquare, Square, Minus } from 'lucide-react'
import { apiFetch, fmtDate, statusColor, apiPost, apiPatch } from '../../lib/api'

const MODES = ['LTL','FTL','PARCEL','INTERMODAL','AIR','OCEAN','RAIL']
const STATUSES = ['open','planned','tendered','shipped','delivered','closed','canceled']
const EMPTY_FORM = {
  purchase_order_id: '', transport_mode: 'LTL',
  requested_pickup_date: '', requested_delivery_date: '',
  total_weight: '', weight_uom: 'LBS',
  total_volume: '', volume_uom: 'CFT',
  special_instructions: '',
}

// Bulk action definitions
const BULK_ACTIONS = [
  { key: 'plan_shipment',    label: 'Plan Shipment',     icon: Truck,  color: 'bg-blue-600 hover:bg-blue-700 text-white' },
  { key: 'change_status',    label: 'Change Status',     icon: Tag,    color: 'bg-indigo-600 hover:bg-indigo-700 text-white' },
  { key: 'cancel',           label: 'Cancel Selected',   icon: X,      color: 'bg-red-600 hover:bg-red-700 text-white' },
]

export default function OrderReleasesPage() {
  const [releases, setReleases] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')

  // Selection state
  const [selected, setSelected] = useState<Set<string>>(new Set())

  // Create modal
  const [showModal, setShowModal] = useState(false)
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const [pos, setPOs] = useState<any[]>([])

  // Bulk action modal
  const [bulkAction, setBulkAction] = useState<string | null>(null)
  const [bulkStatus, setBulkStatus] = useState('planned')
  const [bulkLoading, setBulkLoading] = useState(false)
  const [bulkResult, setBulkResult] = useState<string | null>(null)

  function loadReleases() {
    const params = new URLSearchParams({ limit: '100' })
    if (statusFilter) params.set('status', statusFilter)
    apiFetch(`/order-releases/?${params}`)
      .then(d => { setReleases(Array.isArray(d) ? d : (d.data || [])); setLoading(false) })
      .catch(() => setLoading(false))
  }

  useEffect(() => { loadReleases() }, [statusFilter])

  useEffect(() => {
    if (showModal && pos.length === 0) {
      apiFetch('/purchase-orders/?limit=50').then(d => setPOs(Array.isArray(d) ? d : d.data || [])).catch(() => {})
    }
  }, [showModal])

  // ── Selection helpers ────────────────────────────────────────
  const filtered = releases.filter(r =>
    !search ||
    r.order_release_number?.toLowerCase().includes(search.toLowerCase()) ||
    r.customer_name?.toLowerCase().includes(search.toLowerCase())
  )
  const allIds = filtered.map(r => r.order_release_id)
  const allSelected = allIds.length > 0 && allIds.every(id => selected.has(id))
  const someSelected = allIds.some(id => selected.has(id)) && !allSelected
  const selectedCount = allIds.filter(id => selected.has(id)).length

  function toggleAll() {
    if (allSelected) {
      setSelected(prev => { const s = new Set(prev); allIds.forEach(id => s.delete(id)); return s })
    } else {
      setSelected(prev => new Set([...prev, ...allIds]))
    }
  }

  function toggleOne(id: string) {
    setSelected(prev => {
      const s = new Set(prev)
      s.has(id) ? s.delete(id) : s.add(id)
      return s
    })
  }

  function clearSelection() { setSelected(new Set()) }

  // ── Create release ───────────────────────────────────────────
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true); setSubmitError('')
    try {
      const body: any = { ...form }
      if (body.total_weight) body.total_weight = parseFloat(body.total_weight)
      if (body.total_volume) body.total_volume = parseFloat(body.total_volume)
      Object.keys(body).forEach(k => { if (body[k] === '') delete body[k] })
      await apiPost('/order-releases/', body)
      setShowModal(false); setForm({ ...EMPTY_FORM })
      setLoading(true); loadReleases()
    } catch {
      setSubmitError('Failed to create release. Check required fields.')
    } finally { setSubmitting(false) }
  }

  // ── Bulk actions ─────────────────────────────────────────────
  const selectedReleases = filtered.filter(r => selected.has(r.order_release_id))

  async function executeBulkAction() {
    if (!bulkAction || selectedReleases.length === 0) return
    setBulkLoading(true); setBulkResult(null)

    try {
      let successCount = 0
      for (const r of selectedReleases) {
        try {
          if (bulkAction === 'change_status') {
            await apiPatch(`/order-releases/${r.order_release_id}/status`, { status: bulkStatus })
            successCount++
          } else if (bulkAction === 'cancel') {
            await apiPatch(`/order-releases/${r.order_release_id}/status`, { status: 'canceled' })
            successCount++
          } else if (bulkAction === 'plan_shipment') {
            // Mark as planned — shipment creation typically done separately
            await apiPatch(`/order-releases/${r.order_release_id}/status`, { status: 'planned' })
            successCount++
          }
        } catch { /* continue on individual failures */ }
      }
      setBulkResult(`✓ ${successCount} of ${selectedReleases.length} releases updated.`)
      clearSelection(); loadReleases()
    } catch {
      setBulkResult('Some actions failed. Refresh to see current state.')
    } finally { setBulkLoading(false) }
  }

  // Checkbox column header icon
  const CheckIcon = allSelected ? CheckSquare : someSelected ? Minus : Square

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Layers className="text-blue-600" size={24} /> Order Releases
          </h1>
          <p className="text-sm text-gray-500 mt-1">Transportation order releases linked to PO lines</p>
        </div>
        <button onClick={() => setShowModal(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 transition-colors shadow-sm">
          <Plus size={16} /> New Release
        </button>
      </div>

      {/* Bulk action toolbar — appears when rows are selected */}
      {selectedCount > 0 && (
        <div className="flex items-center gap-3 mb-4 px-4 py-3 bg-blue-50 border border-blue-200 rounded-xl">
          <span className="text-sm font-semibold text-blue-700">
            {selectedCount} release{selectedCount !== 1 ? 's' : ''} selected
          </span>
          <div className="flex items-center gap-2 ml-2 flex-wrap">
            {BULK_ACTIONS.map(a => (
              <button key={a.key}
                onClick={() => { setBulkAction(a.key); setBulkResult(null) }}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg transition-colors ${a.color}`}>
                <a.icon size={12} /> {a.label}
              </button>
            ))}
          </div>
          <button onClick={clearSelection}
            className="ml-auto text-xs text-blue-500 hover:text-blue-700 font-medium">
            Clear selection
          </button>
        </div>
      )}

      {/* Bulk action confirmation panel */}
      {bulkAction && selectedCount > 0 && (
        <div className="mb-4 p-4 bg-white border border-gray-200 rounded-xl shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div className="flex-1">
              <p className="text-sm font-semibold text-gray-800 mb-2">
                {bulkAction === 'plan_shipment' && `Plan ${selectedCount} release(s) for shipment`}
                {bulkAction === 'change_status' && `Change status for ${selectedCount} release(s)`}
                {bulkAction === 'cancel' && `Cancel ${selectedCount} release(s)`}
              </p>

              {/* Selected releases preview */}
              <div className="flex flex-wrap gap-1.5 mb-3">
                {selectedReleases.slice(0, 8).map(r => (
                  <span key={r.order_release_id} className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded-full font-mono">
                    {r.order_release_number}
                  </span>
                ))}
                {selectedReleases.length > 8 && (
                  <span className="px-2 py-0.5 bg-gray-100 text-gray-500 text-xs rounded-full">
                    +{selectedReleases.length - 8} more
                  </span>
                )}
              </div>

              {/* Status picker for change_status */}
              {bulkAction === 'change_status' && (
                <div className="flex items-center gap-2 mb-3">
                  <label className="text-xs font-medium text-gray-600">New status:</label>
                  <select value={bulkStatus} onChange={e => setBulkStatus(e.target.value)}
                    className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500">
                    {STATUSES.map(s => <option key={s} value={s}>{s.replace(/_/g,' ')}</option>)}
                  </select>
                </div>
              )}

              {bulkAction === 'cancel' && (
                <p className="text-xs text-red-600 mb-3">⚠ This will cancel all selected releases. This cannot be undone.</p>
              )}

              {bulkResult && (
                <p className={`text-xs px-3 py-2 rounded-lg ${bulkResult.startsWith('✓') ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-600'}`}>
                  {bulkResult}
                </p>
              )}
            </div>
            <div className="flex gap-2 flex-shrink-0">
              <button onClick={() => { setBulkAction(null); setBulkResult(null) }}
                className="px-3 py-1.5 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50">
                Cancel
              </button>
              <button onClick={executeBulkAction} disabled={bulkLoading}
                className={`px-4 py-1.5 text-sm font-semibold rounded-lg text-white disabled:opacity-50 transition-colors ${bulkAction === 'cancel' ? 'bg-red-600 hover:bg-red-700' : 'bg-blue-600 hover:bg-blue-700'}`}>
                {bulkLoading ? 'Working...' : 'Confirm'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      <div className="flex gap-3 mb-4">
        <div className="relative flex-1 max-w-xs">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Search release number..."
            className="pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-blue-500" />
        </div>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
          className="text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="">All Statuses</option>
          {STATUSES.map(s => (
            <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
          ))}
        </select>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {/* Select all checkbox */}
              <th className="w-10 px-3 py-3">
                <button onClick={toggleAll} className={`text-gray-400 hover:text-blue-600 transition-colors ${allSelected ? 'text-blue-600' : ''}`}>
                  <CheckIcon size={16} />
                </button>
              </th>
              {['Release #', 'PO #', 'Customer', 'Origin', 'Destination', 'Ship Date', 'Delivery', 'Mode', 'Status', ''].map(h => (
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={11} className="text-center py-12 text-gray-400">Loading releases...</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={11} className="text-center py-12 text-gray-400">No order releases found</td></tr>
            ) : filtered.map((r: any) => {
              const isSelected = selected.has(r.order_release_id)
              return (
                <tr key={r.order_release_id}
                  className={`transition-colors ${isSelected ? 'bg-blue-50 hover:bg-blue-50' : 'hover:bg-gray-50'}`}>
                  {/* Row checkbox */}
                  <td className="px-3 py-3">
                    <button onClick={() => toggleOne(r.order_release_id)}
                      className={`transition-colors ${isSelected ? 'text-blue-600' : 'text-gray-300 hover:text-gray-500'}`}>
                      {isSelected ? <CheckSquare size={16} /> : <Square size={16} />}
                    </button>
                  </td>
                  <td className="px-4 py-3 font-mono font-medium text-blue-600">
                    <Link href={`/order-releases/${r.order_release_id}`}>{r.order_release_number}</Link>
                  </td>
                  <td className="px-4 py-3 text-gray-700">{r.customer_name || '—'}</td>
                  <td className="px-4 py-3 text-gray-600 text-xs">{r.shipper_city || r.shipper_name || '—'}</td>
                  <td className="px-4 py-3 text-gray-600 text-xs">{r.consignee_city || r.consignee_name || '—'}</td>
                  <td className="px-4 py-3 text-gray-500">{fmtDate(r.requested_ship_date)}</td>
                  <td className="px-4 py-3 text-gray-500">{fmtDate(r.requested_delivery_date)}</td>
                  <td className="px-4 py-3 text-gray-600 uppercase text-xs">{r.transport_mode || '—'}</td>
                  <td className="px-4 py-3 text-gray-600">{r.service_level || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium capitalize ${statusColor(r.status_code)}`}>
                      {r.status_code?.replace(/_/g, ' ') || '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <Link href={`/order-releases/${r.order_release_id}`} className="text-blue-600 hover:underline text-xs">View →</Link>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>

        {/* Footer: selection summary */}
        {filtered.length > 0 && (
          <div className="px-4 py-2 border-t border-gray-100 bg-gray-50 flex items-center justify-between">
            <span className="text-xs text-gray-400">{filtered.length} releases</span>
            {selectedCount > 0 && (
              <span className="text-xs font-medium text-blue-600">{selectedCount} selected</span>
            )}
          </div>
        )}
      </div>

      {/* Create Release Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <h2 className="text-lg font-bold text-gray-900">Create Order Release</h2>
              <button onClick={() => { setShowModal(false); setSubmitError('') }}
                className="text-gray-400 hover:text-gray-600 transition-colors">
                <X size={20} />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1.5">Purchase Order</label>
                <select value={form.purchase_order_id}
                  onChange={e => setForm({ ...form, purchase_order_id: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option value="">Select PO (optional)</option>
                  {pos.map((po: any) => (
                    <option key={po.purchase_order_id} value={po.purchase_order_id}>
                      {po.purchase_order_number}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1.5">Transport Mode <span className="text-red-500">*</span></label>
                <select value={form.transport_mode}
                  onChange={e => setForm({ ...form, transport_mode: e.target.value })}
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" required>
                  {MODES.map(m => <option key={m} value={m}>{m}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1.5">Requested Pickup <span className="text-red-500">*</span></label>
                  <input type="date" value={form.requested_pickup_date} required
                    onChange={e => setForm({ ...form, requested_pickup_date: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1.5">Requested Delivery <span className="text-red-500">*</span></label>
                  <input type="date" value={form.requested_delivery_date} required
                    onChange={e => setForm({ ...form, requested_delivery_date: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1.5">Total Weight</label>
                  <div className="flex gap-2">
                    <input type="number" value={form.total_weight} placeholder="0"
                      onChange={e => setForm({ ...form, total_weight: e.target.value })}
                      className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
                    <select value={form.weight_uom} onChange={e => setForm({ ...form, weight_uom: e.target.value })}
                      className="w-20 px-2 py-2 text-xs border border-gray-200 rounded-lg focus:outline-none">
                      <option>LBS</option><option>KGS</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1.5">Total Volume</label>
                  <div className="flex gap-2">
                    <input type="number" value={form.total_volume} placeholder="0"
                      onChange={e => setForm({ ...form, total_volume: e.target.value })}
                      className="flex-1 px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500" />
                    <select value={form.volume_uom} onChange={e => setForm({ ...form, volume_uom: e.target.value })}
                      className="w-20 px-2 py-2 text-xs border border-gray-200 rounded-lg focus:outline-none">
                      <option>CFT</option><option>CBM</option>
                    </select>
                  </div>
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1.5">Special Instructions</label>
                <textarea value={form.special_instructions}
                  onChange={e => setForm({ ...form, special_instructions: e.target.value })}
                  rows={2} placeholder="Any special handling or instructions..."
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none" />
              </div>
              {submitError && (
                <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg">{submitError}</p>
              )}
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => { setShowModal(false); setSubmitError('') }}
                  className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50">
                  Cancel
                </button>
                <button type="submit" disabled={submitting}
                  className="px-5 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors">
                  {submitting ? 'Creating...' : 'Create Release'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
