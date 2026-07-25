'use client'

import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import { useQuery } from '@tanstack/react-query'
import apiClient from '@/lib/api-client'
import type { BalanceSheetData } from '@/lib/types'
import { AsOfDatePicker } from '@/components/reports/ReportDatePicker'
import { useReportAsOfDate } from '@/hooks/useReportDates'

export default function BalanceSheetPage() {
  const { asOf, setAsOf } = useReportAsOfDate()
  const { data: bs, isLoading } = useQuery<BalanceSheetData>({
    queryKey: ['report-balance-sheet', asOf],
    queryFn: async () => {
      const { data } = await apiClient.get('/reports/balance-sheet', {
        params: { as_of: asOf },
      })
      return data
    },
  })

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1">
        <Header />
        <main className="p-6">
          <h2 className="text-2xl font-bold mb-6">Balance Sheet</h2>
          <AsOfDatePicker asOf={asOf} onChange={setAsOf} />
          {isLoading ? (
            <p className="text-gray-500">Loading...</p>
          ) : bs ? (
            <div className="bg-white rounded-lg shadow p-6 max-w-2xl">
              <p className="text-sm text-gray-500 mb-4">As of: {bs.as_of}</p>
              <div className="space-y-6">
                <div>
                  <h3 className="font-semibold text-blue-700 mb-2">Assets</h3>
                  {bs.assets.length === 0 ? (
                    <p className="text-sm text-gray-500">No assets</p>
                  ) : bs.assets.map((item, i) => (
                    <div key={i} className="flex justify-between text-sm py-1 border-b">
                      <span>{String(item.account)}</span>
                      <span>{bs.base_currency} {Number(item.amount).toLocaleString()}</span>
                    </div>
                  ))}
                  <div className="flex justify-between text-sm font-bold pt-2">
                    <span>Total Assets</span>
                    <span>{bs.base_currency} {bs.total_assets.toLocaleString()}</span>
                  </div>
                </div>
                <div>
                  <h3 className="font-semibold text-red-700 mb-2">Liabilities</h3>
                  {bs.liabilities.length === 0 ? (
                    <p className="text-sm text-gray-500">No liabilities</p>
                  ) : bs.liabilities.map((item, i) => (
                    <div key={i} className="flex justify-between text-sm py-1 border-b">
                      <span>{String(item.account)}</span>
                      <span>{bs.base_currency} {Number(item.amount).toLocaleString()}</span>
                    </div>
                  ))}
                  <div className="flex justify-between text-sm font-bold pt-2">
                    <span>Total Liabilities</span>
                    <span>{bs.base_currency} {bs.total_liabilities.toLocaleString()}</span>
                  </div>
                </div>
                <div>
                  <h3 className="font-semibold text-purple-700 mb-2">Equity</h3>
                  {bs.equity.length === 0 ? (
                    <p className="text-sm text-gray-500">No equity</p>
                  ) : bs.equity.map((item, i) => (
                    <div key={i} className="flex justify-between text-sm py-1 border-b">
                      <span>{String(item.account)}</span>
                      <span>{bs.base_currency} {Number(item.amount).toLocaleString()}</span>
                    </div>
                  ))}
                  <div className="flex justify-between text-sm font-bold pt-2">
                    <span>Total Equity</span>
                    <span>{bs.base_currency} {bs.total_equity.toLocaleString()}</span>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-gray-500">Failed to load report</p>
          )}
        </main>
      </div>
    </div>
  )
}
