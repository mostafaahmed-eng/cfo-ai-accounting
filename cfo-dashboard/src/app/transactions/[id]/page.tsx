'use client'

import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/api-client'
import type { Account, DraftTransaction } from '@/lib/types'
import { useParams } from 'next/navigation'
import { useState, useEffect } from 'react'

export default function TransactionDetailPage() {
  const params = useParams()
  const id = params.id as string
  const queryClient = useQueryClient()
  const [editMode, setEditMode] = useState(false)
  const [form, setForm] = useState<Partial<DraftTransaction>>({})
  const [categoryAccountId, setCategoryAccountId] = useState('')
  const [paymentAccountId, setPaymentAccountId] = useState('')
  const [approvalError, setApprovalError] = useState('')

  const { data: transaction, isLoading } = useQuery<DraftTransaction>({
    queryKey: ['draft-transaction', id],
    queryFn: async () => {
      const { data } = await apiClient.get(`/draft-transactions/${id}`)
      return data
    },
  })

  const { data: accounts = [] } = useQuery<Account[]>({
    queryKey: ['accounts'],
    queryFn: async () => {
      const { data } = await apiClient.get('/accounts')
      return data
    },
  })

  const { data: extractions = [] } = useQuery<
    Array<{ validated_result: { category_hint?: string | null } | null }>
  >({
    queryKey: ['ai-extractions', transaction?.inbox_item_id],
    queryFn: async () => {
      const { data } = await apiClient.get(
        `/ai-extraction/${transaction?.inbox_item_id}`,
      )
      return data
    },
    enabled: Boolean(transaction?.inbox_item_id),
  })

  useEffect(() => {
    if (transaction) {
      setForm(transaction)
      setCategoryAccountId(transaction.category_account_id || '')
      setPaymentAccountId(transaction.payment_account_id || '')
    }
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
      setApprovalError('')
      await apiClient.patch(`/draft-transactions/${id}`, {
        category_account_id: categoryAccountId,
        payment_account_id: paymentAccountId,
      })
      const { data } = await apiClient.post(`/draft-transactions/${id}/approve`)
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['draft-transaction', id] })
      queryClient.invalidateQueries({ queryKey: ['draft-transactions'] })
      queryClient.invalidateQueries({ queryKey: ['inbox'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['report-cashflow'] })
      queryClient.invalidateQueries({ queryKey: ['report-expenses-by-category'] })
    },
    onError: (error: { response?: { data?: { detail?: string } } }) => {
      setApprovalError(error.response?.data?.detail || 'Approval failed')
    },
  })

  const categoryAccounts = accounts.filter((account) => {
    if (!account.is_active || account.is_payment_account) return false
    if (transaction?.type === 'income') return account.type === 'revenue'
    if (transaction?.type === 'transfer') return account.type === 'asset'
    return account.type === 'expense'
  })
  const paymentAccounts = accounts.filter(
    (account) => account.is_active && account.is_payment_account,
  )

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
                  {transaction.status === 'needs_clarification' && (
                    <div className="rounded bg-amber-50 p-3 text-amber-800">
                      Waiting on the submitter to confirm or correct the extracted details.
                    </div>
                  )}
                  {transaction.status === 'ready_for_review' && (
                    <div className="space-y-4 border-t pt-4">
                      <p className="font-medium">Accounting review</p>
                      {extractions[0]?.validated_result?.category_hint && (
                        <p className="rounded bg-blue-50 p-3 text-blue-800">
                          AI category suggestion: {extractions[0].validated_result.category_hint}
                        </p>
                      )}
                      <div>
                        <label className="block text-sm font-medium mb-1" htmlFor="category-account">
                          {transaction.type === 'income' ? 'Income account' : 'Category account'}
                        </label>
                        <select
                          id="category-account"
                          value={categoryAccountId}
                          onChange={(event) => setCategoryAccountId(event.target.value)}
                          className="w-full border rounded px-3 py-2 text-sm"
                        >
                          <option value="">Select an account</option>
                          {categoryAccounts.map((account) => (
                            <option key={account.id} value={account.id}>
                              {account.code} — {account.name_en}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-1" htmlFor="payment-account">
                          Payment account
                        </label>
                        <select
                          id="payment-account"
                          value={paymentAccountId}
                          onChange={(event) => setPaymentAccountId(event.target.value)}
                          className="w-full border rounded px-3 py-2 text-sm"
                        >
                          <option value="">Select an account</option>
                          {paymentAccounts.map((account) => (
                            <option key={account.id} value={account.id}>
                              {account.code} — {account.name_en}
                            </option>
                          ))}
                        </select>
                      </div>
                      {approvalError && <p className="text-sm text-red-700">{approvalError}</p>}
                      <button
                        onClick={() => approveMutation.mutate()}
                        disabled={!categoryAccountId || !paymentAccountId || approveMutation.isPending}
                        className="bg-green-600 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
                      >
                        {approveMutation.isPending ? 'Approving…' : 'Approve and post'}
                      </button>
                    </div>
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
