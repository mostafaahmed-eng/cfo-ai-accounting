'use client'

import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/api-client'
import type { Account, DraftTransaction, Vendor } from '@/lib/types'
import { useParams } from 'next/navigation'
import { useState, useEffect } from 'react'
import { useCompany } from '@/contexts/CompanyContext'

interface DraftEditForm {
  type: DraftTransaction['type']
  amount: string
  tax_amount: string
  currency: string
  transaction_date: string
  description: string
  vendor_id: string
  reference_number: string
}

const emptyForm: DraftEditForm = {
  type: 'expense',
  amount: '',
  tax_amount: '',
  currency: '',
  transaction_date: '',
  description: '',
  vendor_id: '',
  reference_number: '',
}

export default function TransactionDetailPage() {
  const params = useParams()
  const id = params.id as string
  const { selectedCompanyId } = useCompany()
  const queryClient = useQueryClient()
  const [editMode, setEditMode] = useState(false)
  const [form, setForm] = useState<DraftEditForm>(emptyForm)
  const [savedForm, setSavedForm] = useState<DraftEditForm>(emptyForm)
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({})
  const [saveMessage, setSaveMessage] = useState('')
  const [categoryAccountId, setCategoryAccountId] = useState('')
  const [paymentAccountId, setPaymentAccountId] = useState('')
  const [approvalError, setApprovalError] = useState('')

  const { data: transaction, isLoading } = useQuery<DraftTransaction>({
    queryKey: ['draft-transaction', selectedCompanyId, id],
    queryFn: async () => {
      const { data } = await apiClient.get(`/draft-transactions/${id}`)
      return data
    },
    enabled: Boolean(selectedCompanyId),
  })

  const { data: accounts = [] } = useQuery<Account[]>({
    queryKey: ['accounts', selectedCompanyId],
    queryFn: async () => {
      const { data } = await apiClient.get('/accounts')
      return data
    },
    enabled: Boolean(selectedCompanyId),
  })

  const { data: vendors = [] } = useQuery<Vendor[]>({
    queryKey: ['vendors', selectedCompanyId],
    queryFn: async () => {
      const { data } = await apiClient.get('/vendors')
      return data
    },
    enabled: Boolean(selectedCompanyId),
  })

  const { data: extractions = [] } = useQuery<
    Array<{ validated_result: { category_hint?: string | null } | null }>
  >({
    queryKey: ['ai-extractions', selectedCompanyId, transaction?.inbox_item_id],
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
      const nextForm: DraftEditForm = {
        type: transaction.type,
        amount: String(transaction.amount),
        tax_amount: String(transaction.tax_amount),
        currency: transaction.currency,
        transaction_date: transaction.transaction_date,
        description: transaction.description,
        vendor_id: transaction.vendor_id || '',
        reference_number: transaction.reference_number || '',
      }
      setForm(nextForm)
      setSavedForm(nextForm)
      setCategoryAccountId(transaction.category_account_id || '')
      setPaymentAccountId(transaction.payment_account_id || '')
    }
  }, [transaction])

  useEffect(() => {
    setEditMode(false)
    setForm(emptyForm)
    setSavedForm(emptyForm)
    setFieldErrors({})
    setSaveMessage('')
  }, [selectedCompanyId])

  const updateMutation = useMutation({
    mutationFn: async (updates: DraftEditForm) => {
      const { data } = await apiClient.patch(`/draft-transactions/${id}`, {
        ...updates,
        vendor_id: updates.vendor_id || null,
        reference_number: updates.reference_number || null,
      })
      return data
    },
    onSuccess: (updated: DraftTransaction) => {
      queryClient.setQueryData(
        ['draft-transaction', selectedCompanyId, id],
        updated,
      )
      queryClient.invalidateQueries({
        queryKey: ['draft-transactions'],
      })
      queryClient.invalidateQueries({
        queryKey: ['inbox'],
      })
      setSavedForm(form)
      setFieldErrors({})
      setSaveMessage('Corrections saved. The draft has not been approved.')
      setEditMode(false)
    },
    onError: (error: {
      response?: { data?: { detail?: string | Array<{ loc?: string[]; msg: string }> } }
    }) => {
      const detail = error.response?.data?.detail
      if (Array.isArray(detail)) {
        const errors: Record<string, string> = {}
        detail.forEach((item) => {
          const field = item.loc?.at(-1) || 'form'
          errors[field] = item.msg
        })
        setFieldErrors(errors)
      } else {
        setFieldErrors({ form: detail || 'Unable to save corrections' })
      }
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
      queryClient.invalidateQueries({
        queryKey: ['draft-transaction', selectedCompanyId, id],
      })
      queryClient.invalidateQueries({
        queryKey: ['draft-transactions'],
      })
      queryClient.invalidateQueries({ queryKey: ['inbox'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard', selectedCompanyId] })
      queryClient.invalidateQueries({
        queryKey: ['report-cashflow', selectedCompanyId],
      })
      queryClient.invalidateQueries({
        queryKey: ['report-expenses-by-category', selectedCompanyId],
      })
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
  const isEditable = ['draft', 'needs_clarification', 'ready_for_review'].includes(
    transaction?.status ?? '',
  )
  const hasUnsavedChanges = JSON.stringify(form) !== JSON.stringify(savedForm)
  const fieldError = (field: string) =>
    fieldErrors[field] ? (
      <p className="mt-1 text-xs text-red-700">{fieldErrors[field]}</p>
    ) : null

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
                  {!editMode && isEditable && (
                    <button
                      onClick={() => {
                        setFieldErrors({})
                        setSaveMessage('')
                        setEditMode(true)
                      }}
                      className="text-blue-600 hover:underline text-sm"
                    >
                      Edit
                    </button>
                  )}
                </div>
              </div>

              {editMode ? (
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">Vendor</label>
                    <select
                      value={form.vendor_id}
                      onChange={(e) => setForm({ ...form, vendor_id: e.target.value })}
                      className="w-full border rounded px-3 py-2 text-sm"
                    >
                      <option value="">No vendor selected</option>
                      {vendors.map((vendor) => (
                        <option key={vendor.id} value={vendor.id}>{vendor.name}</option>
                      ))}
                    </select>
                    {fieldError('vendor_id')}
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Description</label>
                    <input value={form.description || ''} onChange={(e) => setForm({ ...form, description: e.target.value })}
                      className="w-full border rounded px-3 py-2 text-sm" />
                    {fieldError('description')}
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Amount</label>
                    <input type="number" step="0.0001" min="0.0001" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })}
                      className="w-full border rounded px-3 py-2 text-sm" />
                    {fieldError('amount')}
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Tax amount</label>
                    <input type="number" step="0.0001" min="0" value={form.tax_amount} onChange={(e) => setForm({ ...form, tax_amount: e.target.value })}
                      className="w-full border rounded px-3 py-2 text-sm" />
                    {fieldError('tax_amount')}
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Currency</label>
                    <input
                      value={form.currency}
                      maxLength={3}
                      onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })}
                      className="w-full border rounded px-3 py-2 text-sm uppercase"
                      placeholder="EGP"
                    />
                    {fieldError('currency')}
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Transaction type</label>
                    <select
                      value={form.type}
                      onChange={(e) => setForm({ ...form, type: e.target.value as DraftTransaction['type'] })}
                      className="w-full border rounded px-3 py-2 text-sm"
                    >
                      <option value="expense">Expense</option>
                      <option value="income">Income</option>
                      <option value="transfer">Transfer</option>
                    </select>
                    {fieldError('type')}
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Transaction Date</label>
                    <input type="date" value={form.transaction_date || ''} onChange={(e) => setForm({ ...form, transaction_date: e.target.value })}
                      className="w-full border rounded px-3 py-2 text-sm" />
                    {fieldError('transaction_date')}
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Reference / invoice number</label>
                    <input value={form.reference_number} onChange={(e) => setForm({ ...form, reference_number: e.target.value })}
                      className="w-full border rounded px-3 py-2 text-sm" />
                    {fieldError('reference_number')}
                  </div>
                  {hasUnsavedChanges && <p className="text-sm text-amber-700">You have unsaved changes.</p>}
                  {fieldErrors.form && <p className="text-sm text-red-700">{fieldErrors.form}</p>}
                  <div className="flex gap-2">
                    <button
                      onClick={() => updateMutation.mutate(form)}
                      disabled={!hasUnsavedChanges || updateMutation.isPending}
                      className="bg-blue-600 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
                    >
                      {updateMutation.isPending ? 'Saving…' : 'Save corrections'}
                    </button>
                    <button
                      onClick={() => {
                        setForm(savedForm)
                        setFieldErrors({})
                        setEditMode(false)
                      }}
                      disabled={updateMutation.isPending}
                      className="text-gray-600 hover:underline text-sm disabled:opacity-50"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="space-y-3 text-sm">
                  {saveMessage && (
                    <p className="rounded bg-green-50 p-3 text-green-800">{saveMessage}</p>
                  )}
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
