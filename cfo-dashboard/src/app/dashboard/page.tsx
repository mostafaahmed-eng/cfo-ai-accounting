'use client'

import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/contexts/AuthContext'
import { useCompany } from '@/contexts/CompanyContext'
import apiClient, { fetchAll } from '@/lib/api-client'
import type {
  CashFlowData,
  DashboardData,
  DraftTransaction,
  ExpenseByCategoryData,
} from '@/lib/types'
import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import DashboardCards from '@/components/dashboard/DashboardCards'
import CashFlowChart from '@/components/dashboard/CashFlowChart'
import ExpenseCategoryChart from '@/components/dashboard/ExpenseCategoryChart'
import RecentTransactions from '@/components/dashboard/RecentTransactions'
import BudgetWarnings from '@/components/dashboard/BudgetWarnings'
import AIReviewQueue from '@/components/dashboard/AIReviewQueue'
import QuickCapture from '@/components/dashboard/QuickCapture'
import ReceiptUpload from '@/components/dashboard/ReceiptUpload'
import { DateRangePicker } from '@/components/reports/ReportDatePicker'
import { useReportDateRange } from '@/hooks/useReportDates'

export default function DashboardPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth()
  const { selectedCompanyId } = useCompany()
  const {
    startDate,
    endDate,
    isValid,
    setStartDate,
    setEndDate,
  } = useReportDateRange()
  const reportParams = { start_date: startDate, end_date: endDate }
  const companyReady = Boolean(selectedCompanyId)

  const { data: dashboard, isLoading: dashLoading } = useQuery<DashboardData>({
    queryKey: ['dashboard', selectedCompanyId, startDate, endDate],
    queryFn: async () => {
      const { data } = await apiClient.get('/reports/dashboard', {
        params: reportParams,
      })
      return data
    },
    enabled: isAuthenticated && companyReady && isValid,
  })

  const { data: drafts } = useQuery<DraftTransaction[]>({
    queryKey: ['draft-transactions', selectedCompanyId],
    queryFn: () => fetchAll<DraftTransaction>('/draft-transactions'),
    enabled: isAuthenticated && companyReady,
  })

  const { data: cashFlow } = useQuery<CashFlowData>({
    queryKey: ['report-cashflow', selectedCompanyId, startDate, endDate],
    queryFn: async () => {
      const { data } = await apiClient.get('/reports/cash-flow', {
        params: reportParams,
      })
      return data
    },
    enabled: isAuthenticated && companyReady && isValid,
  })

  const { data: expenseCategories } = useQuery<ExpenseByCategoryData>({
    queryKey: ['report-expenses-by-category', selectedCompanyId, startDate, endDate],
    queryFn: async () => {
      const { data } = await apiClient.get('/reports/expenses-by-category', {
        params: reportParams,
      })
      return data
    },
    enabled: isAuthenticated && companyReady && isValid,
  })

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">Loading...</p>
      </div>
    )
  }

  if (!isAuthenticated) {
    return null
  }

  const reviewItems = (drafts || []).filter(d => d.status === 'ready_for_review')

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1">
        <Header />
        <main className="p-6">
          <h2 className="text-2xl font-bold mb-6">Dashboard</h2>
          <DateRangePicker
            startDate={startDate}
            endDate={endDate}
            onStartDateChange={setStartDate}
            onEndDateChange={setEndDate}
          />
          {dashLoading || !companyReady ? (
            <p className="text-gray-500">Loading...</p>
          ) : dashboard ? (
            <div className="space-y-6">
              <DashboardCards data={dashboard} />
              <QuickCapture />
              <ReceiptUpload />
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <CashFlowChart data={{ monthly_data: cashFlow?.monthly_data || [] }} />
                <ExpenseCategoryChart categories={expenseCategories?.categories || []} />
              </div>
              <BudgetWarnings warnings={dashboard.budget_warnings} />
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <RecentTransactions transactions={dashboard.recent_transactions} />
                <AIReviewQueue items={reviewItems} />
              </div>
            </div>
          ) : (
            <p className="text-gray-500">Failed to load dashboard</p>
          )}
        </main>
      </div>
    </div>
  )
}
