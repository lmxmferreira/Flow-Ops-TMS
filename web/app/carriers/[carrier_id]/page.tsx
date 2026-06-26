'use client'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { ArrowLeft, Truck, DollarSign, Shield, CreditCard, Pencil, X, Save } from 'lucide-react'

const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1'
function authHeaders() {
  return { 'Content-Type': 'application/json', Authorization: `Bearer ${localStorage.getItem('tms_token')}` }
}

interface Carrier {
  carrier_id: string
  party_id: string
  carrier_name: string
  carrier_code: string
  scac: string
  mc_number: string
  dot_number: string
  tax_identifier: string
  status_id: string
  status_code: string
  status_name: string
  payment_terms_id: string
  onboarding_status_id: string
  safety_rating_id: string
  remittance_party_id: string
  onboarding_status: string
  safety_rating: string
  payment_terms: string
  remittance_party: string
  created_at: string
  updated_at: string
}

interface RateCard {
  rate_card_id: string; name: string; mode: string; rate_type: string
  effective_date: string; expiry_date: string; status: string
  contract_reference: string; route_priority: number; lane_count: number
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

const RATE_TYPE_STYLES: Record<string, string> = {
  contract:          'bg-blue-50 text-blue-700',
  tariff:            'bg-purple-50 text-purple-700',
  spot:              'bg-orange-50 text-orange-700',
  route_guide:       'bg-teal-50 text-teal-700',
  customer_specific: 'bg-indigo-50 text-indigo-700',
  carrier_specific:  'bg-gray-50 text-gray-600',
}

function fmt(d: string | null) {
  if (!d) return '—'
  return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function Section({ title, icon: Icon, children }: { title: string; icon: React.ElementType; children: React.ReactNode }) {
  return (
    <div className="bg-white rounded-lg border overflow-hidden">
      <div className="flex items-center gap-2 px-5 py-3 border-b bg-gray-50">
        <Icon size={15} className="text-blue-600" />
        <h2 className="text-sm font-semibold text-gray-700">{title}</h2>
      </div>
      <div className="px-5 py-4">{children}</div>
    </div>
  )
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs text-gray-400 mb-0.5">{label}</p>
      <p className="text-sm text-gray-800 font-medium">{value || '—'}</p>
    </div>
  )
}

const inp = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"

function EditModal({ carrier, lookups, onClose, onSaved }: {
  carrier: Carrier; lookups: Lookups; onClose: () => void; onSaved: (c: Partial<Carrier>) => void
}) {
  const [form, setForm] = useState({
    scac:                 carrier.scac || '',
    mc_number:            carrier.mc_number || '',
    dot_number:           carrier.dot_number || '',
    status_id:            carrier.status_id || '',
    payment_terms_id:     carrier.payment_terms_id || '',
    onboarding_status_id: carrier.onboarding_status_id || '',
    safety_rating_id:     carrier.safety_rating_id || '',
  })
  const [saving, setSaving] = useState(false)
  const [error, setError]   = useState('')

  const f = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm(prev => ({ ...prev, [k]: e.target.value }))

  async function save() {
    setSaving(true); setError('')
    try {
      const body: Record<string, unknown> = {}
      Object.entries(form).forEach(([k, v]) => {
        const orig = carrier[k as keyof Carrier] as string
        if (v !== (orig || '')) body[k] = v || null
      })
      if (Object.keys(body).length === 0) { onClose(); return }
      const r = await fetch(`${API}/carriers/${carrier.carrier_id}`, {
        method: 'PATCH', headers: authHeaders(), body: JSON.stringify(body)
      })
      if (!r.ok) { const d = await r.json(); throw new Error(d.detail ?? 'Save failed') }
      onSaved(body as Partial<Carrier>)
      onClose()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Save failed')
    } finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h2 className="text-base font-semibold text-gray-900 flex items-center gap-2">
            <Pencil size={15} className="text-blue-600" /> Edit {carrier.carrier_name}
          </h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600"><X size={18} /></button>
        </div>
        <div className="px-6 py-5 space-y-4">
          {error && <p className="text-sm text-red-500">{error}</p>}
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">SCAC</label>
              <input className={inp} value={form.scac} onChange={f('scac')} placeholder="e.g. FXFE" />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">MC Number</label>
              <input className={inp} value={form.mc_number} onChange={f('mc_number')} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">DOT Number</label>
              <input className={inp} value={form.dot_number} onChange={f('dot_number')} />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Status</label>
              <select className={inp} value={form.status_id} onChange={f('status_id')}>
                <option value="">— Select —</option>
                {(lookups.CARRIER_STATUS ?? []).map(l => <option key={l.id} value={l.id}>{l.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 mb-1">Payment Terms</label>
              <select className={inp} value={form.payment_terms_id} onChange={f('payment_terms_id')}>
                <option value="">— Select —</option>
                {(lookups.PAYMENT_TERMS ?? []).map(l => <option key={l.id} value={l.id}>{l.label}</option>)}
              </select>
            </div>
          </div>
          <p className="text-xs text-gray-400">
            To update carrier name, code, or tax ID, use the Parties master data module.
          </p>
        </div>
        <div className="flex justify-end gap-3 px-6 py-4 border-t">
          <button onClick={onClose} className="px-4 py-2 text-sm text-gray-600 font-medium">Cancel</button>
          <button onClick={save} disabled={saving}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:opacity-50">
            <Save size={14} />{saving ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  )
}

export default function CarrierDetailPage() {
  const params  = useParams<{ carrier_id: string }>()
  const router  = useRouter()
  const [carrier, setCarrier]     = useState<Carrier | null>(null)
  const [rateCards, setRateCards] = useState<RateCard[]>([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState('')
  const [showEdit, setShowEdit]   = useState(false)
  const [lookups, setLookups]     = useState<Lookups>({})

  useEffect(() => {
    if (!params.carrier_id) return
    setLoading(true)
    Promise.all([
      fetch(`${API}/carriers/${params.carrier_id}`, { headers: authHeaders() }).then(r => r.json()),
      fetch(`${API}/carriers/lookups`, { headers: authHeaders() }).then(r => r.json()),
    ])
      .then(([data, lkp]) => {
        setCarrier(data.carrier); setRateCards(data.rate_cards ?? [])
        setLookups(lkp)
      })
      .catch(() => setError('Failed to load carrier.'))
      .finally(() => setLoading(false))
  }, [params.carrier_id])

  function handleSaved(updated: Partial<Carrier>) {
    if (carrier) setCarrier({ ...carrier, ...updated })
  }

  if (loading) return <div className="flex items-center justify-center h-64 text-gray-400">Loading…</div>
  if (error || !carrier) return <div className="flex items-center justify-center h-64 text-red-500">{error || 'Not found'}</div>

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <button onClick={() => router.back()} className="text-gray-400 hover:text-blue-600 transition-colors">
              <ArrowLeft size={18} />
            </button>
            <Truck size={18} className="text-blue-600" />
            <h1 className="text-xl font-semibold text-gray-800">{carrier.carrier_name}</h1>
            <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${STATUS_STYLES[carrier.status_code] ?? STATUS_STYLES.UNKNOWN}`}>
              {carrier.status_name}
            </span>
          </div>
          <button onClick={() => setShowEdit(true)}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-gray-700 border border-gray-300 rounded-lg hover:bg-gray-50 hover:border-blue-400 hover:text-blue-600 transition">
            <Pencil size={14} /> Edit Carrier
          </button>
        </div>
        <p className="text-xs text-gray-400 ml-9 mt-1">
          {carrier.carrier_code && `${carrier.carrier_code} · `}Created {fmt(carrier.created_at)} · Updated {fmt(carrier.updated_at)}
        </p>
      </div>

      <div className="px-6 py-5 space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Section title="Identity" icon={Truck}>
            <div className="space-y-3">
              <Field label="Carrier Name"  value={carrier.carrier_name} />
              <Field label="Carrier Code"  value={carrier.carrier_code} />
              <Field label="SCAC"          value={<span className="font-mono font-bold text-gray-900">{carrier.scac || '—'}</span>} />
              <Field label="MC Number"     value={carrier.mc_number} />
              <Field label="DOT Number"    value={carrier.dot_number} />
              <Field label="Tax ID"        value={carrier.tax_identifier} />
            </div>
          </Section>

          <Section title="Compliance & Safety" icon={Shield}>
            <div className="space-y-3">
              <Field label="Status" value={
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${STATUS_STYLES[carrier.status_code] ?? STATUS_STYLES.UNKNOWN}`}>
                  {carrier.status_name}
                </span>
              } />
              <Field label="Onboarding Status" value={carrier.onboarding_status} />
              <Field label="Safety Rating"     value={carrier.safety_rating} />
            </div>
          </Section>

          <Section title="Financial" icon={CreditCard}>
            <div className="space-y-3">
              <Field label="Payment Terms"    value={carrier.payment_terms} />
              <Field label="Remittance Party" value={carrier.remittance_party} />
            </div>
          </Section>
        </div>

        <div className="bg-white rounded-lg border overflow-hidden">
          <div className="flex items-center gap-2 px-5 py-3 border-b bg-gray-50">
            <DollarSign size={15} className="text-blue-600" />
            <h2 className="text-sm font-semibold text-gray-700">Rate Cards ({rateCards.length})</h2>
          </div>
          {rateCards.length === 0 ? (
            <div className="px-5 py-8 text-center text-gray-400 text-sm">No rate cards configured.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-gray-50 border-b text-left text-xs text-gray-600">
                    {["Name","Mode","Rate Type","Contract Ref","Effective","Expiry","Status","Priority","Lanes"].map(h => (
                      <th key={h} className="px-4 py-2.5 font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rateCards.map((rc, i) => (
                    <tr key={rc.rate_card_id}
                      className={`border-b last:border-0 hover:bg-blue-50 cursor-pointer ${i % 2 === 0 ? 'bg-white' : 'bg-gray-50/50'}`}
                      onClick={() => router.push('/settings/rating')}>
                      <td className="px-4 py-2.5 font-medium text-gray-800">{rc.name}</td>
                      <td className="px-4 py-2.5"><span className="text-xs bg-indigo-50 text-indigo-700 px-2 py-0.5 rounded">{rc.mode}</span></td>
                      <td className="px-4 py-2.5"><span className={`text-xs px-2 py-0.5 rounded ${RATE_TYPE_STYLES[rc.rate_type] ?? 'bg-gray-100 text-gray-600'}`}>{rc.rate_type?.replace(/_/g,' ')}</span></td>
                      <td className="px-4 py-2.5 text-xs font-mono text-gray-600">{rc.contract_reference || '—'}</td>
                      <td className="px-4 py-2.5 text-xs text-gray-600">{fmt(rc.effective_date)}</td>
                      <td className="px-4 py-2.5 text-xs text-gray-600">{rc.expiry_date ? fmt(rc.expiry_date) : 'Open'}</td>
                      <td className="px-4 py-2.5"><span className={`text-xs px-2 py-0.5 rounded ${rc.status === 'active' ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-500'}`}>{rc.status}</span></td>
                      <td className="px-4 py-2.5 text-xs text-gray-600 text-center">{rc.route_priority}</td>
                      <td className="px-4 py-2.5 text-xs text-center"><span className="bg-gray-100 text-gray-600 px-2 py-0.5 rounded">{rc.lane_count}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {showEdit && carrier && (
        <EditModal carrier={carrier} lookups={lookups} onClose={() => setShowEdit(false)} onSaved={handleSaved} />
      )}
    </div>
  )
}
