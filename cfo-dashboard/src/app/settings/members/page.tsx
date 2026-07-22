'use client'

import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'

export default function MembersPage() {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1">
        <Header />
        <main className="p-6">
          <h2 className="text-2xl font-bold mb-6">Team Members</h2>
          <div className="bg-white rounded-lg shadow p-6">
            <p className="text-gray-500 text-sm">
              Manage your team members and their roles. Create a company first to start inviting members.
            </p>
          </div>
        </main>
      </div>
    </div>
  )
}
