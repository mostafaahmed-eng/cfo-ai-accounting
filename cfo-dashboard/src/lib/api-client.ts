import axios from 'axios'

// ---------------------------------------------------------------------------
// Company-context readiness gate.
//
// The backend returns 409 "Explicit company selection required" for any
// company-scoped endpoint when the user belongs to more than one active
// company and no X-Company-ID header is supplied. On a fresh login the
// dashboard/report/draft queries fire in parallel with (or before) the
// /companies/memberships request settles, so they were racing ahead of the
// company selection and failing with 409 on the first attempt. This module
// defers company-scoped requests until the active company has been resolved
// after login, eliminating the race instead of papering over it with retries.
// ---------------------------------------------------------------------------

let companyContextResolved = false
let companyWaiters: Array<() => void> = []
let companyWaitTimer: ReturnType<typeof setTimeout> | null = null
const COMPANY_CONTEXT_WAIT_MS = 5000

// Called by CompanyProvider once the memberships response has settled and the
// selected company has been established (or determined to be unselectable).
export function markCompanyContextResolved() {
  companyContextResolved = true
  if (companyWaitTimer) {
    clearTimeout(companyWaitTimer)
    companyWaitTimer = null
  }
  companyWaiters.forEach((resolve) => resolve())
  companyWaiters = []
}

// Called by CompanyProvider on logout so the next login waits again.
export function resetCompanyContextGate() {
  companyContextResolved = false
  companyWaiters = []
  if (companyWaitTimer) {
    clearTimeout(companyWaitTimer)
    companyWaitTimer = null
  }
}

function waitForCompanyContext(): Promise<void> {
  if (companyContextResolved) return Promise.resolve()
  return new Promise((resolve) => {
    companyWaiters.push(resolve)
    if (!companyWaitTimer) {
      companyWaitTimer = setTimeout(() => {
        companyContextResolved = true
        companyWaiters.forEach((r) => r())
        companyWaiters = []
      }, COMPANY_CONTEXT_WAIT_MS)
    }
  })
}

// Endpoints that do not depend on the selected company and must never block.
const NON_COMPANY_PREFIXES = ['/auth/', '/companies']

function requiresCompanyContext(url: string, token: string | null): boolean {
  if (!token) return false
  return !NON_COMPANY_PREFIXES.some((prefix) => url.startsWith(prefix))
}

const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use(async (config) => {
  if (typeof window === 'undefined') return config
  const token = localStorage.getItem('token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }

  const companyId = localStorage.getItem('selected_company_id')
  if (companyId) {
    config.headers['X-Company-ID'] = companyId
    return config
  }

  const url = config.url || ''
  if (requiresCompanyContext(url, token)) {
    await waitForCompanyContext()
    const settledCompanyId = localStorage.getItem('selected_company_id')
    if (settledCompanyId) {
      config.headers['X-Company-ID'] = settledCompanyId
    }
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('token')
      localStorage.removeItem('selected_company_id')
      window.location.href = '/'
    }
    return Promise.reject(error)
  }
)

export default apiClient
