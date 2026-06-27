'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { MapPin, Search, Plus, Pencil, X, CheckSquare, Square, Minus, Trash2 } from 'lucide-react'
import { apiFetch, apiPost, apiPatch } from '../../../lib/api'

const EMPTY_FORM = {
  location_code: '', location_name: '', address_line1: '', address_line2: '',
  city: '', state_province: '', postal_code: '', country_id: '',
  latitude: '', longitude: '', time_zone: '',
}

const US_STATES = ['AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA',
  'KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC',
  'ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY']

function Modal({ title, onClose, children }: any) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">{title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20}/></button>
        </div>
        {children}
      </div>
    </div>
  )
}

function LocationForm({ form, setForm, onSubmit, onCancel, saving, submitLabel }: any) {
  return (
    <form onSubmit={onSubmit} className="px-6 py-5 space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1.5">Location Code <span className="text-red-500">*</span></label>
          <input value={form.location_code} onChange={e => setForm({...form, location_code: e.target.value.toUpperCase()})} required
            placeholder="e.g. WH-LA" className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"/>
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1.5">Location Name <span className="text-red-500">*</span></label>
          <input value={form.location_name} onChange={e => setForm({...form, location_name: e.target.value})} required
            placeholder="e.g. Los Angeles Warehouse" className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"/>
        </div>
      </div>
      <div>
        <label className="block text-xs font-semibold text-gray-600 mb-1.5">Address Line 1</label>
        <input value={form.address_line1} onChange={e => setForm({...form, address_line1: e.target.value})}
          placeholder="Street address" className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"/>
      </div>
      <div>
        <label className="block text-xs font-semibold text-gray-600 mb-1.5">Address Line 2</label>
        <input value={form.address_line2} onChange={e => setForm({...form, address_line2: e.target.value})}
          placeholder="Suite, floor, etc." className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"/>
      </div>
      <div className="grid grid-cols-3 gap-3">
        <div className="col-span-1">
          <label className="block text-xs font-semibold text-gray-600 mb-1.5">City</label>
          <input value={form.city} onChange={e => setForm({...form, city: e.target.value})}
            placeholder="City" className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"/>
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
            placeholder="ZIP" className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"/>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1.5">Latitude</label>
          <input type="number" step="any" value={form.latitude} onChange={e => setForm({...form, latitude: e.target.value})}
            placeholder="e.g. 34.0522" className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"/>
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1.5">Longitude</label>
          <input type="number" step="any" value={form.longitude} onChange={e => setForm({...form, longitude: e.target.value})}
            placeholder="e.g. -118.2437" className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"/>
        </div>
      </div>
      <div>
        <label className="block text-xs font-semibold text-gray-600 mb-1.5">Time Zone</label>
        <select value={form.time_zone} onChange={e => setForm({...form, time_zone: e.target.value})}
          className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
          <option value="">— Select time zone —</option>
          {['America/New_York','America/Chicago','America/Denver','America/Los_Angeles',
            'America/Phoenix','America/Anchorage','Pacific/Honolulu','Europe/London',
            'Europe/Berlin','Asia/Tokyo','Australia/Sydney'].map(tz => (
            <option key={tz} value={tz}>{tz}</option>
          ))}
        </select>
      </div>
      <div className="flex justify-end gap-3 pt-2">
        <button type="button" onClick={onCancel}
          className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
        <button type="submit" disabled={saving}
          className="px-5 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50">
          {saving ? 'Saving...' : submitLabel}
        </button>
      </div>
    </form>
  )
}

