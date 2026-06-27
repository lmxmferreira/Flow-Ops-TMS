'use client'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  ArrowLeft, Package, ChevronRight, Building2, MapPin, DollarSign,
  Calendar, Tag, AlertTriangle, CheckCircle, Layers, Truck,
  BarChart3, FileText, Clock, ExternalLink
} from 'lucide-react'
import { apiFetch, fmtDate, fmtCurrency, statusColor } from '../../../lib/api'

const STATUS_COLORS: Record<string, string> = {
  OPEN:               'bg-blue-100 text-blue-700',
  PARTIALLY_RELEASED: 'bg-yellow-100 text-yellow-700',
  FULLY_RELEASED:     'bg-purple-100 text-purple-700',
  SHIPPED:            'bg-indigo-100 text-indigo-700',
  DELIVERED:          'bg-green-100 text-green-700',
  CLOSED:             'bg-gray-100 text-gray-500',
  CANCELED:           'bg-red-100 text-red-600',
  IN_TRANSIT:         'bg-indigo-100 text-indigo-700',
  READY:              'bg-teal-100 text-teal-700',
}

function Field({ label, value, mono = false, highlight = false }: any) {
  return (
    <div>
      <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-0.5">{label}</p>
      <p className={`text-sm ${mono ? 'font-mono' : ''} ${highlight ? 'font-semibold text-gray-900' : 'text-gray-700'} ${!value ? 'text-gray-300' : ''}`}>
        {value || '—'}
      </p>
    </div>
  )
}

function Section({ title, icon: Icon, color = 'text-blue-600', children }: any) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
      <div className="flex items-center gap-2 px-5 py-3.5 border-b border-gray-100 bg-gray-50">
        <Icon size={14} className={color} />
        <h3 className="text-sm font-bold text-gray-700">{title}</h3>
      </div>
      <div className="p-5">{children}</div>
    </div>
  )
}

