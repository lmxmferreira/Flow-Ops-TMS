'use client'
import { useEffect, useState } from 'react'
import { MapPin, Plus, X, ChevronRight, Search } from 'lucide-react'
import { apiFetch, apiPost } from '../../../lib/api'

const MEMBER_TYPES = ['state','city','postal_code','postal_range','country','location_id']
const US_STATES = ['AL','AK','AZ','AR','CA','CO','CT','DE','FL','GA','HI','ID','IL','IN','IA','KS','KY','LA','ME','MD','MA','MI','MN','MS','MO','MT','NE','NV','NH','NJ','NM','NY','NC','ND','OH','OK','OR','PA','RI','SC','SD','TN','TX','UT','VT','VA','WA','WV','WI','WY']
const REGION_TYPES = ['custom','state','city','postal','country']
const TYPE_COLORS: Record<string,string> = {
  custom:'bg-purple-100 text-purple-700', state:'bg-blue-100 text-blue-700',
  city:'bg-green-100 text-green-700', postal:'bg-orange-100 text-orange-700',
  country:'bg-indigo-100 text-indigo-700'
}

export default function RegionsPage() {
  const [regions, setRegions] = useState<any[]>([])
  const [selected, setSelected] = useState<any>(null)
  const [members, setMembers] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [showAddMember, setShowAddMember] = useState(false)
  const [form, setForm] = useState({ region_code:'', region_name:'', region_type:'custom', description:'' })
  const [memberForm, setMemberForm] = useState({ member_type:'state', member_value:'', member_value_to:'', country_code:'US' })
  const [saving, setSaving] = useState(false)

  function loadRegions() {
    apiFetch('/master-data/rate-regions')
      .then(d => { setRegions(d.regions || []); setLoading(false) })
      .catch(() => setLoading(false))
  }
  useEffect(() => { loadRegions() }, [])

  async function selectRegion(r: any) {
    setSelected(r)
    const d = await apiFetch(`/master-data/rate-regions/${r.region_id}`)
    setMembers(d.members || [])
  }

  async function createRegion(e: React.FormEvent) {
    e.preventDefault(); setSaving(true)
    try {
      await apiPost('/master-data/rate-regions', form)
      setShowCreate(false)
      setForm({ region_code:'', region_name:'', region_type:'custom', description:'' })
      loadRegions()
    } finally { setSaving(false) }
  }

  async function addMember(e: React.FormEvent) {
    e.preventDefault(); setSaving(true)
    try {
      await apiPost(`/master-data/rate-regions/${selected.region_id}/members`, memberForm)
      setShowAddMember(false)
      const d = await apiFetch(`/master-data/rate-regions/${selected.region_id}`)
      setMembers(d.members || [])
      loadRegions()
    } finally { setSaving(false) }
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

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <MapPin className="text-blue-600" size={24}/> Rate Regions
          </h1>
          <p className="text-sm text-gray-500 mt-1">Group locations into zones to simplify carrier rate setup</p>
        </div>
        <button onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700">
          <Plus size={16}/> New Region
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Region list */}
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="p-3 border-b border-gray-100">
            <div className="relative">
              <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400"/>
              <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search regions..."
                className="pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-blue-500"/>
            </div>
          </div>
          <div className="divide-y divide-gray-100 max-h-[calc(100vh-260px)] overflow-y-auto">
            {loading ? <p className="text-center py-8 text-gray-400 text-sm">Loading...</p>
            : filtered.length === 0 ? <p className="text-center py-8 text-gray-400 text-sm">No regions</p>
            : filtered.map(r => (
              <button key={r.region_id} onClick={() => selectRegion(r)}
                className={`w-full text-left px-4 py-3 hover:bg-gray-50 transition-colors ${selected?.region_id === r.region_id ? 'bg-blue-50 border-l-2 border-blue-600' : ''}`}>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm font-semibold text-gray-900">{r.region_name}</p>
                    <p className="text-xs font-mono text-gray-400 mt-0.5">{r.region_code}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${TYPE_COLORS[r.region_type] || 'bg-gray-100 text-gray-600'}`}>{r.region_type}</span>
                    <span className="text-xs text-gray-400">{r.member_count}</span>
                    <ChevronRight size={14} className="text-gray-300"/>
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Region detail */}
        <div className="lg:col-span-2">
          {!selected ? (
            <div className="bg-white rounded-xl border border-gray-200 h-full flex items-center justify-center">
              <div className="text-center py-16">
                <MapPin size={32} className="text-gray-200 mx-auto mb-3"/>
                <p className="text-sm text-gray-400">Select a region to view and edit members</p>
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              <div className="flex items-center justify-between px-5 py-4 border-b border-gray-100">
                <div>
                  <h2 className="text-base font-bold text-gray-900">{selected.region_name}</h2>
                  <p className="text-xs text-gray-400 mt-0.5">{selected.description || 'No description'}</p>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-1 rounded-full font-medium ${TYPE_COLORS[selected.region_type] || 'bg-gray-100 text-gray-600'}`}>{selected.region_type}</span>
                  <button onClick={() => setShowAddMember(true)}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-600 text-white text-xs font-semibold rounded-lg hover:bg-blue-700">
                    <Plus size={12}/> Add Member
                  </button>
                </div>
              </div>

              <div className="px-5 py-3 bg-gray-50 border-b border-gray-100 flex gap-4 flex-wrap">
                {['state','city','postal_code','country'].map(t => {
                  const count = members.filter(m => m.member_type === t).length
                  return count > 0 ? (
                    <span key={t} className="text-xs text-gray-600 font-medium">
                      {t.replace('_',' ')}: <span className="font-bold text-gray-900">{count}</span>
                    </span>
                  ) : null
                })}
                {members.length === 0 && <span className="text-xs text-gray-400">No members yet</span>}
              </div>

              <div className="p-5 max-h-[calc(100vh-320px)] overflow-y-auto">
                {['country','state','city','postal_code','postal_range','location_id'].map(type => {
                  const group = members.filter(m => m.member_type === type)
                  if (group.length === 0) return null
                  return (
                    <div key={type} className="mb-5">
                      <p className="text-xs font-bold text-gray-400 uppercase tracking-wide mb-2 capitalize">{type.replace('_',' ')}s</p>
                      <div className="flex flex-wrap gap-2">
                        {group.map(m => (
                          <div key={m.member_id} className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-100 rounded-lg group">
                            <span className="text-sm font-medium text-gray-700">
                              {m.member_value}{m.member_value_to ? ` – ${m.member_value_to}` : ''}
                              {m.country_code && m.member_type !== 'country' && (
                                <span className="text-gray-400 ml-1 text-xs">({m.country_code})</span>
                              )}
                            </span>
                            <button onClick={() => removeMember(m.member_id)}
                              className="text-gray-300 hover:text-red-500 transition-colors ml-1 opacity-0 group-hover:opacity-100">
                              <X size={12}/>
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )
                })}
              </div>
            </div>
          )}
        </div>
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
                  <input value={form.region_code} onChange={e => setForm({...form, region_code: e.target.value.toUpperCase()})}
                    required placeholder="e.g. WEST_US"
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"/>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1.5">Type</label>
                  <select value={form.region_type} onChange={e => setForm({...form, region_type: e.target.value})}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                    {REGION_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1.5">Region Name <span className="text-red-500">*</span></label>
                <input value={form.region_name} onChange={e => setForm({...form, region_name: e.target.value})}
                  required placeholder="e.g. West Coast US"
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"/>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1.5">Description</label>
                <textarea value={form.description} onChange={e => setForm({...form, description: e.target.value})}
                  rows={2} placeholder="e.g. CA, OR, WA states"
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"/>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setShowCreate(false)}
                  className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
                <button type="submit" disabled={saving}
                  className="px-5 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50">
                  {saving ? 'Creating...' : 'Create Region'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Member Modal */}
      {showAddMember && selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-md">
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <h2 className="text-lg font-bold text-gray-900">Add Member to {selected.region_name}</h2>
              <button onClick={() => setShowAddMember(false)} className="text-gray-400 hover:text-gray-600"><X size={20}/></button>
            </div>
            <form onSubmit={addMember} className="px-6 py-5 space-y-4">
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1.5">Member Type <span className="text-red-500">*</span></label>
                <select value={memberForm.member_type}
                  onChange={e => setMemberForm({...memberForm, member_type: e.target.value, member_value:''})}
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                  {MEMBER_TYPES.map(t => <option key={t} value={t}>{t.replace('_',' ')}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1.5">
                  {memberForm.member_type === 'postal_range' ? 'Postal From' : 'Value'} <span className="text-red-500">*</span>
                </label>
                {memberForm.member_type === 'state' ? (
                  <select value={memberForm.member_value}
                    onChange={e => setMemberForm({...memberForm, member_value: e.target.value})} required
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                    <option value="">Select state...</option>
                    {US_STATES.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                ) : (
                  <input value={memberForm.member_value}
                    onChange={e => setMemberForm({...memberForm, member_value: e.target.value})} required
                    placeholder={memberForm.member_type === 'postal_code' ? '90001' : memberForm.member_type === 'city' ? 'Los Angeles' : memberForm.member_type === 'country' ? 'US' : ''}
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"/>
                )}
              </div>
              {memberForm.member_type === 'postal_range' && (
                <div>
                  <label className="block text-xs font-semibold text-gray-600 mb-1.5">Postal To <span className="text-red-500">*</span></label>
                  <input value={memberForm.member_value_to}
                    onChange={e => setMemberForm({...memberForm, member_value_to: e.target.value})} required
                    placeholder="90099"
                    className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"/>
                </div>
              )}
              <div>
                <label className="block text-xs font-semibold text-gray-600 mb-1.5">Country</label>
                <select value={memberForm.country_code}
                  onChange={e => setMemberForm({...memberForm, country_code: e.target.value})}
                  className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
                  {['US','CA','MX','GB','DE','FR','NL','BE','ES','IT'].map(c => <option key={c} value={c}>{c}</option>)}
                </select>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={() => setShowAddMember(false)}
                  className="px-4 py-2 text-sm text-gray-600 border border-gray-200 rounded-lg hover:bg-gray-50">Cancel</button>
                <button type="submit" disabled={saving}
                  className="px-5 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 disabled:opacity-50">
                  {saving ? 'Adding...' : 'Add Member'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}
