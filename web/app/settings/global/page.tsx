'use client'
import { useEffect, useState, useCallback } from 'react'
import { Globe, RefreshCw, Check, X, Search } from 'lucide-react'
import { api } from '../../lib/api'

// ── Types ─────────────────────────────────────────────────────
interface Currency    { currency_code: string; currency_name: string; currency_symbol: string; decimal_places: number; is_active: boolean }
interface Language    { language_code: string; language_name: string; native_name: string; locale_code: string; is_active: boolean; is_default: boolean }
interface DateFormat  { format_code: string; format_pattern: string; display_example: string; region: string; is_active: boolean; is_default: boolean }
interface TimeZone    { tz_code: string; tz_name: string; utc_offset: string; region: string; is_active: boolean; is_default: boolean }
interface TaxJur      { jurisdiction_code: string; jurisdiction_name: string; country_code: string; state_province: string; tax_type: string; standard_rate: number; reduced_rate: number|null; currency_code: string; is_active: boolean }
interface UOM         { uom_id: string; uom_code: string; uom_name: string; uom_type: string; base_uom_code: string|null; conversion_factor: number|null; is_active: boolean }

const TABS = [
  { key: 'currencies',   label: 'Currencies',        color: 'text-green-600'  },
  { key: 'languages',    label: 'Languages',          color: 'text-blue-600'   },
  { key: 'dateformats',  label: 'Date Formats',       color: 'text-purple-600' },
  { key: 'timezones',    label: 'Time Zones',         color: 'text-orange-600' },
  { key: 'tax',          label: 'Tax Jurisdictions',  color: 'text-red-600'    },
  { key: 'uoms',         label: 'Units of Measure',   color: 'text-teal-600'   },
]

const UOM_TYPE_COLORS: Record<string,string> = {
  WEIGHT:'bg-blue-100 text-blue-700', VOLUME:'bg-cyan-100 text-cyan-700',
  LENGTH:'bg-purple-100 text-purple-700', QTY:'bg-green-100 text-green-700',
  TIME:'bg-orange-100 text-orange-700',
}

