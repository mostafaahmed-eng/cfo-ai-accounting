'use client'

import { useAuth } from '@/contexts/AuthContext'
import { useCompany } from '@/contexts/CompanyContext'

export default function Header() {
  const { user, logout, isAuthenticated } = useAuth()
  const { companies, selectedCompanyId, selectCompany } = useCompany()

  return (
    <header className="h-16 border-b bg-white flex items-center justify-between px-6">
      <div />
      <div className="flex items-center gap-4">
        {isAuthenticated && (
          <>
            {companies.length > 1 && (
              <label className="text-sm text-gray-600">
                <span className="sr-only">Company</span>
                <select
                  aria-label="Company"
                  value={selectedCompanyId ?? ''}
                  onChange={(event) => selectCompany(event.target.value)}
                  className="rounded border border-gray-300 bg-white px-3 py-2 text-sm"
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
              className="text-sm text-red-600 hover:text-red-800 font-medium"
            >
              Logout
            </button>
          </>
        )}
      </div>
    </header>
  )
}
