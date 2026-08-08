'use client'

import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import { useQuery } from '@tanstack/react-query'
import apiClient, { fetchAll } from '@/lib/api-client'
import { useCompany } from '@/contexts/CompanyContext'
import type { InboxItem } from '@/lib/types'
import { useState } from 'react'

export default function InboxPage() {
  const [view, setView] = useState<'active' | 'archived'>('active')
  const { selectedCompanyId } = useCompany()
  const { data: items, isLoading } = useQuery<InboxItem[]>({
    queryKey: ['inbox', selectedCompanyId, view],
    queryFn: () =>
      fetchAll<InboxItem>(view === 'archived' ? '/intake' : '/intake', {
        status: view === 'archived' ? 'archived' : undefined,
      }),
    enabled: Boolean(selectedCompanyId),
    refetchInterval: (query) =>
      query.state.data?.some((item) => ['queued', 'processing'].includes(item.status))
        ? 3000
        : false,
  })

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1">
        <Header />
        <main className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-bold">Inbox</h2>
            <div className="flex gap-2">
              <button
                onClick={() => setView('active')}
                className={`px-3 py-2 rounded text-sm ${view === 'active' ? 'bg-brand-600 text-white' : 'bg-gray-100'}`}
              >
                Active
              </button>
              <button
                onClick={() => setView('archived')}
                className={`px-3 py-2 rounded text-sm ${view === 'archived' ? 'bg-brand-600 text-white' : 'bg-gray-100'}`}
              >
                Archived
              </button>
            </div>
          </div>
          {isLoading ? (
            <p className="text-gray-500">Loading...</p>
          ) : (
            <div className="bg-white rounded-lg shadow">
              <table className="w-full">
                <thead>
                  <tr className="border-b text-left text-sm text-gray-500">
                    <th className="p-4">Source</th>
                    <th className="p-4">Content</th>
                    <th className="p-4">Language</th>
                    <th className="p-4">Status</th>
                    <th className="p-4">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {(items || []).length === 0 ? (
                    <tr>
                      <td colSpan={5} className="p-4 text-center text-gray-500">
                        No inbox items. Submit text or upload a receipt from the dashboard.
                      </td>
                    </tr>
                  ) : (
                    (items || []).map((item) => (
                      <tr key={item.id} className="border-b hover:bg-gray-50">
                        <td className="p-4 text-sm">{item.source}</td>
                        <td className="p-4 text-sm truncate max-w-xs">{item.original_text || '-'}</td>
                        <td className="p-4 text-sm">{item.detected_language}</td>
                        <td className="p-4 text-sm">
                          <span className={`px-2 py-1 rounded text-xs ${
                            ['extracted', 'completed', 'review_required'].includes(item.status) ? 'bg-green-100 text-green-800' :
                            item.status === 'failed' ? 'bg-red-100 text-red-800' :
                            'bg-yellow-100 text-yellow-800'
                          }`}>
                            {item.duplicate_status === 'likely_duplicate' || item.duplicate_status === 'exact_duplicate'
                              ? 'Likely duplicate'
                              : item.status === 'review_required'
                                ? 'Ready for review'
                                : item.status}
                          </span>
                          {item.error_message && (
                            <p className="mt-1 text-xs text-red-700">{item.error_message}</p>
                          )}
                          {item.duplicate_reason && (
                            <p className="mt-1 text-xs text-amber-700">{item.duplicate_reason}</p>
                          )}
                        </td>
                        <td className="p-4 text-sm text-gray-500">
                          {new Date(item.created_at).toLocaleDateString()}
                        </td>
                      </tr>
                    ))
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
