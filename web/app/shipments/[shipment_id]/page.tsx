'use client'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  ArrowLeft, ChevronRight, Truck, MapPin, Calendar, DollarSign,
  FileText, AlertTriangle, Search, Activity, CheckCircle, Circle,
  Package, BarChart3, Clock, ExternalLink, Zap, Navigation
} from 'lucide-react'
import { apiFetch, fmtDate, fmtDateTime, fmtCurrency, statusColor } from '../../../lib/api'

const STAGE_COLORS: Record<string, string> = {
  DELIVERED:  'bg-green-100 text-green-700',
  DISPATCHED: 'bg-blue-100 text-blue-700',
  IN_TRANSIT: 'bg-indigo-100 text-indigo-700',
  PLANNED:    'bg-gray-100 text-gray-600',
  ACCEPTED:   'bg-purple-100 text-purple-700',
  EXCEPTION:  'bg-red-100 text-red-700',
  CLOSED:     'bg-gray-50 text-gray-400',
  COSTED:     'bg-teal-100 text-teal-700',
}

function Field({ label, value, mono = false }: any) {
  return (
    <div>
      <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-0.5">{label}</p>
      <p className={`text-sm text-gray-800 ${mono ? 'font-mono' : ''} ${!value ? 'text-gray-300' : ''}`}>{value || '—'}</p>
    </div>
  )
}

