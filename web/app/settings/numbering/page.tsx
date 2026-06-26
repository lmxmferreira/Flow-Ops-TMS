'use client'
import { useEffect, useState, useCallback } from 'react'
import { Hash, RefreshCw, Save, RotateCcw, Eye, Check, X } from 'lucide-react'
import { api } from '../../lib/api'

interface Scheme {
  scheme_id: string
  entity_type: string
  scheme_name: string
  prefix: string
  suffix: string
  separator: string
  padding: number
  include_year: boolean
  include_month: boolean
  reset_period: string
  next_value: number
  last_reset_at: string | null
  is_active: boolean
  preview: string
}

const ENTITY_LABELS: Record<string, string> = {
  SHIPMENT:        'Shipments',
  PURCHASE_ORDER:  'Purchase Orders',
  ORDER_RELEASE:   'Order Releases',
  LOAD:            'Loads',
  STOP:            'Stops',
  CARRIER_INVOICE: 'Carrier Invoices',
  CLIENT_BILL:     'Client Bills',
  VOUCHER:         'Vouchers',
  CLAIM:           'Claims',
  DISPUTE:         'Disputes',
}

const ENTITY_COLORS: Record<string, string> = {
  SHIPMENT:'bg-blue-100 text-blue-700', PURCHASE_ORDER:'bg-indigo-100 text-indigo-700',
  ORDER_RELEASE:'bg-purple-100 text-purple-700', LOAD:'bg-cyan-100 text-cyan-700',
  STOP:'bg-teal-100 text-teal-700', CARRIER_INVOICE:'bg-orange-100 text-orange-700',
  CLIENT_BILL:'bg-pink-100 text-pink-700', VOUCHER:'bg-rose-100 text-rose-700',
  CLAIM:'bg-red-100 text-red-700', DISPUTE:'bg-yellow-100 text-yellow-700',
}