export default function LocationsPage() {
  const [locations, setLocations] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [showAdd, setShowAdd] = useState(false)
  const [editLocation, setEditLocation] = useState<any>(null)
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  function load() {
    apiFetch('/master-data/locations?limit=200')
      .then(d => { setLocations(Array.isArray(d) ? d : d.locations || []); setLoading(false) })
      .catch(() => setLoading(false))
  }
  useEffect(() => { load() }, [])

  const filtered = locations.filter(l =>
    !search ||
    l.location_name?.toLowerCase().includes(search.toLowerCase()) ||
    l.location_code?.toLowerCase().includes(search.toLowerCase()) ||
    l.city?.toLowerCase().includes(search.toLowerCase())
  )

  // Selection
  const allIds = filtered.map(l => l.location_id)
  const allSelected = allIds.length > 0 && allIds.every(id => selected.has(id))
  const someSelected = allIds.some(id => selected.has(id)) && !allSelected
  const selectedCount = allIds.filter(id => selected.has(id)).length

  function toggleAll() {
    if (allSelected) setSelected(prev => { const s = new Set(prev); allIds.forEach(id => s.delete(id)); return s })
    else setSelected(prev => new Set([...prev, ...allIds]))
  }
  function toggleOne(id: string) {
    setSelected(prev => { const s = new Set(prev); s.has(id) ? s.delete(id) : s.add(id); return s })
  }

  // Add
  async function handleAdd(e: React.FormEvent) {
    e.preventDefault(); setSaving(true); setError('')
    try {
      const body: any = { ...form }
      if (body.latitude) body.latitude = parseFloat(body.latitude)
      if (body.longitude) body.longitude = parseFloat(body.longitude)
      Object.keys(body).forEach(k => { if (body[k] === '') delete body[k] })
      await apiPost('/master-data/locations', body)
      setShowAdd(false); setForm({ ...EMPTY_FORM }); load()
    } catch {
      setError('Failed to create location. Check required fields.')
    } finally { setSaving(false) }
  }

  // Edit
  function openEdit(l: any) {
    setEditLocation(l)
    setForm({
      location_code: l.location_code || '',
      location_name: l.location_name || '',
      address_line1: l.address_line1 || '',
      address_line2: l.address_line2 || '',
      city: l.city || '',
      state_province: l.state_province || '',
      postal_code: l.postal_code || '',
      country_id: l.country_id || '',
      latitude: l.latitude?.toString() || '',
      longitude: l.longitude?.toString() || '',
      time_zone: l.time_zone || '',
    })
    setError('')
  }

  async function handleEdit(e: React.FormEvent) {
    e.preventDefault(); setSaving(true); setError('')
    try {
      const body: any = { ...form }
      if (body.latitude) body.latitude = parseFloat(body.latitude)
      if (body.longitude) body.longitude = parseFloat(body.longitude)
      Object.keys(body).forEach(k => { if (body[k] === '') delete body[k] })
      await apiPatch(`/master-data/locations/${editLocation.location_id}`, body)
      setEditLocation(null); setForm({ ...EMPTY_FORM }); load()
    } catch {
      setError('Failed to update location.')
    } finally { setSaving(false) }
  }

  const CheckIcon = allSelected ? CheckSquare : someSelected ? Minus : Square

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <MapPin className="text-blue-600" size={24}/> Locations
          </h1>
          <p className="text-sm text-gray-500 mt-1">Warehouses, distribution centers, plants, and customer sites</p>
        </div>
        <button onClick={() => { setShowAdd(true); setForm({ ...EMPTY_FORM }); setError('') }}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 shadow-sm">
          <Plus size={16}/> Add Location
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-5">
        {[['Total', locations.length], ['With Coordinates', locations.filter(l => l.latitude && l.longitude).length], ['Showing', filtered.length]].map(([label, val]) => (
          <div key={label as string} className="bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">{label}</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">{val}</p>
          </div>
        ))}
      </div>

      {/* Selection toolbar */}
      {selectedCount > 0 && (
        <div className="flex items-center gap-3 mb-4 px-4 py-3 bg-blue-50 border border-blue-200 rounded-xl">
          <span className="text-sm font-semibold text-blue-700">{selectedCount} location{selectedCount !== 1 ? 's' : ''} selected</span>
          <button onClick={() => setSelected(new Set())} className="ml-auto text-xs text-blue-500 hover:text-blue-700 font-medium">
            Clear selection
          </button>
        </div>
      )}

      {/* Search */}
      <div className="relative max-w-sm mb-4">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"/>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search name, code, city..."
          className="pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-blue-500"/>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="w-10 px-3 py-3">
                <button onClick={toggleAll} className={`transition-colors ${allSelected ? 'text-blue-600' : 'text-gray-400 hover:text-blue-500'}`}>
                  <CheckIcon size={16}/>
                </button>
              </th>
              {['Code','Name','Address','City','State','Zip','Coordinates','Status',''].map(h => (
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={10} className="text-center py-12 text-gray-400">Loading locations...</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={10} className="text-center py-12 text-gray-400">No locations found</td></tr>
            ) : filtered.map((l: any) => {
              const isSelected = selected.has(l.location_id)
              return (
                <tr key={l.location_id} className={`transition-colors ${isSelected ? 'bg-blue-50' : 'hover:bg-gray-50'}`}>
                  <td className="px-3 py-3">
                    <button onClick={() => toggleOne(l.location_id)}
                      className={`transition-colors ${isSelected ? 'text-blue-600' : 'text-gray-300 hover:text-gray-500'}`}>
                      {isSelected ? <CheckSquare size={16}/> : <Square size={16}/>}
                    </button>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-blue-600">{l.location_code}</td>
                  <td className="px-4 py-3 font-medium text-blue-600 hover:underline"><Link href={`/master-data/locations/${l.location_id}`}>{l.location_name}</Link></td>
                  <td className="px-4 py-3 text-gray-500 text-xs">{l.address_line1 || '—'}</td>
                  <td className="px-4 py-3 text-gray-600">{l.city || '—'}</td>
                  <td className="px-4 py-3 text-gray-500">{l.state_province || '—'}</td>
                  <td className="px-4 py-3 text-gray-500 font-mono text-xs">{l.postal_code || '—'}</td>
                  <td className="px-4 py-3 text-gray-400 font-mono text-xs">
                    {l.latitude && l.longitude ? `${parseFloat(l.latitude).toFixed(3)}, ${parseFloat(l.longitude).toFixed(3)}` : '—'}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${l.status_id ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {l.status_id ? 'Active' : 'Unknown'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button onClick={() => openEdit(l)}
                      className="flex items-center gap-1 text-xs text-gray-400 hover:text-blue-600 transition-colors px-2 py-1 rounded hover:bg-blue-50">
                      <Pencil size={12}/> Edit
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
        {filtered.length > 0 && (
          <div className="px-4 py-2 border-t border-gray-100 bg-gray-50 flex items-center justify-between">
            <span className="text-xs text-gray-400">{filtered.length} locations</span>
            {selectedCount > 0 && <span className="text-xs font-medium text-blue-600">{selectedCount} selected</span>}
          </div>
        )}
      </div>

      {/* Add Modal */}
      {showAdd && (
        <Modal title="Add Location" onClose={() => setShowAdd(false)}>
          {error && <p className="mx-6 mt-4 text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>}
          <LocationForm form={form} setForm={setForm} onSubmit={handleAdd}
            onCancel={() => setShowAdd(false)} saving={saving} submitLabel="Create Location"/>
        </Modal>
      )}

      {/* Edit Modal */}
      {editLocation && (
        <Modal title={`Edit — ${editLocation.location_name}`} onClose={() => setEditLocation(null)}>
          {error && <p className="mx-6 mt-4 text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>}
          <LocationForm form={form} setForm={setForm} onSubmit={handleEdit}
            onCancel={() => setEditLocation(null)} saving={saving} submitLabel="Save Changes"/>
        </Modal>
      )}
    </div>
  )
}
