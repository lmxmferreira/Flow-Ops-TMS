'use client'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { MapPin, ArrowLeft, ChevronRight, Pencil, Truck, Calendar, X, CheckCircle } from 'lucide-react'
import { apiFetch, apiPatch, fmtDate, fmtDateTime, statusColor } from '../../../../lib/api'

const US_STATES = ['AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA',
  'KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC',
  'ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY']

function Field({ label, value, mono = false }: any) {
  return (
    <div>
      <p className="text-[10px] font-bold text-gray-400 uppercase tracking-wide mb-0.5">{label}</p>
      <p className={`text-sm text-gray-800 ${mono ? 'font-mono' : ''} ${!value ? 'text-gray-300' : ''}`}>{value || '—'}</p>
    </div>
  )
}

export default function LocationDetailPage() {
  const params = useParams()
  const router = useRouter()
  const id = params?.location_id as string

  const [location, setLocation] = useState<any>(null)
  const [shipments, setShipments] = useState<any[]>([])
  const [stops, setStops] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [showEdit, setShowEdit] = useState(false)
  const [form, setForm] = useState<any>({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [tab, setTab] = useState('shipments')

  function load() {
    apiFetch(`/master-data/locations/${id}`)
      .then(d => {
        setLocation(d.location || d)
        setShipments(d.shipments || [])
        setStops(d.stops || [])
        setLoading(false)
      }).catch(() => setLoading(false))
  }

  useEffect(() => { if (id) load() }, [id])

  function openEdit() {
    setForm({
      location_code: location.location_code || '',
      location_name: location.location_name || '',
      address_line1: location.address_line1 || '',
      address_line2: location.address_line2 || '',
      city: location.city || '',
      state_province: location.state_province || '',
      postal_code: location.postal_code || '',
      latitude: location.latitude?.toString() || '',
      longitude: location.longitude?.toString() || '',
      time_zone: location.time_zone || '',
    })
    setError('')
    setShowEdit(true)
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault(); setSaving(true); setError('')
    try {
      const body: any = { ...form }
      if (body.latitude) body.latitude = parseFloat(body.latitude)
      if (body.longitude) body.longitude = parseFloat(body.longitude)
      Object.keys(body).forEach(k => { if (body[k] === '') delete body[k] })
      await apiPatch(`/master-data/locations/${id}`, body)
      setShowEdit(false); load()
    } catch {
      setError('Failed to save changes.')
    } finally { setSaving(false) }
  }

  if (loading) return (
    <div className="flex items-center justify-center h-full py-24">
      <div className="animate-spin w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full"/>
    </div>
  )

  if (!location) return (
    <div className="p-8 text-center">
      <p className="text-gray-500 mb-3">Location not found.</p>
      <button onClick={() => router.push('/master-data/locations')} className="text-blue-600 text-sm hover:underline">← Back</button>
    </div>
  )

  const TABS = [
    { key: 'shipments', label: 'Shipments', count: shipments.length },
    { key: 'stops', label: 'Stops', count: stops.length },
  ]

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-gray-500">
        <button onClick={() => router.push('/master-data/locations')} className="flex items-center gap-1 hover:text-gray-800">
          <ArrowLeft size={14}/> Locations
        </button>
        <ChevronRight size={14}/>
        <span className="text-gray-900 font-medium">{location.location_name}</span>
      </div>

      {/* Header card */}
      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <div className="flex items-start justify-between gap-4 mb-5">
          <div className="flex items-start gap-4">
            <div className="w-12 h-12 bg-blue-50 rounded-xl flex items-center justify-center flex-shrink-0">
              <MapPin size={22} className="text-blue-600"/>
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{location.location_name}</h1>
              <p className="text-sm font-mono text-gray-400 mt-0.5">{location.location_code}</p>
              <div className="flex items-center gap-2 mt-2">
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${location.status_id ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                  {location.status_name || (location.status_id ? 'Active' : 'Unknown')}
                </span>
              </div>
            </div>
          </div>
          <button onClick={openEdit}
            className="flex items-center gap-2 px-4 py-2 border border-gray-200 text-gray-600 text-sm font-medium rounded-lg hover:bg-gray-50 hover:text-blue-600 transition-colors">
            <Pencil size={14}/> Edit
          </button>
        </div>

        {/* Address */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div>
            <p className="text-xs font-bold text-gray-400 uppercase tracking-wide mb-2">Address</p>
            <div className="bg-gray-50 rounded-xl p-4 space-y-1">
              {location.address_line1 && <p className="text-sm text-gray-800">{location.address_line1}</p>}
              {location.address_line2 && <p className="text-sm text-gray-600">{location.address_line2}</p>}
              <p className="text-sm text-gray-600">
                {[location.city, location.state_province, location.postal_code].filter(Boolean).join(', ')}
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <Field label="Latitude" value={location.latitude?.toFixed(6)} mono/>
            <Field label="Longitude" value={location.longitude?.toFixed(6)} mono/>
            <Field label="Time Zone" value={location.time_zone}/>
            <Field label="Party" value={location.party_name}/>
          </div>
        </div>

        {/* Map link if coords available */}
        {location.latitude && location.longitude && (
          <div className="mt-4 pt-4 border-t border-gray-100">
            <a href={`https://www.google.com/maps?q=${location.latitude},${location.longitude}`}
              target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-800 font-medium w-fit">
              <MapPin size={14}/> View on Google Maps
            </a>
          </div>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-100 p-1 rounded-xl w-fit">
        {TABS.map(t => (
          <button key={t.key} onClick={() => setTab(t.key)}
            className={`flex items-center gap-1.5 px-4 py-1.5 text-sm font-medium rounded-lg transition-colors ${tab === t.key ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
            {t.label}
            {t.count > 0 && <span className="text-xs px-1.5 py-0.5 rounded-full bg-gray-200 text-gray-600 font-semibold">{t.count}</span>}
          </button>
        ))}
      </div>

      {/* Shipments tab */}
      {tab === 'shipments' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h3 className="text-sm font-bold text-gray-700 flex items-center gap-2">
              <Truck size={14} className="text-blue-600"/> Recent Shipments
            </h3>
          </div>
          {shipments.length === 0 ? (
            <div className="text-center py-10">
              <Truck size={28} className="text-gray-200 mx-auto mb-3"/>
              <p className="text-sm text-gray-400">No shipments at this location</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>{['Shipment #','Status','Planned Pickup','Planned Delivery',''].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}</tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {shipments.map((s: any) => (
                  <tr key={s.shipment_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-sm text-blue-600">
                      <Link href={`/shipments/${s.shipment_id}`}>{s.shipment_number}</Link>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(s.status_code)}`}>
                        {s.status_name || s.status_code}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-gray-500">{fmtDateTime(s.planned_pickup_datetime)}</td>
                    <td className="px-4 py-3 text-gray-500">{fmtDateTime(s.planned_delivery_datetime)}</td>
                    <td className="px-4 py-3">
                      <Link href={`/shipments/${s.shipment_id}`} className="text-blue-600 text-xs hover:underline">View →</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Stops tab */}
      {tab === 'stops' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-gray-100">
            <h3 className="text-sm font-bold text-gray-700 flex items-center gap-2">
              <Calendar size={14} className="text-green-600"/> Stop Activity
            </h3>
          </div>
          {stops.length === 0 ? (
            <div className="text-center py-10">
              <Calendar size={28} className="text-gray-200 mx-auto mb-3"/>
              <p className="text-sm text-gray-400">No stop activity at this location</p>
            </div>
          ) : (
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>{['Shipment #','Stop #','Planned Arrival','Actual Arrival',''].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}</tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {stops.map((s: any) => (
                  <tr key={s.shipment_stop_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 font-mono text-sm text-blue-600">
                      <Link href={`/shipments/${s.shipment_id}`}>{s.shipment_number}</Link>
                    </td>
                    <td className="px-4 py-3 text-gray-600">{s.stop_sequence}</td>
                    <td className="px-4 py-3 text-gray-500">{fmtDateTime(s.planned_arrival_datetime)}</td>
                    <td className="px-4 py-3">
                      {s.actual_arrival_datetime
                        ? <span className="text-green-600 font-medium flex items-center gap-1"><CheckCircle size={12}/>{fmtDateTime(s.actual_arrival_datetime)}</span>
                        : <span className="text-gray-300">Not recorded</span>}
                    </td>
                    <td className="px-4 py-3">
                      <Link href={`/shipments/${s.shipment_id}`} className="text-blue-600 text-xs hover:underline">View →</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      {/* Edit Modal */}
      {showEdit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <h2 className="text-lg font-bold text-gray-900">Edit Location</h2>
              <button onClick={() => setShowEdit(false)} className="text-gray-400 hover:text-gray-600"><X size={20}/></button>
            </div>
            <form onSubmit={handleSave} className="px-6 py-5 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1.5">Location Code <span className="text-red-500">*</span></label>
                  <input value={form.location_code} onChange={e => setForm({...form, location_code: e.target.value.toUpperCase()})} required
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"/>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1.5">Location Name <span className="text-red-500">*</span></label>
                  <input value={form.location_name} onChange={e => setForm({...form, location_name: e.target.value})} required
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"/>
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1.5">Address Line 1</label>
                <input value={form.address_line1} onChange={e => setForm({...form, address_line1: e.target.value})}
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"/>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1.5">Address Line 2</label>
                <input value={form.address_line2} onChange={e => setForm({...form, address_line2: e.target.value})}
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"/>
              </div>
              <div className="grid grid-cols-3 gap-3">
                <div className="col-span-1">
                  <label className="block text-xs font-semibold text-gray-600 mb-1.5">City</label>
                  <input value={form.city} onChange={e => setForm({...form, city: e.target.value})}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"/>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1.5">State</label>
                  <select value={form.state_province} onChange={e => setForm({...form, state_province: e.target.value})}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <option value="">—</option>
                    {US_STATES.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1.5">Postal Code</label>
                  <input value={form.postal_code} onChange={e => setForm({...form, postal_code: e.target.value})}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"/>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1.5">Latitude</label>
                  <input type="number" step="any" value={form.latitude} onChange={e => setForm({...form, latitude: e.target.value})}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"/>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1.5">Longitude</label>
                  <input type="number" step="any" value={form.longitude} onChange={e => setForm({...form, longitude: e.target.value})}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"/>
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1.5">Time Zone</label>
                <select value={form.time_zone} onChange={e => setForm({...form, time_zone: e.target.value})}
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                  <option value="">— Select —</option>
                  {['America/New_York','America/Chicago','America/Denver','America/Los_Angeles',
                    'America/Phoenix','America/Anchorage','Pacific/Honolulu','Europe/London',
                    'Europe/Berlin','Asia/Tokyo','Australia/Sydney'].map(tz => (
                    <option key={tz} value={tz}>{tz}</option>
                  ))}
                </select>
              </div>
              {error && <p className="text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>}
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setShowEdit(false)}
                  className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
                <button type="submit" disabled={saving}
                  className="px-5 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50">
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
