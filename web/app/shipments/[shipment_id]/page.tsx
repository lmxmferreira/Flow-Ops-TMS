'use client'
import { useEffect, useState, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  ArrowLeft, Package, Truck, MapPin, Calendar, DollarSign,
  Scale, FileText, AlertTriangle, Pencil, X, Save, RefreshCw, Check
} from 'lucide-react'
import { apiFetch as api } from '../../lib/api'

// ── Types ──────────────────────────────────────────────────────
interface Shipment {
  shipment_id: string; shipment_number: string; closeout_completed_flag: boolean
  total_weight: number|null; total_volume: number|null; pallet_count: number|null
  carton_count: number|null; unit_count: number|null; linear_feet: number|null
  distance_value: number|null; chargeable_weight: number|null
  planned_pickup_datetime: string|null; planned_delivery_datetime: string|null
  actual_pickup_datetime: string|null; actual_delivery_datetime: string|null
  created_at: string; updated_at: string
  // FK ids
  shipment_status_id: string|null; carrier_id: string|null
  transport_mode_id: string|null; service_level_id: string|null
  equipment_type_id: string|null; origin_location_id: string|null
  destination_location_id: string|null; customer_party_id: string|null
  supplier_party_id: string|null; financial_owner_party_id: string|null
  freight_terms_id: string|null; currency_id: string|null
  // Resolved
  status_code: string; status_name: string; shipment_type: string
  carrier_name: string; transport_mode: string; service_level: string
  equipment_type: string; freight_terms: string; currency: string; distance_uom: string
  origin_name: string; origin_code: string; origin_address: string
  origin_city: string; origin_state: string; origin_zip: string
  destination_name: string; destination_code: string; destination_address: string
  destination_city: string; destination_state: string; destination_zip: string
  customer_name: string; supplier_name: string; financial_owner_name: string
}

interface LinkedPO {
  purchase_order_id: string; purchase_order_number: string
  status_code: string; status_name: string; supplier_name: string
  requested_ship_date: string|null; requested_delivery_date: string|null
  hold_flag: boolean; order_release_number: string
}

// ── Helpers ────────────────────────────────────────────────────
const STATUS_COLORS: Record<string,string> = {
  DRAFT:'bg-gray-100 text-gray-700', PLANNED:'bg-blue-100 text-blue-700',
  IN_TRANSIT:'bg-orange-100 text-orange-700', DELIVERED:'bg-green-100 text-green-700',
  CANCELLED:'bg-red-100 text-red-700', EXCEPTION:'bg-red-200 text-red-800',
  UNKNOWN:'bg-gray-100 text-gray-500',
}
const sc = (code: string) => STATUS_COLORS[code] ?? STATUS_COLORS.UNKNOWN

