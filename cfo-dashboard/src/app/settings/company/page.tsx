'use client'

import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/api-client'
import { useState } from 'react'

export default function CompanySettingsPage() {
  const queryClient = useQueryClient()
  const [form, setForm] = useState({
    name: '', legal_name: '', country_code: '', base_currency: 'USD',
    fiscal_year_start: 1, timezone: 'UTC', tax_number: '',
  })

  const createMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post('/companies', form)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['company'] })
    },
  })

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1">
        <Header />
        <main className="p-6">
          <h2 className="text-2xl font-bold mb-6">Company Settings</h2>
          <div className="bg-white rounded-lg shadow p-6 max-w-lg">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Company Name *</label>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full border rounded px-3 py-2 text-sm" placeholder="My Company" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Legal Name</label>
                <input value={form.legal_name} onChange={(e) => setForm({ ...form, legal_name: e.target.value })}
                  className="w-full border rounded px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Country Code *</label>
                <input value={form.country_code} onChange={(e) => setForm({ ...form, country_code: e.target.value })}
                  className="w-full border rounded px-3 py-2 text-sm" placeholder="US" maxLength={2} />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Base Currency *</label>
                <input value={form.base_currency} onChange={(e) => setForm({ ...form, base_currency: e.target.value })}
                  className="w-full border rounded px-3 py-2 text-sm" placeholder="USD" maxLength={3} />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Fiscal Year Start Month</label>
                <input type="number" min={1} max={12} value={form.fiscal_year_start}
                  onChange={(e) => setForm({ ...form, fiscal_year_start: Number(e.target.value) })}
                  className="w-full border rounded px-3 py-2 text-sm" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Timezone</label>
                <input value={form.timezone} onChange={(e) => setForm({ ...form, timezone: e.target.value })}
                  className="w-full border rounded px-3 py-2 text-sm" placeholder="UTC" />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Tax Number</label>
                <input value={form.tax_number} onChange={(e) => setForm({ ...form, tax_number: e.target.value })}
                  className="w-full border rounded px-3 py-2 text-sm" />
              </div>
              <button
                onClick={() => createMutation.mutate()}
                disabled={!form.name || !form.country_code || !form.base_currency || createMutation.isPending}
                className="bg-blue-600 text-white px-6 py-2 rounded text-sm disabled:opacity-50"
              >
                {createMutation.isPending ? 'Creating...' : 'Create Company'}
              </button>
              {createMutation.isError && <p className="text-red-600 text-sm">Failed to create company</p>}
              {createMutation.isSuccess && <p className="text-green-600 text-sm">Company created successfully</p>}
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
