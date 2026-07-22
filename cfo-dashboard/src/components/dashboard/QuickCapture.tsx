'use client'

import { useState } from 'react'
import apiClient from '@/lib/api-client'
import { useMutation, useQueryClient } from '@tanstack/react-query'

export default function QuickCapture() {
  const [text, setText] = useState('')
  const queryClient = useQueryClient()

  const mutation = useMutation({
    mutationFn: async () => {
      await apiClient.post('/intake/text', { text })
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
          disabled={!text || mutation.isPending}
          className="bg-blue-600 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
        >
          {mutation.isPending ? 'Submitting...' : 'Submit'}
        </button>
      </div>
      {mutation.isError && <p className="text-red-600 text-sm mt-2">Failed to submit</p>}
      {mutation.isSuccess && <p className="text-green-600 text-sm mt-2">Submitted successfully</p>}
    </div>
  )
}
