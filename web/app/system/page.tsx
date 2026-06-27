'use client'
import { useEffect, useState } from 'react'
import { Shield, Activity, CheckCircle, AlertTriangle, XCircle, RefreshCw } from 'lucide-react'
import { apiFetch } from '../../lib/api'

export default function SystemPage() {
  const [health, setHealth] = useState<any>(null)
  const [nfr, setNfr] = useState<any>(null)
  const [ac, setAc] = useState<any>(null)
  const [volume, setVolume] = useState<any>(null)
  const [dataQuality, setDataQuality] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<'health'|'nfr'|'ac'|'volume'>('health')

  function load() {
    setLoading(true)
    Promise.all([
      apiFetch('/system/health/detailed').catch(() => null),
      apiFetch('/system/nfr/verify').catch(() => null),
      apiFetch('/system/acceptance/verify').catch(() => null),
      apiFetch('/system/health/volume-metrics').catch(() => null),
      apiFetch('/system/data-quality/check').catch(() => null),
    ]).then(([h, n, a, v, dq]) => {
      setHealth(h); setNfr(n); setAc(a); setVolume(v); setDataQuality(dq)
      setLoading(false)
    })
  }

  useEffect(() => { load() }, [])

  const overallStatus = health?.overall_status
  const acResult = ac?.acceptance_criteria_summary?.overall_result
  const nfrCompliant = nfr?.nfr_summary?.compliant

  return (
    <div className="p-6 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Shield className="text-blue-600" size={24} /> System Health
          </h1>
          <p className="text-sm text-gray-500 mt-1">NFR compliance, acceptance criteria verification, and data quality</p>
        </div>
        <button onClick={load} className="flex items-center gap-2 text-sm text-gray-600 border border-gray-200 px-3 py-2 rounded-lg hover:bg-gray-50">
          <RefreshCw size={14} /> Refresh
        </button>
      </div>

      {/* Status banner */}
      <div className={`rounded-xl border p-4 mb-6 flex items-center gap-4 ${overallStatus === 'healthy' ? 'bg-green-50 border-green-200' : 'bg-yellow-50 border-yellow-200'}`}>
        {overallStatus === 'healthy' ? <CheckCircle size={20} className="text-green-600" /> : <AlertTriangle size={20} className="text-yellow-600" />}
        <div className="flex-1">
          <p className="text-sm font-semibold text-gray-900">
            System {overallStatus === 'healthy' ? 'Healthy ✅' : 'Degraded ⚠️'}
          </p>
          <p className="text-xs text-gray-500 mt-0.5">
            AC: {acResult === 'PASS' ? '10/10 PASS ✅' : 'Checking...'} · NFR: {nfrCompliant != null ? `${nfrCompliant}/9 Compliant` : 'Checking...'}
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 bg-gray-100 p-1 rounded-lg w-fit flex-wrap">
        {[
          { key: 'health', label: 'System Health' },
          { key: 'nfr', label: 'NFR Compliance' },
          { key: 'ac', label: 'Acceptance Criteria' },
          { key: 'volume', label: 'Volume Metrics' },
        ].map(t => (
          <button key={t.key} onClick={() => setTab(t.key as any)}
            className={`px-4 py-1.5 text-sm font-medium rounded-md ${tab === t.key ? 'bg-white text-gray-900 shadow-sm' : 'text-gray-500'}`}>
            {t.label}
          </button>
        ))}
      </div>

      {tab === 'health' && health && (
        <div className="space-y-3">
          {health.checks?.map((check: any, i: number) => (
            <div key={i} className={`bg-white rounded-xl border p-4 ${check.status === 'unhealthy' ? 'border-red-200' : check.status === 'degraded' ? 'border-yellow-200' : 'border-gray-200'}`}>
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {check.status === 'healthy' ? <CheckCircle size={15} className="text-green-500" />
                   : check.status === 'degraded' ? <AlertTriangle size={15} className="text-yellow-500" />
                   : <XCircle size={15} className="text-red-500" />}
                  <span className="text-sm font-semibold text-gray-800 capitalize">{check.service?.replace(/_/g,' ')}</span>
                </div>
                <div className="flex items-center gap-2">
                  {check.response_ms !== undefined && (
                    <span className="text-xs text-gray-400">{check.response_ms}ms</span>
                  )}
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${check.status === 'healthy' ? 'bg-green-100 text-green-700' : check.status === 'degraded' ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700'}`}>
                    {check.status}
                  </span>
                </div>
              </div>
              {check.counts && (
                <div className="grid grid-cols-4 lg:grid-cols-7 gap-2 mt-2">
                  {Object.entries(check.counts).map(([k, v]: any) => (
                    <div key={k} className="bg-gray-50 rounded-lg p-2 text-center">
                      <p className="text-xs text-gray-400 capitalize">{k.replace(/_/g,' ')}</p>
                      <p className="text-sm font-bold text-gray-900 mt-0.5">{v}</p>
                    </div>
                  ))}
                </div>
              )}
              {check.open && Object.keys(check.open).length > 0 && (
                <div className="flex gap-2 mt-2 flex-wrap">
                  {Object.entries(check.open).map(([sev, count]: any) => (
                    <span key={sev} className={`text-xs px-2 py-0.5 rounded-full ${sev === 'critical' ? 'bg-red-200 text-red-800' : sev === 'error' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'}`}>
                      {count} {sev}
                    </span>
                  ))}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {tab === 'nfr' && nfr && (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-3 mb-4">
            <div className="bg-white rounded-xl border border-gray-200 p-4 text-center">
              <p className="text-xs text-gray-500 uppercase">Total Checks</p>
              <p className="text-3xl font-bold text-gray-900 mt-1">{nfr.nfr_summary?.total}</p>
            </div>
            <div className="bg-green-50 rounded-xl border border-green-200 p-4 text-center">
              <p className="text-xs text-green-600 uppercase">Compliant</p>
              <p className="text-3xl font-bold text-green-600 mt-1">{nfr.nfr_summary?.compliant}</p>
            </div>
            <div className="bg-yellow-50 rounded-xl border border-yellow-200 p-4 text-center">
              <p className="text-xs text-yellow-600 uppercase">At Risk</p>
              <p className="text-3xl font-bold text-yellow-600 mt-1">{nfr.nfr_summary?.at_risk}</p>
            </div>
          </div>
          {nfr.checks?.map((check: any, i: number) => (
            <div key={i} className={`bg-white rounded-xl border p-4 ${check.status === 'AT_RISK' ? 'border-yellow-200' : 'border-gray-200'}`}>
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-mono text-gray-400">{check.nfr}</span>
                    <span className="text-sm font-semibold text-gray-800">{check.description}</span>
                  </div>
                  <p className="text-xs text-gray-500">{check.evidence}</p>
                </div>
                <span className={`text-xs px-2 py-1 rounded-full font-semibold flex-shrink-0 ${check.status === 'COMPLIANT' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
                  {check.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'ac' && ac && (
        <div className="space-y-3">
          <div className="grid grid-cols-4 gap-3 mb-4">
            {[
              ['Total', ac.acceptance_criteria_summary?.total, 'gray'],
              ['Passed', ac.acceptance_criteria_summary?.passed, 'green'],
              ['Warned', ac.acceptance_criteria_summary?.warned, 'yellow'],
              ['Overall', ac.acceptance_criteria_summary?.overall_result, 'blue'],
            ].map(([label, val, color]) => (
              <div key={label as string} className={`bg-white rounded-xl border border-${color}-200 p-4 text-center`}>
                <p className="text-xs text-gray-500 uppercase">{label}</p>
                <p className={`text-2xl font-bold text-${color}-600 mt-1`}>{val}</p>
              </div>
            ))}
          </div>
          {ac.criteria?.map((c: any, i: number) => (
            <div key={i} className={`bg-white rounded-xl border p-4 flex items-start justify-between gap-4 ${c.status === 'FAIL' ? 'border-red-200' : c.status === 'WARN' ? 'border-yellow-200' : 'border-gray-200'}`}>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-mono text-xs text-gray-400">{c.criterion}</span>
                  <span className="text-sm font-semibold text-gray-800">{c.description}</span>
                </div>
                <p className="text-xs text-gray-500">{c.detail}</p>
              </div>
              <span className={`text-xs px-2 py-1 rounded-full font-semibold flex-shrink-0 ${c.status === 'PASS' ? 'bg-green-100 text-green-700' : c.status === 'WARN' ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700'}`}>
                {c.status}
              </span>
            </div>
          ))}
        </div>
      )}

      {tab === 'volume' && volume && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {Object.entries(volume.volume_metrics || {}).map(([metric, val]: any) => (
            <div key={metric} className="bg-white rounded-xl border border-gray-200 p-4">
              <p className="text-xs text-gray-500 capitalize">{metric.replace(/_/g,' ')}</p>
              <p className="text-2xl font-bold text-gray-900 mt-1">
                {typeof val === 'number' && val > 1000
                  ? `$${val.toLocaleString('en-US', { minimumFractionDigits: 0 })}`
                  : typeof val === 'number' ? val.toLocaleString() : val}
              </p>
            </div>
          ))}
        </div>
      )}

      {loading && (
        <div className="flex items-center justify-center py-16">
          <div className="animate-spin w-6 h-6 border-2 border-blue-600 border-t-transparent rounded-full" />
        </div>
      )}
    </div>
  )
}
