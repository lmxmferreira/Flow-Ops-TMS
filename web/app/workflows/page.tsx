'use client'
import { useEffect, useState } from 'react'
import { Workflow, CheckCircle, XCircle, Clock, ArrowRight } from 'lucide-react'
import { apiFetch, statusColor } from '../../lib/api'

export default function WorkflowsPage() {
  const [definitions, setDefinitions] = useState<any[]>([])
  const [worklist, setWorklist] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<'worklist'|'definitions'>('worklist')
  const [actioning, setActioning] = useState<string|null>(null)

  function load() {
    setLoading(true)
    Promise.all([
      apiFetch('/platform/workflows/definitions').catch(() => []),
      apiFetch('/platform/workflows/worklist?status=in_progress').catch(() => ({ items: [] })),
    ]).then(([d, w]) => {
      setDefinitions(Array.isArray(d) ? d : [])
      setWorklist(w.items || [])
      setLoading(false)
    })
  }

  useEffect(() => { load() }, [])

  async function takeAction(instanceId: string, action: string) {
    setActioning(instanceId)
    try {
      await apiFetch(`/platform/workflows/${instanceId}/action`, {
        method: 'PATCH',
        body: JSON.stringify({ action, comments: `${action} via dashboard` }),
      })
      load()
    } catch {
      // ignore
    } finally {
      setActioning(null)
    }
  }

  const STEP_COLORS: Record<string, string> = {
    approved: 'bg-green-100 text-green-700',
    rejected: 'bg-red-100 text-red-700',
    in_progress: 'bg-blue-100 text-blue-700',
    pending: 'bg-yellow-100 text-yellow-700',
    escalated: 'bg-orange-100 text-orange-700',
    withdrawn: 'bg-gray-100 text-gray-500',
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Workflow className="text-violet-600" size={24} /> Workflow & Approvals
          </h1>
          <p className="text-sm text-gray-500 mt-1">Approval worklist, workflow definitions, and escalations</p>
        </div>
        {worklist.length > 0 && (
          <div className="flex items-center gap-2 bg-yellow-50 border border-yellow-200 px-3 py-2 rounded-lg">
            <Clock size={14} className="text-yellow-600" />
            <span className="text-sm font-medium text-yellow-700">{worklist.length} pending approval{worklist.length !== 1 ? 's' : ''}</span>
          </div>
        )}
      </div>

      <div className="flex gap-1 mb-4 bg-gray-100 p-1 rounded-lg w-fit">
        {(['worklist', 'definitions'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-1.5 text-sm font-medium rounded-md ${tab === t ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'}`}>
            {t === 'worklist' ? `Worklist (${worklist.length})` : 'Definitions'}
          </button>
        ))}
      </div>

      {tab === 'worklist' && (
        <div className="space-y-3">
          {loading ? <p className="text-gray-400 text-sm">Loading...</p>
          : worklist.length === 0 ? (
            <div className="bg-white rounded-xl border border-gray-200 p-10 text-center">
              <CheckCircle size={32} className="text-green-400 mx-auto mb-3" />
              <p className="text-gray-500 text-sm font-medium">No pending approvals</p>
              <p className="text-gray-400 text-xs mt-1">All workflows are up to date</p>
            </div>
          ) : worklist.map((item: any) => (
            <div key={item.instance_id} className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-sm font-semibold text-gray-900">{item.workflow_name}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${STEP_COLORS[item.status] || 'bg-gray-100 text-gray-600'}`}>
                      {item.status?.replace(/_/g,' ')}
                    </span>
                  </div>
                  <p className="text-xs text-gray-500">
                    {item.entity_type} · Step {item.current_step} · Requested by {item.requested_by}
                  </p>
                  {item.amount && (
                    <p className="text-xs text-gray-700 mt-1 font-medium">Amount: ${parseFloat(item.amount).toLocaleString('en-US', {minimumFractionDigits:2})}</p>
                  )}
                  {item.notes && <p className="text-xs text-gray-500 mt-1 italic">{item.notes}</p>}
                </div>
                <div className="flex gap-2 flex-shrink-0">
                  <button
                    disabled={actioning === item.instance_id}
                    onClick={() => takeAction(item.instance_id, 'approve')}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-green-600 text-white text-xs font-medium rounded-lg hover:bg-green-700 disabled:opacity-50 transition-colors">
                    <CheckCircle size={12} /> Approve
                  </button>
                  <button
                    disabled={actioning === item.instance_id}
                    onClick={() => takeAction(item.instance_id, 'reject')}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-red-100 text-red-700 text-xs font-medium rounded-lg hover:bg-red-200 disabled:opacity-50 transition-colors">
                    <XCircle size={12} /> Reject
                  </button>
                  <button
                    disabled={actioning === item.instance_id}
                    onClick={() => takeAction(item.instance_id, 'escalate')}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-orange-100 text-orange-700 text-xs font-medium rounded-lg hover:bg-orange-200 disabled:opacity-50 transition-colors">
                    Escalate
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'definitions' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {loading ? <p className="text-gray-400 text-sm">Loading...</p>
          : definitions.length === 0 ? <p className="text-gray-400 text-sm col-span-2">No workflow definitions</p>
          : definitions.map((d: any) => (
            <div key={d.workflow_id} className={`bg-white rounded-xl border p-5 ${d.is_active ? 'border-gray-200' : 'border-gray-100 opacity-60'}`}>
              <div className="flex items-center justify-between mb-2">
                <span className="font-semibold text-gray-900 text-sm">{d.workflow_name}</span>
                <div className="flex items-center gap-2">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-violet-100 text-violet-700 font-medium">{d.workflow_type}</span>
                  {!d.is_active && <span className="text-xs text-gray-400">Inactive</span>}
                </div>
              </div>
              <p className="font-mono text-xs text-gray-400 mb-3">{d.workflow_code}</p>
              <div className="text-xs text-gray-500 space-y-1">
                <div className="flex gap-1"><span className="text-gray-400">Trigger:</span> <span>{d.trigger_entity} → {d.trigger_event}</span></div>
                {(d.steps || []).length > 0 && (
                  <div className="flex items-center gap-1 flex-wrap mt-2">
                    {d.steps.map((step: any, i: number) => (
                      <span key={i} className="flex items-center gap-1">
                        <span className="bg-gray-100 text-gray-700 px-2 py-0.5 rounded font-medium text-xs">{step.role}</span>
                        {i < d.steps.length - 1 && <ArrowRight size={10} className="text-gray-400" />}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
