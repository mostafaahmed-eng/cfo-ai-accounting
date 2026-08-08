'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'

const links = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/inbox', label: 'Inbox' },
  { href: '/transactions', label: 'Transactions' },
  { href: '/accounts', label: 'Accounts' },
  { href: '/vendors', label: 'Vendors' },
  { href: '/budgets', label: 'Budgets' },
  { href: '/exchange-rates', label: 'Exchange Rates' },
  { href: '/reports/profit-and-loss', label: 'P&L' },
  { href: '/reports/cash-flow', label: 'Cash Flow' },
  { href: '/reports/balance-sheet', label: 'Balance Sheet' },
  { href: '/settings/company', label: 'Company Settings' },
  { href: '/settings/members', label: 'Members' },
  { href: '/settings/integrations', label: 'Integrations' },
  { href: '/settings/telegram', label: 'Telegram' },
]

export default function Sidebar() {
  const pathname = usePathname()

  return (
    <aside className="w-64 bg-white border-r border-brand-200 min-h-screen p-4">
      <h1 className="text-xl font-bold mb-6">
        <span className="text-brand-600">AI</span>{" "}
        <span className="text-gray-900">CFO</span>
      </h1>
      <nav className="space-y-1">
        {links.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className={`block px-3 py-2 rounded-lg text-sm transition-colors ${
              pathname === link.href
                ? 'bg-brand-100 text-brand-700 font-medium'
                : 'text-gray-600 hover:bg-brand-50 hover:text-gray-900'
            }`}
          >
            {link.label}
          </Link>
        ))}
      </nav>
    </aside>
  )
}