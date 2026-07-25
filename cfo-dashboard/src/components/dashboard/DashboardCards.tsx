'use client'

import type { DashboardData } from '@/lib/types'

export default function DashboardCards({ data }: { data: DashboardData }) {
  const formatAmount = (amount: number) =>
    `${data.base_currency} ${amount.toLocaleString()}`
  const cards = [
    { label: 'Monthly Income', value: formatAmount(data.monthly_income), color: 'text-green-600' },
    { label: 'Monthly Expenses', value: formatAmount(data.monthly_expenses), color: 'text-red-600' },
    { label: 'Net Cash Flow', value: formatAmount(data.net_cash_flow), color: data.net_cash_flow >= 0 ? 'text-green-600' : 'text-red-600' },
    { label: 'Pending Approvals', value: data.pending_approvals.toString(), color: 'text-yellow-600' },
  ]

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
      {cards.map((card) => (
        <div key={card.label} className="bg-white rounded-lg shadow p-6">
          <p className="text-sm text-gray-500">{card.label}</p>
          <p className={`text-2xl font-bold ${card.color}`}>{card.value}</p>
        </div>
      ))}
    </div>
  )
}
