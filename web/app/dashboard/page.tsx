'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Truck, Package, Receipt, AlertTriangle, DollarSign, TrendingUp, Clock, CheckCircle, ArrowRight, Activity, BarChart3 } from 'lucide-react'
import { apiFetch, fmtCurrency } from '../../lib/api'

export default function DashboardPage() {
  const [ops, setOps] = useState<any>(null)
  const [financial, setFinancial] = useState<any>(null)
  const [health, setHealth] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.all([
      apiFetch('/platform/reports/operational').catch(() => null),
      apiFetch('/platform/reports/financial').catch(() => null),
      apiFetch('/system/health/detailed').catch(() => null),
    ]).then(([o, f, h]) => {
      setOps(o); setFinancial(f); setHealth(h)
      setLoading(false)
    })
  }, [])

  const statusColors: Record<string, string> = {
    planned: 'bg-gray-100 text-gray-600', dispatched: 'bg-blue-100 text-blue-700',
    in_transit: 'bg-indigo-100 text-indigo-700', delivered: 'bg-green-100 text-green-700',
    exception: 'bg-red-100 text-red-700', costed: 'bg-purple-100 text-purple-700',
    closed: 'bg-gray-50 text-gray-400',
  }

  if (loading) return (
    <div className="flex items-center justify-center h-full">
      <div className="text-center">
        <div className="animate-spin w-8 h-8 border-2 border-blue-600 border-t-transparent rounded-full mx-auto mb-3" />
        <p className="text-sm text-gray-500">Loading dashboard...</p>
      </div>
    </div>
  )

  const shipmentStatuses = ops?.shipment_status || {}
  const totalShipments = Object.values(shipmentStatuses).reduce((a: any, b: any) => a + b, 0) as number
  const openExceptions = ops?.open_exceptions || {}
  const totalExceptions = Object.values(openExceptions).reduce((a: any, b: any) => a + b, 0) as number
  const revenue = financial?.revenue || {}
  const healthStatus = health?.overall_status || 'unknown'

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-0.5">Flow Ops TMS — {new Date().toLocaleDateString('en-US', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}</p>
        </div>
        <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium ${healthStatus === 'healthy' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
          <Activity size={12} />
          System {healthStatus}
        </div>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Active Shipments</p>
            <div className="w-8 h-8 bg-blue-50 rounded-lg flex items-center justify-center">
              <Truck size={14} className="text-blue-600" />
            </div>
          </div>
          <p className="text-3xl font-bold text-gray-900">{totalShipments}</p>
          <p className="text-xs text-gray-400 mt-1">Across all stages</p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Total Billed</p>
            <div className="w-8 h-8 bg-green-50 rounded-lg flex items-center justify-center">
              <DollarSign size={14} className="text-green-600" />
            </div>
          </div>
          <p className="text-3xl font-bold text-gray-900">{fmtCurrency(revenue.total_billed)}</p>
          <p className="text-xs text-gray-400 mt-1">{fmtCurrency(revenue.total_outstanding)} outstanding</p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Open Exceptions</p>
            <div className="w-8 h-8 bg-red-50 rounded-lg flex items-center justify-center">
              <AlertTriangle size={14} className="text-red-600" />
            </div>
          </div>
          <p className="text-3xl font-bold text-gray-900">{totalExceptions}</p>
          <p className="text-xs text-red-400 mt-1">{openExceptions.error || 0} errors, {openExceptions.critical || 0} critical</p>
        </div>

        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide">Margin</p>
            <div className="w-8 h-8 bg-purple-50 rounded-lg flex items-center justify-center">
              <TrendingUp size={14} className="text-purple-600" />
            </div>
          </div>
          <p className="text-3xl font-bold text-gray-900">{financial?.margin?.overall_margin_pct?.toFixed(1) || '—'}%</p>
          <p className="text-xs text-gray-400 mt-1">{fmtCurrency(financial?.margin?.total_markup)} total markup</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        {/* Shipment Status */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-800">Shipments by Stage</h3>
            <Link href="/shipments" className="text-xs text-blue-600 hover:underline flex items-center gap-1">View all <ArrowRight size={10} /></Link>
          </div>
          <div className="space-y-2">
            {Object.entries(shipmentStatuses).map(([stage, count]: any) => (
              <div key={stage} className="flex items-center justify-between">
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${statusColors[stage] || 'bg-gray-100 text-gray-600'}`}>
                  {stage.replace(/_/g, ' ')}
                </span>
                <span className="text-sm font-semibold text-gray-700">{count}</span>
              </div>
            ))}
            {Object.keys(shipmentStatuses).length === 0 && (
              <p className="text-xs text-gray-400">No shipments yet</p>
            )}
          </div>
        </div>

        {/* Tender Status */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-800">Tender Status</h3>
            <Link href="/carriers" className="text-xs text-blue-600 hover:underline flex items-center gap-1">View all <ArrowRight size={10} /></Link>
          </div>
          <div className="space-y-2">
            {Object.entries(ops?.tender_status || {}).map(([status, count]: any) => (
              <div key={status} className="flex items-center justify-between">
                <span className="text-sm text-gray-600">{status}</span>
                <span className="text-sm font-semibold text-gray-700">{count}</span>
              </div>
            ))}
            {Object.keys(ops?.tender_status || {}).length === 0 && (
              <p className="text-xs text-gray-400">No tenders yet</p>
            )}
          </div>
        </div>

        {/* Invoice Aging */}
        <div className="bg-white rounded-xl border border-gray-200 p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-800">Invoice Aging</h3>
            <Link href="/carrier-invoices" className="text-xs text-blue-600 hover:underline flex items-center gap-1">View all <ArrowRight size={10} /></Link>
          </div>
          <div className="space-y-2">
            {Object.entries(financial?.invoice_aging || {}).map(([bucket, data]: any) => (
              <div key={bucket} className="flex items-center justify-between">
                <span className="text-xs text-gray-500">{bucket.replace(/_/g, ' ')}</span>
                <div className="text-right">
                  <span className="text-sm font-semibold text-gray-700">{data.count}</span>
                  <span className="text-xs text-gray-400 ml-1">({fmtCurrency(data.total)})</span>
                </div>
              </div>
            ))}
            {Object.keys(financial?.invoice_aging || {}).length === 0 && (
              <p className="text-xs text-gray-400">No aging data</p>
            )}
          </div>
        </div>
      </div>

      {/* Quick Links */}
      <div className="bg-white rounded-xl border border-gray-200 p-5">
        <h3 className="text-sm font-semibold text-gray-800 mb-4">Quick Actions</h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
          {[
            { label: 'New Shipment', href: '/shipments', icon: Truck, color: 'bg-blue-50 text-blue-600' },
            { label: 'Purchase Orders', href: '/purchase-orders', icon: Package, color: 'bg-purple-50 text-purple-600' },
            { label: 'Carrier Invoices', href: '/carrier-invoices', icon: Receipt, color: 'bg-green-50 text-green-600' },
            { label: 'Exceptions', href: '/exceptions', icon: AlertTriangle, color: 'bg-red-50 text-red-600' },
            { label: 'Reports', href: '/reports', icon: BarChart3, color: 'bg-orange-50 text-orange-600' },
            { label: 'E2E Trace', href: '/e2e', icon: Activity, color: 'bg-indigo-50 text-indigo-600' },
          ].map(q => (
            <Link key={q.href} href={q.href}
              className="flex flex-col items-center gap-2 p-3 rounded-lg hover:bg-gray-50 transition-colors border border-gray-100 group">
              <div className={`w-9 h-9 rounded-lg flex items-center justify-center ${q.color}`}>
                <q.icon size={16} />
              </div>
              <span className="text-xs font-medium text-gray-600 text-center group-hover:text-gray-900">{q.label}</span>
            </Link>
          ))}
        </div>
      </div>
    </div>
  )
}
