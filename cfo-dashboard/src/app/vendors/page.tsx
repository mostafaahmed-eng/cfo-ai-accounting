'use client'

import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient, { fetchAll } from '@/lib/api-client'
import { useCompany } from '@/contexts/CompanyContext'
import type { Vendor } from '@/lib/types'
import { useState } from 'react'

interface VendorForm {
  name: string
  email: string
  phone: string
  tax_number: string
  country_code: string
  default_currency: string
}

const emptyForm: VendorForm = {
  name: '',
  email: '',
  phone: '',
  tax_number: '',
  country_code: '',
  default_currency: '',
}

export default function VendorsPage() {
  const queryClient = useQueryClient()
  const { selectedCompanyId } = useCompany()
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<Vendor | null>(null)
  const [form, setForm] = useState<VendorForm>(emptyForm)
  const [actionError, setActionError] = useState('')

  const { data: vendors, isLoading } = useQuery<Vendor[]>({
    queryKey: ['vendors', selectedCompanyId],
    queryFn: () => fetchAll<Vendor>('/vendors'),
    enabled: Boolean(selectedCompanyId),
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['vendors', selectedCompanyId] })

  const createMutation = useMutation({
    mutationFn: async (payload: VendorForm) => {
      await apiClient.post('/vendors', {
        name: payload.name,
        email: payload.email || null,
        phone: payload.phone || null,
        tax_number: payload.tax_number || null,
        country_code: payload.country_code || null,
        default_currency: payload.default_currency || null,
      })
    },
    onSuccess: () => {
      invalidate()
      setShowForm(false)
      setForm(emptyForm)
      setActionError('')
    },
    onError: () => setActionError('Failed to create vendor'),
  })

  const updateMutation = useMutation({
    mutationFn: async (payload: { id: string; form: VendorForm }) => {
      const { data } = await apiClient.patch(`/vendors/${payload.id}`, {
        name: payload.form.name,
        email: payload.form.email || null,
        phone: payload.form.phone || null,
        tax_number: payload.form.tax_number || null,
        country_code: payload.form.country_code || null,
        default_currency: payload.form.default_currency || null,
      })
      return data
    },
    onSuccess: () => {
      invalidate()
      setEditing(null)
      setActionError('')
    },
    onError: () => setActionError('Failed to update vendor'),
  })

  const toggleActiveMutation = useMutation({
    mutationFn: async (vendor: Vendor) => {
      await apiClient.patch(`/vendors/${vendor.id}`, {
        is_active: !vendor.is_active,
      })
    },
    onSuccess: invalidate,
    onError: () => setActionError('Failed to update vendor status'),
  })

  const startEdit = (vendor: Vendor) => {
    setEditing(vendor)
    setForm({
      name: vendor.name,
      email: vendor.email || '',
      phone: vendor.phone || '',
      tax_number: vendor.tax_number || '',
      country_code: vendor.country_code || '',
      default_currency: vendor.default_currency || '',
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
            <h2 className="text-2xl font-bold">Vendors</h2>
            <button
              onClick={() => {
                setEditing(null)
                setForm(emptyForm)
                setShowForm(!showForm)
              }}
              className="bg-purple-600 text-white px-4 py-2 rounded text-sm"
            >
              {showForm || editing ? 'Cancel' : 'Add Vendor'}
            </button>
          </div>

          {(showForm || editing) && (
            <div className="bg-white rounded-lg shadow p-6 mb-6 max-w-lg">
              <h3 className="font-semibold mb-4">
                {editing ? `Edit Vendor: ${editing.name}` : 'Create Vendor'}
              </h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Name *</label>
                  <input
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="w-full border rounded px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Email</label>
                  <input
                    type="email"
                    value={form.email}
                    onChange={(e) => setForm({ ...form, email: e.target.value })}
                    className="w-full border rounded px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Phone</label>
                  <input
                    value={form.phone}
                    onChange={(e) => setForm({ ...form, phone: e.target.value })}
                    className="w-full border rounded px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Tax number</label>
                  <input
                    value={form.tax_number}
                    onChange={(e) => setForm({ ...form, tax_number: e.target.value })}
                    className="w-full border rounded px-3 py-2 text-sm"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium mb-1">Country code</label>
                    <input
                      value={form.country_code}
                      maxLength={2}
                      onChange={(e) =>
                        setForm({ ...form, country_code: e.target.value.toUpperCase() })
                      }
                      placeholder="US"
                      className="w-full border rounded px-3 py-2 text-sm uppercase"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Default currency</label>
                    <input
                      value={form.default_currency}
                      maxLength={3}
                      onChange={(e) =>
                        setForm({ ...form, default_currency: e.target.value.toUpperCase() })
                      }
                      placeholder="USD"
                      className="w-full border rounded px-3 py-2 text-sm uppercase"
                    />
                  </div>
                </div>
                {actionError && <p className="text-red-600 text-sm">{actionError}</p>}
                <button
                  onClick={() =>
                    editing
                      ? updateMutation.mutate({ id: editing.id, form })
                      : createMutation.mutate(form)
                  }
                  disabled={
                    (createMutation.isPending ||
                      updateMutation.isPending ||
                      !form.name.trim())
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
                    <th className="p-4">Name</th>
                    <th className="p-4">Email</th>
                    <th className="p-4">Phone</th>
                    <th className="p-4">Country</th>
                    <th className="p-4">Status</th>
                    <th className="p-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {(vendors || []).map((vendor) => (
                    <tr key={vendor.id} className="border-b hover:bg-gray-50">
                      <td className="p-4 text-sm font-medium">{vendor.name}</td>
                      <td className="p-4 text-sm">{vendor.email || '-'}</td>
                      <td className="p-4 text-sm">{vendor.phone || '-'}</td>
                      <td className="p-4 text-sm">{vendor.country_code || '-'}</td>
                      <td className="p-4 text-sm">
                        <span
                          className={`px-2 py-1 rounded text-xs ${
                            vendor.is_active
                              ? 'bg-green-100 text-green-700'
                              : 'bg-gray-100 text-gray-500'
                          }`}
                        >
                          {vendor.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="p-4 text-sm text-right">
                        <button
                          onClick={() => startEdit(vendor)}
                          className="text-purple-600 hover:underline text-xs mr-3"
                        >
                          Edit
                        </button>
                        <button
                          onClick={() => {
                            if (
                              window.confirm(
                                vendor.is_active
                                  ? `Deactivate ${vendor.name}?`
                                  : `Reactivate ${vendor.name}?`,
                              )
                            ) {
                              toggleActiveMutation.mutate(vendor)
                            }
                          }}
                          disabled={toggleActiveMutation.isPending}
                          className="text-red-600 hover:underline text-xs disabled:opacity-50"
                        >
                          {vendor.is_active ? 'Deactivate' : 'Reactivate'}
                        </button>
                      </td>
                    </tr>
                  ))}
                  {(vendors || []).length === 0 && (
                    <tr>
                      <td colSpan={6} className="p-4 text-center text-gray-500">
                        No vendors yet
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