function fmtDate(d: string|null) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'})
}
function fmtDateTime(d: string|null) {
  if (!d) return '—'
  return new Date(d).toLocaleString('en-US',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'})
}
function fmtNum(n: number|null, dec=2) {
  if (n===null||n===undefined) return '—'
  return Number(n).toLocaleString('en-US',{minimumFractionDigits:dec,maximumFractionDigits:dec})
}
function fmtLoc(name:string, city:string, state:string) {
  const place = [city,state].filter(Boolean).join(', ')
  return place || name || '—'
}

function Section({title,icon:Icon,children}:{title:string;icon:React.ElementType;children:React.ReactNode}) {
  return (
    <div className="bg-white rounded-lg border overflow-hidden">
      <div className="flex items-center gap-2 px-5 py-3 border-b bg-gray-50">
        <Icon size={15} className="text-blue-600"/>
        <h2 className="text-sm font-semibold text-gray-700">{title}</h2>
      </div>
      <div className="px-5 py-4">{children}</div>
    </div>
  )
}

function Field({label,value}:{label:string;value:React.ReactNode}) {
  return (
    <div>
      <p className="text-xs text-gray-400 mb-0.5">{label}</p>
      <p className="text-sm text-gray-800 font-medium">{value||'—'}</p>
    </div>
  )
}

// ── Edit Modal ─────────────────────────────────────────────────
function EditModal({shipment, onClose, onSaved}: {
  shipment: Shipment; onClose: () => void; onSaved: () => void
}) {
  const [form, setForm] = useState({
    planned_pickup_datetime:   shipment.planned_pickup_datetime?.slice(0,16) ?? '',
    planned_delivery_datetime: shipment.planned_delivery_datetime?.slice(0,16) ?? '',
    actual_pickup_datetime:    shipment.actual_pickup_datetime?.slice(0,16) ?? '',
    actual_delivery_datetime:  shipment.actual_delivery_datetime?.slice(0,16) ?? '',
    total_weight:     shipment.total_weight?.toString() ?? '',
    total_volume:     shipment.total_volume?.toString() ?? '',
    pallet_count:     shipment.pallet_count?.toString() ?? '',
    carton_count:     shipment.carton_count?.toString() ?? '',
    unit_count:       shipment.unit_count?.toString() ?? '',
    linear_feet:      shipment.linear_feet?.toString() ?? '',
    distance_value:   shipment.distance_value?.toString() ?? '',
    chargeable_weight:shipment.chargeable_weight?.toString() ?? '',
    closeout_completed_flag: shipment.closeout_completed_flag,
  })
  const [saving, setSaving] = useState(false)
  const [error, setError]   = useState('')

  const set = (k: string, v: string | boolean) => setForm(f => ({...f, [k]: v}))

  const save = async () => {
    setSaving(true); setError('')
    try {
      const payload: Record<string, unknown> = {
        closeout_completed_flag: form.closeout_completed_flag,
      }
      const numFields = ['total_weight','total_volume','pallet_count','carton_count',
        'unit_count','linear_feet','distance_value','chargeable_weight']
      const dtFields = ['planned_pickup_datetime','planned_delivery_datetime',
        'actual_pickup_datetime','actual_delivery_datetime']
      numFields.forEach(f => { if (form[f as keyof typeof form]) payload[f] = parseFloat(form[f as keyof typeof form] as string) })
      dtFields.forEach(f => { if (form[f as keyof typeof form]) payload[f] = form[f as keyof typeof form] })
      await api.shipments.update(shipment.shipment_id, payload)
      onSaved()
    } catch { setError('Failed to save changes') }
    finally { setSaving(false) }
  }

  const inp = 'w-full border rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500'
  const lbl = 'text-xs text-gray-500 mb-1 block'

  return (
    <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b sticky top-0 bg-white z-10">
          <div className="flex items-center gap-2">
            <Pencil size={16} className="text-blue-600"/>
            <h2 className="text-lg font-semibold text-gray-800">Edit Shipment</h2>
            <span className="font-mono text-sm text-gray-400">{shipment.shipment_number}</span>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 p-1"><X size={18}/></button>
        </div>

        <div className="px-6 py-5 space-y-5">
          {error && <div className="bg-red-50 border border-red-200 rounded p-3 text-sm text-red-600">{error}</div>}

          {/* Dates */}
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Dates & Times</p>
            <div className="grid grid-cols-2 gap-3">
              {[
                ['planned_pickup_datetime','Planned Pickup'],
                ['planned_delivery_datetime','Planned Delivery'],
                ['actual_pickup_datetime','Actual Pickup'],
                ['actual_delivery_datetime','Actual Delivery'],
              ].map(([key, label]) => (
                <div key={key}>
                  <label className={lbl}>{label}</label>
                  <input type="datetime-local" value={form[key as keyof typeof form] as string}
                    onChange={e => set(key, e.target.value)} className={inp}/>
                </div>
              ))}
            </div>
          </div>

          {/* Cargo */}
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Cargo Measurements</p>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {[
                ['total_weight','Total Weight (kg)'],
                ['total_volume','Total Volume (m³)'],
                ['chargeable_weight','Chargeable Weight (kg)'],
                ['pallet_count','Pallet Count'],
                ['carton_count','Carton Count'],
                ['unit_count','Unit Count'],
                ['linear_feet','Linear Feet'],
                ['distance_value','Distance'],
              ].map(([key, label]) => (
                <div key={key}>
                  <label className={lbl}>{label}</label>
                  <input type="number" step="0.001" value={form[key as keyof typeof form] as string}
                    onChange={e => set(key, e.target.value)} className={inp} placeholder="0"/>
                </div>
              ))}
            </div>
          </div>

          {/* Flags */}
          <div>
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">Flags</p>
            <label className="flex items-center gap-2 text-sm cursor-pointer">
              <input type="checkbox" checked={form.closeout_completed_flag}
                onChange={e => set('closeout_completed_flag', e.target.checked)}
                className="rounded border-gray-300"/>
              <span className="text-gray-700">Closeout Completed</span>
            </label>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t flex justify-end gap-3 sticky bottom-0 bg-white">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-500 hover:text-gray-700">Cancel</button>
          <button onClick={save} disabled={saving}
            className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2">
            {saving ? <RefreshCw size={14} className="animate-spin"/> : <Save size={14}/>}
            Save Changes
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Main page ──────────────────────────────────────────────────
export default function ShipmentDetailPage() {
  const params  = useParams<{shipment_id: string}>()
  const router  = useRouter()
  const [shipment, setShipment] = useState<Shipment|null>(null)
  const [pos, setPos]           = useState<LinkedPO[]>([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState('')
  const [editing, setEditing]   = useState(false)

  const load = useCallback(async () => {
    if (!params.shipment_id) return
    setLoading(true)
    try {
      const res = await api.shipments.get(params.shipment_id)
      setShipment(res.shipment)
      setPos(res.purchase_orders)
    } catch { setError('Failed to load shipment') }
    finally { setLoading(false) }
  }, [params.shipment_id])

  useEffect(() => { load() }, [load])

  if (loading) return <div className="flex items-center justify-center h-64 text-gray-400 text-sm"><RefreshCw size={18} className="animate-spin mr-2"/>Loading…</div>
  if (error||!shipment) return <div className="flex items-center justify-center h-64 text-red-500 text-sm">{error||'Not found'}</div>

  return (
    <div className="min-h-screen bg-gray-50">
      {editing && (
        <EditModal shipment={shipment} onClose={() => setEditing(false)} onSaved={() => { setEditing(false); load() }}/>
      )}

      {/* Header */}
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center gap-3 mb-1">
          <button onClick={() => router.back()} className="text-gray-400 hover:text-blue-600 transition-colors">
            <ArrowLeft size={18}/>
          </button>
          <Package size={18} className="text-blue-600"/>
          <h1 className="text-xl font-semibold text-gray-800">{shipment.shipment_number}</h1>
          <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${sc(shipment.status_code)}`}>
            {shipment.status_name}
          </span>
          {shipment.closeout_completed_flag && (
            <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700 flex items-center gap-1">
              <Check size={10}/> Closed Out
            </span>
          )}
          {shipment.shipment_type && (
            <span className="text-xs text-gray-400">{shipment.shipment_type}</span>
          )}
          <div className="ml-auto flex items-center gap-2">
            <button onClick={() => load()}
              className="text-gray-400 hover:text-blue-600 p-1.5 rounded hover:bg-gray-100">
              <RefreshCw size={15}/>
            </button>
            <button onClick={() => setEditing(true)}
              className="flex items-center gap-1.5 px-3 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors">
              <Pencil size={14}/> Edit Shipment
            </button>
          </div>
        </div>
        <p className="text-xs text-gray-400 ml-9">
          Created {fmtDate(shipment.created_at)} · Updated {fmtDate(shipment.updated_at)}
        </p>
      </div>

      <div className="px-6 py-5 space-y-4">
        {/* Row 1 — Route / Carrier / Dates */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Section title="Route" icon={MapPin}>
            <div className="space-y-3">
              <div>
                <p className="text-xs text-gray-400 mb-1">Origin</p>
                <p className="text-sm font-semibold text-gray-800">{shipment.origin_name||fmtLoc(shipment.origin_name, shipment.origin_city, shipment.origin_state)||'—'}</p>
                {shipment.origin_address && <p className="text-xs text-gray-500">{shipment.origin_address}</p>}
                <p className="text-xs text-gray-500">{[shipment.origin_city,shipment.origin_state,shipment.origin_zip].filter(Boolean).join(', ')}</p>
                {shipment.origin_code && <p className="text-xs text-gray-400 font-mono">{shipment.origin_code}</p>}
              </div>
              <div>
                <p className="text-xs text-gray-400 mb-1">Destination</p>
                <p className="text-sm font-semibold text-gray-800">{shipment.destination_name||fmtLoc(shipment.destination_name, shipment.destination_city, shipment.destination_state)||'—'}</p>
                {shipment.destination_address && <p className="text-xs text-gray-500">{shipment.destination_address}</p>}
                <p className="text-xs text-gray-500">{[shipment.destination_city,shipment.destination_state,shipment.destination_zip].filter(Boolean).join(', ')}</p>
                {shipment.destination_code && <p className="text-xs text-gray-400 font-mono">{shipment.destination_code}</p>}
              </div>
              {shipment.distance_value && (
                <Field label="Distance" value={`${fmtNum(shipment.distance_value)} ${shipment.distance_uom||'mi'}`}/>
              )}
            </div>
          </Section>

          <Section title="Carrier & Transport" icon={Truck}>
            <div className="space-y-3">
              <Field label="Carrier"         value={shipment.carrier_name}/>
              <Field label="Transport Mode"  value={shipment.transport_mode}/>
              <Field label="Service Level"   value={shipment.service_level}/>
              <Field label="Equipment Type"  value={shipment.equipment_type}/>
              <Field label="Freight Terms"   value={shipment.freight_terms}/>
              <Field label="Currency"        value={shipment.currency}/>
            </div>
          </Section>

          <Section title="Dates" icon={Calendar}>
            <div className="space-y-3">
              <Field label="Planned Pickup"    value={fmtDateTime(shipment.planned_pickup_datetime)}/>
              <Field label="Planned Delivery"  value={fmtDateTime(shipment.planned_delivery_datetime)}/>
              <Field label="Actual Pickup"     value={fmtDateTime(shipment.actual_pickup_datetime)}/>
              <Field label="Actual Delivery"   value={fmtDateTime(shipment.actual_delivery_datetime)}/>
            </div>
          </Section>
        </div>

        {/* Row 2 — Cargo / Parties */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Section title="Cargo Measurements" icon={Scale}>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Total Weight"       value={shipment.total_weight      ? `${fmtNum(shipment.total_weight,3)} kg`  : '—'}/>
              <Field label="Total Volume"       value={shipment.total_volume      ? `${fmtNum(shipment.total_volume,3)} m³`  : '—'}/>
              <Field label="Chargeable Weight"  value={shipment.chargeable_weight ? `${fmtNum(shipment.chargeable_weight,3)} kg` : '—'}/>
              <Field label="Pallet Count"       value={shipment.pallet_count      ? fmtNum(shipment.pallet_count,0) : '—'}/>
              <Field label="Carton Count"       value={shipment.carton_count      ? fmtNum(shipment.carton_count,0) : '—'}/>
              <Field label="Unit Count"         value={shipment.unit_count        ? fmtNum(shipment.unit_count,0)   : '—'}/>
              <Field label="Linear Feet"        value={shipment.linear_feet       ? `${fmtNum(shipment.linear_feet,2)} ft` : '—'}/>
              <Field label="Distance"           value={shipment.distance_value    ? `${fmtNum(shipment.distance_value,2)} ${shipment.distance_uom||'mi'}` : '—'}/>
            </div>
          </Section>

          <Section title="Parties" icon={Package}>
            <div className="space-y-3">
              <Field label="Customer"         value={shipment.customer_name}/>
              <Field label="Supplier"         value={shipment.supplier_name}/>
              <Field label="Financial Owner"  value={shipment.financial_owner_name}/>
            </div>
            {pos.length > 0 && (
              <div className="mt-4 pt-4 border-t">
                <p className="text-xs text-gray-400 mb-2">Linked Purchase Orders ({pos.length})</p>
                <div className="space-y-2">
                  {pos.map(po => (
                    <div key={po.purchase_order_id} className="flex items-center justify-between">
                      <div>
                        <Link href={`/purchase-orders/${po.purchase_order_id}`}
                          className="flex items-center gap-1 text-sm font-mono font-semibold text-indigo-700 hover:underline">
                          <FileText size={12}/>{po.purchase_order_number}
                        </Link>
                        <p className="text-xs text-gray-400">{po.order_release_number} · {po.supplier_name}</p>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${sc(po.status_code)}`}>
                          {po.status_name}
                        </span>
                        {po.hold_flag && <AlertTriangle size={13} className="text-yellow-500"/>}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Section>
        </div>
      </div>
    </div>
  )
}