function QuantityBar({ label, value, total, color }: { label: string; value: number; total: number; color: string }) {
  const pct = total > 0 ? Math.min(value / total * 100, 100) : 0
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-gray-500">{label}</span>
        <span className="font-semibold text-gray-800">{value?.toLocaleString()}</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-1.5">
        <div className={`${color} h-1.5 rounded-full transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

export default function PODetailPage() {
  const params = useParams()
  const router = useRouter()
  const id = params?.po_id as string

  const [po, setPO] = useState<any>(null)
  const [lines, setLines] = useState<any[]>([])
  const [releases, setReleases] = useState<any[]>([])
  const [versions, setVersions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('lines')

  useEffect(() => {
    if (!id) return
    Promise.all([
      apiFetch(`/purchase-orders/${id}`),
      apiFetch(`/order-releases/?po_id=${id}&limit=50`).catch(() => ({ data: [] })),
    ]).then(([poData, relData]) => {
      setPO(poData.purchase_order || poData)
      setLines(poData.lines || [])
      setVersions(poData.versions || [])
      setReleases(relData.data || (Array.isArray(relData) ? relData : []))
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [id])

  if (loading) return (
    <div className="flex items-center justify-center h-full">
      <div className="animate-spin w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full" />
    </div>
  )

  if (!po) return (
    <div className="p-6 text-center">
      <p className="text-gray-500 mb-3">Purchase order not found.</p>
      <button onClick={() => router.push('/purchase-orders')} className="text-blue-600 text-sm hover:underline">← Back</button>
    </div>
  )

  // Aggregate quantities across lines
  const totals = lines.reduce((acc: any, l: any) => ({
    ordered:   acc.ordered   + (l.ordered_quantity   || 0),
    released:  acc.released  + (l.released_quantity  || 0),
    shipped:   acc.shipped   + (l.shipped_quantity   || 0),
    delivered: acc.delivered + (l.delivered_quantity || 0),
    remaining: acc.remaining + (l.remaining_quantity || 0),
    value:     acc.value     + (l.line_value         || 0),
    weight:    acc.weight    + (l.weight_value       || 0),
  }), { ordered: 0, released: 0, shipped: 0, delivered: 0, remaining: 0, value: 0, weight: 0 })

  const TABS = [
    { key: 'lines',    label: 'PO Lines',      icon: Package,  count: lines.length },
    { key: 'releases', label: 'Order Releases', icon: Layers,   count: releases.length },
    { key: 'versions', label: 'Version History', icon: Clock,   count: versions.length },
  ]

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-4">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <button onClick={() => router.push('/purchase-orders')} className="flex items-center gap-1 hover:text-gray-800">
          <ArrowLeft size={14} /> Purchase Orders
        </button>
        <ChevronRight size={14} />
        <span className="font-mono text-gray-900 font-medium">{po.purchase_order_number}</span>
      </div>

      {/* ── HEADER ──────────────────────────────────────────────── */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-start justify-between gap-4 mb-5">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-2xl font-bold text-gray-900 font-mono">{po.purchase_order_number}</h1>
              <span className={`px-3 py-1 rounded-full text-xs font-semibold ${STATUS_COLORS[po.status_code] || 'bg-gray-100 text-gray-600'}`}>
                {po.status_name || po.status_code}
              </span>
              {po.hold_flag && (
                <span className="px-2 py-0.5 bg-red-100 text-red-700 text-xs rounded-full font-medium flex items-center gap-1">
                  <AlertTriangle size={10} /> On Hold
                </span>
              )}
            </div>
            <p className="text-sm text-gray-500">
              {po.po_type || 'Standard'} · Version {po.version_number || 1} · {po.priority && `Priority: ${po.priority}`}
            </p>
          </div>
          <div className="text-right flex-shrink-0">
            <p className="text-2xl font-bold text-gray-900">{fmtCurrency(totals.value)}</p>
            <p className="text-xs text-gray-400 mt-0.5">{po.currency || 'USD'} · {po.payment_terms}</p>
          </div>
        </div>

        {/* Quantity summary */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 p-4 bg-gray-50 rounded-xl mb-5">
          <QuantityBar label="Ordered" value={totals.ordered} total={totals.ordered} color="bg-gray-400" />
          <QuantityBar label="Released" value={totals.released} total={totals.ordered} color="bg-blue-500" />
          <QuantityBar label="Shipped" value={totals.shipped} total={totals.ordered} color="bg-indigo-500" />
          <QuantityBar label="Delivered" value={totals.delivered} total={totals.ordered} color="bg-green-500" />
        </div>

        {/* Key fields */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
          <Field label="Supplier" value={po.supplier_name} highlight />
          <Field label="Supplier Code" value={po.supplier_code} mono />
          <Field label="Buyer / Customer" value={po.buyer_name} highlight />
          <Field label="Buyer Code" value={po.buyer_code} mono />
          <Field label="Source Reference" value={po.source_reference} mono />
          <Field label="Incoterm" value={po.incoterm} />
          <Field label="Freight Terms" value={po.freight_terms} />
          <Field label="Payment Terms" value={po.payment_terms} />
          <Field label="Requested Ship" value={fmtDate(po.requested_ship_date)} />
          <Field label="Requested Delivery" value={fmtDate(po.requested_delivery_date)} />
          <Field label="Business Unit" value={po.business_unit} />
          <Field label="Cost Center" value={po.cost_center} />
        </div>

        {/* Ship from / to */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-5 pt-5 border-t border-gray-100">
          <div className="flex gap-3">
            <div className="w-8 h-8 bg-blue-50 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
              <Building2 size={14} className="text-blue-600" />
            </div>
            <div>
              <p className="text-xs font-bold text-gray-400 uppercase tracking-wide mb-1">Ship From</p>
              <p className="text-sm font-semibold text-gray-800">{po.ship_from_name}</p>
              <p className="text-xs text-gray-500">{po.ship_from_address}</p>
              <p className="text-xs text-gray-500">{[po.ship_from_city, po.ship_from_state, po.ship_from_zip].filter(Boolean).join(', ')}</p>
            </div>
          </div>
          <div className="flex gap-3">
            <div className="w-8 h-8 bg-green-50 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
              <MapPin size={14} className="text-green-600" />
            </div>
            <div>
              <p className="text-xs font-bold text-gray-400 uppercase tracking-wide mb-1">Ship To</p>
              <p className="text-sm font-semibold text-gray-800">{po.ship_to_name}</p>
              <p className="text-xs text-gray-500">{po.ship_to_address}</p>
              <p className="text-xs text-gray-500">{[po.ship_to_city, po.ship_to_state, po.ship_to_zip].filter(Boolean).join(', ')}</p>
            </div>
          </div>
        </div>

        {po.hold_flag && po.hold_reason && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
            <AlertTriangle size={14} className="text-red-500 mt-0.5 flex-shrink-0" />
            <div>
              <p className="text-xs font-semibold text-red-700">Hold Reason</p>
              <p className="text-xs text-red-600 mt-0.5">{po.hold_reason}</p>
            </div>
          </div>
        )}
      </div>

      {/* ── TABS ────────────────────────────────────────────────── */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-xl w-fit">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setActiveTab(t.key)}
            className={`flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium rounded-lg transition-colors ${activeTab === t.key ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
            <t.icon size={13} /> {t.label}
            {t.count > 0 && (
              <span className="text-xs px-1.5 py-0.5 rounded-full bg-gray-200 text-gray-600 font-semibold">{t.count}</span>
            )}
          </button>
        ))}
      </div>

      {/* ── PO LINES ──────────────────────────────────────────────  */}
      {activeTab === 'lines' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {['Line','Item #','Description','Ordered','Released','Shipped','Delivered','Remaining','Value','Status'].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {lines.length === 0 ? (
                <tr><td colSpan={10} className="text-center py-12 text-gray-400">No PO lines found</td></tr>
              ) : lines.map((line: any) => (
                <tr key={line.purchase_order_line_id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3 font-mono text-xs text-gray-500">{line.line_number}</td>
                  <td className="px-4 py-3 font-mono text-xs text-blue-600">{line.item_number}</td>
                  <td className="px-4 py-3">
                    <p className="font-medium text-gray-800 text-sm">{line.item_name || line.item_description}</p>
                    {line.item_name !== line.item_description && (
                      <p className="text-xs text-gray-400">{line.item_description}</p>
                    )}
                    <div className="flex items-center gap-2 mt-1">
                      {line.hazardous_flag && <span className="text-[10px] bg-orange-100 text-orange-700 px-1.5 py-0.5 rounded font-medium">HAZ</span>}
                      {line.temperature_requirement && <span className="text-[10px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-medium">TEMP</span>}
                      {line.packaging_type && <span className="text-[10px] text-gray-400">{line.packaging_type}</span>}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-gray-700 font-medium">{line.ordered_quantity?.toLocaleString()} <span className="text-xs text-gray-400">{line.quantity_uom}</span></td>
                  <td className="px-4 py-3 text-blue-600">{line.released_quantity?.toLocaleString()}</td>
                  <td className="px-4 py-3 text-indigo-600">{line.shipped_quantity?.toLocaleString()}</td>
                  <td className="px-4 py-3 text-green-600">{line.delivered_quantity?.toLocaleString()}</td>
                  <td className="px-4 py-3">
                    <span className={`font-semibold ${line.remaining_quantity > 0 ? 'text-orange-600' : 'text-gray-400'}`}>
                      {line.remaining_quantity?.toLocaleString()}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-medium text-gray-800">{fmtCurrency(line.line_value)}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[line.status_code] || 'bg-gray-100 text-gray-600'}`}>
                      {line.status_name || line.status_code}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
            {lines.length > 0 && (
              <tfoot className="bg-gray-50 border-t border-gray-200">
                <tr>
                  <td colSpan={3} className="px-4 py-3 text-xs font-bold text-gray-600 uppercase">Totals</td>
                  <td className="px-4 py-3 text-sm font-bold text-gray-900">{totals.ordered.toLocaleString()}</td>
                  <td className="px-4 py-3 text-sm font-bold text-blue-600">{totals.released.toLocaleString()}</td>
                  <td className="px-4 py-3 text-sm font-bold text-indigo-600">{totals.shipped.toLocaleString()}</td>
                  <td className="px-4 py-3 text-sm font-bold text-green-600">{totals.delivered.toLocaleString()}</td>
                  <td className="px-4 py-3 text-sm font-bold text-orange-600">{totals.remaining.toLocaleString()}</td>
                  <td className="px-4 py-3 text-sm font-bold text-gray-900">{fmtCurrency(totals.value)}</td>
                  <td />
                </tr>
              </tfoot>
            )}
          </table>
        </div>
      )}

      {/* ── ORDER RELEASES ──────────────────────────────────────── */}
      {activeTab === 'releases' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          {releases.length === 0 ? (
            <div className="p-10 text-center">
              <Layers size={32} className="text-gray-200 mx-auto mb-3" />
              <p className="text-sm text-gray-400">No order releases created yet</p>
              <Link href="/order-releases"
                className="inline-flex items-center gap-1.5 mt-3 text-sm text-blue-600 hover:underline">
                Go to Order Releases <ExternalLink size={12} />
              </Link>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {['Release #','Customer','Origin','Destination','Ship Date','Delivery','Mode','Lines','Status'].map(h => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {releases.map((r: any) => (
                  <tr key={r.order_release_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-sm text-blue-600">
                      <Link href={`/order-releases/${r.order_release_id}`}>{r.order_release_number}</Link>
                    </td>
                    <td className="px-4 py-3 text-gray-700">{r.customer_name || '—'}</td>
                    <td className="px-4 py-3 text-xs text-gray-500">{r.shipper_city ? `${r.shipper_city}, ${r.shipper_state}` : '—'}</td>
                    <td className="px-4 py-3 text-xs text-gray-500">{r.consignee_city ? `${r.consignee_city}, ${r.consignee_state}` : '—'}</td>
                    <td className="px-4 py-3 text-gray-500">{fmtDate(r.requested_ship_date)}</td>
                    <td className="px-4 py-3 text-gray-500">{fmtDate(r.requested_delivery_date)}</td>
                    <td className="px-4 py-3 text-gray-600 uppercase text-xs">{r.transport_mode || '—'}</td>
                    <td className="px-4 py-3 text-gray-600">{r.line_count || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_COLORS[r.status_code] || 'bg-gray-100 text-gray-600'}`}>
                        {r.status_name || r.status_code}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* ── VERSION HISTORY ─────────────────────────────────────── */}
      {activeTab === 'versions' && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          {versions.length === 0 ? (
            <div className="text-center py-8">
              <Clock size={28} className="text-gray-200 mx-auto mb-3" />
              <p className="text-sm text-gray-400">No version history available</p>
              <p className="text-xs text-gray-300 mt-1">Version {po.version_number || 1} is the current version</p>
            </div>
          ) : (
            <div className="space-y-3">
              {versions.map((v: any, i: number) => (
                <div key={i} className="flex items-start gap-4 p-4 bg-gray-50 rounded-lg">
                  <div className="w-8 h-8 bg-white border border-gray-200 rounded-full flex items-center justify-center text-xs font-bold text-gray-600 flex-shrink-0">
                    v{v.version_number}
                  </div>
                  <div className="flex-1">
                    <p className="text-sm font-medium text-gray-800">{v.change_reason || 'Version update'}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{fmtDate(v.created_at)} · {v.created_by}</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
