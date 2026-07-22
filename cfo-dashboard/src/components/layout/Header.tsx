'use client'

import { useAuth } from '@/contexts/AuthContext'

export default function Header() {
  const { user, logout, isAuthenticated } = useAuth()

  return (
    <header className="h-16 border-b bg-white flex items-center justify-between px-6">
      <div />
      <div className="flex items-center gap-4">
        {isAuthenticated && (
          <>
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
