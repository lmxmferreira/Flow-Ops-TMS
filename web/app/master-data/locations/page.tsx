'use client'
import { useEffect, useState } from 'react'
import { MapPin, Search } from 'lucide-react'
import { apiFetch } from '../../../lib/api'

export default function LocationsPage() {
  const [locations, setLocations] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  useEffect(() => {
    apiFetch('/master-data/locations?limit=200')
      .then(d => { setLocations(Array.isArray(d) ? d : d.locations || []); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const filtered = locations.filter(l =>
    !search ||
    l.location_name?.toLowerCase().includes(search.toLowerCase()) ||
    l.location_code?.toLowerCase().includes(search.toLowerCase()) ||
    l.city?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <MapPin className="text-blue-600" size={24}/> Locations
        </h1>
        <p className="text-sm text-gray-500 mt-1">Warehouses, distribution centers, plants, and customer sites</p>
      </div>
      <div className="grid grid-cols-3 gap-4 mb-5">
        {[['Total Locations', locations.length],['With Coordinates', locations.filter(l => l.latitude && l.longitude).length],['Showing', filtered.length]].map(([label, val]) => (
          <div key={label as string} className="bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-xs font-semibold text-gray-400 uppercase tracking-wide">{label}</p>
            <p className="text-2xl font-bold text-gray-900 mt-1">{val}</p>
          </div>
        ))}
      </div>
      <div className="relative max-w-sm mb-4">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"/>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search name, code, city..."
          className="pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-blue-500"/>
      </div>
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>{['Code','Name','Address','City','State','Zip','Coordinates','Status'].map(h => (
              <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
            ))}</tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={8} className="text-center py-12 text-gray-400">Loading locations...</td></tr>
            ) : filtered.length === 0 ? (
              <tr><td colSpan={8} className="text-center py-12 text-gray-400">No locations found</td></tr>
            ) : filtered.map((l: any) => (
              <tr key={l.location_id} className="hover:bg-gray-50 transition-colors">
                <td className="px-4 py-3 font-mono text-xs text-blue-600">{l.location_code}</td>
                <td className="px-4 py-3 font-medium text-gray-900">{l.location_name}</td>
                <td className="px-4 py-3 text-gray-500 text-xs">{l.address_line1 || '—'}</td>
                <td className="px-4 py-3 text-gray-600">{l.city || '—'}</td>
                <td className="px-4 py-3 text-gray-500">{l.state_province || '—'}</td>
                <td className="px-4 py-3 text-gray-500 font-mono text-xs">{l.postal_code || '—'}</td>
                <td className="px-4 py-3 text-gray-400 font-mono text-xs">
                  {l.latitude && l.longitude ? parseFloat(l.latitude).toFixed(3) + ', ' + parseFloat(l.longitude).toFixed(3) : '—'}
                </td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${l.status_id ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                    {l.status_id ? 'Active' : 'Unknown'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length > 0 && <div className="px-4 py-2 border-t border-gray-100 bg-gray-50"><span className="text-xs text-gray-400">{filtered.length} locations</span></div>}
      </div>
    </div>
  )
}
