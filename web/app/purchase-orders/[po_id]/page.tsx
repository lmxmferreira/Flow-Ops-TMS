'use client'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import {
  ArrowLeft, FileText, AlertTriangle, CheckCircle, Clock,
  MapPin, Building, DollarSign, Package, History, Pencil, X, Save
} from 'lucide-react'
import { api } from '../../lib/api'

// ── Types ────────────────────────────────────────────────────
interface PO {
  purchase_order_id: string
  purchase_order_number: string
  source_reference: string
  po_type: string
  status_code: string
  status_name: string
  supplier_name: string
  supplier_code: string
  supplier_tax_id: string
  buyer_name: string
  buyer_code: string
  ship_from_name: string
  ship_from_address: string
  ship_from_city: string
  ship_from_state: string
  ship_from_zip: string
  ship_from_country: string
  ship_to_name: string
  ship_to_address: string
  ship_to_city: string
  ship_to_state: string
  ship_to_zip: string
  ship_to_country: string
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
}

interface POLine {
  purchase_order_line_id: string
  line_number: string
  item_number: string
  item_name: string
  item_description: string
  status_code: string
  status_name: string
  ordered_quantity: number
  releasable_quantity: number
  released_quantity: number
  planned_quantity: number
  shipped_quantity: number
  delivered_quantity: number
  received_quantity: number
  canceled_quantity: number
  remaining_quantity: number
  quantity_uom: string
  weight_value: number | null
  weight_uom: string
  volume_value: number | null
  volume_uom: string
  line_value: number | null
  currency: string
  freight_class: string
  packaging_type: string
  hazardous_flag: boolean
  temperature_requirement: string
  requested_ship_date: string | null
  requested_delivery_date: string | null
  hold_flag: boolean
  hold_reason: string
}

interface POVersion {
  version_number: number
  change_reason: string
  created_by: string
  created_at: string
}

// ── Helpers ──────────────────────────────────────────────────
const STATUS_COLORS: Record<string, string> = {
  OPEN:               'bg-blue-100 text-blue-700',
  RECEIVED:           'bg-blue-50 text-blue-700',
  VALIDATED:          'bg-cyan-50 text-cyan-700',
  RELEASED:           'bg-indigo-100 text-indigo-700',
  PARTIALLY_RELEASED: 'bg-purple-50 text-purple-700',
  FULLY_RELEASED:     'bg-indigo-50 text-indigo-700',
  SHIPPED:            'bg-orange-50 text-orange-700',
  PARTIALLY_RECEIVED: 'bg-lime-50 text-lime-700',
  CLOSED:             'bg-green-100 text-green-700',
  CANCELLED:          'bg-red-100 text-red-700',
  CANCELED:           'bg-red-100 text-red-700',
  ON_HOLD:            'bg-yellow-100 text-yellow-800',
  EXCEPTION:          'bg-rose-100 text-rose-700',
  UNKNOWN:            'bg-gray-100 text-gray-500',
}
const sc = (code: string) => STATUS_COLORS[code] ?? STATUS_COLORS.UNKNOWN

function fmtDate(d: string | null) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}
function fmtNum(n: number | null, dec = 2) {
  if (n === null || n === undefined) return '—'
  return Number(n).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec })
}
function fmtQty(n: number) {
  return Number(n).toLocaleString('en-US', { maximumFractionDigits: 3 })
}
function toDateInput(d: string | null) {
  if (!d) return ''
  return d.slice(0, 10)
}

// ── Section card ─────────────────────────────────────────────
function Section({ title, icon: Icon, children }: {
  title: string; icon: React.ElementType; children: React.ReactNode
}) {
  return (
    <div className="bg-white rounded-lg border overflow-hidden">
      <div className="flex items-center gap-2 px-5 py-3 border-b bg-gray-50">
        <Icon size={15} className="text-blue-600" />
        <h2 className="text-sm font-semibold text-gray-700">{title}</h2>
      </div>
      <div className="px-5 py-4">{children}</div>
    </div>
  )
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs text-gray-400 mb-0.5">{label}</p>
      <p className="text-sm text-gray-800 font-medium">{value || '—'}</p>
    </div>
  )
}

