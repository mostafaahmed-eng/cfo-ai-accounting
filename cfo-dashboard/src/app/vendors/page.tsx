'use client'

import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient, { fetchAll } from '@/lib/api-client'
import { useCompany } from '@/contexts/CompanyContext'
import type { Vendor } from '@/lib/types'
import { useState } from 'react'

export default function VendorsPage() {
  const queryClient = useQueryClient()
  const { selectedCompanyId } = useCompany()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({ name: '', email: '', phone: '' })

  const { data: vendors, isLoading } = useQuery<Vendor[]>({
    queryKey: ['vendors', selectedCompanyId],
    queryFn: () => fetchAll<Vendor>('/vendors'),
    enabled: Boolean(selectedCompanyId),
  })

  const createMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post('/vendors', form)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['vendors'] })
      setShowForm(false)
      setForm({ name: '', email: '', phone: '' })
    },
  })

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1">
        <Header />
        <main className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold">Vendors</h2>
            <button onClick={() => setShowForm(!showForm)} className="bg-blue-600 text-white px-4 py-2 rounded text-sm">
              {showForm ? 'Cancel' : 'Add Vendor'}
            </button>
          </div>

          {showForm && (
            <div className="bg-white rounded-lg shadow p-6 mb-6 max-w-lg">
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Name</label>
                  <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className="w-full border rounded px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Email</label>
                  <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} className="w-full border rounded px-3 py-2 text-sm" />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Phone</label>
                  <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} className="w-full border rounded px-3 py-2 text-sm" />
                </div>
                <button onClick={() => createMutation.mutate()} disabled={createMutation.isPending || !form.name} className="bg-blue-600 text-white px-4 py-2 rounded text-sm disabled:opacity-50">
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
                    <th className="p-4">Name</th>
                    <th className="p-4">Email</th>
                    <th className="p-4">Phone</th>
                    <th className="p-4">Country</th>
                    <th className="p-4">Active</th>
                  </tr>
                </thead>
                <tbody>
                  {(vendors || []).map((vendor) => (
                    <tr key={vendor.id} className="border-b hover:bg-gray-50">
                      <td className="p-4 text-sm font-medium">{vendor.name}</td>
                      <td className="p-4 text-sm">{vendor.email || '-'}</td>
                      <td className="p-4 text-sm">{vendor.phone || '-'}</td>
                      <td className="p-4 text-sm">{vendor.country_code || '-'}</td>
                      <td className="p-4 text-sm">{vendor.is_active ? 'Yes' : 'No'}</td>
                    </tr>
                  ))}
                  {(vendors || []).length === 0 && (
                    <tr><td colSpan={5} className="p-4 text-center text-gray-500">No vendors yet</td></tr>
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
