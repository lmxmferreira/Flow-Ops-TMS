'use client'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  ArrowLeft, FileText, MapPin, Truck, Calendar,
  AlertTriangle, Package, Activity, Ship
} from 'lucide-react'
import { apiFetch as api } from '../../lib/api'

interface OrderRelease {
  order_release_id: string
  order_release_number: string
  status_code: string
  status_name: string
  release_source_type: string
  override_reason: string
  po_number: string
  po_id: string
  customer_name: string
  customer_code: string
  supplier_name: string
  supplier_code: string
  responsible_party: string
  shipper_name: string
  shipper_address: string
  shipper_city: string
  shipper_state: string
  shipper_zip: string
  consignee_name: string
  consignee_address: string
  consignee_city: string
  consignee_state: string
  consignee_zip: string
  transport_mode: string
  service_level: string
  equipment_type: string
  freight_terms: string
  priority: string
  release_rule: string
  requested_ship_date: string | null
  requested_delivery_date: string | null
  created_by: string
  created_at: string
  updated_at: string
}

interface ReleaseLine {
  order_release_line_id: string
  line_number: string
  item_number: string
  item_description: string
  status_code: string
  status_name: string
  quantity: number
  quantity_uom: string
  weight_value: number | null
  weight_uom: string
  cube_value: number | null
  cube_uom: string
  line_value: number | null
  currency: string
  packaging_type: string
  hazardous_flag: boolean
  temperature_requirement: string
  handling_instructions: string
  po_line_number: string
}

interface ReleaseEvent {
  release_event_id: string
  event_type: string
  event_timestamp: string
  quantity: number | null
  source_channel: string
  created_by: string
  notes: string
}

interface LinkedShipment {
  shipment_id: string
  shipment_number: string
  status_code: string
  status_name: string
  planned_pickup_datetime: string | null
  planned_delivery_datetime: string | null
}

const STATUS_COLORS: Record<string, string> = {
  DRAFT: 'bg-gray-100 text-gray-700', OPEN: 'bg-blue-100 text-blue-700',
  PLANNED: 'bg-indigo-100 text-indigo-700', RELEASED: 'bg-yellow-100 text-yellow-800',
  SHIPPED: 'bg-orange-100 text-orange-700', DELIVERED: 'bg-green-100 text-green-700',
  CANCELLED: 'bg-red-100 text-red-700', UNKNOWN: 'bg-gray-100 text-gray-500',
}
const sc = (code: string) => STATUS_COLORS[code] ?? STATUS_COLORS.UNKNOWN

function fmtDate(d: string | null) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}
function fmtDateTime(d: string | null) {
  if (!d) return '—'
  return new Date(d).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}
function fmtNum(n: number | null, dec = 3) {
  if (n === null || n === undefined) return '—'
  return Number(n).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec })
}
function fmtLoc(name: string, city: string, state: string, zip: string) {
  const line2 = [city, state, zip].filter(Boolean).join(', ')
  return { name: name || '—', line2 }
}

