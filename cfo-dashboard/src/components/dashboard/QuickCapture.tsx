'use client'

import { useState } from 'react'
import axios from 'axios'
import apiClient from '@/lib/api-client'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useCompany } from '@/contexts/CompanyContext'
import type { InboxItem } from '@/lib/types'

export default function QuickCapture() {
  const [text, setText] = useState('')
  const { selectedCompanyId } = useCompany()
  const queryClient = useQueryClient()
  const companyReady = Boolean(selectedCompanyId)

  const mutation = useMutation<InboxItem>({
    mutationFn: async () => {
      const { data } = await apiClient.post('/intake/text', {
        text,
        idempotency_key: crypto.randomUUID(),
      })
      return data
    },
    onSuccess: () => {
      setText('')
      queryClient.invalidateQueries({ queryKey: ['inbox'] })
      queryClient.invalidateQueries({ queryKey: ['dashboard'] })
    },
  })

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold mb-4">Quick Capture</h3>
      <div className="flex gap-2">
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="I spent $100 for VPS..."
          className="flex-1 border rounded px-3 py-2 text-sm"
        />
        <button
          onClick={() => mutation.mutate()}
          disabled={!companyReady || !text || mutation.isPending}
          title={companyReady ? undefined : 'Waiting for company context...'}
          className="bg-brand-600 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
        >
          {mutation.isPending ? 'Submitting...' : 'Submit'}
        </button>
      </div>
      {!companyReady && (
        <p className="text-gray-500 text-sm mt-2">Loading company context...</p>
      )}
      {mutation.isError && (
        <p className="text-red-600 text-sm mt-2">
          {axios.isAxiosError(mutation.error)
            ? (mutation.error.response?.data as { detail?: string })?.detail ?? 'Failed to submit'
            : 'Failed to submit'}
        </p>
      )}
      {mutation.isSuccess && !mutation.isPending && (
        <p className="text-green-600 text-sm mt-2">
          Submitted: {mutation.data.status === 'queued' ? 'queued for processing' : mutation.data.status}
        </p>
      )}
    </div>
  )
}
