'use client'

import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient, { fetchAll } from '@/lib/api-client'
import { useCompany } from '@/contexts/CompanyContext'
import type { Company, ExchangeRate } from '@/lib/types'
import { useState } from 'react'

interface RateForm {
  quote_currency: string
  rate: string
  rate_date: string
  source: string
}

const emptyForm: RateForm = {
  quote_currency: '',
  rate: '',
  rate_date: '',
  source: 'manual',
}

function apiError(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } })?.response
    ?.data?.detail
  return typeof detail === 'string' ? detail : 'Request failed'
}

export default function ExchangeRatesPage() {
  const queryClient = useQueryClient()
  const { selectedCompanyId } = useCompany()
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState<RateForm>(emptyForm)
  const [actionError, setActionError] = useState('')

  const { data: rates, isLoading } = useQuery<ExchangeRate[]>({
    queryKey: ['exchange-rates', selectedCompanyId],
    queryFn: () => fetchAll<ExchangeRate>('/exchange-rates'),
    enabled: Boolean(selectedCompanyId),
  })

  const { data: company } = useQuery<Company>({
    queryKey: ['company-detail', selectedCompanyId],
    queryFn: async () => {
      const { data } = await apiClient.get(`/companies/${selectedCompanyId}`)
      return data
    },
    enabled: Boolean(selectedCompanyId),
  })

  const invalidate = () =>
    queryClient.invalidateQueries({
      queryKey: ['exchange-rates', selectedCompanyId],
    })

  const createMutation = useMutation({
    mutationFn: async (payload: RateForm) => {
      const { data } = await apiClient.post('/exchange-rates', {
        base_currency: company?.base_currency,
        quote_currency: payload.quote_currency.toUpperCase(),
        rate: Number(payload.rate),
        rate_date: payload.rate_date,
        source: payload.source || 'manual',
      })
      return data
    },
    onSuccess: () => {
      invalidate()
      setShowForm(false)
      setForm(emptyForm)
      setActionError('')
    },
    onError: (error) => setActionError(apiError(error)),
  })

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1">
        <Header />
        <main className="p-6">
          <div className="flex justify-between items-center mb-6">
            <h2 className="text-2xl font-bold">Exchange Rates</h2>
            <button
              onClick={() => {
                setShowForm(!showForm)
                setActionError('')
              }}
              className="bg-purple-600 text-white px-4 py-2 rounded text-sm"
            >
              {showForm ? 'Cancel' : 'Add Rate'}
            </button>
          </div>

          <p className="text-sm text-gray-500 mb-4">
            Rates are stored as base-currency units per one unit of the quote
            currency (base currency: {company?.base_currency || '…'}). They are
            used to convert transactions into {company?.base_currency || 'the base currency'} for
            reporting.
          </p>

          {showForm && (
            <div className="bg-white rounded-lg shadow p-6 mb-6 max-w-lg">
              <h3 className="font-semibold mb-4">
                Add rate for {company?.base_currency || 'base'} → quote
              </h3>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Quote currency *</label>
                  <input
                    value={form.quote_currency}
                    maxLength={3}
                    onChange={(e) =>
                      setForm({ ...form, quote_currency: e.target.value.toUpperCase() })
                    }
                    placeholder="EUR"
                    className="w-full border rounded px-3 py-2 text-sm uppercase"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Rate ({company?.base_currency || 'base'} per 1 quote) *
                  </label>
                  <input
                    type="number"
                    step="0.00000001"
                    min="0.00000001"
                    value={form.rate}
                    onChange={(e) => setForm({ ...form, rate: e.target.value })}
                    placeholder="0.85"
                    className="w-full border rounded px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Date *</label>
                  <input
                    type="date"
                    value={form.rate_date}
                    onChange={(e) => setForm({ ...form, rate_date: e.target.value })}
                    className="w-full border rounded px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Source</label>
                  <input
                    value={form.source}
                    onChange={(e) => setForm({ ...form, source: e.target.value })}
                    placeholder="manual"
                    className="w-full border rounded px-3 py-2 text-sm"
                  />
                </div>
                {actionError && <p className="text-red-600 text-sm">{actionError}</p>}
                <button
                  onClick={() => createMutation.mutate(form)}
                  disabled={
                    createMutation.isPending ||
                    !form.quote_currency.trim() ||
                    !form.rate ||
                    !form.rate_date
                  }
                  className="bg-purple-600 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
                >
                  {createMutation.isPending ? 'Adding...' : 'Add rate'}
                </button>
              </div>
            </div>
          )}

          {isLoading ? (
            <p className="text-gray-500">Loading...</p>
          ) : (rates || []).length === 0 ? (
            <div className="bg-white rounded-lg shadow p-8 text-center">
              <p className="text-gray-500 mb-4">No exchange rates yet</p>
              <p className="text-sm text-gray-400">
                Add rates to enable multi-currency reporting.
              </p>
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow">
              <table className="w-full">
                <thead>
                  <tr className="border-b text-left text-sm text-gray-500">
                    <th className="p-4">Base</th>
                    <th className="p-4">Quote</th>
                    <th className="p-4">Rate</th>
                    <th className="p-4">Date</th>
                    <th className="p-4">Source</th>
                  </tr>
                </thead>
                <tbody>
                  {(rates || []).map((rate) => (
                    <tr key={rate.id} className="border-b hover:bg-gray-50">
                      <td className="p-4 text-sm font-medium">{rate.base_currency}</td>
                      <td className="p-4 text-sm font-medium">{rate.quote_currency}</td>
                      <td className="p-4 text-sm font-mono">{rate.rate}</td>
                      <td className="p-4 text-sm">{rate.rate_date}</td>
                      <td className="p-4 text-sm">{rate.source}</td>
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