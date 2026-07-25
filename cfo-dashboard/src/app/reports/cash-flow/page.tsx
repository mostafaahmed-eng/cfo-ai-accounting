'use client'

import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import { useQuery } from '@tanstack/react-query'
import apiClient from '@/lib/api-client'
import type { CashFlowData } from '@/lib/types'
import { DateRangePicker } from '@/components/reports/ReportDatePicker'
import { useReportDateRange } from '@/hooks/useReportDates'

export default function CashFlowPage() {
  const {
    startDate,
    endDate,
    isValid,
    setStartDate,
    setEndDate,
  } = useReportDateRange()
  const { data: cashFlow, isLoading } = useQuery<CashFlowData>({
    queryKey: ['report-cashflow', startDate, endDate],
    queryFn: async () => {
      const { data } = await apiClient.get('/reports/cash-flow', {
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
          <h2 className="text-2xl font-bold mb-6">Cash Flow</h2>
          <DateRangePicker
            startDate={startDate}
            endDate={endDate}
            onStartDateChange={setStartDate}
            onEndDateChange={setEndDate}
          />
          {isLoading ? (
            <p className="text-gray-500">Loading...</p>
          ) : cashFlow ? (
            <div className="bg-white rounded-lg shadow p-6 max-w-2xl">
              <p className="text-sm text-gray-500 mb-4">Period: {cashFlow.period}</p>
              <div className="space-y-4">
                <div className="flex justify-between text-sm py-2 border-b">
                  <span>Operating Activities</span>
                  <span className="font-medium">{cashFlow.base_currency} {cashFlow.operating.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-sm py-2 border-b">
                  <span>Investing Activities</span>
                  <span className="font-medium">{cashFlow.base_currency} {cashFlow.investing.toLocaleString()}</span>
                </div>
                <div className="flex justify-between text-sm py-2 border-b">
                  <span>Financing Activities</span>
                  <span className="font-medium">{cashFlow.base_currency} {cashFlow.financing.toLocaleString()}</span>
                </div>
                <div className="flex justify-between font-bold text-lg border-t pt-4">
                  <span>Net Cash Flow</span>
                  <span className={cashFlow.net >= 0 ? 'text-green-700' : 'text-red-700'}>
                    {cashFlow.base_currency} {cashFlow.net.toLocaleString()}
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