// ── Edit Modal ───────────────────────────────────────────────
function EditModal({ po, onClose, onSave }: {
  po: PO
  onClose: () => void
  onSave: (updated: Partial<PO>) => void
}) {
  const [form, setForm] = useState({
    source_reference:        po.source_reference || '',
    requested_ship_date:     toDateInput(po.requested_ship_date),
    requested_delivery_date: toDateInput(po.requested_delivery_date),
    hold_flag:               po.hold_flag,
  })
  const [saving, setSaving] = useState(false)
  const [error, setError]   = useState('')

  const inp = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"

  async function handleSave() {
    setSaving(true)
    setError('')
    try {
      const body: Record<string, unknown> = {}
      if (form.source_reference        !== (po.source_reference || ''))         body.source_reference        = form.source_reference
      if (form.requested_ship_date     !== toDateInput(po.requested_ship_date))  body.requested_ship_date     = form.requested_ship_date || null
      if (form.requested_delivery_date !== toDateInput(po.requested_delivery_date)) body.requested_delivery_date = form.requested_delivery_date || null
      if (form.hold_flag               !== po.hold_flag)                         body.hold_flag               = form.hold_flag

      if (Object.keys(body).length === 0) { onClose(); return }

      await api.purchaseOrders.update(po.purchase_order_id, body)
      onSave({ ...body, updated_at: new Date().toISOString() } as Partial<PO>)
      onClose()
    } catch {
      setError('Failed to save changes.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div className="flex items-center gap-2">
            <Pencil size={16} className="text-blue-600" />
            <h2 className="text-base font-semibold text-gray-900">Edit {po.purchase_order_number}</h2>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X size={18} />
          </button>
        </div>

        {/* Fields */}
        <div className="px-6 py-5 space-y-4">
          {error && <p className="text-sm text-red-500">{error}</p>}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Source Reference</label>
            <input
              className={inp}
              value={form.source_reference}
              onChange={e => setForm({ ...form, source_reference: e.target.value })}
              placeholder="ERP reference number"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Requested Ship Date</label>
              <input
                type="date"
                className={inp}
                value={form.requested_ship_date}
                onChange={e => setForm({ ...form, requested_ship_date: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Requested Delivery Date</label>
              <input
                type="date"
                className={inp}
                value={form.requested_delivery_date}
                onChange={e => setForm({ ...form, requested_delivery_date: e.target.value })}
              />
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setForm({ ...form, hold_flag: !form.hold_flag })}
              className={`w-10 h-5 rounded-full transition-colors ${form.hold_flag ? 'bg-yellow-400' : 'bg-gray-300'}`}
            >
              <span className={`block w-4 h-4 bg-white rounded-full shadow transform transition-transform mx-0.5 ${form.hold_flag ? 'translate-x-5' : 'translate-x-0'}`} />
            </button>
            <span className="text-sm text-gray-700">On Hold</span>
            {form.hold_flag && (
              <span className="text-xs text-yellow-700 bg-yellow-50 px-2 py-0.5 rounded-full">
                <AlertTriangle size={10} className="inline mr-1" />Hold will be applied
              </span>
            )}
          </div>

          <p className="text-xs text-gray-400 pt-1">
            To update supplier, buyer, locations, incoterms, or financial terms, use the ERP integration or contact your administrator.
          </p>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-3 px-6 py-4 border-t border-gray-200">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 font-medium"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50 transition"
          >
            <Save size={14} />
            {saving ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Main component ───────────────────────────────────────────
export default function PODetailPage() {
  const params  = useParams<{ po_id: string }>()
  const router  = useRouter()
  const [po, setPo]             = useState<PO | null>(null)
  const [lines, setLines]       = useState<POLine[]>([])
  const [versions, setVersions] = useState<POVersion[]>([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState('')
  const [activeTab, setActiveTab] = useState<'lines' | 'versions'>('lines')
  const [showEdit, setShowEdit] = useState(false)

  useEffect(() => {
    if (!params.po_id) return
    setLoading(true)
    api.purchaseOrders.get(params.po_id)
      .then((res: { purchase_order: PO; lines: POLine[]; versions: POVersion[] }) => {
        setPo(res.purchase_order)
        setLines(res.lines)
        setVersions(res.versions)
      })
      .catch(() => setError('Failed to load purchase order.'))
      .finally(() => setLoading(false))
  }, [params.po_id])

  function handleSaved(updated: Partial<PO>) {
    if (po) setPo({ ...po, ...updated })
  }

  if (loading) return (
    <div className="flex items-center justify-center h-64 text-gray-400 text-sm">Loading…</div>
  )
  if (error || !po) return (
    <div className="flex items-center justify-center h-64 text-red-500 text-sm">{error || 'Not found'}</div>
  )

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => router.back()}
              className="text-gray-400 hover:text-blue-600 transition-colors">
              <ArrowLeft size={18} />
            </button>
            <FileText size={18} className="text-blue-600" />
            <h1 className="text-xl font-semibold text-gray-800">PO {po.purchase_order_number}</h1>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${sc(po.status_code)}`}>
              {po.status_name}
            </span>
            {po.hold_flag && (
              <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                <AlertTriangle size={11} /> On Hold
              </span>
            )}
          </div>
          {/* Edit button */}
          <button
            onClick={() => setShowEdit(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 hover:border-blue-400 hover:text-blue-600 transition"
          >
            <Pencil size={14} />
            Edit PO
          </button>
        </div>
        <p className="text-xs text-gray-400 ml-9 mt-1">
          v{po.version_number} · Created {fmtDate(po.created_at)} · Updated {fmtDate(po.updated_at)}
        </p>
      </div>

      <div className="px-6 py-5 space-y-4">
        {/* Top row — 3 cols */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Section title="Parties" icon={Building}>
            <div className="space-y-3">
              <div>
                <p className="text-xs text-gray-400 mb-1">Supplier</p>
                <p className="text-sm font-semibold text-gray-800">{po.supplier_name || '—'}</p>
                {po.supplier_code && <p className="text-xs text-gray-400">{po.supplier_code}</p>}
                {po.supplier_tax_id && <p className="text-xs text-gray-400">Tax: {po.supplier_tax_id}</p>}
              </div>
              <div>
                <p className="text-xs text-gray-400 mb-1">Buyer</p>
                <p className="text-sm font-semibold text-gray-800">{po.buyer_name || '—'}</p>
                {po.buyer_code && <p className="text-xs text-gray-400">{po.buyer_code}</p>}
              </div>
            </div>
          </Section>

          <Section title="Locations" icon={MapPin}>
            <div className="space-y-3">
              <div>
                <p className="text-xs text-gray-400 mb-1">Ship From</p>
                <p className="text-sm font-semibold text-gray-800">{po.ship_from_name || '—'}</p>
                {po.ship_from_address && <p className="text-xs text-gray-500">{po.ship_from_address}</p>}
                <p className="text-xs text-gray-500">
                  {[po.ship_from_city, po.ship_from_state, po.ship_from_zip].filter(Boolean).join(', ')}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-400 mb-1">Ship To</p>
                <p className="text-sm font-semibold text-gray-800">{po.ship_to_name || '—'}</p>
                {po.ship_to_address && <p className="text-xs text-gray-500">{po.ship_to_address}</p>}
                <p className="text-xs text-gray-500">
                  {[po.ship_to_city, po.ship_to_state, po.ship_to_zip].filter(Boolean).join(', ')}
                </p>
              </div>
            </div>
          </Section>

          <Section title="Dates & Priority" icon={Clock}>
            <div className="space-y-3">
              <Field label="Requested Ship Date"     value={fmtDate(po.requested_ship_date)} />
              <Field label="Requested Delivery Date" value={fmtDate(po.requested_delivery_date)} />
              <Field label="Priority"                value={po.priority} />
              <Field label="PO Type"                 value={po.po_type} />
            </div>
          </Section>
        </div>

        {/* Second row — 2 cols */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Section title="Financial Terms" icon={DollarSign}>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Currency"       value={po.currency} />
              <Field label="Payment Terms"  value={po.payment_terms} />
              <Field label="Incoterm"       value={po.incoterm} />
              <Field label="Freight Terms"  value={po.freight_terms} />
            </div>
          </Section>

          <Section title="Organisation & Source" icon={Building}>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Business Unit" value={po.business_unit} />
              <Field label="Project"       value={po.project} />
              <Field label="Cost Center"   value={po.cost_center} />
              <Field label="Source System" value={po.source_system} />
              <Field label="Source Ref"    value={po.source_reference} />
              {po.hold_flag && <Field label="Hold Reason" value={po.hold_reason} />}
            </div>
          </Section>
        </div>

        {/* Lines / Versions tabs */}
        <div className="bg-white rounded-lg border overflow-hidden">
          <div className="flex border-b">
            {(['lines', 'versions'] as const).map(tab => (
              <button key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-5 py-3 text-sm font-medium transition-colors border-b-2 ${
                  activeTab === tab
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}
              >
                {tab === 'lines' ? `Lines (${lines.length})` : `Version History (${versions.length})`}
              </button>
            ))}
          </div>

          {activeTab === 'lines' && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-gray-50 border-b text-left text-gray-600">
                    <th className="px-3 py-2.5 font-medium">#</th>
                    <th className="px-3 py-2.5 font-medium">Item</th>
                    <th className="px-3 py-2.5 font-medium">Status</th>
                    <th className="px-3 py-2.5 font-medium text-right">Ordered</th>
                    <th className="px-3 py-2.5 font-medium text-right">Releasable</th>
                    <th className="px-3 py-2.5 font-medium text-right">Released</th>
                    <th className="px-3 py-2.5 font-medium text-right">Planned</th>
                    <th className="px-3 py-2.5 font-medium text-right">Shipped</th>
                    <th className="px-3 py-2.5 font-medium text-right">Delivered</th>
                    <th className="px-3 py-2.5 font-medium text-right">Received</th>
                    <th className="px-3 py-2.5 font-medium text-right">Cancelled</th>
                    <th className="px-3 py-2.5 font-medium text-right">Remaining</th>
                    <th className="px-3 py-2.5 font-medium text-right">Weight</th>
                    <th className="px-3 py-2.5 font-medium text-right">Volume</th>
                    <th className="px-3 py-2.5 font-medium text-right">Line Value</th>
                    <th className="px-3 py-2.5 font-medium">Freight Class</th>
                    <th className="px-3 py-2.5 font-medium">Packaging</th>
                    <th className="px-3 py-2.5 font-medium">Haz</th>
                    <th className="px-3 py-2.5 font-medium">Temp Req</th>
                    <th className="px-3 py-2.5 font-medium">Ship Date</th>
                    <th className="px-3 py-2.5 font-medium">Dlv Date</th>
                    <th className="px-3 py-2.5 font-medium">Hold</th>
                  </tr>
                </thead>
                <tbody>
                  {lines.length === 0 && (
                    <tr><td colSpan={22} className="px-3 py-8 text-center text-gray-400">No lines</td></tr>
                  )}
                  {lines.map((l, i) => (
                    <tr key={l.purchase_order_line_id}
                      className={`border-b last:border-0 ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}`}>
                      <td className="px-3 py-2 font-mono text-gray-600">{l.line_number}</td>
                      <td className="px-3 py-2">
                        <p className="font-medium text-gray-800">{l.item_number || l.item_name || '—'}</p>
                        {l.item_description && <p className="text-gray-400 text-xs">{l.item_description}</p>}
                      </td>
                      <td className="px-3 py-2">
                        <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${sc(l.status_code)}`}>
                          {l.status_name}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-right tabular-nums">{fmtQty(l.ordered_quantity)} <span className="text-gray-400">{l.quantity_uom}</span></td>
                      <td className="px-3 py-2 text-right tabular-nums">{fmtQty(l.releasable_quantity)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{fmtQty(l.released_quantity)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{fmtQty(l.planned_quantity)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{fmtQty(l.shipped_quantity)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{fmtQty(l.delivered_quantity)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{fmtQty(l.received_quantity)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{fmtQty(l.canceled_quantity)}</td>
                      <td className="px-3 py-2 text-right tabular-nums font-semibold text-blue-700">{fmtQty(l.remaining_quantity)}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{l.weight_value ? `${fmtNum(l.weight_value, 3)} ${l.weight_uom}` : '—'}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{l.volume_value ? `${fmtNum(l.volume_value, 3)} ${l.volume_uom}` : '—'}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{l.line_value ? `${l.currency} ${fmtNum(l.line_value)}` : '—'}</td>
                      <td className="px-3 py-2">{l.freight_class || '—'}</td>
                      <td className="px-3 py-2">{l.packaging_type || '—'}</td>
                      <td className="px-3 py-2 text-center">
                        {l.hazardous_flag
                          ? <AlertTriangle size={13} className="text-red-500 mx-auto" />
                          : <CheckCircle  size={13} className="text-green-400 mx-auto" />}
                      </td>
                      <td className="px-3 py-2">{l.temperature_requirement || '—'}</td>
                      <td className="px-3 py-2">{fmtDate(l.requested_ship_date)}</td>
                      <td className="px-3 py-2">{fmtDate(l.requested_delivery_date)}</td>
                      <td className="px-3 py-2 text-center">
                        {l.hold_flag && <AlertTriangle size={13} className="text-yellow-500 mx-auto" />}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {activeTab === 'versions' && (
            <div className="px-5 py-4">
              {versions.length === 0 && (
                <p className="text-sm text-gray-400 text-center py-6">No version history recorded</p>
              )}
              <div className="space-y-3">
                {versions.map(v => (
                  <div key={v.version_number} className="flex items-start gap-3 py-3 border-b last:border-0">
                    <History size={14} className="text-gray-400 mt-0.5" />
                    <div>
                      <p className="text-sm font-medium text-gray-700">Version {v.version_number}</p>
                      {v.change_reason && <p className="text-xs text-gray-500">{v.change_reason}</p>}
                      <p className="text-xs text-gray-400 mt-0.5">
                        {v.created_by && `${v.created_by} · `}{fmtDate(v.created_at)}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Edit modal */}
      {showEdit && (
        <EditModal
          po={po}
          onClose={() => setShowEdit(false)}
          onSave={handleSaved}
        />
      )}
    </div>
  )
}
