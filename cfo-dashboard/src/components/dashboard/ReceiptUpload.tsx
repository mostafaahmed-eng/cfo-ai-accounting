'use client'

import { useState, useRef } from 'react'
import apiClient from '@/lib/api-client'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import type { Document } from '@/lib/types'

export default function ReceiptUpload() {
  const fileRef = useRef<HTMLInputElement>(null)
  const [error, setError] = useState('')
  const queryClient = useQueryClient()

  const mutation = useMutation<Document, Error, File>({
    mutationFn: async (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      const { data } = await apiClient.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      return data
    },
    onSuccess: () => {
      if (fileRef.current) fileRef.current.value = ''
      setError('')
      queryClient.invalidateQueries({ queryKey: ['inbox'] })
    },
    onError: () => setError('Upload failed. Use a valid JPG, PNG, or PDF within the configured size limit.'),
  })

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold mb-4">Upload Receipt</h3>
      <input
        ref={fileRef}
        type="file"
        accept=".jpg,.jpeg,.png,.pdf"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) mutation.mutate(file)
        }}
        className="text-sm"
      />
      {mutation.isPending && <p className="text-sm text-gray-500 mt-2">Uploading...</p>}
      {mutation.data && <p className="text-sm text-green-600 mt-2">Uploaded and queued for processing</p>}
      {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
    </div>
  )
}
