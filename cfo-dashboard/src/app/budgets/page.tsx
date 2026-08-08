'use client'

import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient, { fetchAll } from '@/lib/api-client'
import { useCompany } from '@/contexts/CompanyContext'
import type { Account, Budget } from '@/lib/types'
import { useState } from 'react'

interface BudgetLineInput {
  account_id: string
  planned_amount: string
  alert_percentage: string
}

interface BudgetForm {
  name: string
  period_type: 'monthly' | 'quarterly' | 'yearly'
  start_date: string
  end_date: string
  currency: string
  lines: BudgetLineInput[]
}

const emptyForm: BudgetForm = {
  name: '',
  period_type: 'monthly',
  start_date: '',
  end_date: '',
  currency: 'USD',
  lines: [{ account_id: '', planned_amount: '', alert_percentage: '80' }],
}

function apiError(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response
    ?.data?.detail
  return typeof detail === 'string' ? detail : 'Request failed'
}

export default function BudgetsPage() {
  const queryClient = useQueryClient()
  const { selectedCompanyId } = useCompany()
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<Budget | null>(null)
  const [form, setForm] = useState<BudgetForm>(emptyForm)
  const [actionError, setActionError] = useState('')

  const { data: budgets, isLoading } = useQuery<Budget[]>({
    queryKey: ['budgets', selectedCompanyId],
    queryFn: () => fetchAll<Budget>('/budgets'),
    enabled: Boolean(selectedCompanyId),
  })

  const { data: accounts = [] } = useQuery<Account[]>({
    queryKey: ['accounts', selectedCompanyId],
    queryFn: () => fetchAll<Account>('/accounts'),
    enabled: Boolean(selectedCompanyId),
  })

  const expenseAccounts = accounts.filter(
    (account) => account.is_active && account.type === 'expense',
  )

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['budgets', selectedCompanyId] })

  const toPayload = () => ({
    name: form.name,
    period_type: form.period_type,
    start_date: form.start_date,
    end_date: form.end_date,
    currency: form.currency.toUpperCase(),
    lines: form.lines
      .filter((line) => line.account_id && line.planned_amount)
      .map((line) => ({
        account_id: line.account_id,
        planned_amount: Number(line.planned_amount),
        alert_percentage: Number(line.alert_percentage || 80),
      })),
  })

  const createMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post('/budgets', toPayload())
    },
    onSuccess: () => {
      invalidate()
      setShowForm(false)
      setForm(emptyForm)
      setActionError('')
    },
    onError: (error) => setActionError(apiError(error)),
  })

  const updateMutation = useMutation({
    mutationFn: async (payload: { id: string; body: Record<string, unknown> }) => {
      const { data } = await apiClient.patch(`/budgets/${payload.id}`, payload.body)
      return data
    },
    onSuccess: () => {
      invalidate()
      setEditing(null)
      setActionError('')
    },
    onError: (error) => setActionError(apiError(error)),
  })

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/budgets/${id}`)
    },
    onSuccess: () => {
      invalidate()
      setActionError('')
    },
    onError: (error) => setActionError(apiError(error)),
  })

  const startEdit = (budget: Budget) => {
    setEditing(budget)
    setForm({
      name: budget.name,
      period_type: budget.period_type,
      start_date: budget.start_date,
      end_date: budget.end_date,
      currency: budget.currency,
      lines:
        budget.lines.length > 0
          ? budget.lines.map((line) => ({
              account_id: String(line.account_id),
              planned_amount: String(line.planned_amount),
              alert_percentage: String(line.alert_percentage),
            }))
          : [{ account_id: '', planned_amount: '', alert_percentage: '80' }],
    })
    setShowForm(false)
  }

  const setLine = (index: number, key: keyof BudgetLineInput, value: string) => {
    const lines = [...form.lines]
    lines[index] = { ...lines[index], [key]: value }
    setForm({ ...form, lines })
  }

  const submitForm = () => {
    setActionError('')
    if (editing) {
      updateMutation.mutate({
        id: editing.id,
        body: {
          name: form.name,
          lines: toPayload().lines,
        },
      })
    } else {
      createMutation.mutate()
    }
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1">
        <Header />
        <main className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold">Budgets</h2>
            <button
              onClick={() => {
                setEditing(null)
                setForm(emptyForm)
                setShowForm(!showForm)
              }}
              className="bg-purple-600 text-white px-4 py-2 rounded text-sm"
            >
              {showForm || editing ? 'Cancel' : 'Create Budget'}
            </button>
          </div>

          {(showForm || editing) && (
            <div className="bg-white rounded-lg shadow p-6 mb-6">
              <h3 className="font-semibold mb-4">
                {editing ? `Edit Budget: ${editing.name}` : 'Create Budget'}
              </h3>
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium mb-1">Name *</label>
                    <input
                      value={form.name}
                      onChange={(e) => setForm({ ...form, name: e.target.value })}
                      className="w-full border rounded px-3 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Period type</label>
                    <select
                      value={form.period_type}
                      onChange={(e) =>
                        setForm({
                          ...form,
                          period_type: e.target.value as BudgetForm['period_type'],
                        })
                      }
                      className="w-full border rounded px-3 py-2 text-sm"
                    >
                      <option value="monthly">Monthly</option>
                      <option value="quarterly">Quarterly</option>
                      <option value="yearly">Yearly</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Start date *</label>
                    <input
                      type="date"
                      value={form.start_date}
                      onChange={(e) => setForm({ ...form, start_date: e.target.value })}
                      className="w-full border rounded px-3 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">End date *</label>
                    <input
                      type="date"
                      value={form.end_date}
                      onChange={(e) => setForm({ ...form, end_date: e.target.value })}
                      className="w-full border rounded px-3 py-2 text-sm"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Currency</label>
                    <input
                      value={form.currency}
                      maxLength={3}
                      onChange={(e) =>
                        setForm({ ...form, currency: e.target.value.toUpperCase() })
                      }
                      className="w-full border rounded px-3 py-2 text-sm uppercase"
                    />
                  </div>
                </div>

                <div>
                  <p className="text-sm font-medium mb-2">Budget lines</p>
                  {form.lines.map((line, index) => (
                    <div key={index} className="flex gap-2 mb-2">
                      <select
                        value={line.account_id}
                        onChange={(e) => setLine(index, 'account_id', e.target.value)}
                        className="flex-1 border rounded px-3 py-2 text-sm"
                      >
                        <option value="">Select expense account</option>
                        {expenseAccounts.map((account) => (
                          <option key={account.id} value={account.id}>
                            {account.code} — {account.name_en}
                          </option>
                        ))}
                      </select>
                      <input
                        type="number"
                        min="0"
                        placeholder="Planned"
                        value={line.planned_amount}
                        onChange={(e) => setLine(index, 'planned_amount', e.target.value)}
                        className="w-32 border rounded px-3 py-2 text-sm"
                      />
                      <input
                        type="number"
                        min="0"
                        max="100"
                        placeholder="Alert %"
                        value={line.alert_percentage}
                        onChange={(e) =>
                          setLine(index, 'alert_percentage', e.target.value)
                        }
                        className="w-24 border rounded px-3 py-2 text-sm"
                      />
                      {form.lines.length > 1 && (
                        <button
                          onClick={() =>
                            setForm({
                              ...form,
                              lines: form.lines.filter((_, i) => i !== index),
                            })
                          }
                          className="text-red-600 text-sm"
                        >
                          ×
                        </button>
                      )}
                    </div>
                  ))}
                  <button
                    onClick={() =>
                      setForm({
                        ...form,
                        lines: [
                          ...form.lines,
                          { account_id: '', planned_amount: '', alert_percentage: '80' },
                        ],
                      })
                    }
                    className="text-purple-600 text-sm hover:underline"
                  >
                    + Add line
                  </button>
                </div>

                {actionError && <p className="text-red-600 text-sm">{actionError}</p>}
                <div className="flex gap-2">
                  <button
                    onClick={submitForm}
                    disabled={
                      createMutation.isPending ||
                      updateMutation.isPending ||
                      !form.name.trim() ||
                      !form.start_date ||
                      !form.end_date ||
                      toPayload().lines.length === 0
                    }
                    className="bg-purple-600 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
                  >
                    {editing
                      ? updateMutation.isPending
                        ? 'Saving...'
                        : 'Save changes'
                      : createMutation.isPending
                        ? 'Creating...'
                        : 'Create'}
                  </button>
                </div>
              </div>
            </div>
          )}

          {isLoading ? (
            <p className="text-gray-500">Loading...</p>
          ) : (budgets || []).length === 0 ? (
            <div className="bg-white rounded-lg shadow p-8 text-center">
              <p className="text-gray-500 mb-4">No budgets created yet</p>
              <p className="text-sm text-gray-400">
                Create a budget to track planned vs actual spending.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {(budgets || []).map((budget) => (
                <div key={budget.id} className="bg-white rounded-lg shadow p-6">
                  <div className="flex justify-between items-start">
                    <div>
                      <h3 className="text-lg font-semibold">{budget.name}</h3>
                      <p className="text-sm text-gray-500">
                        {budget.period_type} &middot; {budget.start_date} to{' '}
                        {budget.end_date}
                      </p>
                    </div>
                    <div className="flex items-center gap-3">
                      <span
                        className={`px-2 py-1 rounded text-xs ${
                          budget.status === 'active'
                            ? 'bg-green-100 text-green-800'
                            : budget.status === 'closed'
                              ? 'bg-gray-100 text-gray-800'
                              : 'bg-yellow-100 text-yellow-800'
                        }`}
                      >
                        {budget.status}
                      </span>
                      <button
                        onClick={() => startEdit(budget)}
                        disabled={budget.status === 'closed'}
                        className="text-purple-600 hover:underline text-sm disabled:opacity-40"
                      >
                        Edit
                      </button>
                      {budget.status === 'draft' && (
                        <button
                          onClick={() => {
                            if (
                              window.confirm(
                                `Activate budget "${budget.name}"? Active budgets cannot be deleted.`,
                              )
                            ) {
                              updateMutation.mutate({
                                id: budget.id,
                                body: { status: 'active' },
                              })
                            }
                          }}
                          className="text-green-600 hover:underline text-sm"
                        >
                          Activate
                        </button>
                      )}
                      {budget.status === 'active' && (
                        <button
                          onClick={() => {
                            if (
                              window.confirm(
                                `Close budget "${budget.name}"? Closing is permanent.`,
                              )
                            ) {
                              updateMutation.mutate({
                                id: budget.id,
                                body: { status: 'closed' },
                              })
                            }
                          }}
                          className="text-amber-600 hover:underline text-sm"
                        >
                          Close
                        </button>
                      )}
                      {(budget.status === 'draft' || budget.status === 'closed') && (
                        <button
                          onClick={() => {
                            if (
                              window.confirm(
                                `Delete budget "${budget.name}"? This cannot be undone.`,
                              )
                            ) {
                              deleteMutation.mutate(budget.id)
                            }
                          }}
                          className="text-red-600 hover:underline text-sm"
                        >
                          Delete
                        </button>
                      )}
                    </div>
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
                          {budget.lines.map((line) => {
                            const account = accounts.find(
                              (a) => a.id === String(line.account_id),
                            )
                            return (
                              <tr key={line.id} className="border-b">
                                <td className="py-2">
                                  {account
                                    ? `${account.code} — ${account.name_en}`
                                    : String(line.account_id)}
                                </td>
                                <td className="py-2 text-right">
                                  {budget.currency}{' '}
                                  {line.planned_amount.toLocaleString()}
                                </td>
                                <td className="py-2 text-right">
                                  {line.alert_percentage}%
                                </td>
                              </tr>
                            )
                          })}
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