'use client'
import { useEffect, useState } from 'react'
import { FileText, Search } from 'lucide-react'
import { apiFetch, fmtDate, statusColor } from '../../lib/api'

export default function DocumentsPage() {
  const [docs, setDocs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')

  useEffect(() => {
    apiFetch('/documents/?limit=100')
      .then(d => { setDocs(d.documents || (Array.isArray(d) ? d : [])); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const filtered = docs.filter(d => !search || d.document_number?.toLowerCase().includes(search.toLowerCase()) || d.document_type?.toLowerCase().includes(search.toLowerCase()))

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2"><FileText className="text-blue-600" size={24}/> Document Management</h1>
        <p className="text-sm text-gray-500 mt-1">BOLs, PODs, CMRs, invoices, and all shipment documents</p>
      </div>
      <div className="relative max-w-xs mb-4">
        <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"/>
        <input value={search} onChange={e => setSearch(e.target.value)} placeholder="Search documents..." className="pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-blue-500"/>
      </div>
      <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>{['Document #','Type','Shipment','Created','Status',''].map(h => <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>)}</tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? <tr><td colSpan={6} className="text-center py-12 text-gray-400">Loading...</td></tr>
            : filtered.length === 0 ? <tr><td colSpan={6} className="text-center py-12 text-gray-400">No documents found</td></tr>
            : filtered.map((d: any) => (
              <tr key={d.document_id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-mono text-xs text-blue-700">{d.document_number || '—'}</td>
                <td className="px-4 py-3 text-gray-600 uppercase text-xs">{d.document_type || '—'}</td>
                <td className="px-4 py-3 font-mono text-xs text-gray-500">{d.shipment_id?.slice(0,12) || '—'}</td>
                <td className="px-4 py-3 text-gray-500">{fmtDate(d.created_at)}</td>
                <td className="px-4 py-3"><span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColor(d.document_status || 'generated')}`}>{d.document_status || 'generated'}</span></td>
                <td className="px-4 py-3"><span className="text-blue-600 text-xs cursor-pointer hover:underline">Download</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
