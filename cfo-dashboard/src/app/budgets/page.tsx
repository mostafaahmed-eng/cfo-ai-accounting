'use client'

import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import { useQuery } from '@tanstack/react-query'
import apiClient from '@/lib/api-client'
import type { Budget } from '@/lib/types'

export default function BudgetsPage() {
  const { data: budgets, isLoading } = useQuery<Budget[]>({
    queryKey: ['budgets'],
    queryFn: async () => {
      const { data } = await apiClient.get('/budgets')
      return data
    },
  })

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1">
        <Header />
        <main className="p-6">
          <h2 className="text-2xl font-bold mb-6">Budgets</h2>
          {isLoading ? (
            <p className="text-gray-500">Loading...</p>
          ) : (budgets || []).length === 0 ? (
            <div className="bg-white rounded-lg shadow p-8 text-center">
              <p className="text-gray-500 mb-4">No budgets created yet</p>
              <p className="text-sm text-gray-400">Create a budget to track planned vs actual spending.</p>
            </div>
          ) : (
            <div className="space-y-4">
              {(budgets || []).map((budget) => (
                <div key={budget.id} className="bg-white rounded-lg shadow p-6">
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="text-lg font-semibold">{budget.name}</h3>
                      <p className="text-sm text-gray-500">{budget.period_type} &middot; {budget.start_date} to {budget.end_date}</p>
                    </div>
                    <span className={`px-2 py-1 rounded text-xs ${
                      budget.status === 'active' ? 'bg-green-100 text-green-800' :
                      budget.status === 'closed' ? 'bg-gray-100 text-gray-800' :
                      'bg-yellow-100 text-yellow-800'
                    }`}>
                      {budget.status}
                    </span>
                  </div>
                  {budget.lines.length > 0 && (
                    <div className="mt-4">
                      <table className="w-full text-sm">
                        <thead>
                          <tr className="text-gray-500 border-b">
                            <th className="py-2 text-left">Account</th>
                            <th className="py-2 text-right">Planned</th>
                            <th className="py-2 text-right">Alert %</th>
                          </tr>
                        </thead>
                        <tbody>
                          {budget.lines.map((line) => (
                            <tr key={line.id} className="border-b">
                              <td className="py-2">{line.account_id}</td>
                              <td className="py-2 text-right">{budget.currency} {line.planned_amount.toLocaleString()}</td>
                              <td className="py-2 text-right">{line.alert_percentage}%</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
