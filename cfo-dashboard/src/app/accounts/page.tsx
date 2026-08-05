'use client'

import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/api-client'
import { useCompany } from '@/contexts/CompanyContext'
import type { Account } from '@/lib/types'
import { useState } from 'react'

export default function AccountsPage() {
  const queryClient = useQueryClient()
  const { selectedCompanyId } = useCompany()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ code: '', name_en: '', type: 'expense', subtype: 'general' })

  const { data: accounts, isLoading } = useQuery<Account[]>({
    queryKey: ['accounts', selectedCompanyId],
    queryFn: async () => {
      const { data } = await apiClient.get('/accounts')
      return data
    },
    enabled: Boolean(selectedCompanyId),
  })

  const createMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post('/accounts', form)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accounts'] })
      setShowForm(false)
      setForm({ code: '', name_en: '', type: 'expense', subtype: 'general' })
    },
  })

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1">
        <Header />
        <main className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold">Chart of Accounts</h2>
            <button onClick={() => setShowForm(!showForm)} className="bg-blue-600 text-white px-4 py-2 rounded text-sm">
              {showForm ? 'Cancel' : 'Add Account'}
            </button>
          </div>

          {showForm && (
            <div className="bg-white rounded-lg shadow p-6 mb-6 max-w-lg">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Code</label>
                  <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} className="w-full border rounded px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Name</label>
                  <input value={form.name_en} onChange={(e) => setForm({ ...form, name_en: e.target.value })} className="w-full border rounded px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Type</label>
                  <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })} className="w-full border rounded px-3 py-2 text-sm">
                    <option value="asset">Asset</option>
                    <option value="liability">Liability</option>
                    <option value="equity">Equity</option>
                    <option value="revenue">Revenue</option>
                    <option value="expense">Expense</option>
                  </select>
                </div>
                <button onClick={() => createMutation.mutate()} disabled={createMutation.isPending} className="bg-blue-600 text-white px-4 py-2 rounded text-sm disabled:opacity-50">
                  Create
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
                    <th className="p-4">Active</th>
                  </tr>
                </thead>
                <tbody>
                  {(accounts || []).map((account) => (
                    <tr key={account.id} className="border-b hover:bg-gray-50">
                      <td className="p-4 text-sm font-mono">{account.code}</td>
                      <td className="p-4 text-sm">{account.name_en}</td>
                      <td className="p-4 text-sm capitalize">{account.type}</td>
                      <td className="p-4 text-sm">{account.subtype}</td>
                      <td className="p-4 text-sm">{account.is_payment_account ? 'Yes' : 'No'}</td>
                      <td className="p-4 text-sm">{account.is_active ? 'Yes' : 'No'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