function Section({ title, icon: Icon, children }: { title: string; icon: React.ElementType; children: React.ReactNode }) {
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

export default function OrderReleaseDetailPage() {
  const params = useParams<{ release_id: string }>()
  const router = useRouter()
  const [release, setRelease]   = useState<OrderRelease | null>(null)
  const [lines, setLines]       = useState<ReleaseLine[]>([])
  const [events, setEvents]     = useState<ReleaseEvent[]>([])
  const [shipments, setShipments] = useState<LinkedShipment[]>([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState('')
  const [activeTab, setActiveTab] = useState<'lines' | 'events' | 'shipments'>('lines')

  useEffect(() => {
    if (!params.release_id) return
    api(`/order-releases/${params.release_id}`)
      .then((res: { order_release: OrderRelease; lines: ReleaseLine[]; events: ReleaseEvent[]; shipments: LinkedShipment[] }) => {
        setRelease(res.order_release)
        setLines(res.lines)
        setEvents(res.events)
        setShipments(res.shipments)
      })
      .catch(() => setError('Failed to load order release.'))
      .finally(() => setLoading(false))
  }, [params.release_id])

  if (loading) return <div className="flex items-center justify-center h-64 text-gray-400 text-sm">Loading…</div>
  if (error || !release) return <div className="flex items-center justify-center h-64 text-red-500 text-sm">{error || 'Not found'}</div>

  const shipper   = fmtLoc(release.shipper_name,   release.shipper_city,   release.shipper_state,   release.shipper_zip)
  const consignee = fmtLoc(release.consignee_name, release.consignee_city, release.consignee_state, release.consignee_zip)

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center gap-3 mb-1">
          <button onClick={() => router.back()} className="text-gray-400 hover:text-blue-600 transition-colors">
            <ArrowLeft size={18} />
          </button>
          <FileText size={18} className="text-blue-600" />
          <h1 className="text-xl font-semibold text-gray-800">{release.order_release_number}</h1>
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${sc(release.status_code)}`}>
            {release.status_name}
          </span>
          {release.priority && (
            <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-700">
              {release.priority}
            </span>
          )}
        </div>
        <div className="flex items-center gap-4 ml-9 text-xs text-gray-400">
          {release.po_id && (
            <Link href={`/purchase-orders/${release.po_id}`}
              className="flex items-center gap-1 text-indigo-600 hover:underline font-medium">
              <FileText size={11} /> PO {release.po_number}
            </Link>
          )}
          <span>Created {fmtDate(release.created_at)}</span>
          {release.created_by && <span>by {release.created_by}</span>}
          <span>Updated {fmtDate(release.updated_at)}</span>
        </div>
      </div>

      <div className="px-6 py-5 space-y-4">
        {/* Row 1 — 3 cols */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Parties */}
          <Section title="Parties" icon={Package}>
            <div className="space-y-3">
              <div>
                <p className="text-xs text-gray-400 mb-1">Customer</p>
                <p className="text-sm font-semibold text-gray-800">{release.customer_name || '—'}</p>
                {release.customer_code && <p className="text-xs text-gray-400">{release.customer_code}</p>}
              </div>
              <div>
                <p className="text-xs text-gray-400 mb-1">Supplier</p>
                <p className="text-sm font-semibold text-gray-800">{release.supplier_name || '—'}</p>
                {release.supplier_code && <p className="text-xs text-gray-400">{release.supplier_code}</p>}
              </div>
              {release.responsible_party && (
                <Field label="Responsible Party" value={release.responsible_party} />
              )}
            </div>
          </Section>

          {/* Locations */}
          <Section title="Locations" icon={MapPin}>
            <div className="space-y-3">
              <div>
                <p className="text-xs text-gray-400 mb-1">Shipper (Origin)</p>
                <p className="text-sm font-semibold text-gray-800">{shipper.name}</p>
                {release.shipper_address && <p className="text-xs text-gray-500">{release.shipper_address}</p>}
                {shipper.line2 && <p className="text-xs text-gray-500">{shipper.line2}</p>}
              </div>
              <div>
                <p className="text-xs text-gray-400 mb-1">Consignee (Destination)</p>
                <p className="text-sm font-semibold text-gray-800">{consignee.name}</p>
                {release.consignee_address && <p className="text-xs text-gray-500">{release.consignee_address}</p>}
                {consignee.line2 && <p className="text-xs text-gray-500">{consignee.line2}</p>}
              </div>
            </div>
          </Section>

          {/* Transport & Dates */}
          <Section title="Transport & Dates" icon={Truck}>
            <div className="space-y-3">
              <Field label="Transport Mode"  value={release.transport_mode} />
              <Field label="Service Level"   value={release.service_level} />
              <Field label="Equipment Type"  value={release.equipment_type} />
              <Field label="Freight Terms"   value={release.freight_terms} />
              <Field label="Requested Ship"  value={fmtDate(release.requested_ship_date)} />
              <Field label="Requested Delivery" value={fmtDate(release.requested_delivery_date)} />
            </div>
          </Section>
        </div>

        {/* Row 2 — meta */}
        {(release.release_source_type || release.release_rule || release.override_reason) && (
          <div className="bg-white rounded-lg border px-5 py-4">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Field label="Release Source"  value={release.release_source_type} />
              <Field label="Release Rule"    value={release.release_rule} />
              <Field label="Override Reason" value={release.override_reason} />
            </div>
          </div>
        )}

        {/* Tabs — Lines / Events / Shipments */}
        <div className="bg-white rounded-lg border overflow-hidden">
          <div className="flex border-b">
            {([
              { key: 'lines',     label: `Lines (${lines.length})` },
              { key: 'events',    label: `Events (${events.length})` },
              { key: 'shipments', label: `Shipments (${shipments.length})` },
            ] as const).map(tab => (
              <button key={tab.key} onClick={() => setActiveTab(tab.key)}
                className={`px-5 py-3 text-sm font-medium transition-colors border-b-2 ${
                  activeTab === tab.key
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700'
                }`}>
                {tab.label}
              </button>
            ))}
          </div>

          {/* Lines */}
          {activeTab === 'lines' && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-gray-50 border-b text-left text-gray-600">
                    <th className="px-3 py-2.5 font-medium">#</th>
                    <th className="px-3 py-2.5 font-medium">Item</th>
                    <th className="px-3 py-2.5 font-medium">Status</th>
                    <th className="px-3 py-2.5 font-medium">PO Line</th>
                    <th className="px-3 py-2.5 font-medium text-right">Qty</th>
                    <th className="px-3 py-2.5 font-medium text-right">Weight</th>
                    <th className="px-3 py-2.5 font-medium text-right">Cube</th>
                    <th className="px-3 py-2.5 font-medium text-right">Value</th>
                    <th className="px-3 py-2.5 font-medium">Packaging</th>
                    <th className="px-3 py-2.5 font-medium">Haz</th>
                    <th className="px-3 py-2.5 font-medium">Temp</th>
                    <th className="px-3 py-2.5 font-medium">Handling</th>
                  </tr>
                </thead>
                <tbody>
                  {lines.length === 0 && (
                    <tr><td colSpan={12} className="px-3 py-8 text-center text-gray-400">No lines</td></tr>
                  )}
                  {lines.map((l, i) => (
                    <tr key={l.order_release_line_id}
                      className={`border-b last:border-0 ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}`}>
                      <td className="px-3 py-2 font-mono text-gray-600">{l.line_number}</td>
                      <td className="px-3 py-2">
                        <p className="font-medium text-gray-800">{l.item_number || '—'}</p>
                        {l.item_description && <p className="text-gray-400">{l.item_description}</p>}
                      </td>
                      <td className="px-3 py-2">
                        <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${sc(l.status_code)}`}>
                          {l.status_name}
                        </span>
                      </td>
                      <td className="px-3 py-2 font-mono text-gray-500">{l.po_line_number || '—'}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{fmtNum(l.quantity)} <span className="text-gray-400">{l.quantity_uom}</span></td>
                      <td className="px-3 py-2 text-right tabular-nums">{l.weight_value ? `${fmtNum(l.weight_value)} ${l.weight_uom}` : '—'}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{l.cube_value ? `${fmtNum(l.cube_value)} ${l.cube_uom}` : '—'}</td>
                      <td className="px-3 py-2 text-right tabular-nums">{l.line_value ? `${l.currency} ${fmtNum(l.line_value, 2)}` : '—'}</td>
                      <td className="px-3 py-2">{l.packaging_type || '—'}</td>
                      <td className="px-3 py-2 text-center">
                        {l.hazardous_flag && <AlertTriangle size={13} className="text-red-500 mx-auto" />}
                      </td>
                      <td className="px-3 py-2">{l.temperature_requirement || '—'}</td>
                      <td className="px-3 py-2">{l.handling_instructions || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Events */}
          {activeTab === 'events' && (
            <div className="px-5 py-4 space-y-3">
              {events.length === 0 && <p className="text-sm text-gray-400 text-center py-6">No events recorded</p>}
              {events.map(e => (
                <div key={e.release_event_id} className="flex items-start gap-3 py-3 border-b last:border-0">
                  <Activity size={14} className="text-blue-400 mt-0.5 shrink-0" />
                  <div className="flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-medium text-gray-700">{e.event_type}</p>
                      <p className="text-xs text-gray-400">{fmtDateTime(e.event_timestamp)}</p>
                    </div>
                    {e.quantity !== null && (
                      <p className="text-xs text-gray-500">Qty: {fmtNum(e.quantity)}</p>
                    )}
                    {e.source_channel && <p className="text-xs text-gray-400">Via {e.source_channel}</p>}
                    {e.created_by && <p className="text-xs text-gray-400">{e.created_by}</p>}
                    {e.notes && <p className="text-xs text-gray-600 mt-1 italic">{e.notes}</p>}
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Shipments */}
          {activeTab === 'shipments' && (
            <div className="px-5 py-4 space-y-3">
              {shipments.length === 0 && <p className="text-sm text-gray-400 text-center py-6">No shipments linked to this release</p>}
              {shipments.map(s => (
                <div key={s.shipment_id} className="flex items-center justify-between py-3 border-b last:border-0">
                  <div>
                    <Link href={`/shipments/${s.shipment_id}`}
                      className="flex items-center gap-1.5 font-mono font-semibold text-blue-700 hover:underline text-sm">
                      <Ship size={13} /> {s.shipment_number}
                    </Link>
                    <p className="text-xs text-gray-400 mt-0.5">
                      Pickup: {fmtDate(s.planned_pickup_datetime)} · Delivery: {fmtDate(s.planned_delivery_datetime)}
                    </p>
                  </div>
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${sc(s.status_code)}`}>
                    {s.status_name}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
