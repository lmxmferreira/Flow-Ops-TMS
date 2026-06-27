'use client'
import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import Link from 'next/link'
import { GitBranch, ArrowLeft, CheckCircle, Circle, AlertTriangle, Package, DollarSign, FileText } from 'lucide-react'

const API = process.env.NEXT_PUBLIC_API_URL

export default function LifecycleDetailPage() {
  const { shipment_id } = useParams()
  const [lc, setLc] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  const token = () => localStorage.getItem('tms_token')

  useEffect(() => {
    fetch(`${API}/e2e/lifecycle/${shipment_id}`, { headers: { Authorization: `Bearer ${token()}` } })
      .then(r => r.json()).then(d => { setLc(d); setLoading(false) })
  }, [shipment_id])

  if (loading) return <div className="p-8 text-gray-400">Loading lifecycle...</div>
  if (!lc) return <div className="p-8 text-gray-400">Not found.</div>

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Link href="/e2e" className="text-gray-400 hover:text-gray-700"><ArrowLeft size={20} /></Link>
        <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
          <GitBranch size={20} className="text-blue-600" />
          {lc.shipment_number} — Full Lifecycle
        </h1>
      </div>

      {/* Progress */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <p className="text-sm text-gray-500">Carrier: <span className="font-medium text-gray-800">{lc.carrier || '—'}</span></p>
            <p className="text-sm text-gray-500">Current Stage: <span className="font-medium text-gray-800 capitalize">{lc.current_stage?.replace(/_/g,' ')}</span></p>
          </div>
          <div className="text-right">
            <p className="text-3xl font-bold text-blue-600">{lc.pct_complete}%</p>
            <p className="text-xs text-gray-500">{lc.stages_done}/{lc.total_stages} stages</p>
          </div>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-3">
          <div className="bg-blue-600 h-3 rounded-full transition-all" style={{ width: `${lc.pct_complete}%` }} />
        </div>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Stage timeline */}
        <div className="col-span-2">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Stage Timeline</h2>
          <div className="space-y-2">
            {(lc.stage_timeline || []).map((stage: any, i: number) => (
              <div key={stage.stage} className="flex items-center gap-3 bg-white rounded-lg border border-gray-100 p-3">
                {stage.done
                  ? <CheckCircle size={18} className="text-green-500 shrink-0" />
                  : <Circle size={18} className="text-gray-200 shrink-0" />}
                <div className="flex-1">
                  <p className={`text-sm font-medium ${stage.done ? 'text-gray-800' : 'text-gray-400'}`}>{stage.label}</p>
                </div>
                {stage.at && stage.at !== '' && (
                  <p className="text-xs text-gray-400">{new Date(stage.at).toLocaleString()}</p>
                )}
                {!stage.done && <span className="text-xs text-gray-300">Pending</span>}
              </div>
            ))}
          </div>
        </div>

        {/* Right: linked data */}
        <div className="space-y-4">
          {/* Linked POs */}
          {lc.linked_pos?.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
                <FileText size={14} /> Linked POs
              </h2>
              <div className="space-y-2">
                {lc.linked_pos.map((po: any) => (
                  <Link key={po.purchase_order_id} href={`/purchase-orders/${po.purchase_order_id}`}
                    className="block text-xs text-blue-600 hover:underline font-mono">{po.purchase_order_number}</Link>
                ))}
              </div>
            </div>
          )}

          {/* Financials */}
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <h2 className="text-sm font-semibold text-gray-700 mb-3 flex items-center gap-2">
              <DollarSign size={14} /> Financials
            </h2>
            <div className="space-y-2 text-xs">
              <div className="flex justify-between"><span className="text-gray-500">Carrier Cost</span><span className="font-medium">${lc.financials?.carrier_total?.toFixed(2)}</span></div>
              <div className="flex justify-between"><span className="text-gray-500">Client Charges</span><span className="font-medium">${lc.financials?.client_total?.toFixed(2)}</span></div>
              <div className="flex justify-between border-t pt-2">
                <span className="text-gray-500">Margin</span>
                <span className="font-bold text-green-600">
                  ${((lc.financials?.client_total || 0) - (lc.financials?.carrier_total || 0)).toFixed(2)}
                </span>
              </div>
            </div>
          </div>

          {/* Documents */}
          {lc.documents?.length > 0 && (
            <div className="bg-white rounded-xl border border-gray-200 p-4">
              <h2 className="text-sm font-semibold text-gray-700 mb-3">Documents</h2>
              <div className="space-y-1">
                {lc.documents.map((d: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <span className="font-mono text-gray-600">{d.type_code}</span>
                    <span className={`px-1.5 py-0.5 rounded text-xs ${d.status === 'generated' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'}`}>{d.status}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Exceptions */}
          {lc.exceptions?.length > 0 && (
            <div className="bg-red-50 border border-red-200 rounded-xl p-4">
              <h2 className="text-sm font-semibold text-red-700 mb-3 flex items-center gap-2">
                <AlertTriangle size={14} /> Exceptions ({lc.exceptions.length})
              </h2>
              <div className="space-y-2">
                {lc.exceptions.map((ex: any, i: number) => (
                  <p key={i} className="text-xs text-red-700">{ex.exception_type?.replace(/_/g,' ')}: {ex.description}</p>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
