import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Flow Ops TMS',
  description: 'Transportation Management System',
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}
