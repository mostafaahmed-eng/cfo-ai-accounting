'use client'

import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/api-client'
import type { DraftTransaction } from '@/lib/types'
import { useParams } from 'next/navigation'
import { useState, useEffect } from 'react'

export default function TransactionDetailPage() {
  const params = useParams()
  const id = params.id as string
  const queryClient = useQueryClient()
  const [editMode, setEditMode] = useState(false)
  const [form, setForm] = useState<Partial<DraftTransaction>>({})

  const { data: transaction, isLoading } = useQuery<DraftTransaction>({
    queryKey: ['draft-transaction', id],
    queryFn: async () => {
      const { data } = await apiClient.get(`/draft-transactions/${id}`)
      return data
    },
  })

  useEffect(() => {
    if (transaction) setForm(transaction)
  }, [transaction])

  const updateMutation = useMutation({
    mutationFn: async (updates: Partial<DraftTransaction>) => {
      const { data } = await apiClient.patch(`/draft-transactions/${id}`, updates)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['draft-transaction', id] })
      queryClient.invalidateQueries({ queryKey: ['draft-transactions'] })
      setEditMode(false)
    },
  })

  const approveMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post(`/draft-transactions/${id}/approve`)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['draft-transaction', id] })
      queryClient.invalidateQueries({ queryKey: ['draft-transactions'] })
    },
  })

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1">
        <Header />
        <main className="p-6">
          <h2 className="text-2xl font-bold mb-6">Transaction Detail</h2>
          {isLoading ? (
            <p className="text-gray-500">Loading...</p>
          ) : transaction ? (
            <div className="bg-white rounded-lg shadow p-6 max-w-2xl">
              <div className="flex justify-between items-start mb-6">
                <h3 className="text-lg font-semibold">{transaction.description}</h3>
                <div className="flex gap-2">
                  {!editMode && transaction.status !== 'posted' && transaction.status !== 'approved' && (
                    <button onClick={() => setEditMode(true)} className="text-blue-600 hover:underline text-sm">
                      Edit
                    </button>
                  )}
                  {(transaction.status === 'ready_for_review' || transaction.status === 'needs_clarification') && (
                    <button onClick={() => approveMutation.mutate()} className="bg-green-600 text-white px-4 py-2 rounded text-sm">
                      Approve
                    </button>
                  )}
                </div>
              </div>

              {editMode ? (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">Description</label>
                    <input value={form.description || ''} onChange={(e) => setForm({ ...form, description: e.target.value })}
                      className="w-full border rounded px-3 py-2 text-sm" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Amount</label>
                    <input type="number" value={form.amount || 0} onChange={(e) => setForm({ ...form, amount: Number(e.target.value) })}
                      className="w-full border rounded px-3 py-2 text-sm" />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Transaction Date</label>
                    <input type="date" value={form.transaction_date || ''} onChange={(e) => setForm({ ...form, transaction_date: e.target.value })}
                      className="w-full border rounded px-3 py-2 text-sm" />
                  </div>
                  <div className="flex gap-2">
                    <button onClick={() => updateMutation.mutate(form)} className="bg-blue-600 text-white px-4 py-2 rounded text-sm">
                      Save
                    </button>
                    <button onClick={() => setEditMode(false)} className="text-gray-600 hover:underline text-sm">
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-3 text-sm">
                  <div className="flex justify-between"><span className="text-gray-500">Type</span><span className="capitalize">{transaction.type}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Amount</span><span>{transaction.currency} {transaction.amount.toLocaleString()}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Tax</span><span>{transaction.currency} {transaction.tax_amount.toLocaleString()}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Date</span><span>{transaction.transaction_date}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Status</span><span className="capitalize">{transaction.status.replace('_', ' ')}</span></div>
                  {transaction.ai_confidence != null && (
                    <div className="flex justify-between"><span className="text-gray-500">AI Confidence</span><span>{(transaction.ai_confidence * 100).toFixed(0)}%</span></div>
                  )}
                  {transaction.reference_number && (
                    <div className="flex justify-between"><span className="text-gray-500">Reference</span><span>{transaction.reference_number}</span></div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <p className="text-gray-500">Transaction not found</p>
          )}
        </main>
      </div>
    </div>
  )
}
