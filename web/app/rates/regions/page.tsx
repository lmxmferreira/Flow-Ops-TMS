'use client'
import { useEffect, useState } from 'react'
import { MapPin, Plus, X, Search, Pencil, Trash2, ChevronRight, Globe, ArrowLeft } from 'lucide-react'
import { apiFetch, apiPost, apiPatch } from '../../../lib/api'

const MEMBER_TYPES = [
  { value: 'country',      label: 'Country',       placeholder: 'e.g. US, CA, MX' },
  { value: 'state',        label: 'State/Province', placeholder: 'e.g. CA, TX, NY' },
  { value: 'city',         label: 'City',           placeholder: 'e.g. Los Angeles' },
  { value: 'postal_code',  label: 'Postal Code',    placeholder: 'e.g. 90001' },
  { value: 'postal_range', label: 'Postal Range',   placeholder: 'e.g. 90001' },
  { value: 'location_id',  label: 'Location ID',    placeholder: 'UUID of a location' },
]

const REGION_TYPES = ['custom','state','city','postal','country']

const US_STATES = ['AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA',
  'KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC',
  'ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY']

const COUNTRIES = ['US','CA','MX','GB','DE','FR','NL','BE','ES','IT','CN','JP','AU','BR']

const TYPE_COLORS: Record<string, string> = {
  custom:  'bg-purple-100 text-purple-700',
  state:   'bg-blue-100 text-blue-700',
  city:    'bg-green-100 text-green-700',
  postal:  'bg-orange-100 text-orange-700',
  country: 'bg-indigo-100 text-indigo-700',
}

const MEMBER_TYPE_COLORS: Record<string, string> = {
  country:      'bg-indigo-50 text-indigo-700 border-indigo-200',
  state:        'bg-blue-50 text-blue-700 border-blue-200',
  city:         'bg-green-50 text-green-700 border-green-200',
  postal_code:  'bg-orange-50 text-orange-700 border-orange-200',
  postal_range: 'bg-amber-50 text-amber-700 border-amber-200',
  location_id:  'bg-gray-50 text-gray-700 border-gray-200',
}

