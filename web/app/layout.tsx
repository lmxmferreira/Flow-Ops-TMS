'use client'
import { useEffect, useState } from 'react'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import './globals.css'
import { LayoutDashboard, ShoppingCart, Truck, Users, DollarSign, FileText, Shield, Search, Settings, Activity, ChevronDown, ChevronRight, LogOut, Bell, Menu } from 'lucide-react'

const NAV = [
  { label: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { label: 'Orders', icon: ShoppingCart, children: [{ label: 'Purchase Orders', href: '/purchase-orders' }, { label: 'Order Releases', href: '/order-releases' }] },
  { label: 'Transportation', icon: Truck, children: [{ label: 'Shipments', href: '/shipments' }, { label: 'Stops', href: '/stops' }, { label: 'Execution', href: '/execution' }] },
  { label: 'Carriers', icon: Users, children: [{ label: 'Carrier Management', href: '/carriers' }, { label: 'Rating', href: '/rating' }] },
  { label: 'Financials', icon: DollarSign, children: [{ label: 'Carrier Invoices', href: '/carrier-invoices' }, { label: 'Freight Audit', href: '/freight-audit' }, { label: 'Cost Allocation', href: '/allocation' }, { label: 'Client Billing', href: '/billing' }, { label: 'Accruals & GL', href: '/financials' }] },
  { label: 'Operations', icon: Activity, children: [{ label: 'Exceptions & Claims', href: '/exceptions' }, { label: 'Yard & Gate', href: '/yard' }] },
  { label: 'Documents', icon: FileText, children: [{ label: 'Documents', href: '/documents' }, { label: 'Master Data', href: '/master-data' }] },
  { label: 'Platform', icon: Settings, children: [{ label: 'Integration', href: '/integration' }, { label: 'Reports', href: '/reports' }, { label: 'Security & Audit', href: '/security' }, { label: 'Workflows', href: '/workflows' }] },
  { label: 'E2E Traceability', href: '/e2e', icon: Search },
  { label: 'System Health', href: '/system', icon: Shield },
]

function NavItem({ item }: { item: any }) {
  const pathname = usePathname()
  const [open, setOpen] = useState(() => item.children?.some((c: any) => pathname.startsWith(c.href)))
  const Icon = item.icon
  if (item.children) {
    return (
      <div>
        <button onClick={() => setOpen(!open)} className={`w-full flex items-center justify-between px-3 py-2 text-sm rounded-lg transition-colors ${open ? 'text-blue-600 bg-blue-50' : 'text-gray-600 hover:bg-gray-100'}`}>
          <span className="flex items-center gap-2.5">{Icon && <Icon size={16}/>}<span className="font-medium">{item.label}</span></span>
          {open ? <ChevronDown size={14}/> : <ChevronRight size={14}/>}
        </button>
        {open && (
          <div className="ml-6 mt-0.5 space-y-0.5 border-l border-gray-100 pl-3">
            {item.children.map((child: any) => (
              <Link key={child.href} href={child.href} className={`block px-2 py-1.5 text-sm rounded-md transition-colors ${pathname.startsWith(child.href) ? 'text-blue-600 font-medium bg-blue-50' : 'text-gray-500 hover:text-gray-800 hover:bg-gray-50'}`}>{child.label}</Link>
            ))}
          </div>
        )}
      </div>
    )
  }
  const active = item.href && pathname.startsWith(item.href)
  return (
    <Link href={item.href} className={`flex items-center gap-2.5 px-3 py-2 text-sm rounded-lg transition-colors ${active ? 'text-blue-600 font-semibold bg-blue-50' : 'text-gray-600 hover:bg-gray-100'}`}>
      {Icon && <Icon size={16}/>}<span className="font-medium">{item.label}</span>
    </Link>
  )
}

function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname()
  const [open, setOpen] = useState(true)
  const [user, setUser] = useState('')
  useEffect(() => { setUser(localStorage.getItem('tms_user') || 'user@flowops.com') }, [])
  if (pathname === '/login') return <>{children}</>
  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      <aside className={`${open ? 'w-60' : 'w-0'} flex-shrink-0 transition-all duration-200 overflow-hidden bg-white border-r border-gray-200 flex flex-col`}>
        <div className="flex items-center gap-2.5 px-4 py-4 border-b border-gray-100">
          <img src="/logo.png" alt="Flow Ops Global" className="h-9 w-auto object-contain" />
        </div>
        <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-0.5">
          {NAV.map((item, i) => <NavItem key={i} item={item}/>)}
        </nav>
        <div className="px-3 py-3 border-t border-gray-100">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-full flex items-center justify-center text-white text-xs font-bold">{user.charAt(0).toUpperCase()}</div>
            <div className="flex-1 min-w-0"><p className="text-xs font-medium text-gray-700 truncate">{user}</p><p className="text-[10px] text-gray-400">Admin</p></div>
            <button onClick={() => { localStorage.clear(); window.location.href = '/login' }} className="text-gray-400 hover:text-red-500"><LogOut size={14}/></button>
          </div>
        </div>
      </aside>
      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="bg-white border-b border-gray-200 px-4 py-3 flex items-center gap-3 flex-shrink-0">
          <button onClick={() => setOpen(!open)} className="text-gray-400 hover:text-gray-600"><Menu size={18}/></button>
          <div className="flex-1"/>
          <button className="text-gray-400 hover:text-gray-600 relative"><Bell size={18}/><span className="absolute -top-0.5 -right-0.5 w-2 h-2 bg-red-500 rounded-full"/></button>
        </header>
        <main className="flex-1 overflow-y-auto">{children}</main>
      </div>
    </div>
  )
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  )
}