function SchemeCard({ scheme, onRefresh }: { scheme: Scheme; onRefresh: () => void }) {
  const [editing, setEditing] = useState(false)
  const [saving, setSaving]   = useState(false)
  const [preview, setPreview] = useState(scheme.preview || '')
  const [form, setForm]       = useState({
    prefix: scheme.prefix, suffix: scheme.suffix, separator: scheme.separator,
    padding: String(scheme.padding), include_year: scheme.include_year,
    include_month: scheme.include_month, reset_period: scheme.reset_period,
    next_value: String(scheme.next_value),
  })

  const buildPreview = () => {
    const pad = parseInt(form.padding) || 6
    const counter = '1'.padStart(pad, '0')
    const now = new Date()
    let yearPart = ''
    if (form.include_month) yearPart = `${now.getFullYear()}${String(now.getMonth()+1).padStart(2,'0')}${form.separator}`
    else if (form.include_year) yearPart = `${now.getFullYear()}${form.separator}`
    return `${form.prefix}${yearPart}${counter}${form.suffix}`
  }

  const save = async () => {
    setSaving(true)
    try {
      await api.numbering.update(scheme.entity_type, {
        prefix: form.prefix, suffix: form.suffix, separator: form.separator,
        padding: parseInt(form.padding) || 6,
        include_year: form.include_year, include_month: form.include_month,
        reset_period: form.reset_period,
        next_value: parseInt(form.next_value) || 1,
      })
      setEditing(false)
      onRefresh()
    } finally { setSaving(false) }
  }

  const reset = async () => {
    if (!confirm(`Reset ${ENTITY_LABELS[scheme.entity_type]} counter to 1?`)) return
    await api.numbering.reset(scheme.entity_type, { start_from: 1 })
    onRefresh()
  }

  const inp = 'border rounded px-2 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500 w-full'
  const lbl = 'text-xs text-gray-500 mb-0.5 block'

  return (
    <div className={`bg-white rounded-lg border overflow-hidden ${!scheme.is_active ? 'opacity-60' : ''}`}>
      {/* Header */}
      <div className="flex items-center gap-3 px-5 py-3 border-b bg-gray-50">
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${ENTITY_COLORS[scheme.entity_type] ?? 'bg-gray-100 text-gray-600'}`}>
          {ENTITY_LABELS[scheme.entity_type] ?? scheme.entity_type}
        </span>
        <span className="text-sm font-medium text-gray-700 flex-1">{scheme.scheme_name}</span>
        {/* Preview badge */}
        <span className="font-mono text-sm font-bold text-blue-700 bg-blue-50 px-3 py-1 rounded-lg border border-blue-100">
          {editing ? buildPreview() : (scheme.preview || '—')}
        </span>
        <div className="flex gap-1">
          {editing ? (
            <>
              <button onClick={save} disabled={saving}
                className="flex items-center gap-1 px-2.5 py-1.5 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 disabled:opacity-50">
                {saving ? <RefreshCw size={12} className="animate-spin" /> : <Save size={12} />} Save
              </button>
              <button onClick={() => setEditing(false)}
                className="p-1.5 text-gray-400 hover:text-gray-600 rounded hover:bg-gray-100">
                <X size={14} />
              </button>
            </>
          ) : (
            <>
              <button onClick={() => setEditing(true)}
                className="px-2.5 py-1.5 text-xs text-gray-500 border rounded hover:bg-gray-50">
                Edit
              </button>
              <button onClick={reset}
                className="p-1.5 text-gray-400 hover:text-orange-500 rounded hover:bg-gray-100"
                title="Reset counter">
                <RotateCcw size={14} />
              </button>
            </>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="px-5 py-4">
        {!editing ? (
          /* View mode */
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
            <div><p className={lbl}>Prefix</p><p className="font-mono font-medium">{scheme.prefix || '—'}</p></div>
            <div><p className={lbl}>Suffix</p><p className="font-mono font-medium">{scheme.suffix || '—'}</p></div>
            <div><p className={lbl}>Separator</p><p className="font-mono font-medium">{scheme.separator || '—'}</p></div>
            <div><p className={lbl}>Padding</p><p className="font-medium">{scheme.padding} digits</p></div>
            <div><p className={lbl}>Next #</p><p className="font-bold text-blue-700">{scheme.next_value}</p></div>
            <div><p className={lbl}>Include Year</p><p>{scheme.include_year ? '✓ Yes' : '✗ No'}</p></div>
            <div><p className={lbl}>Include Month</p><p>{scheme.include_month ? '✓ Yes' : '✗ No'}</p></div>
            <div><p className={lbl}>Reset Period</p><p>{scheme.reset_period}</p></div>
            {scheme.last_reset_at && (
              <div className="col-span-2"><p className={lbl}>Last Reset</p>
                <p className="text-gray-500 text-xs">{new Date(scheme.last_reset_at).toLocaleString()}</p>
              </div>
            )}
          </div>
        ) : (
          /* Edit mode */
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div>
              <label className={lbl}>Prefix</label>
              <input value={form.prefix} onChange={e => setForm(f=>({...f,prefix:e.target.value}))} className={inp} placeholder="SHP-" />
            </div>
            <div>
              <label className={lbl}>Suffix</label>
              <input value={form.suffix} onChange={e => setForm(f=>({...f,suffix:e.target.value}))} className={inp} placeholder="-US" />
            </div>
            <div>
              <label className={lbl}>Separator (year/counter)</label>
              <input value={form.separator} onChange={e => setForm(f=>({...f,separator:e.target.value}))} className={inp} placeholder="-" />
            </div>
            <div>
              <label className={lbl}>Padding (digits)</label>
              <input type="number" min="1" max="12" value={form.padding}
                onChange={e => setForm(f=>({...f,padding:e.target.value}))} className={inp} />
            </div>
            <div>
              <label className={lbl}>Next value</label>
              <input type="number" min="1" value={form.next_value}
                onChange={e => setForm(f=>({...f,next_value:e.target.value}))} className={inp} />
            </div>
            <div>
              <label className={lbl}>Reset period</label>
              <select value={form.reset_period} onChange={e => setForm(f=>({...f,reset_period:e.target.value}))} className={inp}>
                <option value="NEVER">Never</option>
                <option value="YEARLY">Yearly</option>
                <option value="MONTHLY">Monthly</option>
              </select>
            </div>
            <div className="flex items-center gap-4 col-span-2 pt-4">
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={form.include_year}
                  onChange={e => setForm(f=>({...f,include_year:e.target.checked, include_month: e.target.checked ? false : f.include_month}))}
                  className="rounded" />
                Include Year
              </label>
              <label className="flex items-center gap-2 text-sm cursor-pointer">
                <input type="checkbox" checked={form.include_month}
                  onChange={e => setForm(f=>({...f,include_month:e.target.checked, include_year: e.target.checked ? false : f.include_year}))}
                  className="rounded" />
                Include Month
              </label>
            </div>
            <div className="col-span-4 mt-1">
              <p className={lbl}>Preview</p>
              <p className="font-mono text-lg font-bold text-blue-700">{buildPreview()}</p>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default function NumberingPage() {
  const [schemes, setSchemes] = useState<Scheme[]>([])
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await api.numbering.list()
      setSchemes(res.data)
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-white border-b px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Hash className="text-blue-600" size={22} />
          <div>
            <h1 className="text-xl font-semibold text-gray-800">Numbering Schemes</h1>
            <p className="text-xs text-gray-400">
              Configure document numbering for all entity types — prefix, suffix, padding, year, and reset rules
            </p>
          </div>
        </div>
        <button onClick={load}
          className="text-gray-400 hover:text-blue-600 p-1.5 rounded hover:bg-gray-100">
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
        </button>
      </div>

      <div className="px-6 py-5 space-y-3">
        {loading && schemes.length === 0 ? (
          <div className="flex items-center justify-center py-16 text-gray-400">
            <RefreshCw size={18} className="animate-spin mr-2" /> Loading…
          </div>
        ) : (
          schemes.map(s => <SchemeCard key={s.scheme_id} scheme={s} onRefresh={load} />)
        )}
      </div>
    </div>
  )
}
