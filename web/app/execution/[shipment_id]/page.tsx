'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { Navigation, ArrowLeft, MapPin, CheckCircle, Clock, AlertTriangle, Package, FileText } from 'lucide-react'

const API = process.env.NEXT_PUBLIC_API_URL

const MILESTONE_ICONS: Record<string, string> = {
  tendered: '📤', accepted: '✅', dispatched: '🚛', arrived_pickup: '📍',
  picked_up: '📦', departed_pickup: '🛣️', in_transit: '🛣️',
  arrived_delivery: '📍', delivered: '✅', completed: '🏁', closed: '🔒', exception: '⚠️',
}

export default function ExecutionDetailPage() {
  const { shipment_id } = useParams()
  const [events, setEvents] = useState<any>(null)
  const [shipment, setShipment] = useState<any>(null)
  const [assets, setAssets] = useState<any[]>([])
  const [proof, setProof] = useState<any[]>([])
  const [lifecycle, setLifecycle] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [dispatchLoading, setDispatchLoading] = useState(false)
  const [newEvent, setNewEvent] = useState({ event_code: '', city: '', state_province: '', notes: '' })

  const token = () => localStorage.getItem('tms_token')

  useEffect(() => {
    Promise.all([
      fetch(`${API}/shipments/${shipment_id}`, { headers: { Authorization: `Bearer ${token()}` } }).then(r => r.json()),
      fetch(`${API}/execution/${shipment_id}/events`, { headers: { Authorization: `Bearer ${token()}` } }).then(r => r.json()),
      fetch(`${API}/execution/${shipment_id}/assets`, { headers: { Authorization: `Bearer ${token()}` } }).then(r => r.json()),
      fetch(`${API}/execution/${shipment_id}/proof`, { headers: { Authorization: `Bearer ${token()}` } }).then(r => r.json()),
      fetch(`${API}/e2e/lifecycle/${shipment_id}`, { headers: { Authorization: `Bearer ${token()}` } }).then(r => r.json()),
    ]).then(([shp, evts, ast, prf, lc]) => {
      setShipment(shp)
      setEvents(evts)
      setAssets(Array.isArray(ast) ? ast : [])
      setProof(Array.isArray(prf) ? prf : [])
      setLifecycle(lc)
      setLoading(false)
    })
  }, [shipment_id])

  const dispatch = async () => {
    setDispatchLoading(true)
    await fetch(`${API}/execution/${shipment_id}/dispatch`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token()}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ dispatch_notes: 'Dispatched from TMS' }),
    })
    const evts = await fetch(`${API}/execution/${shipment_id}/events`, { headers: { Authorization: `Bearer ${token()}` } }).then(r => r.json())
    setEvents(evts)
    setDispatchLoading(false)
  }

  const recordEvent = async () => {
    if (!newEvent.event_code) return
    await fetch(`${API}/execution/${shipment_id}/events`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token()}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...newEvent, event_source: 'manual' }),
    })
    const evts = await fetch(`${API}/execution/${shipment_id}/events`, { headers: { Authorization: `Bearer ${token()}` } }).then(r => r.json())
    setEvents(evts)
    setNewEvent({ event_code: '', city: '', state_province: '', notes: '' })
  }

  if (loading) return <div className="p-8 text-gray-400">Loading...</div>

  const milestoneSeq = ['tendered','accepted','dispatched','arrived_pickup','picked_up','departed_pickup','in_transit','arrived_delivery','delivered','completed','closed']
  const currentIdx = milestoneSeq.indexOf(events?.current_milestone || '')

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Link href="/execution" className="text-gray-400 hover:text-gray-700"><ArrowLeft size={20} /></Link>
        <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
          <Navigation size={20} className="text-blue-600" />
          {shipment?.shipment_number} — Execution
        </h1>
        <span className="text-sm text-gray-500">{shipment?.origin_city} → {shipment?.destination_city}</span>
      </div>

      {/* Milestone progress bar */}
      <div className="bg-white rounded-xl border border-gray-200 p-5 mb-6">
        <h2 className="text-sm font-semibold text-gray-700 mb-4">Milestone Progress</h2>
        <div className="flex items-center gap-0 overflow-x-auto pb-2">
          {milestoneSeq.map((m, idx) => (
            <div key={m} className="flex items-center">
              <div className={`flex flex-col items-center min-w-[80px]`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm ${
                  idx < currentIdx ? 'bg-green-500 text-white' :
                  idx === currentIdx ? 'bg-blue-600 text-white' :
                  'bg-gray-100 text-gray-400'
                }`}>
                  {idx < currentIdx ? '✓' : MILESTONE_ICONS[m] || '·'}
                </div>
                <span className={`text-xs mt-1 text-center leading-tight ${idx <= currentIdx ? 'text-gray-700 font-medium' : 'text-gray-400'}`}>
                  {m.replace(/_/g,' ')}
                </span>
              </div>
              {idx < milestoneSeq.length - 1 && (
                <div className={`h-0.5 w-6 mx-1 mb-5 ${idx < currentIdx ? 'bg-green-400' : 'bg-gray-200'}`} />
              )}
            </div>
          ))}
        </div>
        <div className="mt-4 flex gap-2">
          <button onClick={dispatch} disabled={dispatchLoading}
            className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded-lg hover:bg-blue-700 disabled:opacity-50">
            {dispatchLoading ? 'Dispatching...' : '🚛 Dispatch'}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Event log */}
        <div className="col-span-2 space-y-4">
          {/* Record event */}
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Record Event</h2>
            <div className="flex gap-2">
              <select value={newEvent.event_code} onChange={e => setNewEvent({...newEvent, event_code: e.target.value})}
                className="text-sm border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none focus:ring-2 focus:ring-blue-500">
                <option value="">Select milestone...</option>
                {milestoneSeq.map(m => <option key={m} value={m}>{m.replace(/_/g,' ')}</option>)}
                <option value="exception">Exception</option>
              </select>
              <input placeholder="City" value={newEvent.city} onChange={e => setNewEvent({...newEvent, city: e.target.value})}
                className="text-sm border border-gray-200 rounded-lg px-2 py-1.5 w-24 focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <input placeholder="State" value={newEvent.state_province} onChange={e => setNewEvent({...newEvent, state_province: e.target.value})}
                className="text-sm border border-gray-200 rounded-lg px-2 py-1.5 w-16 focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <input placeholder="Notes" value={newEvent.notes} onChange={e => setNewEvent({...newEvent, notes: e.target.value})}
                className="text-sm border border-gray-200 rounded-lg px-2 py-1.5 flex-1 focus:outline-none focus:ring-2 focus:ring-blue-500" />
              <button onClick={recordEvent}
                className="px-3 py-1.5 bg-blue-600 text-white text-xs rounded-lg hover:bg-blue-700">
                Record
              </button>
            </div>
          </div>

          {/* Events timeline */}
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h2 className="text-sm font-semibold text-gray-700 mb-4">Event History ({events?.event_count || 0})</h2>
            <div className="space-y-3">
              {(events?.events || []).map((e: any) => (
                <div key={e.tracking_event_id} className="flex items-start gap-3 text-sm">
                  <div className="text-lg w-6 text-center mt-0.5">{MILESTONE_ICONS[e.event_code] || '•'}</div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-800 capitalize">{e.event_code?.replace(/_/g,' ')}</span>
                      {e.city && <span className="text-gray-400 text-xs flex items-center gap-1"><MapPin size={10}/>{e.city}, {e.state_province}</span>}
                      <span className="text-xs text-gray-400 ml-auto">{new Date(e.event_datetime).toLocaleString()}</span>
                    </div>
                    {e.notes && <p className="text-gray-500 text-xs mt-0.5">{e.notes}</p>}
                    <p className="text-gray-400 text-xs">via {e.event_source}</p>
                  </div>
                </div>
              ))}
              {(!events?.events || events.events.length === 0) && (
                <p className="text-gray-400 text-sm text-center py-4">No events recorded yet</p>
              )}
            </div>
          </div>
        </div>

        {/* Right panel */}
        <div className="space-y-4">
          {/* Assets */}
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Assets & References</h2>
            {assets.length === 0 ? (
              <p className="text-xs text-gray-400">No assets assigned</p>
            ) : (
              <div className="space-y-2">
                {assets.map((a: any) => (
                  <div key={a.asset_id} className="flex justify-between text-xs">
                    <span className="text-gray-500 capitalize">{a.asset_type?.replace(/_/g,' ')}</span>
                    <span className="font-mono font-medium text-gray-800">{a.asset_value}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* POD */}
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-3">Proof of Delivery</h2>
            {proof.length === 0 ? (
              <div>
                <p className="text-xs text-gray-400 mb-2">No POD captured</p>
                <button onClick={() => {
                  fetch(`${API}/execution/${shipment_id}/proof`, {
                    method: 'POST',
                    headers: { Authorization: `Bearer ${token()}`, 'Content-Type': 'application/json' },
                    body: JSON.stringify({ proof_type: 'pod', signatory_name: 'Receiver', notes: 'Manual POD capture' }),
                  }).then(() => fetch(`${API}/execution/${shipment_id}/proof`, { headers: { Authorization: `Bearer ${token()}` } })
                    .then(r => r.json()).then(d => setProof(Array.isArray(d) ? d : [])))
                }} className="text-xs px-2 py-1 bg-green-600 text-white rounded hover:bg-green-700">
                  Capture POD
                </button>
              </div>
            ) : proof.map((p: any) => (
              <div key={p.proof_id} className="text-xs space-y-1">
                <div className="flex justify-between"><span className="text-gray-500">Type</span><span className="font-medium uppercase">{p.proof_type}</span></div>
                <div className="flex justify-between"><span className="text-gray-500">Captured</span><span>{new Date(p.captured_at).toLocaleDateString()}</span></div>
                {p.signatory_name && <div className="flex justify-between"><span className="text-gray-500">Signatory</span><span>{p.signatory_name}</span></div>}
                <div className="flex justify-between"><span className="text-gray-500">Source</span><span className="capitalize">{p.capture_source}</span></div>
              </div>
            ))}
          </div>

          {/* Lifecycle % */}
          {lifecycle && (
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <h2 className="text-sm font-semibold text-gray-700 mb-3">Lifecycle</h2>
              <div className="flex items-center gap-3">
                <div className="flex-1 bg-gray-100 rounded-full h-2">
                  <div className="bg-blue-600 h-2 rounded-full" style={{ width: `${lifecycle.pct_complete}%` }} />
                </div>
                <span className="text-sm font-bold text-gray-900">{lifecycle.pct_complete}%</span>
              </div>
              <p className="text-xs text-gray-500 mt-2">{lifecycle.stages_done}/{lifecycle.total_stages} stages complete</p>
              <Link href={`/e2e/lifecycle/${shipment_id}`} className="text-xs text-blue-600 hover:underline mt-1 block">
                Full lifecycle →
              </Link>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
