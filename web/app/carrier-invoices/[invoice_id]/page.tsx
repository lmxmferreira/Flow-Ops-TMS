'use client'
import { useEffect, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { Receipt, ArrowLeft, CheckCircle, AlertTriangle, PauseCircle, RefreshCw } from 'lucide-react'

const API = process.env.NEXT_PUBLIC_API_URL

function statusBadge(status: string) {
  const map: Record<string, string> = {
    received: 'bg-gray-100 text-gray-700',
    matched: 'bg-green-100 text-green-700',
    exception: 'bg-red-100 text-red-700',
    approved: 'bg-blue-100 text-blue-700',
    paid: 'bg-emerald-100 text-emerald-700',
    disputed: 'bg-orange-100 text-orange-700',
  }
  return map[status] || 'bg-gray-100 text-gray-600'
}

export default function CarrierInvoiceDetailPage() {
  const { invoice_id } = useParams()
  const router = useRouter()
  const [inv, setInv] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState('')

  const token = () => localStorage.getItem('tms_token')

  useEffect(() => {
    fetch(`${API}/carrier-invoices/${invoice_id}`, { headers: { Authorization: `Bearer ${token()}` } })
      .then(r => r.json()).then(d => { setInv(d); setLoading(false) })
  }, [invoice_id])

  const doAction = async (action: string, body: any = {}) => {
    setActionLoading(action)
    const url = action === 'match'
      ? `${API}/carrier-invoices/${invoice_id}/match`
      : action === 'hold'
      ? `${API}/carrier-invoices/${invoice_id}/hold`
      : `${API}/carrier-invoices/${invoice_id}/status`
    const method = 'POST'
    await fetch(url, {
      method: action === 'status' ? 'PATCH' : 'POST',
      headers: { Authorization: `Bearer ${token()}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const updated = await fetch(`${API}/carrier-invoices/${invoice_id}`, { headers: { Authorization: `Bearer ${token()}` } }).then(r => r.json())
    setInv(updated)
    setActionLoading('')
  }

  if (loading) return <div className="p-8 text-gray-400">Loading...</div>
  if (!inv) return <div className="p-8 text-gray-400">Invoice not found.</div>

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <Link href="/carrier-invoices" className="text-gray-400 hover:text-gray-700"><ArrowLeft size={20} /></Link>
        <h1 className="text-xl font-bold text-gray-900 flex items-center gap-2">
          <Receipt size={20} className="text-blue-600" />
          {inv.carrier_invoice_number}
        </h1>
        <span className={`px-2 py-1 rounded-full text-xs font-medium capitalize ${statusBadge(inv.status)}`}>
          {inv.status?.replace(/_/g,' ')}
        </span>
        {inv.on_hold && <span className="px-2 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-700">On Hold</span>}
      </div>

      {/* Actions */}
      <div className="flex gap-2 mb-6">
        {inv.status === 'received' && (
          <button onClick={() => doAction('match', { shipment_id: inv.shipment_id, auto_match_lines: true, tolerance_pct: 5 })}
            className="flex items-center gap-2 px-3 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700">
            <RefreshCw size={14} /> Match to Shipment
          </button>
        )}
        {inv.status === 'matched' && (
          <button onClick={() => doAction('status', { status: 'approved' })}
            className="flex items-center gap-2 px-3 py-2 bg-green-600 text-white text-sm rounded-lg hover:bg-green-700">
            <CheckCircle size={14} /> Approve
          </button>
        )}
        {inv.status === 'approved' && (
          <button onClick={() => doAction('status', { status: 'paid', paid_amount: inv.invoice_total_amount })}
            className="flex items-center gap-2 px-3 py-2 bg-emerald-600 text-white text-sm rounded-lg hover:bg-emerald-700">
            Mark as Paid
          </button>
        )}
        <button onClick={() => doAction('hold', { on_hold: !inv.on_hold, reason: 'Manual hold' })}
          className="flex items-center gap-2 px-3 py-2 bg-yellow-500 text-white text-sm rounded-lg hover:bg-yellow-600">
          <PauseCircle size={14} /> {inv.on_hold ? 'Release Hold' : 'Place Hold'}
        </button>
        {['received','matched','exception'].includes(inv.status) && (
          <button onClick={() => doAction('status', { status: 'disputed' })}
            className="flex items-center gap-2 px-3 py-2 bg-orange-500 text-white text-sm rounded-lg hover:bg-orange-600">
            <AlertTriangle size={14} /> Dispute
          </button>
        )}
      </div>

      <div className="grid grid-cols-3 gap-6 mb-6">
        {/* Header info */}
        <div className="col-span-2 bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Invoice Details</h2>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            {[
              ['Carrier', inv.carrier_name],
              ['SCAC', inv.scac],
              ['Invoice Date', inv.invoice_date],
              ['Due Date', inv.due_date || '—'],
              ['Currency', 'USD'],
              ['Source', inv.source_channel],
              ['Invoice Type', inv.invoice_type],
              ['Shipment', inv.shipment_id ? inv.shipment_id.slice(0,8)+'...' : '—'],
            ].map(([k,v]) => (
              <div key={k}><dt className="text-gray-500">{k}</dt><dd className="font-medium text-gray-900 mt-0.5">{v}</dd></div>
            ))}
          </dl>
        </div>

        {/* Financials */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-4">Financials</h2>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between"><span className="text-gray-500">Invoice Total</span><span className="font-bold text-gray-900">${parseFloat(inv.invoice_total_amount||0).toLocaleString('en-US',{minimumFractionDigits:2})}</span></div>
            <div className="flex justify-between"><span className="text-gray-500">Tax</span><span className="font-medium">${parseFloat(inv.tax_total_amount||0).toLocaleString('en-US',{minimumFractionDigits:2})}</span></div>
            {inv.matched_amount && <div className="flex justify-between"><span className="text-gray-500">Matched Amount</span><span className="font-medium">${parseFloat(inv.matched_amount).toLocaleString('en-US',{minimumFractionDigits:2})}</span></div>}
            {inv.variance_amount != null && (
              <div className="flex justify-between border-t pt-3">
                <span className="text-gray-500">Variance</span>
                <span className={`font-bold ${Math.abs(inv.variance_amount) > 0 ? 'text-red-600' : 'text-green-600'}`}>
                  ${parseFloat(inv.variance_amount||0).toFixed(2)} ({parseFloat(inv.variance_pct||0).toFixed(1)}%)
                </span>
              </div>
            )}
            {inv.paid_amount && <div className="flex justify-between text-green-700"><span>Paid</span><span className="font-bold">${parseFloat(inv.paid_amount).toFixed(2)}</span></div>}
          </div>
        </div>
      </div>

      {/* Lines */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden mb-6">
        <div className="px-5 py-3 border-b border-gray-100">
          <h2 className="text-sm font-semibold text-gray-700">Invoice Lines ({inv.lines?.length || 0})</h2>
        </div>
        <table className="w-full text-sm">
          <thead className="bg-gray-50">
            <tr>
              {['#','Charge Code','Description','Qty','Rate','Amount','Tax','Match Status'].map(h => (
                <th key={h} className="text-left px-4 py-2 text-xs text-gray-500 font-semibold">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {(inv.lines || []).map((line: any) => (
              <tr key={line.carrier_invoice_line_id} className="hover:bg-gray-50">
                <td className="px-4 py-2 text-gray-500">{line.line_number}</td>
                <td className="px-4 py-2 font-mono text-xs font-medium">{line.charge_code || '—'}</td>
                <td className="px-4 py-2 text-gray-700">{line.description}</td>
                <td className="px-4 py-2">{line.quantity}</td>
                <td className="px-4 py-2">${parseFloat(line.rate_amount||0).toFixed(2)}</td>
                <td className="px-4 py-2 font-medium">${parseFloat(line.line_amount||0).toFixed(2)}</td>
                <td className="px-4 py-2 text-gray-500">${parseFloat(line.tax_amount||0).toFixed(2)}</td>
                <td className="px-4 py-2">
                  <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                    line.match_status === 'matched' ? 'bg-green-100 text-green-700' :
                    line.match_status === 'variance' ? 'bg-red-100 text-red-700' :
                    'bg-gray-100 text-gray-600'}`}>
                    {line.match_status || 'unmatched'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Audit trail */}
      {inv.audit_trail?.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <h2 className="text-sm font-semibold text-gray-700 mb-3">Audit Trail</h2>
          <div className="space-y-2">
            {inv.audit_trail.map((a: any) => (
              <div key={a.audit_id} className="flex items-start gap-3 text-sm">
                <div className="w-2 h-2 rounded-full bg-blue-400 mt-1.5 shrink-0" />
                <div>
                  <span className="font-medium text-gray-700 capitalize">{a.event_type?.replace(/_/g,' ')}</span>
                  {a.from_status && <span className="text-gray-400 ml-2">{a.from_status} → {a.to_status}</span>}
                  {a.notes && <span className="text-gray-500 ml-2">— {a.notes}</span>}
                  <span className="text-gray-400 ml-2 text-xs">{new Date(a.performed_at).toLocaleString()}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
