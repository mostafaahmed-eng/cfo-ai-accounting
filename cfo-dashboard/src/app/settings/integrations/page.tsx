'use client'

import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import { useQuery } from '@tanstack/react-query'
import apiClient from '@/lib/api-client'
import { useCompany } from '@/contexts/CompanyContext'
import type { TelegramStatus } from '@/lib/types'

export default function IntegrationsPage() {
  const { selectedCompanyId } = useCompany()
  const { data: tgStatus } = useQuery<TelegramStatus>({
    queryKey: ['telegram-status', selectedCompanyId],
    queryFn: async () => {
      const { data } = await apiClient.get('/integrations/telegram/status')
      return data
    },
    enabled: Boolean(selectedCompanyId),
  })

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1">
        <Header />
        <main className="p-6">
          <h2 className="text-2xl font-bold mb-6">Integrations</h2>
          <div className="bg-white rounded-lg shadow p-6 max-w-lg">
            <h3 className="text-lg font-semibold mb-4">Telegram Bot</h3>
            <div className="flex items-center gap-3 mb-4">
              <span className={`w-3 h-3 rounded-full ${tgStatus?.connected ? 'bg-green-500' : 'bg-gray-300'}`} />
              <span className="text-sm">{tgStatus?.connected ? `Connected as @${tgStatus.bot_username}` : 'Not connected'}</span>
            </div>
            <p className="text-sm text-gray-500">
              Connect a Telegram bot to receive and process expense messages and receipt photos directly from chat.
            </p>
          </div>
        </main>
      </div>
    </div>
  )
}
