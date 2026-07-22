'use client'

import { createContext, useContext, useState, useEffect, useCallback, type ReactNode } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import apiClient from '@/lib/api-client'
import type { User, LoginResponse } from '@/lib/types'

interface AuthContextType {
  user: User | null
  token: string | null
  isLoading: boolean
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
  const router = useRouter()
  const pathname = usePathname()

  const isProtected = PROTECTED_PREFIXES.some((p) => pathname.startsWith(p))

  const loadUser = useCallback(async (accessToken: string) => {
    try {
      const { data } = await apiClient.get<User>('/auth/me', {
        headers: { Authorization: `Bearer ${accessToken}` },
      })
      setUser(data)
    } catch {
      localStorage.removeItem('token')
      setToken(null)
      setUser(null)
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
    const { data } = await apiClient.post<LoginResponse>('/auth/login', { email, password })
    localStorage.setItem('token', data.access_token)
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
    setToken(null)
    setUser(null)
    router.push('/')
  }, [router])

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, logout, isAuthenticated: !!token }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
