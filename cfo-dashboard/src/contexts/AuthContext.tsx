'use client'

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import axios from 'axios'
import apiClient from '@/lib/api-client'
import type { User, LoginResponse } from '@/lib/types'

interface AuthContextType {
  user: User | null
  token: string | null
  isLoading: boolean
  authError: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

const PROTECTED_PREFIXES = ['/dashboard', '/inbox', '/transactions', '/accounts', '/vendors', '/budgets', '/reports', '/settings']

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [authError, setAuthError] = useState<string | null>(null)
  const router = useRouter()
  const pathname = usePathname()

  const isProtected = PROTECTED_PREFIXES.some((p) => pathname.startsWith(p))

  const loadUser = useCallback(async (accessToken: string) => {
    try {
      const { data } = await apiClient.get<User>('/auth/me', {
        headers: { Authorization: `Bearer ${accessToken}` },
        timeout: 15000,
      })
      setUser(data)
      setAuthError(null)
    } catch (err) {
      localStorage.removeItem('token')
      localStorage.removeItem('refresh_token')
      setToken(null)
      setUser(null)
      if (axios.isAxiosError(err) && err.response) {
        // Server answered (e.g. 401 expired/invalid token, or a 5xx).
        // A 401 is a normal "no valid session" -> show plain login, no error.
        setAuthError(
          err.response.status === 401
            ? null
            : 'Session check failed (server error). Please try again.'
        )
      } else {
        // Network error / timeout (e.g. an unreachable API or a browser-forced
        // HTTPS upgrade that fails) — surface it instead of hanging forever.
        setAuthError(
          'Could not reach the server to verify your session. Check your connection and refresh.'
        )
      }
    }
  }, [])

  useEffect(() => {
    const stored = localStorage.getItem('token')
    if (stored) {
      setToken(stored)
      loadUser(stored).finally(() => setIsLoading(false))
    } else {
      setIsLoading(false)
    }
  }, [loadUser])

  useEffect(() => {
    if (!isLoading && isProtected && !token) {
      router.replace('/')
    }
  }, [isLoading, isProtected, token, router])

  const login = useCallback(async (email: string, password: string) => {
    setAuthError(null)
    const { data } = await apiClient.post<LoginResponse>(
      '/auth/login',
      { email, password },
      { timeout: 15000 }
    )
    localStorage.setItem('token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    setToken(data.access_token)
    setUser(data.user)
    router.push('/dashboard')
  }, [router])

  const logout = useCallback(async () => {
    try {
      await apiClient.post('/auth/logout')
    } catch {
      // ignore — token may already be invalid
    }
    localStorage.removeItem('token')
    localStorage.removeItem('refresh_token')
    setToken(null)
    setUser(null)
    router.push('/')
  }, [router])

  return (
    <AuthContext.Provider value={{ user, token, isLoading, authError, login, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
