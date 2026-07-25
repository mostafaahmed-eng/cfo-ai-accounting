'use client'

import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import { useQuery } from '@tanstack/react-query'
import apiClient from '@/lib/api-client'
import type { PnLData } from '@/lib/types'
import { DateRangePicker } from '@/components/reports/ReportDatePicker'
import { useReportDateRange } from '@/hooks/useReportDates'

export default function PnLPage() {
  const {
    startDate,
    endDate,
    isValid,
    setStartDate,
    setEndDate,
  } = useReportDateRange()
  const { data: pnl, isLoading } = useQuery<PnLData>({
    queryKey: ['report-pnl', startDate, endDate],
    queryFn: async () => {
      const { data } = await apiClient.get('/reports/profit-and-loss', {
        params: { start_date: startDate, end_date: endDate },
      })
      return data
    },
    enabled: isValid,
  })

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1">
        <Header />
        <main className="p-6">
          <h2 className="text-2xl font-bold mb-6">Profit &amp; Loss</h2>
          <DateRangePicker
            startDate={startDate}
            endDate={endDate}
            onStartDateChange={setStartDate}
            onEndDateChange={setEndDate}
          />
          {isLoading ? (
            <p className="text-gray-500">Loading...</p>
          ) : pnl ? (
            <div className="bg-white rounded-lg shadow p-6 max-w-2xl">
              <p className="text-sm text-gray-500 mb-4">Period: {pnl.period}</p>
              <div className="space-y-6">
                <div>
                  <h3 className="font-semibold text-green-700 mb-2">Revenue</h3>
                  {pnl.revenue.length === 0 ? (
                    <p className="text-sm text-gray-500">No revenue recorded</p>
                  ) : (
                    pnl.revenue.map((item, i) => (
                      <div key={i} className="flex justify-between text-sm py-1 border-b">
                        <span>{String(item.account)}</span>
                        <span>{pnl.base_currency} {Number(item.amount).toLocaleString()}</span>
                      </div>
                    ))
                  )}
                </div>
                <div>
                  <h3 className="font-semibold text-red-700 mb-2">Expenses</h3>
                  {pnl.expenses.length === 0 ? (
                    <p className="text-sm text-gray-500">No expenses recorded</p>
                  ) : (
                    pnl.expenses.map((item, i) => (
                      <div key={i} className="flex justify-between text-sm py-1 border-b">
                        <span>{String(item.account)}</span>
                        <span>{pnl.base_currency} {Number(item.amount).toLocaleString()}</span>
                      </div>
                    ))
                  )}
                </div>
                <div className="flex justify-between font-bold text-lg border-t pt-4">
                  <span>Net Income</span>
                  <span className={pnl.net_income >= 0 ? 'text-green-700' : 'text-red-700'}>
                    {pnl.base_currency} {pnl.net_income.toLocaleString()}
                  </span>
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
