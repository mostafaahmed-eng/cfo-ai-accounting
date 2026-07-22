'use client'

import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/api-client'
import type { TelegramStatus } from '@/lib/types'

export default function TelegramSettingsPage() {
  const queryClient = useQueryClient()

  const { data: status } = useQuery<TelegramStatus>({
    queryKey: ['telegram-status'],
    queryFn: async () => {
      const { data } = await apiClient.get('/integrations/telegram/status')
      return data
    },
  })

  const connectMutation = useMutation({
    mutationFn: async () => {
      await apiClient.post('/integrations/telegram/connect')
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['telegram-status'] })
    },
  })

  const disconnectMutation = useMutation({
    mutationFn: async () => {
      await apiClient.delete('/integrations/telegram/disconnect')
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['telegram-status'] })
    },
  })

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1">
        <Header />
        <main className="p-6">
          <h2 className="text-2xl font-bold mb-6">Telegram Settings</h2>
          <div className="bg-white rounded-lg shadow p-6 max-w-lg">
            <div className="flex items-center gap-3 mb-6">
              <span className={`w-3 h-3 rounded-full ${status?.connected ? 'bg-green-500' : 'bg-gray-300'}`} />
              <span className="font-medium">{status?.connected ? 'Connected' : 'Not Connected'}</span>
            </div>

            {status?.connected ? (
              <div className="space-y-4">
                <div className="text-sm">
                  <p><strong>Bot:</strong> @{status.bot_username}</p>
                  <p><strong>Chat ID:</strong> {status.chat_id}</p>
                </div>
                <button
                  onClick={() => disconnectMutation.mutate()}
                  disabled={disconnectMutation.isPending}
                  className="bg-red-600 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
                >
                  Disconnect
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <p className="text-sm text-gray-500">
                  Connect your Telegram bot to process expenses and receipts from chat messages.
                </p>
                <button
                  onClick={() => connectMutation.mutate()}
                  disabled={connectMutation.isPending}
                  className="bg-blue-600 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
                >
                  {connectMutation.isPending ? 'Connecting...' : 'Connect Bot'}
                </button>
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}
