'use client'

import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient, { fetchAll } from '@/lib/api-client'
import { useCompany } from '@/contexts/CompanyContext'
import type { Account } from '@/lib/types'
import { useState } from 'react'

const ACCOUNT_TYPES = ['asset', 'liability', 'equity', 'revenue', 'expense']

interface AccountForm {
  code: string
  name_en: string
  type: string
  subtype: string
  currency: string
  is_payment_account: boolean
}

const emptyForm: AccountForm = {
  code: '',
  name_en: '',
  type: 'expense',
  subtype: 'general',
  currency: '',
  is_payment_account: false,
}

export default function AccountsPage() {
  const queryClient = useQueryClient()
  const { selectedCompanyId } = useCompany()
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<Account | null>(null)
  const [form, setForm] = useState<AccountForm>(emptyForm)
  const [actionError, setActionError] = useState('')

  const { data: accounts, isLoading } = useQuery<Account[]>({
    queryKey: ['accounts', selectedCompanyId],
    queryFn: () => fetchAll<Account>('/accounts'),
    enabled: Boolean(selectedCompanyId),
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['accounts', selectedCompanyId] })

  const createMutation = useMutation({
    mutationFn: async (payload: AccountForm) => {
      await apiClient.post('/accounts', {
        code: payload.code,
        name_en: payload.name_en,
        type: payload.type,
        subtype: payload.subtype,
        currency: payload.currency || null,
        parent_account_id: null,
        is_payment_account: payload.is_payment_account,
      })
    },
    onSuccess: () => {
      invalidate()
      setShowForm(false)
      setForm(emptyForm)
      setActionError('')
    },
    onError: (error) => setActionError('Failed to create account'),
  })

  const updateMutation = useMutation({
    mutationFn: async (payload: { id: string; form: AccountForm }) => {
      const { data } = await apiClient.patch(`/accounts/${payload.id}`, {
        name_en: payload.form.name_en,
        subtype: payload.form.subtype,
        currency: payload.form.currency || null,
        is_payment_account: payload.form.is_payment_account,
      })
      return data
    },
    onSuccess: () => {
      invalidate()
      setEditing(null)
      setActionError('')
    },
    onError: () => setActionError('Failed to update account'),
  })

  const toggleActiveMutation = useMutation({
    mutationFn: async (account: Account) => {
      await apiClient.patch(`/accounts/${account.id}`, {
        is_active: !account.is_active,
      })
    },
    onSuccess: invalidate,
    onError: () => setActionError('Failed to update account status'),
  })

  const startEdit = (account: Account) => {
    setEditing(account)
    setForm({
      code: account.code,
      name_en: account.name_en,
      type: account.type,
      subtype: account.subtype,
      currency: account.currency || '',
      is_payment_account: account.is_payment_account,
    })
    setShowForm(false)
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1">
        <Header />
        <main className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold">Chart of Accounts</h2>
            <button
              onClick={() => {
                setEditing(null)
                setForm(emptyForm)
                setShowForm(!showForm)
              }}
              className="bg-purple-600 text-white px-4 py-2 rounded text-sm"
            >
              {showForm || editing ? 'Cancel' : 'Add Account'}
            </button>
          </div>

          {(showForm || editing) && (
            <div className="bg-white rounded-lg shadow p-6 mb-6 max-w-lg">
              <h3 className="font-semibold mb-4">
                {editing ? `Edit Account ${editing.code}` : 'Create Account'}
              </h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Code</label>
                  <input
                    value={form.code}
                    disabled={Boolean(editing)}
                    onChange={(e) => setForm({ ...form, code: e.target.value })}
                    className="w-full border rounded px-3 py-2 text-sm disabled:bg-gray-100"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Name</label>
                  <input
                    value={form.name_en}
                    onChange={(e) => setForm({ ...form, name_en: e.target.value })}
                    className="w-full border rounded px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Type</label>
                  <select
                    value={form.type}
                    onChange={(e) => setForm({ ...form, type: e.target.value })}
                    className="w-full border rounded px-3 py-2 text-sm"
                  >
                    {ACCOUNT_TYPES.map((type) => (
                      <option key={type} value={type}>
                        {type.charAt(0).toUpperCase() + type.slice(1)}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Subtype</label>
                  <input
                    value={form.subtype}
                    onChange={(e) => setForm({ ...form, subtype: e.target.value })}
                    className="w-full border rounded px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Currency (optional)</label>
                  <input
                    value={form.currency}
                    maxLength={3}
                    onChange={(e) => setForm({ ...form, currency: e.target.value.toUpperCase() })}
                    placeholder="USD"
                    className="w-full border rounded px-3 py-2 text-sm uppercase"
                  />
                </div>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.is_payment_account}
                    onChange={(e) =>
                      setForm({ ...form, is_payment_account: e.target.checked })
                    }
                  />
                  Payment account
                </label>
                {actionError && <p className="text-red-600 text-sm">{actionError}</p>}
                <button
                  onClick={() =>
                    editing
                      ? updateMutation.mutate({ id: editing.id, form })
                      : createMutation.mutate(form)
                  }
                  disabled={
                    createMutation.isPending ||
                    updateMutation.isPending ||
                    !form.code ||
                    !form.name_en
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
          )}

          {isLoading ? (
            <p className="text-gray-500">Loading...</p>
          ) : (
            <div className="bg-white rounded-lg shadow">
              <table className="w-full">
                <thead>
                  <tr className="border-b text-left text-sm text-gray-500">
                    <th className="p-4">Code</th>
                    <th className="p-4">Name</th>
                    <th className="p-4">Type</th>
                    <th className="p-4">Subtype</th>
                    <th className="p-4">Payment</th>
                    <th className="p-4">Status</th>
                    <th className="p-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {(accounts || []).map((account) => (
                    <tr key={account.id} className="border-b hover:bg-gray-50">
                      <td className="p-4 text-sm font-mono">{account.code}</td>
                      <td className="p-4 text-sm">
                        {account.name_en}
                        {account.is_system && (
                          <span className="ml-2 rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-500">
                            system
                          </span>
                        )}
                      </td>
                      <td className="p-4 text-sm capitalize">{account.type}</td>
                      <td className="p-4 text-sm">{account.subtype}</td>
                      <td className="p-4 text-sm">{account.is_payment_account ? 'Yes' : 'No'}</td>
                      <td className="p-4 text-sm">
                        <span
                          className={`px-2 py-1 rounded text-xs ${
                            account.is_active
                              ? 'bg-green-100 text-green-700'
                              : 'bg-gray-100 text-gray-500'
                          }`}
                        >
                          {account.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="p-4 text-sm text-right">
                        <button
                          onClick={() => startEdit(account)}
                          className="text-purple-600 hover:underline text-xs mr-3"
                        >
                          Edit
                        </button>
                        {!account.is_system && (
                          <button
                            onClick={() => {
                              if (
                                window.confirm(
                                  account.is_active
                                    ? `Deactivate ${account.name_en}? It will stop being usable in new drafts.`
                                    : `Reactivate ${account.name_en}?`,
                                )
                              ) {
                                toggleActiveMutation.mutate(account)
                              }
                            }}
                            disabled={toggleActiveMutation.isPending}
                            className="text-red-600 hover:underline text-xs disabled:opacity-50"
                          >
                            {account.is_active ? 'Deactivate' : 'Reactivate'}
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                  {(accounts || []).length === 0 && (
                    <tr>
                      <td colSpan={7} className="p-4 text-center text-gray-500">
                        No accounts yet
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