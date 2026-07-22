'use client'

import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/contexts/AuthContext'
import apiClient from '@/lib/api-client'
import type { DashboardData, DraftTransaction } from '@/lib/types'
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

export default function DashboardPage() {
  const { isAuthenticated, isLoading: authLoading } = useAuth()

  const { data: dashboard, isLoading: dashLoading } = useQuery<DashboardData>({
    queryKey: ['dashboard'],
    queryFn: async () => {
      const { data } = await apiClient.get('/reports/dashboard')
      return data
    },
    enabled: isAuthenticated,
  })

  const { data: drafts } = useQuery<DraftTransaction[]>({
    queryKey: ['draft-transactions'],
    queryFn: async () => {
      const { data } = await apiClient.get('/draft-transactions')
      return data
    },
    enabled: isAuthenticated,
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

  const reviewItems = (drafts || []).filter(d => d.status === 'ready_for_review' || d.status === 'needs_clarification')

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1">
        <Header />
        <main className="p-6">
          <h2 className="text-2xl font-bold mb-6">Dashboard</h2>
          {dashLoading ? (
            <p className="text-gray-500">Loading...</p>
          ) : dashboard ? (
            <div className="space-y-6">
              <DashboardCards data={dashboard} />
              <QuickCapture />
              <ReceiptUpload />
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <CashFlowChart data={{ monthly_data: dashboard.recent_transactions }} />
                <ExpenseCategoryChart categories={[]} />
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
