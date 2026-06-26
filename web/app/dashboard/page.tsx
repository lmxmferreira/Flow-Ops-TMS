'use client'
import Link from 'next/link'
import {
  Package, FileText, Truck, Building2,
  ArrowRight, Activity, GitBranch, DollarSign
} from 'lucide-react'

const QUICK_LINKS = [
  {
    href: '/shipments',
    icon: Package,
    color: 'bg-blue-50 text-blue-600 border-blue-100',
    btnColor: 'text-blue-600 hover:text-blue-800',
    title: 'Shipments',
    description: 'View and track all shipments with status filtering and carrier details.',
  },
  {
    href: '/purchase-orders',
    icon: FileText,
    color: 'bg-indigo-50 text-indigo-600 border-indigo-100',
    btnColor: 'text-indigo-600 hover:text-indigo-800',
    title: 'Purchase Orders',
    description: 'Manage PO headers, lines, and release status across all suppliers.',
  },
  {
    href: '/order-releases',
    icon: Activity,
    color: 'bg-purple-50 text-purple-600 border-purple-100',
    btnColor: 'text-purple-600 hover:text-purple-800',
    title: 'Order Releases',
    description: 'View transportation order releases with lines, events, and linked shipments.',
  },
  {
    href: '/carriers',
    icon: Truck,
    color: 'bg-orange-50 text-orange-600 border-orange-100',
    btnColor: 'text-orange-600 hover:text-orange-800',
    title: 'Carriers',
    description: 'Manage carrier master data, services, compliance, and scorecards.',
  },
  {
    href: '/settings/organizations',
    icon: Building2,
    color: 'bg-teal-50 text-teal-600 border-teal-100',
    btnColor: 'text-teal-600 hover:text-teal-800',
    title: 'Organizations',
    description: 'Manage legal entities, business units, departments, facilities, and warehouses.',
  },
  {
    href: '/settings/rating',
    icon: DollarSign,
    color: 'bg-emerald-50 text-emerald-600 border-emerald-100',
    btnColor: 'text-emerald-600 hover:text-emerald-800',
    title: 'Rates',
    description: 'Manage carrier rate cards, lanes, fuel surcharges, and accessorial charges.',
  },
  {
    href: '/settings/organizations',
    icon: GitBranch,
    color: 'bg-green-50 text-green-600 border-green-100',
    btnColor: 'text-green-600 hover:text-green-800',
    title: 'Org Hierarchy',
    description: 'View and manage the full organization hierarchy tree across all levels.',
  },
]

export default function DashboardPage() {
  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b px-6 py-5">
        <h1 className="text-xl font-semibold text-gray-800">Dashboard</h1>
        <p className="text-sm text-gray-400 mt-0.5">Flow Ops Transportation Management System</p>
      </div>

      <div className="px-6 py-6">
        {/* Quick links */}
        <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">Quick Access</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {QUICK_LINKS.map(({ href, icon: Icon, color, btnColor, title, description }) => (
            <div key={href + title} className={`bg-white rounded-lg border p-5 hover:shadow-sm transition-shadow`}>
              <div className="flex items-start gap-4">
                <div className={`p-2.5 rounded-lg border ${color} shrink-0`}>
                  <Icon size={20} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-gray-800 mb-1">{title}</p>
                  <p className="text-xs text-gray-400 leading-relaxed mb-3">{description}</p>
                  <Link href={href}
                    className={`flex items-center gap-1 text-xs font-medium ${btnColor} transition-colors`}>
                    Open <ArrowRight size={12} />
                  </Link>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Status */}
        <div className="mt-8">
          <h2 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">System</h2>
          <div className="bg-white rounded-lg border p-4 flex items-center gap-3">
            <div className="w-2 h-2 rounded-full bg-green-500 shrink-0"></div>
            <span className="text-sm text-gray-600">All systems operational</span>
            <span className="text-xs text-gray-400 ml-auto">TMS API · PostgreSQL · Next.js</span>
          </div>
        </div>
      </div>
    </div>
  )
}