function ActiveToggle({ value, onChange }: { value: boolean; onChange: (v: boolean) => void }) {
  return (
    <button onClick={() => onChange(!value)}
      className={`w-10 h-5 rounded-full transition-colors ${value ? 'bg-green-500' : 'bg-gray-300'} relative`}>
      <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${value ? 'translate-x-5' : 'translate-x-0.5'}`}/>
    </button>
  )
}

function SearchBar({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <div className="relative w-64">
      <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"/>
      <input value={value} onChange={e => onChange(e.target.value)}
        placeholder="Search…"
        className="w-full pl-8 pr-3 py-1.5 border rounded-lg text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"/>
    </div>
  )
}

export default function GlobalSettingsPage() {
  const [activeTab, setActiveTab] = useState('currencies')
  const [search, setSearch]       = useState('')
  const [loading, setLoading]     = useState(false)

  const [currencies,  setCurrencies]  = useState<Currency[]>([])
  const [languages,   setLanguages]   = useState<Language[]>([])
  const [dateFormats, setDateFormats] = useState<DateFormat[]>([])
  const [timeZones,   setTimeZones]   = useState<TimeZone[]>([])
  const [taxJurs,     setTaxJurs]     = useState<TaxJur[]>([])
  const [uoms,        setUoms]        = useState<UOM[]>([])

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const [c, l, d, t, tx, u] = await Promise.all([
        api.globalSettings.currencies(),
        api.globalSettings.languages(),
        api.globalSettings.dateFormats(),
        api.globalSettings.timeZones(),
        api.globalSettings.taxJurisdictions(),
        api.globalSettings.uoms(),
      ])
      setCurrencies(c.data); setLanguages(l.data); setDateFormats(d.data)
      setTimeZones(t.data); setTaxJurs(tx.data); setUoms(u.data)
    } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])
  useEffect(() => { setSearch('') }, [activeTab])

  const HDR = 'px-4 py-2.5 text-xs font-medium text-gray-500 text-left bg-gray-50 border-b'
  const TD  = 'px-4 py-2 text-sm border-b last:border-0'
  const TBL = 'w-full text-sm'

  const fmtRate = (r: number|null) => r !== null ? `${Number(r).toFixed(2)}%` : '—'

  // Filter helpers
  const f = (str: string) => str?.toLowerCase().includes(search.toLowerCase())

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Globe className="text-blue-600" size={22}/>
          <div>
            <h1 className="text-xl font-semibold text-gray-800">Global Settings</h1>
            <p className="text-xs text-gray-400">Currencies · Languages · Date formats · Time zones · Tax jurisdictions · Units of measure</p>
          </div>
        </div>
        <button onClick={load} className="text-gray-400 hover:text-blue-600 p-1.5 rounded hover:bg-gray-100">
          <RefreshCw size={15} className={loading ? 'animate-spin' : ''}/>
        </button>
      </div>

      {/* Tabs */}
      <div className="bg-white border-b overflow-x-auto">
        <div className="flex px-6 min-w-max">
          {TABS.map(tab => (
            <button key={tab.key} onClick={() => setActiveTab(tab.key)}
              className={`px-4 py-3 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${
                activeTab === tab.key
                  ? `border-blue-600 ${tab.color}`
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}>
              {tab.label}
              <span className="ml-1.5 text-gray-300 text-xs">
                {activeTab === tab.key && {
                  currencies: currencies.length, languages: languages.length,
                  dateformats: dateFormats.length, timezones: timeZones.length,
                  tax: taxJurs.length, uoms: uoms.length
                }[tab.key]}
              </span>
            </button>
          ))}
        </div>
      </div>

      <div className="px-6 py-5">
        {/* Search */}
        <div className="mb-4">
          <SearchBar value={search} onChange={setSearch}/>
        </div>

        {/* ── CURRENCIES ── */}
        {activeTab === 'currencies' && (
          <div className="bg-white rounded-lg border overflow-hidden">
            <table className={TBL}>
              <thead><tr>
                {['Code','Name','Symbol','Decimals','Active'].map(h => <th key={h} className={HDR}>{h}</th>)}
              </tr></thead>
              <tbody>
                {currencies.filter(c => f(c.currency_code)||f(c.currency_name)).map(c => (
                  <tr key={c.currency_code} className="hover:bg-gray-50">
                    <td className={`${TD} font-mono font-bold text-green-700`}>{c.currency_code}</td>
                    <td className={TD}>{c.currency_name}</td>
                    <td className={`${TD} font-mono`}>{c.currency_symbol}</td>
                    <td className={`${TD} text-center`}>{c.decimal_places}</td>
                    <td className={TD}>
                      <ActiveToggle value={c.is_active} onChange={async v => {
                        await api.globalSettings.updateCurrency(c.currency_code, {is_active: v})
                        setCurrencies(cs => cs.map(x => x.currency_code===c.currency_code ? {...x,is_active:v} : x))
                      }}/>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ── LANGUAGES ── */}
        {activeTab === 'languages' && (
          <div className="bg-white rounded-lg border overflow-hidden">
            <table className={TBL}>
              <thead><tr>
                {['Code','Name','Native Name','Locale','Default','Active'].map(h => <th key={h} className={HDR}>{h}</th>)}
              </tr></thead>
              <tbody>
                {languages.filter(l => f(l.language_code)||f(l.language_name)||f(l.native_name)).map(l => (
                  <tr key={l.language_code} className="hover:bg-gray-50">
                    <td className={`${TD} font-mono font-bold text-blue-700`}>{l.language_code}</td>
                    <td className={TD}>{l.language_name}</td>
                    <td className={TD}>{l.native_name}</td>
                    <td className={`${TD} font-mono text-xs text-gray-400`}>{l.locale_code}</td>
                    <td className={`${TD} text-center`}>
                      {l.is_default
                        ? <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded-full font-medium">Default</span>
                        : <button onClick={async () => {
                            await api.globalSettings.updateLanguage(l.language_code, {is_default: true})
                            setLanguages(ls => ls.map(x => ({...x, is_default: x.language_code===l.language_code})))
                          }} className="text-xs text-gray-400 hover:text-blue-600">Set default</button>
                      }
                    </td>
                    <td className={TD}>
                      <ActiveToggle value={l.is_active} onChange={async v => {
                        await api.globalSettings.updateLanguage(l.language_code, {is_active: v})
                        setLanguages(ls => ls.map(x => x.language_code===l.language_code ? {...x,is_active:v} : x))
                      }}/>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ── DATE FORMATS ── */}
        {activeTab === 'dateformats' && (
          <div className="bg-white rounded-lg border overflow-hidden">
            <table className={TBL}>
              <thead><tr>
                {['Code','Pattern','Example','Region','Default','Active'].map(h => <th key={h} className={HDR}>{h}</th>)}
              </tr></thead>
              <tbody>
                {dateFormats.filter(d => f(d.format_pattern)||f(d.region)||f(d.display_example)).map(d => (
                  <tr key={d.format_code} className="hover:bg-gray-50">
                    <td className={`${TD} font-mono text-xs text-purple-700`}>{d.format_code}</td>
                    <td className={`${TD} font-mono font-bold`}>{d.format_pattern}</td>
                    <td className={`${TD} text-gray-600`}>{d.display_example}</td>
                    <td className={TD}>{d.region}</td>
                    <td className={`${TD} text-center`}>
                      {d.is_default
                        ? <span className="text-xs bg-purple-100 text-purple-700 px-2 py-0.5 rounded-full font-medium">Default</span>
                        : <button onClick={async () => {
                            await api.globalSettings.updateDateFormat(d.format_code, {is_default: true})
                            setDateFormats(ds => ds.map(x => ({...x, is_default: x.format_code===d.format_code})))
                          }} className="text-xs text-gray-400 hover:text-purple-600">Set default</button>
                      }
                    </td>
                    <td className={TD}>
                      <ActiveToggle value={d.is_active} onChange={async v => {
                        await api.globalSettings.updateDateFormat(d.format_code, {is_active: v})
                        setDateFormats(ds => ds.map(x => x.format_code===d.format_code ? {...x,is_active:v} : x))
                      }}/>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ── TIME ZONES ── */}
        {activeTab === 'timezones' && (
          <div className="bg-white rounded-lg border overflow-hidden">
            <table className={TBL}>
              <thead><tr>
                {['IANA Code','Name','UTC Offset','Region','Default','Active'].map(h => <th key={h} className={HDR}>{h}</th>)}
              </tr></thead>
              <tbody>
                {timeZones.filter(t => f(t.tz_code)||f(t.tz_name)||f(t.region)).map(t => (
                  <tr key={t.tz_code} className="hover:bg-gray-50">
                    <td className={`${TD} font-mono text-xs text-orange-700`}>{t.tz_code}</td>
                    <td className={TD}>{t.tz_name}</td>
                    <td className={`${TD} font-mono text-xs`}>{t.utc_offset}</td>
                    <td className={TD}>{t.region}</td>
                    <td className={`${TD} text-center`}>
                      {t.is_default
                        ? <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full font-medium">Default</span>
                        : <button onClick={async () => {
                            await api.globalSettings.updateTimeZone(t.tz_code, {is_default: true})
                            setTimeZones(ts => ts.map(x => ({...x, is_default: x.tz_code===t.tz_code})))
                          }} className="text-xs text-gray-400 hover:text-orange-600">Set default</button>
                      }
                    </td>
                    <td className={TD}>
                      <ActiveToggle value={t.is_active} onChange={async v => {
                        await api.globalSettings.updateTimeZone(t.tz_code, {is_active: v})
                        setTimeZones(ts => ts.map(x => x.tz_code===t.tz_code ? {...x,is_active:v} : x))
                      }}/>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ── TAX JURISDICTIONS ── */}
        {activeTab === 'tax' && (
          <div className="bg-white rounded-lg border overflow-hidden">
            <table className={TBL}>
              <thead><tr>
                {['Code','Name','Country','State','Type','Std Rate','Red Rate','Currency','Active'].map(h => <th key={h} className={HDR}>{h}</th>)}
              </tr></thead>
              <tbody>
                {taxJurs.filter(t => f(t.jurisdiction_code)||f(t.jurisdiction_name)||f(t.country_code)).map(t => (
                  <tr key={t.jurisdiction_code} className="hover:bg-gray-50">
                    <td className={`${TD} font-mono text-xs text-red-700 font-bold`}>{t.jurisdiction_code}</td>
                    <td className={TD}>{t.jurisdiction_name}</td>
                    <td className={`${TD} font-mono`}>{t.country_code}</td>
                    <td className={`${TD} text-xs text-gray-400`}>{t.state_province||'—'}</td>
                    <td className={TD}>
                      <span className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded">{t.tax_type}</span>
                    </td>
                    <td className={`${TD} text-right tabular-nums font-medium`}>{fmtRate(t.standard_rate)}</td>
                    <td className={`${TD} text-right tabular-nums text-gray-400`}>{fmtRate(t.reduced_rate)}</td>
                    <td className={`${TD} font-mono text-xs`}>{t.currency_code}</td>
                    <td className={TD}>
                      <ActiveToggle value={t.is_active} onChange={async v => {
                        await api.globalSettings.updateTaxJurisdiction(t.jurisdiction_code, {is_active: v})
                        setTaxJurs(ts => ts.map(x => x.jurisdiction_code===t.jurisdiction_code ? {...x,is_active:v} : x))
                      }}/>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ── UOMs ── */}
        {activeTab === 'uoms' && (
          <div className="bg-white rounded-lg border overflow-hidden">
            <table className={TBL}>
              <thead><tr>
                {['Code','Name','Type','Base UOM','Conversion Factor','Active'].map(h => <th key={h} className={HDR}>{h}</th>)}
              </tr></thead>
              <tbody>
                {uoms.filter(u => f(u.uom_code)||f(u.uom_name)||f(u.uom_type)).map(u => (
                  <tr key={u.uom_id} className="hover:bg-gray-50">
                    <td className={`${TD} font-mono font-bold text-teal-700`}>{u.uom_code}</td>
                    <td className={TD}>{u.uom_name}</td>
                    <td className={TD}>
                      {u.uom_type && (
                        <span className={`text-xs px-2 py-0.5 rounded font-medium ${UOM_TYPE_COLORS[u.uom_type]??'bg-gray-100 text-gray-600'}`}>
                          {u.uom_type}
                        </span>
                      )}
                    </td>
                    <td className={`${TD} font-mono text-xs text-gray-400`}>{u.base_uom_code||'—'}</td>
                    <td className={`${TD} tabular-nums text-xs text-gray-500`}>
                      {u.conversion_factor ? Number(u.conversion_factor).toPrecision(6) : '—'}
                    </td>
                    <td className={TD}>
                      <ActiveToggle value={u.is_active} onChange={async v => {
                        await api.globalSettings.updateUOM(u.uom_code, {is_active: v})
                        setUoms(us => us.map(x => x.uom_id===u.uom_id ? {...x,is_active:v} : x))
                      }}/>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