export default function RegionsPage() {
  // List view state
  const [regions, setRegions] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  // Detail view state
  const [selected, setSelected] = useState<any>(null)
  const [members, setMembers] = useState<any[]>([])
  const [detailLoading, setDetailLoading] = useState(false)

  // Create region modal
  const [showCreate, setShowCreate] = useState(false)
  const [regionForm, setRegionForm] = useState({ region_code: '', region_name: '', region_type: 'custom', description: '' })
  const [savingRegion, setSavingRegion] = useState(false)

  // Add member modal
  const [showAddMember, setShowAddMember] = useState(false)
  const [memberForm, setMemberForm] = useState({ member_type: 'state', member_value: '', member_value_to: '', country_code: 'US' })
  const [savingMember, setSavingMember] = useState(false)

  // Edit region modal
  const [showEditRegion, setShowEditRegion] = useState(false)
  const [editRegionForm, setEditRegionForm] = useState<any>({})

  function loadRegions() {
    apiFetch('/master-data/rate-regions')
      .then(d => { setRegions(d.regions || []); setLoading(false) })
      .catch(() => setLoading(false))
  }

  useEffect(() => { loadRegions() }, [])

  async function selectRegion(r: any) {
    setSelected(r)
    setDetailLoading(true)
    const d = await apiFetch(`/master-data/rate-regions/${r.region_id}`)
    setMembers(d.members || [])
    setDetailLoading(false)
  }

  async function createRegion(e: React.FormEvent) {
    e.preventDefault(); setSavingRegion(true)
    try {
      await apiPost('/master-data/rate-regions', regionForm)
      setShowCreate(false)
      setRegionForm({ region_code: '', region_name: '', region_type: 'custom', description: '' })
      loadRegions()
    } finally { setSavingRegion(false) }
  }

  async function addMember(e: React.FormEvent) {
    e.preventDefault(); setSavingMember(true)
    try {
      await apiPost(`/master-data/rate-regions/${selected.region_id}/members`, memberForm)
      setShowAddMember(false)
      setMemberForm({ member_type: 'state', member_value: '', member_value_to: '', country_code: 'US' })
      const d = await apiFetch(`/master-data/rate-regions/${selected.region_id}`)
      setMembers(d.members || [])
      loadRegions()
    } finally { setSavingMember(false) }
  }

  async function removeMember(memberId: string) {
    const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1'
    await fetch(`${API}/master-data/rate-regions/${selected.region_id}/members/${memberId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${localStorage.getItem('tms_token')}` }
    })
    setMembers(prev => prev.filter(m => m.member_id !== memberId))
    loadRegions()
  }

  const filtered = regions.filter(r =>
    !search ||
    r.region_name?.toLowerCase().includes(search.toLowerCase()) ||
    r.region_code?.toLowerCase().includes(search.toLowerCase())
  )

  const memberTypeDef = MEMBER_TYPES.find(t => t.value === memberForm.member_type)

  // ── DETAIL VIEW ────────────────────────────────────────────
  if (selected) {
    return (
      <div className="p-6 max-w-5xl mx-auto space-y-4">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-sm text-gray-500">
          <button onClick={() => setSelected(null)} className="flex items-center gap-1 hover:text-gray-800 transition-colors">
            <ArrowLeft size={14}/> Rate Regions
          </button>
          <ChevronRight size={14}/>
          <span className="text-gray-900 font-medium">{selected.region_name}</span>
        </div>

        {/* Region header card */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-4">
              <div className="w-11 h-11 bg-blue-50 rounded-xl flex items-center justify-center flex-shrink-0">
                <Globe size={20} className="text-blue-600"/>
              </div>
              <div>
                <div className="flex items-center gap-3 mb-1">
                  <h1 className="text-xl font-bold text-gray-900">{selected.region_name}</h1>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${TYPE_COLORS[selected.region_type] || 'bg-gray-100 text-gray-600'}`}>
                    {selected.region_type}
                  </span>
                </div>
                <p className="text-xs font-mono text-gray-400">{selected.region_code}</p>
                {selected.description && <p className="text-sm text-gray-500 mt-1">{selected.description}</p>}
              </div>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0">
              <button onClick={() => setShowAddMember(true)}
                className="flex items-center gap-1.5 px-3 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700">
                <Plus size={14}/> Add Member
              </button>
            </div>
          </div>

          {/* Summary pills */}
          <div className="flex gap-3 mt-4 pt-4 border-t border-gray-100 flex-wrap">
            {['country','state','city','postal_code','postal_range'].map(type => {
              const count = members.filter(m => m.member_type === type).length
              if (count === 0) return null
              const label = MEMBER_TYPES.find(t => t.value === type)?.label || type
              return (
                <div key={type} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium ${MEMBER_TYPE_COLORS[type]}`}>
                  <span>{label}</span>
                  <span className="font-bold">{count}</span>
                </div>
              )
            })}
            {members.length === 0 && <p className="text-xs text-gray-400">No members yet — add countries, states, cities or postal codes</p>}
          </div>
        </div>

        {/* Members table */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3.5 border-b border-gray-100 bg-gray-50">
            <h3 className="text-sm font-bold text-gray-700">Region Members</h3>
            <span className="text-xs text-gray-400">{members.length} members</span>
          </div>
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                {['Type','Value','Range To','Country',''].map(h => (
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {detailLoading ? (
                <tr><td colSpan={5} className="text-center py-10 text-gray-400">Loading members...</td></tr>
              ) : members.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-center py-12">
                    <Globe size={28} className="text-gray-200 mx-auto mb-3"/>
                    <p className="text-sm text-gray-400 mb-3">No members defined for this region</p>
                    <button onClick={() => setShowAddMember(true)}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-xs font-semibold rounded-lg hover:bg-blue-700">
                      <Plus size={12}/> Add First Member
                    </button>
                  </td>
                </tr>
              ) : members.map((m: any) => {
                const typeDef = MEMBER_TYPES.find(t => t.value === m.member_type)
                return (
                  <tr key={m.member_id} className="hover:bg-gray-50 transition-colors group">
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded-md text-xs font-semibold border ${MEMBER_TYPE_COLORS[m.member_type] || 'bg-gray-50 text-gray-600 border-gray-200'}`}>
                        {typeDef?.label || m.member_type}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-semibold text-gray-900">{m.member_value}</td>
                    <td className="px-4 py-3 text-gray-500">{m.member_value_to || '—'}</td>
                    <td className="px-4 py-3 text-gray-500 font-mono text-xs">{m.country_code || '—'}</td>
                    <td className="px-4 py-3">
                      <button onClick={() => removeMember(m.member_id)}
                        className="opacity-0 group-hover:opacity-100 flex items-center gap-1 text-xs text-gray-400 hover:text-red-600 transition-all px-2 py-1 rounded hover:bg-red-50">
                        <Trash2 size={12}/> Remove
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {/* Add Member Modal */}
        {showAddMember && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
            <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
              <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
                <h2 className="text-lg font-bold text-gray-900">Add Region Member</h2>
                <button onClick={() => setShowAddMember(false)} className="text-gray-400 hover:text-gray-600"><X size={20}/></button>
              </div>
              <form onSubmit={addMember} className="px-6 py-5 space-y-4">
                {/* Member type selector */}
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-2">Member Type <span className="text-red-500">*</span></label>
                  <div className="grid grid-cols-3 gap-2">
                    {MEMBER_TYPES.map(t => (
                      <button key={t.value} type="button"
                        onClick={() => setMemberForm({ ...memberForm, member_type: t.value, member_value: '', member_value_to: '' })}
                        className={`px-3 py-2 text-xs font-medium rounded-lg border transition-colors text-center ${
                          memberForm.member_type === t.value
                            ? `${MEMBER_TYPE_COLORS[t.value]} border-current font-bold`
                            : 'border-gray-200 text-gray-500 hover:border-gray-300 hover:bg-gray-50'
                        }`}>
                        {t.label}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Value input */}
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1.5">
                    {memberForm.member_type === 'postal_range' ? 'Postal Code From' : memberForm.typeDef?.label || 'Value'}
                    <span className="text-red-500"> *</span>
                  </label>
                  {memberForm.member_type === 'state' ? (
                    <select value={memberForm.member_value}
                      onChange={e => setMemberForm({ ...memberForm, member_value: e.target.value })} required
                      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                      <option value="">Select state/province...</option>
                      {US_STATES.map(s => <option key={s} value={s}>{s}</option>)}
                    </select>
                  ) : memberForm.member_type === 'country' ? (
                    <select value={memberForm.member_value}
                      onChange={e => setMemberForm({ ...memberForm, member_value: e.target.value })} required
                      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                      <option value="">Select country...</option>
                      {COUNTRIES.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  ) : (
                    <input value={memberForm.member_value}
                      onChange={e => setMemberForm({ ...memberForm, member_value: e.target.value })} required
                      placeholder={memberTypeDef?.placeholder || ''}
                      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"/>
                  )}
                </div>

                {/* Postal range "to" field */}
                {memberForm.member_type === 'postal_range' && (
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 mb-1.5">Postal Code To <span className="text-red-500">*</span></label>
                    <input value={memberForm.member_value_to}
                      onChange={e => setMemberForm({ ...memberForm, member_value_to: e.target.value })} required
                      placeholder="e.g. 90099"
                      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"/>
                    <p className="text-xs text-gray-400 mt-1">Covers all postal codes between From and To inclusive</p>
                  </div>
                )}

                {/* Country context (for state/city/postal) */}
                {['state','city','postal_code','postal_range'].includes(memberForm.member_type) && (
                  <div>
                    <label className="block text-xs font-semibold text-gray-600 mb-1.5">Country</label>
                    <select value={memberForm.country_code}
                      onChange={e => setMemberForm({ ...memberForm, country_code: e.target.value })}
                      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                      {COUNTRIES.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                )}

                <div className="flex justify-end gap-3 pt-2">
                  <button type="button" onClick={() => setShowAddMember(false)}
                    className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
                  <button type="submit" disabled={savingMember}
                    className="px-5 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50">
                    {savingMember ? 'Adding...' : 'Add Member'}
                  </button>
                </div>
              </form>
            </div>
          </div>
        )}
      </div>
    )
  }

  // ── LIST VIEW ──────────────────────────────────────────────
  return (
    <div className="p-6 max-w-5xl mx-auto space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <MapPin className="text-blue-600" size={24}/> Rate Regions
          </h1>
          <p className="text-sm text-gray-500 mt-1">Define geographic zones to simplify carrier rate lane setup</p>
        </div>
        <button onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 shadow-sm">
          <Plus size={16}/> New Region
        </button>
      </div>

      {/* Search */}
      <div className="relative max-w-sm">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"/>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search regions..."
          className="pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-blue-500"/>
      </div>

      {/* Regions table */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              {['Region Name','Code','Type','Description','Members',''].map(h => (
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <tr><td colSpan={6} className="text-center py-12 text-gray-400">Loading regions...</td></tr>
            ) : filtered.length === 0 ? (
              <tr>
                <td colSpan={6} className="text-center py-12">
                  <MapPin size={28} className="text-gray-200 mx-auto mb-3"/>
                  <p className="text-sm text-gray-400 mb-3">No regions yet</p>
                  <button onClick={() => setShowCreate(true)}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-xs font-semibold rounded-lg hover:bg-blue-700">
                    <Plus size={12}/> Create First Region
                  </button>
                </td>
              </tr>
            ) : filtered.map(r => (
              <tr key={r.region_id} className="hover:bg-gray-50 transition-colors cursor-pointer group"
                onClick={() => selectRegion(r)}>
                <td className="px-4 py-3.5">
                  <p className="font-semibold text-gray-900 group-hover:text-blue-600 transition-colors">{r.region_name}</p>
                </td>
                <td className="px-4 py-3.5 font-mono text-xs text-gray-400">{r.region_code}</td>
                <td className="px-4 py-3.5">
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${TYPE_COLORS[r.region_type] || 'bg-gray-100 text-gray-600'}`}>
                    {r.region_type}
                  </span>
                </td>
                <td className="px-4 py-3.5 text-gray-500 text-xs max-w-xs truncate">{r.description || '—'}</td>
                <td className="px-4 py-3.5">
                  <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${r.member_count > 0 ? 'bg-blue-100 text-blue-700' : 'bg-gray-100 text-gray-400'}`}>
                    {r.member_count} member{r.member_count !== 1 ? 's' : ''}
                  </span>
                </td>
                <td className="px-4 py-3.5">
                  <span className="flex items-center gap-1 text-xs text-gray-400 group-hover:text-blue-600 transition-colors">
                    View <ChevronRight size={14}/>
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filtered.length > 0 && (
          <div className="px-4 py-2 border-t border-gray-100 bg-gray-50">
            <span className="text-xs text-gray-400">{filtered.length} regions</span>
          </div>
        )}
      </div>

      {/* Create Region Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <h2 className="text-lg font-bold text-gray-900">Create Rate Region</h2>
              <button onClick={() => setShowCreate(false)} className="text-gray-400 hover:text-gray-600"><X size={20}/></button>
            </div>
            <form onSubmit={createRegion} className="px-6 py-5 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1.5">Region Code <span className="text-red-500">*</span></label>
                  <input value={regionForm.region_code}
                    onChange={e => setRegionForm({ ...regionForm, region_code: e.target.value.toUpperCase().replace(/\s/g,'_') })}
                    required placeholder="e.g. WEST_US"
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"/>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1.5">Type</label>
                  <select value={regionForm.region_type}
                    onChange={e => setRegionForm({ ...regionForm, region_type: e.target.value })}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                    {REGION_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1.5">Region Name <span className="text-red-500">*</span></label>
                <input value={regionForm.region_name}
                  onChange={e => setRegionForm({ ...regionForm, region_name: e.target.value })}
                  required placeholder="e.g. West Coast US"
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"/>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1.5">Description</label>
                <textarea value={regionForm.description}
                  onChange={e => setRegionForm({ ...regionForm, description: e.target.value })}
                  rows={2} placeholder="e.g. Covers CA, OR, WA states"
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"/>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setShowCreate(false)}
                  className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
                <button type="submit" disabled={savingRegion}
                  className="px-5 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50">
                  {savingRegion ? 'Creating...' : 'Create Region'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
