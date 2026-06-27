'use client'
import { useEffect, useState } from 'react'
import { Database, Package, MapPin, DollarSign, Search, Plus } from 'lucide-react'

const API = process.env.NEXT_PUBLIC_API_URL

type Tab = 'items' | 'locations' | 'charge_codes'

export default function MasterDataPage() {
  const [tab, setTab] = useState<Tab>('charge_codes')
  const [data, setData] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  const token = () => localStorage.getItem('tms_token')

  useEffect(() => {
    setLoading(true)
    const urlMap: Record<Tab, string> = {
      items: `${API}/master-data/items`,
      locations: `${API}/master-data/locations`,
      charge_codes: `${API}/master-data/charge-codes`,
    }
    fetch(urlMap[tab], { headers: { Authorization: `Bearer ${token()}` } })
      .then(r => r.json())
      .then(d => { setData(Array.isArray(d) ? d : []); setLoading(false) })
  }, [tab])

  const filtered = data.filter(d =>
    !search || JSON.stringify(d).toLowerCase().includes(search.toLowerCase())
  )

  const TABS: { key: Tab; label: string; icon: any }[] = [
    { key: 'charge_codes', label: 'Charge Codes', icon: DollarSign },
    { key: 'items', label: 'Items', icon: Package },
    { key: 'locations', label: 'Locations', icon: MapPin },
  ]

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Database className="text-blue-600" size={24} /> Master Data
          </h1>
          <p className="text-sm text-gray-500 mt-1">Manage items, locations, and charge codes</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 bg-gray-100 p-1 rounded-lg w-fit">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button key={key} onClick={() => { setTab(key); setSearch('') }}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              tab === key ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'
            }`}>
            <Icon size={14} />{label}
          </button>
        ))}
      </div>

      {/* Search */}
      <div className="relative max-w-sm mb-4">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
        <input value={search} onChange={e => setSearch(e.target.value)}
          placeholder={`Search ${tab.replace('_',' ')}...`}
          className="pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-blue-500" />
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        {tab === 'charge_codes' && (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {['Code','Name','Category','Applies To','GL Account','Billing Category','Active'].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? <tr><td colSpan={7} className="text-center py-12 text-gray-400">Loading...</td></tr>
                : filtered.map((c: any) => (
                <tr key={c.charge_code_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono font-bold text-blue-600">{c.charge_code}</td>
                  <td className="px-4 py-3 text-gray-800">{c.charge_name}</td>
                  <td className="px-4 py-3 capitalize">
                    <span className="px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700">{c.charge_category}</span>
                  </td>
                  <td className="px-4 py-3 capitalize text-gray-600">{c.applies_to}</td>
                  <td className="px-4 py-3 font-mono text-gray-600">{c.gl_account_code || '—'}</td>
                  <td className="px-4 py-3 text-gray-600">{c.billing_category || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${c.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {c.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {tab === 'items' && (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {['Item #','Description','Freight Class','Weight','Hazmat','Commodity','Status'].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? <tr><td colSpan={7} className="text-center py-12 text-gray-400">Loading...</td></tr>
                : filtered.map((it: any) => (
                <tr key={it.item_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono font-bold text-blue-600">{it.item_number}</td>
                  <td className="px-4 py-3 text-gray-800">{it.item_description}</td>
                  <td className="px-4 py-3 text-gray-600">{it.freight_class || '—'}</td>
                  <td className="px-4 py-3 text-gray-600">{it.weight_value ? `${it.weight_value} kg` : '—'}</td>
                  <td className="px-4 py-3">
                    {it.hazardous_flag
                      ? <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700">Hazmat</span>
                      : <span className="text-gray-400 text-xs">—</span>}
                  </td>
                  <td className="px-4 py-3 text-gray-600 text-xs">{it.commodity_code || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${it.status === 'active' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {it.status || 'active'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {tab === 'locations' && (
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {['Code','Name','Type','City','State','Country','Active'].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {loading ? <tr><td colSpan={7} className="text-center py-12 text-gray-400">Loading...</td></tr>
                : filtered.map((loc: any) => (
                <tr key={loc.location_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono font-bold text-blue-600">{loc.location_code}</td>
                  <td className="px-4 py-3 text-gray-800">{loc.location_name}</td>
                  <td className="px-4 py-3 capitalize text-gray-600">{loc.location_type || loc.location_subtype || '—'}</td>
                  <td className="px-4 py-3 text-gray-600">{loc.city || '—'}</td>
                  <td className="px-4 py-3 text-gray-600">{loc.state_province || '—'}</td>
                  <td className="px-4 py-3 text-gray-600">{loc.country_code || '—'}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${loc.is_active !== false ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'}`}>
                      {loc.is_active !== false ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {!loading && filtered.length === 0 && (
          <div className="text-center py-12 text-gray-400">No {tab.replace('_',' ')} found</div>
        )}
      </div>
    </div>
  )
}
