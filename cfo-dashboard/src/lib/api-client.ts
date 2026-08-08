import axios, { type InternalAxiosRequestConfig } from 'axios'
import type { RefreshResponse } from './types'

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
const NON_COMPANY_PREFIXES = ['/auth/', '/companies', '/integrations/telegram/bot-config']

function requiresCompanyContext(url: string, token: string | null): boolean {
  if (!token) return false
  return !NON_COMPANY_PREFIXES.some((prefix) => url.startsWith(prefix))
}

// Base URL: same-origin by default. The app is served by nginx, which also
// proxies /api/ to the backend, so the browser calls /api/v1 on its own origin.
// Only set NEXT_PUBLIC_API_BASE_URL when the API is served from a different
// origin than the frontend (e.g. local development without nginx).
const apiClient = axios.create({
  baseURL: process.env.NEXT_PUBLIC_API_BASE_URL || '/api/v1',
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

// ---------------------------------------------------------------------------
// Silent access-token refresh.
//
// The backend rotates refresh tokens on every /auth/refresh call and revokes
// the whole family if a rotated token is replayed. These helpers keep exactly
// one refresh in flight at a time, swap both tokens on success, and perform a
// clean logout (clear storage + redirect) when refresh fails.
// ---------------------------------------------------------------------------

interface RetriableConfig extends InternalAxiosRequestConfig {
  _retry?: boolean
}

let isRefreshing = false
let refreshWaiters: Array<(ok: boolean) => void> = []

function clearAuthStorage() {
  localStorage.removeItem('token')
  localStorage.removeItem('refresh_token')
  localStorage.removeItem('selected_company_id')
  window.location.href = '/'
}

async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) return false
  if (isRefreshing) {
    return new Promise((resolve) => refreshWaiters.push(resolve))
  }
  isRefreshing = true
  try {
    const { data } = await axios.post<RefreshResponse>(
      `${apiClient.defaults.baseURL}/auth/refresh`,
      { refresh_token: refreshToken },
      { headers: { 'Content-Type': 'application/json' } },
    )
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    refreshWaiters.forEach((resolve) => resolve(true))
    refreshWaiters = []
    return true
  } catch {
    refreshWaiters.forEach((resolve) => resolve(false))
    refreshWaiters = []
    return false
  } finally {
    isRefreshing = false
  }
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (typeof window === 'undefined') return Promise.reject(error)

    const original = error.config as RetriableConfig | undefined
    const status = error.response?.status

    if (status === 401 && original && !original._retry) {
      original._retry = true
      const refreshed = await refreshAccessToken()
      if (refreshed) {
        const newToken = localStorage.getItem('token')
        original.headers.Authorization = `Bearer ${newToken}`
        return apiClient(original)
      }
    }

    if (status === 401) {
      clearAuthStorage()
    }
    return Promise.reject(error)
  }
)

// ---------------------------------------------------------------------------
// Fetch-all helper for list endpoints.
//
// List endpoints are paginated server-side (limit/offset query params, hard
// max) and report the total row count in the X-Total-Count response header.
// `fetchAll` pages through the whole result set in bounded requests so pages
// that render the full list keep working unchanged while each individual
// request stays within the server's pagination cap.
// ---------------------------------------------------------------------------
export async function fetchAll<T>(
  url: string,
  params?: Record<string, string | number | undefined>,
  chunkSize = 200,
): Promise<T[]> {
  const items: T[] = []
  let offset = 0
  while (true) {
    const { data, headers } = await apiClient.get<T[]>(url, {
      params: { ...params, limit: chunkSize, offset },
    })
    const page = data || []
    items.push(...page)
    const total = Number(headers['x-total-count'])
    offset += chunkSize
    if (Number.isFinite(total) && total >= 0) {
      if (items.length >= total) break
    } else if (page.length < chunkSize) {
      break
    }
  }
  return items
}

export default apiClient
