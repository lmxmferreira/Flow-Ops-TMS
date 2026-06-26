'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  Package, Truck, Navigation, BarChart2, Settings,
  LogOut, Building2, Zap, GitMerge, Hash, FileText, Activity, Globe, DollarSign, ShieldCheck, DollarSign, ShieldCheck
} from 'lucide-react'

const NAV = [
  { href: '/dashboard',      label: 'Dashboard',      icon: BarChart2  },
  { href: '/shipments',      label: 'Shipments',      icon: Package    },
  { href: '/purchase-orders',label: 'Purchase Orders',icon: FileText   },
  { href: '/order-releases', label: 'Order Releases', icon: Activity   },
  { href: '/carriers',       label: 'Carriers',       icon: Truck      },
  { href: '/dispatches',     label: 'Dispatches',     icon: Navigation },
  { href: '/settings/rating', label: 'Rates',          icon: DollarSign },
]

const SETTINGS_NAV = [
  { href: '/settings/organizations', label: 'Organizations', icon: Building2 },
  { href: '/settings/workflows',     label: 'Workflows',     icon: Zap       },
  { href: '/settings/status-models', label: 'Status Models', icon: GitMerge  },
  { href: '/settings/numbering',     label: 'Numbering',     icon: Hash      },
  { href: '/settings/global',        label: 'Global Settings',icon: Globe     },
  { href: '/settings/validation-rules', label: 'Validation Rules', icon: ShieldCheck },
]

export default function NavSidebar() {
  const path = usePathname()
  const logout = () => {
    localStorage.removeItem('tms_token')
    window.location.href = '/login'
  }

  return (
    <aside className="w-56 bg-gray-900 text-gray-300 flex flex-col shrink-0">
      <div className="px-5 py-5 border-b border-gray-700">
        <span className="text-white font-bold text-lg tracking-tight">Flow Ops</span>
        <span className="ml-2 text-xs bg-blue-600 text-white px-1.5 py-0.5 rounded font-medium">TMS</span>
      </div>
      <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
        {NAV.map(({ href, label, icon: Icon }) => (
          <Link key={href} href={href}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              path.startsWith(href) ? 'bg-blue-600 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'
            }`}>
            <Icon size={16} />{label}
          </Link>
        ))}
        <div className="pt-4 pb-1">
          <p className="px-3 text-xs font-semibold text-gray-600 uppercase tracking-wider">Settings</p>
        </div>
        {SETTINGS_NAV.map(({ href, label, icon: Icon }) => (
          <Link key={href} href={href}
            className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              path.startsWith(href) ? 'bg-blue-600 text-white' : 'text-gray-400 hover:bg-gray-800 hover:text-white'
            }`}>
            <Icon size={16} />{label}
          </Link>
        ))}
      </nav>
      <div className="px-3 py-4 border-t border-gray-700 space-y-1">
        <Link href="/settings" className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-400 hover:bg-gray-800 hover:text-white transition-colors">
          <Settings size={16} />Settings
        </Link>
        <button onClick={logout} className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-gray-400 hover:bg-gray-800 hover:text-white transition-colors">
          <LogOut size={16} />Sign out
        </button>
      </div>
    </aside>
  )
}
