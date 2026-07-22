'use client'

import { useState, useRef } from 'react'
import apiClient from '@/lib/api-client'
import { useMutation } from '@tanstack/react-query'

export default function ReceiptUpload() {
  const fileRef = useRef<HTMLInputElement>(null)
  const [error, setError] = useState('')

  const mutation = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData()
      formData.append('file', file)
      await apiClient.post('/documents/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    },
    onSuccess: () => {
      if (fileRef.current) fileRef.current.value = ''
      setError('')
    },
    onError: () => setError('Upload failed. Check file type (JPG/PNG/WEBP/PDF) and size (max 10MB).'),
  })

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold mb-4">Upload Receipt</h3>
      <input
        ref={fileRef}
        type="file"
        accept=".jpg,.jpeg,.png,.webp,.pdf"
        onChange={(e) => {
          const file = e.target.files?.[0]
          if (file) mutation.mutate(file)
        }}
        className="text-sm"
      />
      {mutation.isPending && <p className="text-sm text-gray-500 mt-2">Uploading...</p>}
      {mutation.isSuccess && <p className="text-sm text-green-600 mt-2">Uploaded successfully</p>}
      {error && <p className="text-sm text-red-600 mt-2">{error}</p>}
    </div>
  )
}
