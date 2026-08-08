'use client'

import { useAuth } from '@/contexts/AuthContext'
import { useCompany } from '@/contexts/CompanyContext'

export default function Header() {
  const { user, logout, isAuthenticated } = useAuth()
  const { companies, selectedCompanyId, selectCompany } = useCompany()

  return (
    <header className="h-16 border-b border-brand-200 bg-white flex items-center justify-between px-6">
      <div />
      <div className="flex items-center gap-4">
        {isAuthenticated && (
          <>
            {companies.length > 1 && (
              <label className="text-sm text-gray-500">
                <span className="sr-only">Company</span>
                <select
                  aria-label="Company"
                  value={selectedCompanyId ?? ''}
                  onChange={(event) => selectCompany(event.target.value)}
                  className="rounded-lg border-brand-200 border bg-white px-3 py-2 text-sm"
                >
                  <option value="" disabled>
                    Select company
                  </option>
                  {companies.map((company) => (
                    <option key={company.company_id} value={company.company_id}>
                      {company.company_name} ({company.role})
                    </option>
                  ))}
                </select>
              </label>
            )}
            <span className="text-sm text-gray-600">{user?.name || user?.email}</span>
            <button
              onClick={() => logout()}
              className="text-sm text-brand-700 hover:text-brand-900 font-medium"
            >
              Logout
            </button>
          </>
        )}
      </div>
    </header>
  )
}
