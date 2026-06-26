'use client'
import { useEffect, useState, useCallback } from 'react'
import { useRouter } from 'next/navigation'
import { Search, Truck, X, ChevronLeft, ChevronRight, Plus, Save } from 'lucide-react'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1'

function authHeaders() {
  return { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('tms_token')}` }
}

interface Carrier {
  carrier_id: string
  carrier_name: string
  carrier_code: string
  scac: string
  mc_number: string
  dot_number: string
  status_code: string
  status_name: string
  onboarding_status: string
  safety_rating: string
  payment_terms: string
  remittance_party: string
  tax_identifier: string
  active_rate_cards: number
  created_at: string
  updated_at: string
}

interface Lookup { id: string; code: string; label: string }
interface Lookups { CARRIER_STATUS?: Lookup[]; PAYMENT_TERMS?: Lookup[] }

const STATUS_STYLES: Record<string, string> = {
  ACTIVE:        'bg-green-50 text-green-700',
  INACTIVE:      'bg-gray-100 text-gray-500',
  SUSPENDED:     'bg-red-50 text-red-700',
  PENDING:       'bg-yellow-50 text-yellow-700',
  NON_COMPLIANT: 'bg-orange-50 text-orange-700',
  UNKNOWN:       'bg-gray-100 text-gray-400',
}

function fmt(ts: string) { return new Date(ts).toLocaleDateString('en-CA') }

const inp = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      {children}
    </div>
  )
}

function AddCarrierModal({ lookups, onClose, onSaved }: {
  lookups: Lookups; onClose: () => void; onSaved: () => void
}) {
  const [form, setForm] = useState({
    party_name: '', party_code: '', scac: '', mc_number: '', dot_number: '',
    tax_identifier: '', status_id: '', payment_terms_id: '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  async function save() {
    if (!form.party_name || !form.party_code) { setError('Carrier name and code are required.'); return }
    setSaving(true); setError('')
    try {
      const body: Record<string, unknown> = { ...form }
      Object.keys(body).forEach(k => { if (body[k] === '') body[k] = null })
      const r = await fetch(`${API}/carriers/`, { method: 'POST', headers: authHeaders(), body: JSON.stringify(body) })
      if (!r.ok) { const d = await r.json(); throw new Error(d.detail ?? 'Failed to create') }
      onSaved(); onClose()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally { setSaving(false) }
  }

  const f = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(prev => ({ ...prev, [k]: e.target.value }))

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2"><Truck size={16} className="text-blue-600" /> New Carrier</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
        </div>
        <div className="px-6 py-5 space-y-4">
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="grid grid-cols-2 gap-4">
            <Field label="Carrier Name *">
              <input className={inp} value={form.party_name} onChange={f('party_name')} placeholder="e.g. FedEx Freight" />
            </Field>
            <Field label="Carrier Code *">
              <input className={inp} value={form.party_code} onChange={f('party_code')} placeholder="e.g. CAR-FEDEX" />
            </Field>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <Field label="SCAC">
              <input className={inp} value={form.scac} onChange={f('scac')} placeholder="FXFE" />
            </Field>
            <Field label="MC Number">
              <input className={inp} value={form.mc_number} onChange={f('mc_number')} placeholder="MC-123456" />
            </Field>
            <Field label="DOT Number">
              <input className={inp} value={form.dot_number} onChange={f('dot_number')} placeholder="DOT-123456" />
            </Field>
          </div>
          <Field label="Tax Identifier">
            <input className={inp} value={form.tax_identifier} onChange={f('tax_identifier')} placeholder="EIN / Tax ID" />
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Status">
              <select className={inp} value={form.status_id} onChange={f('status_id')}>
                <option value="">— Select —</option>
                {(lookups.CARRIER_STATUS ?? []).map(l => <option key={l.id} value={l.id}>{l.label}</option>)}
              </select>
            </Field>
            <Field label="Payment Terms">
              <select className={inp} value={form.payment_terms_id} onChange={f('payment_terms_id')}>
                <option value="">— Select —</option>
                {(lookups.PAYMENT_TERMS ?? []).map(l => <option key={l.id} value={l.id}>{l.label}</option>)}
              </select>
            </Field>
          </div>
        </div>
        <div className="flex justify-end gap-3 px-6 py-4 border-t">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 font-medium">Cancel</button>
          <button onClick={save} disabled={saving}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50">
            <Save size={14} />{saving ? 'Saving…' : 'Create Carrier'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function CarriersPage() {
  const router = useRouter()
  const [carriers, setCarriers] = useState<Carrier[]>([])
  const [total, setTotal]       = useState(0)
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState<string | null>(null)
  const [search, setSearch]     = useState('')
  const [searchInput, setSearchInput] = useState('')
  const [page, setPage]         = useState(0)
  const [showAdd, setShowAdd]   = useState(false)
  const [lookups, setLookups]   = useState<Lookups>({})
  const limit = 50

  const fetchCarriers = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const params = new URLSearchParams({ limit: String(limit), offset: String(page * limit) })
      if (search) params.set('search', search)
      const r = await fetch(`${API}/carriers/?${params}`, { headers: authHeaders() })
      const data = await r.json()
      setCarriers(data.data ?? []); setTotal(data.total ?? 0)
    } catch { setError('Failed to load carriers.') }
    finally { setLoading(false) }
  }, [search, page])

  useEffect(() => { fetchCarriers() }, [fetchCarriers])

  useEffect(() => {
    fetch(`${API}/carriers/lookups`, { headers: authHeaders() })
      .then(r => r.json()).then(setLookups).catch(() => {})
  }, [])

  function handleSearch(e: React.FormEvent) { e.preventDefault(); setSearch(searchInput); setPage(0) }
  const totalPages = Math.ceil(total / limit)

  return (
    <div className="flex flex-col h-full bg-gray-50">
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-gray-900">Carriers</h1>
            <p className="text-sm text-gray-500 mt-0.5">{loading ? 'Loading…' : `${total.toLocaleString()} carriers`}</p>
          </div>
          <button onClick={() => setShowAdd(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition">
            <Plus size={15} /> Add Carrier
          </button>
        </div>
        <div className="mt-3 flex items-center gap-3">
          <form onSubmit={handleSearch} className="flex gap-2">
            <div className="relative">
              <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input value={searchInput} onChange={e => setSearchInput(e.target.value)}
                placeholder="Name, code, SCAC, MC number…"
                className="pl-9 pr-3 py-1.5 text-sm border border-gray-300 rounded-lg w-72 focus:outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
            <button type="submit" className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700">Search</button>
            {search && (
              <button type="button" onClick={() => { setSearch(''); setSearchInput(''); setPage(0) }}
                className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700">
                <X size={14} /> Clear
              </button>
            )}
          </form>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        {error ? (
          <div className="flex items-center justify-center h-64 text-red-500">{error}</div>
        ) : loading ? (
          <div className="flex items-center justify-center h-64 text-gray-400">Loading carriers…</div>
        ) : carriers.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-64 text-gray-400">
            <Truck size={40} className="mb-3 opacity-30" />
            <p className="text-sm">No carriers found.</p>
          </div>
        ) : (
          <table className="w-full text-sm border-separate border-spacing-0">
            <thead className="sticky top-0 z-10">
              <tr>
                {["Carrier","Code","SCAC","MC Number","DOT Number","Status","Onboarding","Safety Rating","Payment Terms","Rate Cards","Created"].map(h => (
                  <th key={h} className="text-left px-4 py-2.5 text-xs font-semibold text-gray-600 bg-white border-b border-gray-200 whitespace-nowrap">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {carriers.map((c, i) => (
                <tr key={c.carrier_id} onClick={() => router.push(`/carriers/${c.carrier_id}`)}
                  className={`cursor-pointer hover:bg-blue-50 transition-colors ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50/60'}`}>
                  <td className="px-4 py-2.5 border-b border-gray-100 font-medium text-gray-900 whitespace-nowrap">{c.carrier_name}</td>
                  <td className="px-4 py-2.5 border-b border-gray-100 font-mono text-xs text-gray-600">{c.carrier_code || '—'}</td>
                  <td className="px-4 py-2.5 border-b border-gray-100 font-mono text-xs text-gray-700 font-semibold">{c.scac || '—'}</td>
                  <td className="px-4 py-2.5 border-b border-gray-100 text-xs text-gray-600">{c.mc_number || '—'}</td>
                  <td className="px-4 py-2.5 border-b border-gray-100 text-xs text-gray-600">{c.dot_number || '—'}</td>
                  <td className="px-4 py-2.5 border-b border-gray-100">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLES[c.status_code] ?? STATUS_STYLES.UNKNOWN}`}>{c.status_name}</span>
                  </td>
                  <td className="px-4 py-2.5 border-b border-gray-100 text-xs text-gray-600">{c.onboarding_status || '—'}</td>
                  <td className="px-4 py-2.5 border-b border-gray-100 text-xs text-gray-600">{c.safety_rating || '—'}</td>
                  <td className="px-4 py-2.5 border-b border-gray-100 text-xs text-gray-600">{c.payment_terms || '—'}</td>
                  <td className="px-4 py-2.5 border-b border-gray-100 text-center">
                    {c.active_rate_cards > 0
                      ? <span className="text-xs bg-blue-50 text-blue-700 px-2 py-0.5 rounded font-medium">{c.active_rate_cards}</span>
                      : <span className="text-gray-300 text-xs">0</span>}
                  </td>
                  <td className="px-4 py-2.5 border-b border-gray-100 text-xs text-gray-400">{fmt(c.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {!loading && total > limit && (
        <div className="bg-white border-t border-gray-200 px-6 py-3 flex items-center justify-between">
          <p className="text-sm text-gray-500">Showing {page * limit + 1}–{Math.min((page + 1) * limit, total)} of {total.toLocaleString()}</p>
          <div className="flex items-center gap-2">
            <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
              className="p-1.5 rounded-lg border border-gray-300 disabled:opacity-40 hover:bg-gray-50"><ChevronLeft size={16} /></button>
            <span className="text-sm text-gray-600">Page {page + 1} of {totalPages}</span>
            <button onClick={() => setPage(p => Math.min(totalPages - 1, p + 1))} disabled={page >= totalPages - 1}
              className="p-1.5 rounded-lg border border-gray-300 disabled:opacity-40 hover:bg-gray-50"><ChevronRight size={16} /></button>
          </div>
        </div>
      )}

      {showAdd && <AddCarrierModal lookups={lookups} onClose={() => setShowAdd(false)} onSaved={fetchCarriers} />}
    </div>
  )
}