function TabBtn({ active, onClick, icon: Icon, label, count, danger }: any) {
  return (
    <button onClick={onClick}
      className={`flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium rounded-lg transition-colors ${active ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
      <Icon size={13}/>{label}
      {count != null && count > 0 && (
        <span className={`text-xs px-1.5 py-0.5 rounded-full font-semibold ${danger ? 'bg-red-100 text-red-600' : 'bg-gray-200 text-gray-600'}`}>{count}</span>
      )}
    </button>
  )
}

export default function ShipmentDetailPage() {
  const params = useParams()
  const router = useRouter()
  const id = params?.shipment_id as string

  const [shipment,   setShipment]   = useState<any>(null)
  const [tracking,   setTracking]   = useState<any>(null)
  const [exceptions, setExceptions] = useState<any>(null)
  const [lifecycle,  setLifecycle]  = useState<any>(null)
  const [loading,    setLoading]    = useState(true)
  const [tab,        setTab]        = useState('overview')

  useEffect(() => {
    if (!id) return
    Promise.all([
      apiFetch(`/shipments/${id}`),
      apiFetch(`/execution/${id}/events`).catch(() => null),
      apiFetch(`/ops/exceptions?shipment_id=${id}`).catch(() => null),
      apiFetch(`/e2e/lifecycle/${id}`).catch(() => null),
    ]).then(([shp, tr, exc, lc]) => {
      setShipment(shp.shipment || shp)
      setTracking(tr)
      setExceptions(exc)
      setLifecycle(lc)
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [id])

  if (loading) return (
    <div className="flex items-center justify-center h-full py-24">
      <div className="animate-spin w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full mx-auto" />
    </div>
  )

  if (!shipment) return (
    <div className="p-8 text-center">
      <p className="text-gray-500 mb-3">Shipment not found.</p>
      <button onClick={() => router.push('/shipments')} className="text-blue-600 text-sm hover:underline">Back</button>
    </div>
  )

  const s            = shipment
  const excList      = exceptions?.exceptions || []
  const trackEvents  = tracking?.events || []
  const stageTimeline = lifecycle?.stage_timeline || []
  const financials   = lifecycle?.financials || {}
  const documents    = lifecycle?.documents || []
  const allocations  = lifecycle?.allocations || []
  const linkedPOs    = lifecycle?.linked_pos || []
  const pctComplete  = lifecycle?.pct_complete || 0
  const stagesDone   = lifecycle?.stages_done || 0
  const totalStages  = lifecycle?.total_stages || 14

  const pickupOnTime   = s.actual_pickup_datetime && s.planned_pickup_datetime ? new Date(s.actual_pickup_datetime) <= new Date(s.planned_pickup_datetime) : null
  const deliveryOnTime = s.actual_delivery_datetime && s.planned_delivery_datetime ? new Date(s.actual_delivery_datetime) <= new Date(s.planned_delivery_datetime) : null

  const TABS = [
    { key: 'overview',   label: 'Overview',   icon: Truck },
    { key: 'tracking',   label: 'Tracking',   icon: Navigation, count: trackEvents.length },
    { key: 'financials', label: 'Financials', icon: DollarSign },
    { key: 'documents',  label: 'Documents',  icon: FileText,   count: documents.length },
    { key: 'exceptions', label: 'Exceptions', icon: AlertTriangle, count: excList.length, danger: excList.some((e: any) => e.is_blocking) },
    { key: 'e2e',        label: 'E2E Trace',  icon: Search },
  ]

  return (
    <div className="p-6 max-w-7xl mx-auto space-y-4">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <button onClick={() => router.push('/shipments')} className="flex items-center gap-1 hover:text-gray-800"><ArrowLeft size={14}/> Shipments</button>
        <ChevronRight size={14}/>
        <span className="text-gray-900 font-medium font-mono">{s.shipment_number}</span>
      </div>

      {/* HEADER */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-start justify-between gap-4 mb-4">
          <div>
            <div className="flex items-center gap-3 flex-wrap mb-1">
              <h1 className="text-2xl font-bold text-gray-900 font-mono">{s.shipment_number}</h1>
              <span className={`px-3 py-1 rounded-full text-xs font-semibold ${STAGE_COLORS[s.status_code] || 'bg-gray-100 text-gray-600'}`}>{s.status_name || s.status_code}</span>
              {excList.some((e: any) => e.is_blocking && e.status !== 'resolved') && (
                <span className="px-2 py-0.5 bg-red-100 text-red-700 text-xs rounded-full font-medium flex items-center gap-1"><AlertTriangle size={10}/> Blocked</span>
              )}
              {s.closeout_completed_flag && (
                <span className="px-2 py-0.5 bg-green-100 text-green-700 text-xs rounded-full font-medium flex items-center gap-1"><CheckCircle size={10}/> Closed Out</span>
              )}
            </div>
            <p className="text-sm text-gray-500">{[s.transport_mode, s.service_level, s.equipment_type, s.freight_terms].filter(Boolean).join(' · ')}</p>
          </div>
          <div className="text-right flex-shrink-0">
            <p className="text-2xl font-bold text-gray-900">{fmtCurrency(financials.carrier_total || 0)}</p>
            <p className="text-xs text-gray-400 mt-0.5">Carrier · {financials.carrier_cost_lines || 0} lines</p>
            {financials.client_total > 0 && <p className="text-xs text-blue-600 mt-0.5 font-medium">Client: {fmtCurrency(financials.client_total)}</p>}
          </div>
        </div>

        {/* Progress */}
        <div className="mb-4">
          <div className="flex justify-between mb-1"><p className="text-xs font-semibold text-gray-500">Lifecycle</p><p className="text-xs text-gray-400">{stagesDone}/{totalStages} · {pctComplete.toFixed(0)}%</p></div>
          <div className="w-full bg-gray-100 rounded-full h-2 mb-2">
            <div className="bg-gradient-to-r from-blue-500 to-indigo-500 h-2 rounded-full" style={{ width: `${pctComplete}%` }}/>
          </div>
          {stageTimeline.length > 0 && (
            <div className="flex gap-1 flex-wrap">
              {stageTimeline.map((st: any) => (
                <span key={st.stage} className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${st.done ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-400'}`}>{st.label}</span>
              ))}
            </div>
          )}
        </div>

        {/* Lane */}
        <div className="flex items-center gap-3 p-4 bg-gray-50 rounded-xl mb-4">
          <div className="flex-1 text-right">
            <p className="text-xs text-gray-400 font-semibold uppercase tracking-wide">Origin</p>
            <p className="text-sm font-bold text-gray-900">{s.origin_name}</p>
            <p className="text-xs text-gray-500">{s.origin_address}</p>
            <p className="text-xs text-gray-500">{[s.origin_city, s.origin_state, s.origin_zip].filter(Boolean).join(', ')}</p>
          </div>
          <div className="flex flex-col items-center px-4">
            <div className="flex items-center gap-1 text-blue-500">
              <div className="w-2 h-2 rounded-full border-2 border-blue-400"/>
              <div className="w-12 h-0.5 bg-gradient-to-r from-blue-400 to-indigo-400"/>
              <Truck size={16} className="text-blue-600"/>
              <div className="w-12 h-0.5 bg-gradient-to-r from-indigo-400 to-green-400"/>
              <div className="w-2 h-2 rounded-full bg-green-400"/>
            </div>
            <p className="text-[10px] text-gray-400 mt-1">{s.transport_mode}</p>
          </div>
          <div className="flex-1">
            <p className="text-xs text-gray-400 font-semibold uppercase tracking-wide">Destination</p>
            <p className="text-sm font-bold text-gray-900">{s.destination_name}</p>
            <p className="text-xs text-gray-500">{s.destination_address}</p>
            <p className="text-xs text-gray-500">{[s.destination_city, s.destination_state, s.destination_zip].filter(Boolean).join(', ')}</p>
          </div>
        </div>

        {/* Key fields */}
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-4">
          <Field label="Carrier" value={s.carrier_name}/>
          <Field label="Customer" value={s.customer_name}/>
          <Field label="Service Level" value={s.service_level}/>
          <Field label="Equipment" value={s.equipment_type}/>
          <Field label="Weight" value={s.total_weight ? `${s.total_weight?.toLocaleString()} lbs` : null}/>
          <Field label="Pallets / Cartons" value={[s.pallet_count, s.carton_count].filter(Boolean).join(' / ') || null}/>
        </div>

        {/* Dates */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 p-4 bg-gray-50 rounded-xl">
          {[
            { label: 'Planned Pickup',   planned: s.planned_pickup_datetime,  actual: s.actual_pickup_datetime,   onTime: pickupOnTime },
            { label: 'Planned Delivery', planned: s.planned_delivery_datetime, actual: s.actual_delivery_datetime, onTime: deliveryOnTime },
          ].map(({ label, planned, actual, onTime }) => (
            <div key={label} className="col-span-1 md:col-span-2">
              <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-1">{label}</p>
              <p className="text-sm text-gray-700">{fmtDateTime(planned) || '—'}</p>
              {actual && (
                <p className={`text-xs mt-0.5 flex items-center gap-1 font-medium ${onTime === true ? 'text-green-600' : onTime === false ? 'text-red-600' : 'text-gray-500'}`}>
                  {onTime === true ? <CheckCircle size={11}/> : onTime === false ? <AlertTriangle size={11}/> : null}
                  Actual: {fmtDateTime(actual)}{onTime === true && ' (On time)'}{onTime === false && ' (Late)'}
                </p>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* TABS */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-xl w-fit flex-wrap">
        {TABS.map(t => <TabBtn key={t.key} active={tab===t.key} onClick={() => setTab(t.key)} icon={t.icon} label={t.label} count={(t as any).count} danger={(t as any).danger}/>)}
      </div>

      {/* OVERVIEW */}
      {tab === 'overview' && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="text-sm font-bold text-gray-700 mb-4 flex items-center gap-2"><DollarSign size={14} className="text-green-600"/>Financials</h3>
            <div className="space-y-2">
              {[['Carrier Cost', fmtCurrency(financials.carrier_total)],['Carrier Lines', financials.carrier_cost_lines],['Client Revenue', fmtCurrency(financials.client_total)],['Client Lines', financials.client_charge_lines]].map(([l,v]) => (
                <div key={l as string} className="flex justify-between text-sm"><span className="text-gray-500">{l}</span><span className="font-semibold text-gray-800">{v || '—'}</span></div>
              ))}
              {financials.client_total > 0 && financials.carrier_total > 0 && (
                <div className="flex justify-between text-sm pt-2 border-t border-gray-100">
                  <span className="font-bold text-gray-600">Margin</span>
                  <span className="font-bold text-blue-600">{fmtCurrency(financials.client_total - financials.carrier_total)} ({(((financials.client_total - financials.carrier_total)/financials.client_total)*100).toFixed(1)}%)</span>
                </div>
              )}
            </div>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="text-sm font-bold text-gray-700 mb-4 flex items-center gap-2"><BarChart3 size={14} className="text-purple-600"/>Allocation</h3>
            {allocations.length === 0 ? <p className="text-xs text-gray-400">No allocations</p> : (
              <div className="space-y-2">
                {allocations.map((a: any, i: number) => (
                  <div key={i} className="flex justify-between text-sm"><span className="text-gray-500 capitalize">{a.allocation_type}</span><span className="font-semibold text-gray-800">{fmtCurrency(a.total)} <span className="text-xs text-gray-400">({a.count})</span></span></div>
                ))}
              </div>
            )}
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="text-sm font-bold text-gray-700 mb-4 flex items-center gap-2"><FileText size={14} className="text-blue-600"/>Documents</h3>
            {documents.length === 0 ? <p className="text-xs text-gray-400">No documents</p> : (
              <div className="space-y-2">
                {documents.map((d: any, i: number) => (
                  <div key={i} className="flex items-center justify-between py-1 border-b border-gray-50 last:border-0">
                    <span className="text-xs font-mono bg-gray-50 px-2 py-0.5 rounded text-gray-700">{d.type_code}</span>
                    <div className="flex items-center gap-2">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${statusColor(d.status)}`}>{d.status}</span>
                      <span className="text-xs text-gray-400">{fmtDate(d.created_at)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TRACKING */}
      {tab === 'tracking' && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-bold text-gray-700 flex items-center gap-2"><Navigation size={14} className="text-indigo-600"/>Tracking Events</h3>
            {tracking?.current_milestone && <p className="text-sm font-semibold text-indigo-600 capitalize">{tracking.current_milestone?.replace(/_/g,' ')}</p>}
          </div>
          {trackEvents.length === 0 ? (
            <div className="text-center py-10"><Navigation size={28} className="text-gray-200 mx-auto mb-3"/><p className="text-sm text-gray-400">No tracking events</p></div>
          ) : (
            <div className="space-y-3">
              {trackEvents.map((ev: any, i: number) => (
                <div key={ev.tracking_event_id} className="flex gap-4">
                  <div className="flex flex-col items-center">
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 ${i===0?'bg-indigo-600':'bg-indigo-100'}`}>
                      <Activity size={14} className={i===0?'text-white':'text-indigo-600'}/>
                    </div>
                    {i < trackEvents.length - 1 && <div className="w-0.5 flex-1 bg-gray-100 mt-1"/>}
                  </div>
                  <div className="flex-1 pb-4">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2 mb-0.5">
                          <span className="text-sm font-semibold text-gray-800 font-mono capitalize">{ev.event_code?.replace(/_/g,' ') || 'EVENT'}</span>
                          {ev.source && <span className="text-xs bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded">{ev.source}</span>}
                        </div>
                        {(ev.city || ev.state_province) && (
                          <p className="text-xs text-gray-500 flex items-center gap-1"><MapPin size={10}/>{[ev.city, ev.state_province].filter(Boolean).join(', ')}
                            {ev.latitude && <span className="text-gray-300 ml-1 font-mono">{parseFloat(ev.latitude).toFixed(3)}, {parseFloat(ev.longitude).toFixed(3)}</span>}
                          </p>
                        )}
                        {ev.notes && <p className="text-xs text-gray-400 mt-0.5 italic">{ev.notes}</p>}
                      </div>
                      <span className="text-xs text-gray-400 flex-shrink-0">{fmtDateTime(ev.event_datetime)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* FINANCIALS */}
      {tab === 'financials' && (
        <div className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              { label: 'Carrier Cost',   value: fmtCurrency(financials.carrier_total), sub: `${financials.carrier_cost_lines} lines`, color: 'text-red-600' },
              { label: 'Client Revenue', value: fmtCurrency(financials.client_total),  sub: `${financials.client_charge_lines} charges`, color: 'text-blue-600' },
              { label: 'Gross Margin',   value: fmtCurrency((financials.client_total||0)-(financials.carrier_total||0)),
                sub: financials.client_total > 0 ? `${(((financials.client_total-financials.carrier_total)/financials.client_total)*100).toFixed(1)}%`:'—', color: 'text-green-600' },
            ].map(c => (
              <div key={c.label} className="bg-white rounded-xl border border-gray-200 p-5">
                <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">{c.label}</p>
                <p className={`text-3xl font-bold mt-1 ${c.color}`}>{c.value}</p>
                <p className="text-xs text-gray-400 mt-0.5">{c.sub}</p>
              </div>
            ))}
          </div>
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="text-sm font-bold text-gray-700 mb-4">Cost Allocations</h3>
            {allocations.length === 0 ? <p className="text-sm text-gray-400">No allocations found</p> : (
              <div className="space-y-3">
                {allocations.map((a: any, i: number) => {
                  const pct = financials.carrier_total > 0 ? (a.total/financials.carrier_total*100) : 0
                  return (
                    <div key={i}>
                      <div className="flex justify-between mb-1">
                        <span className="text-sm capitalize text-gray-700">{a.allocation_type}</span>
                        <span className="text-sm font-semibold text-gray-900">{fmtCurrency(a.total)} <span className="text-xs text-gray-400">{a.count} lines</span></span>
                      </div>
                      <div className="w-full bg-gray-100 rounded-full h-1.5">
                        <div className="bg-purple-500 h-1.5 rounded-full" style={{width:`${Math.min(pct,100)}%`}}/>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      )}

      {/* DOCUMENTS */}
      {tab === 'documents' && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          {documents.length === 0 ? (
            <div className="text-center py-10"><FileText size={28} className="text-gray-200 mx-auto mb-3"/><p className="text-sm text-gray-400">No documents attached</p></div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {documents.map((d: any, i: number) => (
                <div key={i} className="flex items-center gap-3 p-4 border border-gray-200 rounded-xl hover:bg-gray-50">
                  <div className="w-10 h-10 bg-blue-50 rounded-lg flex items-center justify-center"><FileText size={18} className="text-blue-600"/></div>
                  <div className="flex-1"><p className="text-sm font-semibold text-gray-800">{d.type_code}</p><p className="text-xs text-gray-400">{fmtDateTime(d.created_at)}</p></div>
                  <span className={`text-xs px-2 py-1 rounded-full font-medium ${statusColor(d.status)}`}>{d.status}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* EXCEPTIONS */}
      {tab === 'exceptions' && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          {excList.length === 0 ? (
            <div className="text-center py-10"><CheckCircle size={28} className="text-green-300 mx-auto mb-3"/><p className="text-sm text-green-600 font-medium">No exceptions</p></div>
          ) : (
            <div className="space-y-3">
              {excList.map((ex: any) => (
                <div key={ex.exception_id} className={`p-4 rounded-xl border ${ex.is_blocking && ex.status!=='resolved' ? 'border-red-200 bg-red-50' : 'border-gray-200 bg-gray-50'}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 flex-wrap mb-1">
                        <span className="font-mono text-xs text-gray-400">{ex.exception_number}</span>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${ex.severity==='critical'?'bg-red-200 text-red-800':ex.severity==='error'?'bg-red-100 text-red-700':'bg-yellow-100 text-yellow-700'}`}>{ex.severity||'warning'}</span>
                        {ex.is_blocking && <span className="text-xs bg-red-600 text-white px-2 py-0.5 rounded-full font-semibold">Blocking</span>}
                      </div>
                      <p className="text-sm font-semibold text-gray-800 capitalize mb-0.5">{ex.exception_type?.replace(/_/g,' ')}</p>
                      {ex.comments && <p className="text-xs text-gray-600">{ex.comments}</p>}
                      {ex.resolution_notes && <p className="text-xs text-green-700 mt-1 italic">✓ {ex.resolution_notes}</p>}
                    </div>
                    <span className={`text-xs px-2 py-1 rounded-full font-medium flex-shrink-0 ${statusColor(ex.status)}`}>{ex.status}</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* E2E TRACE */}
      {tab === 'e2e' && (
        <div className="space-y-4">
          {!lifecycle ? (
            <div className="bg-white rounded-xl border border-gray-200 p-10 text-center"><Search size={28} className="text-gray-200 mx-auto mb-3"/><p className="text-sm text-gray-400">No lifecycle data</p></div>
          ) : (
            <>
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <h3 className="text-sm font-bold text-gray-700 mb-4 flex items-center gap-2"><Zap size={14} className="text-indigo-600"/>Stage Timeline</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
                  {stageTimeline.map((stage: any) => (
                    <div key={stage.stage} className={`p-2.5 rounded-lg border text-center ${stage.done?'border-blue-200 bg-blue-50':'border-gray-100 bg-gray-50'}`}>
                      <div className={`w-5 h-5 rounded-full mx-auto mb-1 flex items-center justify-center ${stage.done?'bg-blue-500':'bg-gray-200'}`}>
                        {stage.done?<CheckCircle size={12} className="text-white"/>:<Circle size={8} className="text-gray-400"/>}
                      </div>
                      <p className={`text-[10px] font-semibold leading-tight ${stage.done?'text-blue-700':'text-gray-400'}`}>{stage.label}</p>
                    </div>
                  ))}
                </div>
              </div>
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <h3 className="text-sm font-bold text-gray-700 mb-3 flex items-center gap-2"><Package size={14} className="text-purple-600"/>Linked POs</h3>
                {linkedPOs.length === 0 ? <p className="text-xs text-gray-400">No POs linked</p> : (
                  <div className="flex flex-wrap gap-2">
                    {linkedPOs.map((po: any) => (
                      <Link key={po.purchase_order_id} href={`/purchase-orders/${po.purchase_order_id}`}
                        className="flex items-center gap-1.5 px-3 py-2 bg-purple-50 border border-purple-200 text-purple-700 text-sm font-medium rounded-lg hover:bg-purple-100">
                        <Package size={12}/>{po.purchase_order_number}<ExternalLink size={10}/>
                      </Link>
                    ))}
                  </div>
                )}
              </div>
              <div className="bg-white rounded-xl border border-gray-200 p-5">
                <h3 className="text-sm font-bold text-gray-700 mb-3">Quick Links</h3>
                <div className="flex flex-wrap gap-2">
                  {[
                    { href:`/e2e/lifecycle/${id}`, icon:Zap, label:'Full E2E Lifecycle', cls:'indigo' },
                    { href:`/carrier-invoices`, icon:DollarSign, label:'Carrier Invoices', cls:'green' },
                    { href:`/allocation`, icon:BarChart3, label:'Cost Allocation', cls:'purple' },
                    { href:`/exceptions`, icon:AlertTriangle, label:'Exceptions', cls:'red' },
                  ].map(l => (
                    <Link key={l.href} href={l.href}
                      className={`flex items-center gap-1.5 px-3 py-2 bg-${l.cls}-50 border border-${l.cls}-200 text-${l.cls}-700 text-sm font-medium rounded-lg hover:bg-${l.cls}-100`}>
                      <l.icon size={12}/>{l.label}<ExternalLink size={10}/>
                    </Link>
                  ))}
                </div>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  )
}
