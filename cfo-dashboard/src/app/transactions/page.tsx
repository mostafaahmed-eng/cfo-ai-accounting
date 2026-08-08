'use client'

import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient, { fetchAll } from '@/lib/api-client'
import { useCompany } from '@/contexts/CompanyContext'
import type { DraftTransaction } from '@/lib/types'
import Link from 'next/link'

const STATUS_COLORS: Record<string, string> = {
  draft: 'bg-gray-100 text-gray-800',
  needs_clarification: 'bg-yellow-100 text-yellow-800',
  ready_for_review: 'bg-blue-100 text-blue-800',
  approved: 'bg-green-100 text-green-800',
  rejected: 'bg-red-100 text-red-800',
  posted: 'bg-purple-100 text-purple-800',
}

export default function TransactionsPage() {
  const queryClient = useQueryClient()
  const { selectedCompanyId } = useCompany()
  const { data: transactions, isLoading } = useQuery<DraftTransaction[]>({
    queryKey: ['draft-transactions', selectedCompanyId],
    queryFn: () => fetchAll<DraftTransaction>('/draft-transactions'),
    enabled: Boolean(selectedCompanyId),
  })

  const rejectMutation = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.post(`/draft-transactions/${id}/reject`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['draft-transactions'] })
      queryClient.invalidateQueries({ queryKey: ['inbox'] })
    },
  })

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1">
        <Header />
        <main className="p-6">
          <h2 className="text-2xl font-bold mb-6">Transactions</h2>
          {isLoading ? (
            <p className="text-gray-500">Loading...</p>
          ) : (
            <div className="bg-white rounded-lg shadow">
              <table className="w-full">
                <thead>
                  <tr className="border-b text-left text-sm text-gray-500">
                    <th className="p-4">Date</th>
                    <th className="p-4">Description</th>
                    <th className="p-4">Type</th>
                    <th className="p-4">Amount</th>
                    <th className="p-4">Status</th>
                    <th className="p-4">AI Conf.</th>
                    <th className="p-4">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {(transactions || []).map((tx) => (
                    <tr key={tx.id} className="border-b hover:bg-gray-50">
                      <td className="p-4 text-sm">{tx.transaction_date}</td>
                      <td className="p-4 text-sm">
                        <Link href={`/transactions/${tx.id}`} className="text-brand-600 hover:underline">
                          {tx.description}
                        </Link>
                      </td>
                      <td className="p-4 text-sm capitalize">{tx.type}</td>
                      <td className="p-4 text-sm font-medium">
                        {tx.currency} {tx.amount.toLocaleString()}
                      </td>
                      <td className="p-4 text-sm">
                        <span className={`px-2 py-1 rounded text-xs ${STATUS_COLORS[tx.status] || 'bg-gray-100'}`}>
                          {tx.status.replace('_', ' ')}
                        </span>
                      </td>
                      <td className="p-4 text-sm text-gray-500">
                        {tx.ai_confidence != null ? `${(tx.ai_confidence * 100).toFixed(0)}%` : '-'}
                      </td>
                      <td className="p-4 text-sm">
                        {tx.status === 'ready_for_review' && (
                          <div className="flex gap-2">
                            <Link href={`/transactions/${tx.id}`} className="text-green-600 hover:underline text-xs">
                              Review
                            </Link>
                            <button
                              onClick={() => rejectMutation.mutate(tx.id)}
                              className="text-red-600 hover:underline text-xs"
                            >
                              Reject
                            </button>
                          </div>
                        )}
                        {tx.status === 'needs_clarification' && (
                          <span className="text-xs text-amber-700">Waiting on submitter</span>
                        )}
                      </td>
                    </tr>
                  ))}
                  {(transactions || []).length === 0 && (
                    <tr>
                      <td colSpan={7} className="p-4 text-center text-gray-500">
                        No transactions yet
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
