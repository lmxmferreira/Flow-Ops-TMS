'use client'
import Link from 'next/link'
import { DollarSign, MapPin, FileText, ArrowRight } from 'lucide-react'

export default function RatesPage() {
  const sections = [
    { href: '/rates/regions', icon: MapPin, color: 'bg-blue-50 text-blue-600 border-blue-200',
      title: 'Rate Regions', desc: 'Group locations by state, city, postal code into named zones for simplified lane setup.' },
    { href: '/rates/rate-cards', icon: FileText, color: 'bg-green-50 text-green-600 border-green-200',
      title: 'Rate Cards', desc: 'Manage carrier rate cards with lanes, origin/destination regions, weight breaks, and charge lines.' },
  ]
  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <DollarSign className="text-green-600" size={24}/> Rates Management
        </h1>
        <p className="text-sm text-gray-500 mt-1">Configure carrier rates, define regions, and manage rate cards with lane-level pricing</p>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {sections.map(s => (
          <Link key={s.href} href={s.href}
            className={`flex gap-4 p-6 bg-white rounded-xl border-2 ${s.color} hover:shadow-md transition-all group`}>
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0 ${s.color}`}>
              <s.icon size={22}/>
            </div>
            <div className="flex-1">
              <h2 className="text-base font-bold text-gray-900 group-hover:text-blue-600 transition-colors">{s.title}</h2>
              <p className="text-sm text-gray-500 mt-1">{s.desc}</p>
            </div>
            <ArrowRight size={16} className="text-gray-400 group-hover:text-blue-600 mt-1 flex-shrink-0"/>
          </Link>
        ))}
      </div>
    </div>
  )
}
