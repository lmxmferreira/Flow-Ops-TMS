'use client'
import { useEffect, useState } from 'react'
import { Shield, Search, Lock } from 'lucide-react'
import { apiFetch, statusColor } from '../../lib/api'

export default function SecurityPage() {
  const [roles, setRoles] = useState<any[]>([])
  const [auditLog, setAuditLog] = useState<any[]>([])
  const [retentionPolicies, setRetentionPolicies] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<'roles'|'audit'|'retention'>('roles')
  const [search, setSearch] = useState('')

  useEffect(() => {
    Promise.all([
      apiFetch('/platform/security/roles').catch(() => []),
      apiFetch('/platform/security/audit-log?limit=50').catch(() => []),
      apiFetch('/platform/security/retention-policies').catch(() => []),
    ]).then(([r, a, p]) => {
      setRoles(Array.isArray(r) ? r : [])
      setAuditLog(Array.isArray(a) ? a : [])
      setRetentionPolicies(Array.isArray(p) ? p : [])
      setLoading(false)
    })
  }, [])

  const ROLE_TYPE_COLORS: Record<string, string> = {
    internal: 'bg-blue-100 text-blue-700',
    carrier: 'bg-green-100 text-green-700',
    customer: 'bg-purple-100 text-purple-700',
    supplier: 'bg-orange-100 text-orange-700',
    auditor: 'bg-gray-100 text-gray-700',
    admin: 'bg-red-100 text-red-700',
  }

  const filteredLog = auditLog.filter(l =>
    !search ||
    l.user_id?.toLowerCase().includes(search.toLowerCase()) ||
    l.action_type?.toLowerCase().includes(search.toLowerCase()) ||
    l.entity_type?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <Shield className="text-red-600" size={24} /> Security, Roles & Audit
        </h1>
        <p className="text-sm text-gray-500 mt-1">Role-based access control, immutable audit trail, and data retention policies</p>
      </div>

      <div className="flex gap-1 mb-4 bg-gray-100 p-1 rounded-lg w-fit">
        {(['roles', 'audit', 'retention'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-1.5 text-sm font-medium rounded-md ${tab === t ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'}`}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
            {t === 'audit' ? ` (${auditLog.length})` : ''}
          </button>
        ))}
      </div>

      {tab === 'roles' && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {loading ? <p className="text-gray-400 text-sm">Loading...</p>
          : roles.length === 0 ? <p className="text-gray-400 text-sm col-span-3">No roles configured</p>
          : roles.map((r: any) => (
            <div key={r.role_id} className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <Lock size={14} className="text-gray-400" />
                  <span className="font-semibold text-gray-900 text-sm">{r.role_name}</span>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${ROLE_TYPE_COLORS[r.role_type] || 'bg-gray-100 text-gray-600'}`}>
                  {r.role_type}
                </span>
              </div>
              <p className="font-mono text-xs text-gray-500 mb-3">{r.role_code}</p>
              {r.permissions && Object.keys(r.permissions).length > 0 ? (
                <div className="space-y-1">
                  {Object.entries(r.permissions).slice(0, 4).map(([resource, actions]: any) => (
                    <div key={resource} className="flex items-center justify-between text-xs">
                      <span className="text-gray-500 capitalize">{resource}</span>
                      <span className="text-gray-600 font-medium">{Array.isArray(actions) ? actions.join(', ') : actions}</span>
                    </div>
                  ))}
                  {Object.keys(r.permissions).length > 4 && (
                    <p className="text-xs text-gray-400">+{Object.keys(r.permissions).length - 4} more</p>
                  )}
                </div>
              ) : (
                <p className="text-xs text-gray-400">No explicit permissions configured</p>
              )}
            </div>
          ))}
        </div>
      )}

      {tab === 'audit' && (
        <>
          <div className="relative max-w-xs mb-4">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input value={search} onChange={e => setSearch(e.target.value)}
              placeholder="Search user, action, entity..."
              className="pl-9 pr-3 py-2 text-sm border border-gray-200 rounded-lg w-full focus:outline-none focus:ring-2 focus:ring-blue-500" />
          </div>
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr>{['User','Action','Entity Type','Entity ID','Reason','Timestamp'].map(h =>
                  <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
                )}</tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {loading ? <tr><td colSpan={6} className="text-center py-12 text-gray-400">Loading...</td></tr>
                : filteredLog.length === 0 ? <tr><td colSpan={6} className="text-center py-12 text-gray-400">No audit events found</td></tr>
                : filteredLog.map((l: any) => (
                  <tr key={l.log_id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-700 text-xs">{l.user_id}</td>
                    <td className="px-4 py-3"><span className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded font-mono">{l.action_type}</span></td>
                    <td className="px-4 py-3 text-gray-500 text-xs capitalize">{l.entity_type || '—'}</td>
                    <td className="px-4 py-3 font-mono text-xs text-gray-400">{l.entity_id?.slice(0,12) || '—'}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{l.reason_code || '—'}</td>
                    <td className="px-4 py-3 text-gray-500 text-xs">{l.performed_at ? new Date(l.performed_at).toLocaleString() : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {tab === 'retention' && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>{['Policy Name','Entity Type','Retention (days)','Archive After','Legal Hold','Purge Allowed'].map(h =>
                <th key={h} className="text-left px-4 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wide">{h}</th>
              )}</tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {retentionPolicies.length === 0 ? <tr><td colSpan={6} className="text-center py-12 text-gray-400">No retention policies</td></tr>
              : retentionPolicies.map((p: any) => (
                <tr key={p.policy_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-medium text-gray-900">{p.policy_name}</td>
                  <td className="px-4 py-3 text-gray-600 capitalize">{p.entity_type}</td>
                  <td className="px-4 py-3 text-gray-700">{p.retention_days} days ({Math.round(p.retention_days/365)}yr)</td>
                  <td className="px-4 py-3 text-gray-500">{p.archive_after_days ? `${p.archive_after_days} days` : '—'}</td>
                  <td className="px-4 py-3">{p.legal_hold ? <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded-full">Yes</span> : <span className="text-xs text-gray-400">No</span>}</td>
                  <td className="px-4 py-3">{p.purge_allowed ? <span className="text-xs bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full">Allowed</span> : <span className="text-xs text-gray-400">No</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
