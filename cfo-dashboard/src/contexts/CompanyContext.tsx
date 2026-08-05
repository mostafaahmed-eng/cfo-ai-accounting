'use client'

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import apiClient, {
  markCompanyContextResolved,
  resetCompanyContextGate,
} from '@/lib/api-client'
import type { CompanyMembership } from '@/lib/types'
import { useAuth } from '@/contexts/AuthContext'

interface CompanyContextType {
  companies: CompanyMembership[]
  selectedCompany: CompanyMembership | null
  selectedCompanyId: string | null
  isLoading: boolean
  selectCompany: (companyId: string) => void
}

const CompanyContext = createContext<CompanyContextType | undefined>(undefined)

export function CompanyProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth()
  const queryClient = useQueryClient()
  const [selectedCompanyId, setSelectedCompanyId] = useState<string | null>(null)

  useEffect(() => {
    setSelectedCompanyId(localStorage.getItem('selected_company_id'))
  }, [])

  const { data: companies = [], isLoading } = useQuery<CompanyMembership[]>({
    queryKey: ['company-memberships'],
    queryFn: async () => {
      const { data } = await apiClient.get('/companies/memberships')
      return data
    },
    enabled: isAuthenticated,
  })

  const selectCompany = useCallback(
    (companyId: string) => {
      if (!companies.some((company) => company.company_id === companyId)) return
      localStorage.setItem('selected_company_id', companyId)
      setSelectedCompanyId(companyId)
      queryClient.invalidateQueries({
        predicate: (query) => query.queryKey[0] !== 'company-memberships',
      })
    },
    [companies, queryClient],
  )

  useEffect(() => {
    if (!isAuthenticated) {
      resetCompanyContextGate()
      localStorage.removeItem('selected_company_id')
      setSelectedCompanyId(null)
      return
    }
    if (isLoading) return

    const selectionIsValid = companies.some(
      (company) => company.company_id === selectedCompanyId,
    )
    if (selectionIsValid) {
      markCompanyContextResolved()
      return
    }

    if (companies.length === 1) {
      selectCompany(companies[0].company_id)
    } else {
      localStorage.removeItem('selected_company_id')
      setSelectedCompanyId(null)
    }
    markCompanyContextResolved()
  }, [
    companies,
    isAuthenticated,
    isLoading,
    selectCompany,
    selectedCompanyId,
  ])

  const selectedCompany = useMemo(
    () =>
      companies.find((company) => company.company_id === selectedCompanyId) ??
      null,
    [companies, selectedCompanyId],
  )

  return (
    <CompanyContext.Provider
      value={{
        companies,
        selectedCompany,
        selectedCompanyId,
        isLoading,
        selectCompany,
      }}
    >
      {children}
    </CompanyContext.Provider>
  )
}

export function useCompany() {
  const context = useContext(CompanyContext)
  if (!context) {
    throw new Error('useCompany must be used within CompanyProvider')
  }
  return context
}
