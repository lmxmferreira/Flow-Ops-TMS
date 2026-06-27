'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Users, Search, Star, Plus, Pencil, X, Award } from 'lucide-react'
import { apiFetch, statusColor, apiPost, apiPatch } from '../../lib/api'

const EMPTY_FORM = {
  carrier_name: '', scac: '', mc_number: '', dot_number: '',
  tax_identifier: '', primary_mode: '', payment_terms: '', status_code: 'ACTIVE',
}
const MODES = ['LTL','FTL','PARCEL','INTERMODAL','AIR','OCEAN','RAIL']
const STATUSES = ['ACTIVE','INACTIVE','SUSPENDED','PENDING']

function Modal({ title, onClose, children }: any) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
          <h2 className="text-lg font-bold text-gray-900">{title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={20}/></button>
        </div>
        {children}
      </div>
    </div>
  )
}

function CarrierForm({ form, setForm, onSubmit, onCancel, saving, submitLabel }: any) {
  return (
    <form onSubmit={onSubmit} className="px-6 py-5 space-y-4">
      <div>
        <label className="block text-xs font-semibold text-gray-600 mb-1.5">Carrier Name <span className="text-red-500">*</span></label>
        <input value={form.carrier_name} onChange={e => setForm({...form, carrier_name: e.target.value})} required
          placeholder="e.g. FedEx Freight" className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"/>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1.5">SCAC</label>
          <input value={form.scac} onChange={e => setForm({...form, scac: e.target.value.toUpperCase()})}
            placeholder="e.g. FXFE" maxLength={4} className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"/>
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1.5">Primary Mode</label>
          <select value={form.primary_mode} onChange={e => setForm({...form, primary_mode: e.target.value})}
            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
            <option value="">— Select —</option>
            {MODES.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1.5">DOT Number</label>
          <input value={form.dot_number} onChange={e => setForm({...form, dot_number: e.target.value})}
            placeholder="e.g. DOT-123456" className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"/>
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1.5">MC Number</label>
          <input value={form.mc_number} onChange={e => setForm({...form, mc_number: e.target.value})}
            placeholder="e.g. MC-567890" className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"/>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1.5">Tax ID</label>
          <input value={form.tax_identifier} onChange={e => setForm({...form, tax_identifier: e.target.value})}
            placeholder="e.g. 12-3456789" className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono"/>
        </div>
        <div>
          <label className="block text-xs font-semibold text-gray-600 mb-1.5">Status</label>
          <select value={form.status_code} onChange={e => setForm({...form, status_code: e.target.value})}
            className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
            {STATUSES.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
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

export default function CarriersPage() {
  const [carriers, setCarriers] = useState<any[]>([])
  const [scorecards, setScorecards] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [tab, setTab] = useState<'carriers' | 'scorecards'>('carriers')
  const [showAdd, setShowAdd] = useState(false)
  const [editCarrier, setEditCarrier] = useState<any>(null)
  const [form, setForm] = useState({ ...EMPTY_FORM })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  function load() {
    Promise.all([
      apiFetch('/carriers/?limit=100').catch(() => ({ data: [] })),
      Promise.resolve([]),
    ]).then(([c, s]) => {
      setCarriers(Array.isArray(c) ? c : c.data || [])
      setScorecards(Array.isArray(s) ? s : [])
      setLoading(false)
    })
  }
  useEffect(() => { load() }, [])

  const filteredCarriers = carriers.filter(c =>
    !search ||
    c.carrier_name?.toLowerCase().includes(search.toLowerCase()) ||
    c.scac?.toLowerCase().includes(search.toLowerCase())
  )

  async function handleAdd(e: React.FormEvent) {
    e.preventDefault(); setSaving(true); setError('')
    try {
      const body: any = { ...form }
      Object.keys(body).forEach(k => { if (body[k] === '') delete body[k] })
      await apiPost('/carriers/', body)
      setShowAdd(false); setForm({ ...EMPTY_FORM }); load()
    } catch {
      setError('Failed to create carrier.')
    } finally { setSaving(false) }
  }

  function openEdit(c: any) {
    setEditCarrier(c)
    setForm({
      carrier_name: c.carrier_name || '',
      scac: c.scac || '',
      mc_number: c.mc_number || '',
      dot_number: c.dot_number || '',
      tax_identifier: c.tax_identifier || '',
      primary_mode: c.primary_mode || '',
      payment_terms: c.payment_terms || '',
      status_code: c.status_code || 'ACTIVE',
    })
    setError('')
  }

  async function handleEdit(e: React.FormEvent) {
    e.preventDefault(); setSaving(true); setError('')
    try {
      const body: any = { ...form }
      Object.keys(body).forEach(k => { if (body[k] === '') delete body[k] })
      await apiPatch(`/carriers/${editCarrier.carrier_id}`, body)
      setEditCarrier(null); setForm({ ...EMPTY_FORM }); load()
    } catch {
      setError('Failed to update carrier.')
    } finally { setSaving(false) }
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Users className="text-blue-600" size={24}/> Carrier Management
          </h1>
          <p className="text-sm text-gray-500 mt-1">Manage carriers, tenders, and performance scorecards</p>
        </div>
        <button onClick={() => { setShowAdd(true); setForm({ ...EMPTY_FORM }); setError('') }}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-semibold rounded-lg hover:bg-blue-700 shadow-sm">
          <Plus size={16}/> Add Carrier
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 bg-gray-100 p-1 rounded-lg w-fit">
        {(['carriers', 'scorecards'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-1.5 text-sm font-medium rounded-md transition-colors ${tab === t ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
            {t === 'carriers' && <span className="ml-1.5 text-xs text-gray-400">({carriers.length})</span>}
          </button>
        ))}
      </div>

      {tab === 'carriers' && (
        <>
          <div className="relative max-w-xs mb-4">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"/>
            <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search carriers..."
              className="pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-blue-500"/>
          </div>
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>
                  {['Carrier','SCAC','DOT #','MC #','Mode','Rate Cards','Status',''].map(h => (
                    <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {loading ? (
                  <tr><td colSpan={8} className="text-center py-12 text-gray-400">Loading carriers...</td></tr>
                ) : filteredCarriers.length === 0 ? (
                  <tr><td colSpan={8} className="text-center py-12 text-gray-400">No carriers found</td></tr>
                ) : filteredCarriers.map((c: any) => (
                  <tr key={c.carrier_id} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 font-medium text-gray-900">
                      <Link href={`/carriers/${c.carrier_id}`} className="hover:text-blue-600">{c.carrier_name}</Link>
                    </td>
                    <td className="px-4 py-3 font-mono text-gray-600">{c.scac || '—'}</td>
                    <td className="px-4 py-3 text-gray-500">{c.dot_number || '—'}</td>
                    <td className="px-4 py-3 text-gray-500">{c.mc_number || '—'}</td>
                    <td className="px-4 py-3 text-gray-600 uppercase text-xs">{c.primary_mode || '—'}</td>
                    <td className="px-4 py-3 text-gray-600">{c.active_rate_cards ?? '—'}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded-full text-xs font-medium ${statusColor(c.status_code || c.status || 'active')}`}>
                        {c.status_name || c.status_code || 'active'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <button onClick={() => openEdit(c)}
                        className="flex items-center gap-1 text-xs text-gray-400 hover:text-blue-600 transition-colors px-2 py-1 rounded hover:bg-blue-50">
                        <Pencil size={12}/> Edit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filteredCarriers.length > 0 && (
              <div className="px-4 py-2 border-t border-gray-100 bg-gray-50">
                <span className="text-xs text-gray-400">{filteredCarriers.length} carriers</span>
              </div>
            )}
          </div>
        </>
      )}

      {tab === 'scorecards' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {loading ? <p className="text-gray-400 text-sm">Loading scorecards...</p>
          : scorecards.length === 0 ? <p className="text-gray-400 text-sm col-span-3">No scorecard data yet</p>
          : scorecards.map((sc: any) => (
            <div key={sc.carrier_id} className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center justify-between mb-4">
                <h3 className="font-semibold text-gray-900 text-sm">{sc.carrier_name || sc.carrier_id?.slice(0,8)}</h3>
                <div className="flex items-center gap-1 text-amber-500">
                  <Star size={14} fill="currentColor"/>
                  <span className="text-sm font-bold">{sc.total_score?.toFixed(1) || '—'}</span>
                </div>
              </div>
              <div className="space-y-2">
                {[
                  ['Acceptance', sc.tender_acceptance_pct, '%'],
                  ['On-Time Pickup', sc.on_time_pickup_pct, '%'],
                  ['On-Time Delivery', sc.on_time_delivery_pct, '%'],
                  ['Invoice Accuracy', sc.invoice_accuracy_pct, '%'],
                  ['Claims Count', sc.claims_count, ''],
                ].map(([label, val, unit]) => (
                  <div key={label as string} className="flex items-center justify-between text-xs">
                    <span className="text-gray-500">{label}</span>
                    <span className="font-medium text-gray-800">{val !== null && val !== undefined ? `${val}${unit}` : '—'}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Add Modal */}
      {showAdd && (
        <Modal title="Add Carrier" onClose={() => setShowAdd(false)}>
          {error && <p className="mx-6 mt-4 text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>}
          <CarrierForm form={form} setForm={setForm} onSubmit={handleAdd}
            onCancel={() => setShowAdd(false)} saving={saving} submitLabel="Create Carrier"/>
        </Modal>
      )}

      {/* Edit Modal */}
      {editCarrier && (
        <Modal title={`Edit — ${editCarrier.carrier_name}`} onClose={() => setEditCarrier(null)}>
          {error && <p className="mx-6 mt-4 text-xs text-red-600 bg-red-50 px-3 py-2 rounded-lg">{error}</p>}
          <CarrierForm form={form} setForm={setForm} onSubmit={handleEdit}
            onCancel={() => setEditCarrier(null)} saving={saving} submitLabel="Save Changes"/>
        </Modal>
      )}
    </div>
  )
}
