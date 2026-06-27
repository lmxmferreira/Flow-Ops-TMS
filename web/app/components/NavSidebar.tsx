'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import {
  LayoutDashboard, Package, Navigation, FileText, Activity,
  Truck, Receipt, Layers, DollarSign, Database, GitBranch,
  Building2, Zap, GitMerge, Hash, Globe, ShieldCheck,
  LogOut, Settings, ChevronRight
} from 'lucide-react'

const NAV_ITEMS = [
  { href: '/dashboard',        label: 'Dashboard',        icon: LayoutDashboard },
  { href: '/shipments',        label: 'Shipments',        icon: Package         },
  { href: '/execution',        label: 'Execution',        icon: Navigation      },
  { href: '/purchase-orders',  label: 'Purchase Orders',  icon: FileText        },
  { href: '/order-releases',   label: 'Order Releases',   icon: Activity        },
  { href: '/carriers',         label: 'Carriers',         icon: Truck           },
  { href: '/carrier-invoices', label: 'Carrier Invoices', icon: Receipt         },
  { href: '/allocation',       label: 'Cost Allocation',  icon: Layers          },
  { href: '/settings/rating',  label: 'Rates',            icon: DollarSign      },
  { href: '/master-data',      label: 'Master Data',      icon: Database        },
  { href: '/e2e',              label: 'Traceability',     icon: GitBranch       },
]

const SETTINGS_ITEMS = [
  { href: '/settings/organizations',    label: 'Organizations',   icon: Building2   },
  { href: '/settings/workflows',        label: 'Workflows',       icon: Zap         },
  { href: '/settings/status-models',    label: 'Status Models',   icon: GitMerge    },
  { href: '/settings/numbering',        label: 'Numbering',       icon: Hash        },
  { href: '/settings/global',           label: 'Global Settings', icon: Globe       },
  { href: '/settings/validation-rules', label: 'Validation',      icon: ShieldCheck },
]

export default function NavSidebar() {
  const path = usePathname()

  const isActive = (href: string) =>
    href === '/dashboard' ? path === '/dashboard' : path.startsWith(href)

  const logout = () => {
    localStorage.removeItem('tms_token')
    window.location.href = '/login'
  }

  return (
    <aside className="w-52 bg-white border-r border-gray-100 flex flex-col shrink-0 shadow-sm">
      {/* Logo */}
      <div className="px-4 py-4 border-b border-gray-100">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-blue-600 rounded-lg flex items-center justify-center">
            <span className="text-white text-xs font-bold">FO</span>
          </div>
          <div>
            <p className="text-sm font-bold text-gray-900 leading-none">Flow Ops</p>
            <p className="text-xs text-gray-400 leading-none mt-0.5">TMS</p>
          </div>
        </div>
      </div>

      {/* Main nav */}
      <nav className="flex-1 overflow-y-auto py-2">
        <div className="px-2 space-y-0.5">
          {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
            const active = isActive(href)
            return (
              <Link key={href} href={href}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors group ${
                  active
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}>
                <Icon size={17} className={active ? 'text-white' : 'text-gray-400 group-hover:text-gray-600'} />
                <span>{label}</span>
              </Link>
            )
          })}
        </div>

        {/* Settings section */}
        <div className="mt-4 px-4 mb-1">
          <p className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Settings</p>
        </div>
        <div className="px-2 space-y-0.5">
          {SETTINGS_ITEMS.map(({ href, label, icon: Icon }) => {
            const active = isActive(href)
            return (
              <Link key={href} href={href}
                className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors group ${
                  active
                    ? 'bg-blue-600 text-white'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`}>
                <Icon size={17} className={active ? 'text-white' : 'text-gray-400 group-hover:text-gray-600'} />
                <span>{label}</span>
              </Link>
            )
          })}
        </div>
      </nav>

      {/* Bottom: sign out */}
      <div className="px-2 py-3 border-t border-gray-100">
        <button onClick={logout}
          className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium text-gray-500 hover:bg-gray-50 hover:text-gray-700 transition-colors">
          <LogOut size={17} className="text-gray-400" />
          <span>Sign out</span>
        </button>
      </div>
    </aside>
  )
}
