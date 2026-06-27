'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { FileText, Plus, Search, ChevronRight, ArrowRight, DollarSign } from 'lucide-react'
import { apiFetch, fmtDate, statusColor } from '../../../lib/api'

const STATUS_COLORS: Record<string,string> = {
  active:'bg-green-100 text-green-700', draft:'bg-gray-100 text-gray-600',
  expired:'bg-red-100 text-red-600', superseded:'bg-orange-100 text-orange-600'
}

export default function RateCardsPage() {
  const [cards, setCards] = useState<any[]>([])
  const [regions, setRegions] = useState<any[]>([])
  const [selected, setSelected] = useState<any>(null)
  const [lanes, setLanes] = useState<any[]>([])
  const [laneLines, setLaneLines] = useState<Record<string,any[]>>({})
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [modeFilter, setModeFilter] = useState('')
  const [expandedLane, setExpandedLane] = useState<string|null>(null)

  useEffect(() => {
    Promise.all([
      apiFetch('/master-data/rate-cards'),
      apiFetch('/master-data/rate-regions'),
    ]).then(([c, r]) => {
      setCards(c.rate_cards || []); setRegions(r.regions || [])
      setLoading(false)
    }).catch(() => setLoading(false))
  }, [])

  async function selectCard(card: any) {
    setSelected(card); setExpandedLane(null); setLaneLines({})
    const d = await apiFetch(`/master-data/rate-cards/${card.rate_card_id}`)
    setLanes(d.lanes || [])
  }

  async function expandLane(lane: any) {
    if (expandedLane === lane.lane_id) { setExpandedLane(null); return }
    setExpandedLane(lane.lane_id)
    if (!laneLines[lane.lane_id]) {
      const d = await apiFetch(`/master-data/rate-cards/${selected.rate_card_id}/lanes/${lane.lane_id}/lines`)
      setLaneLines(prev => ({...prev, [lane.lane_id]: d.lines || []}))
    }
  }

  const filtered = cards.filter(c =>
    (!search || c.name?.toLowerCase().includes(search.toLowerCase()) || c.carrier_name?.toLowerCase().includes(search.toLowerCase())) &&
    (!modeFilter || c.mode === modeFilter)
  )
  const modes = [...new Set(cards.map(c => c.mode).filter(Boolean))]

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><FileText className="text-green-600" size={24}/> Rate Cards</h1>
          <p className="text-sm text-gray-500 mt-1">Carrier rate cards with lanes, regions, weight breaks, and charge lines</p>
        </div>
        <Link href="/rates/regions" className="flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-800 border border-blue-200 px-3 py-2 rounded-lg hover:bg-blue-50">
          Manage Regions <ArrowRight size={14}/>
        </Link>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        {/* Card list */}
        <div className="lg:col-span-2 bg-white rounded-xl border border-gray-200 overflow-hidden">
          <div className="p-3 border-b border-gray-100 space-y-2">
            <div className="relative">
              <Search size={13} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400"/>
              <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search carrier, card name..."
                className="pl-8 pr-3 py-1.5 text-sm border border-gray-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-blue-500"/>
            </div>
            <select value={modeFilter} onChange={e => setModeFilter(e.target.value)}
              className="w-full text-sm border border-gray-200 rounded-lg px-2 py-1.5 focus:outline-none">
              <option value="">All Modes</option>
              {modes.map(m => <option key={m} value={m}>{m}</option>)}
            </select>
          </div>
          <div className="divide-y divide-gray-100 max-h-[calc(100vh-280px)] overflow-y-auto">
            {loading ? <p className="text-center py-8 text-sm text-gray-400">Loading...</p>
            : filtered.length === 0 ? <p className="text-center py-8 text-sm text-gray-400">No rate cards found</p>
            : filtered.map(c => (
              <button key={c.rate_card_id} onClick={() => selectCard(c)}
                className={`w-full text-left px-4 py-3.5 hover:bg-gray-50 transition-colors ${selected?.rate_card_id === c.rate_card_id ? 'bg-green-50 border-l-2 border-green-600' : ''}`}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-gray-900 truncate">{c.name || 'Unnamed Card'}</p>
                    <p className="text-xs text-gray-500 mt-0.5">{c.carrier_name || '—'}</p>
                    <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                      {c.mode && <span className="text-xs bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded font-medium">{c.mode}</span>}
                      <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${STATUS_COLORS[c.status] || 'bg-gray-100 text-gray-600'}`}>{c.status}</span>
                      <span className="text-xs text-gray-400">{c.lane_count || 0} lanes</span>
                    </div>
                    <p className="text-xs text-gray-400 mt-1">{fmtDate(c.effective_date)} → {fmtDate(c.expiry_date) || '—'}</p>
                  </div>
                  <ChevronRight size={14} className="text-gray-300 mt-1 flex-shrink-0"/>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Card detail */}
        <div className="lg:col-span-3">
          {!selected ? (
            <div className="bg-white rounded-xl border border-gray-200 h-full flex items-center justify-center">
              <div className="text-center py-16">
                <FileText size={32} className="text-gray-200 mx-auto mb-3"/>
                <p className="text-sm text-gray-400">Select a rate card to view lanes and charge lines</p>
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
              {/* Card header */}
              <div className="px-5 py-4 border-b border-gray-100 bg-gray-50">
                <div className="flex items-start justify-between">
                  <div>
                    <h2 className="text-base font-bold text-gray-900">{selected.name}</h2>
                    <p className="text-sm text-gray-500 mt-0.5">{selected.carrier_name} · {selected.mode} · v{selected.version_number || 1}</p>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded-full font-medium ${STATUS_COLORS[selected.status] || 'bg-gray-100 text-gray-600'}`}>{selected.status}</span>
                </div>
                <div className="grid grid-cols-4 gap-3 mt-3">
                  {[['Currency', selected.currency],['Effective', fmtDate(selected.effective_date)],['Expires', fmtDate(selected.expiry_date) || '—'],['Lanes', selected.lane_count]].map(([l,v]) => (
                    <div key={l as string} className="bg-white rounded-lg p-2 border border-gray-100">
                      <p className="text-[10px] text-gray-400 font-semibold uppercase">{l}</p>
                      <p className="text-sm font-bold text-gray-900 mt-0.5">{v}</p>
                    </div>
                  ))}
                </div>
                {selected.contract_reference && <p className="text-xs text-gray-400 mt-2">Contract ref: <span className="font-mono">{selected.contract_reference}</span></p>}
              </div>

              {/* Lanes */}
              <div className="max-h-[calc(100vh-380px)] overflow-y-auto">
                {lanes.length === 0 ? (
                  <div className="text-center py-10"><p className="text-sm text-gray-400">No lanes configured for this rate card</p></div>
                ) : lanes.map((lane: any) => (
                  <div key={lane.lane_id} className="border-b border-gray-100 last:border-0">
                    <button onClick={() => expandLane(lane)}
                      className="w-full text-left px-5 py-3.5 hover:bg-gray-50 transition-colors">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="flex items-center gap-2 text-sm">
                            <span className="font-semibold text-gray-800 bg-blue-50 text-blue-700 px-2 py-0.5 rounded text-xs">{lane.origin_type}: {lane.origin_value}</span>
                            <ArrowRight size={12} className="text-gray-400"/>
                            <span className="font-semibold text-gray-800 bg-green-50 text-green-700 px-2 py-0.5 rounded text-xs">{lane.destination_type}: {lane.destination_value}</span>
                          </div>
                          {lane.lane_name && <span className="text-xs text-gray-400">· {lane.lane_name}</span>}
                        </div>
                        <div className="flex items-center gap-2">
                          {lane.min_weight_kg > 0 && <span className="text-xs text-gray-400">{lane.min_weight_kg}–{lane.max_weight_kg}kg</span>}
                          <span className="text-xs text-gray-400">{lane.line_count} lines</span>
                          <ChevronRight size={14} className={`text-gray-300 transition-transform ${expandedLane === lane.lane_id ? 'rotate-90' : ''}`}/>
                        </div>
                      </div>
                    </button>

                    {/* Charge lines */}
                    {expandedLane === lane.lane_id && (
                      <div className="px-5 pb-4 bg-gray-50">
                        {!laneLines[lane.lane_id] ? (
                          <p className="text-xs text-gray-400 py-2">Loading...</p>
                        ) : laneLines[lane.lane_id].length === 0 ? (
                          <p className="text-xs text-gray-400 py-2">No charge lines</p>
                        ) : (
                          <table className="w-full text-xs">
                            <thead>
                              <tr className="border-b border-gray-200">
                                {['Charge Code','Description','Rate','UOM','Min','Max','Formula'].map(h => (
                                  <th key={h} className="text-left py-2 pr-3 font-semibold text-gray-400 uppercase tracking-wide">{h}</th>
                                ))}
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-100">
                              {laneLines[lane.lane_id].map((line: any) => (
                                <tr key={line.rate_line_id} className="hover:bg-white">
                                  <td className="py-2 pr-3 font-mono font-medium text-gray-700">{line.charge_code}</td>
                                  <td className="py-2 pr-3 text-gray-600">{line.description || '—'}</td>
                                  <td className="py-2 pr-3 font-semibold text-gray-900">{line.currency} {parseFloat(line.rate_amount).toFixed(2)}</td>
                                  <td className="py-2 pr-3 text-gray-500">{line.uom || '—'}</td>
                                  <td className="py-2 pr-3 text-gray-500">{line.min_charge ? `${parseFloat(line.min_charge).toFixed(2)}` : '—'}</td>
                                  <td className="py-2 pr-3 text-gray-500">{line.max_charge ? `${parseFloat(line.max_charge).toFixed(2)}` : '—'}</td>
                                  <td className="py-2 text-gray-400 font-mono text-[10px]">{line.formula_text || '—'}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
