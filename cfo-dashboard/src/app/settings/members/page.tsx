'use client'

import { useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import apiClient from '@/lib/api-client'
import type { CompanyInvitation, CompanyMember } from '@/lib/types'

const ROLES = ['OWNER', 'ADMIN', 'ACCOUNTANT', 'APPROVER', 'VIEWER'] as const
type Role = (typeof ROLES)[number]

function apiErrorMessage(error: unknown): string {
  const status = (error as { response?: { status?: number } })?.response?.status
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  switch (status) {
    case 403:
      return 'You do not have permission to manage members'
    case 409:
      return detail || 'This action conflicts with company policy'
    case 422:
      return detail || 'Invalid data'
    default:
      return detail || 'Something went wrong'
  }
}

export default function MembersPage() {
  const queryClient = useQueryClient()
  const selectedCompanyId =
    typeof window !== 'undefined' ? localStorage.getItem('selected_company_id') : null

  const membersQuery = useQuery<CompanyMember[]>({
    queryKey: ['company-members', selectedCompanyId],
    queryFn: async () => {
      const { data } = await apiClient.get(
        `/companies/${selectedCompanyId}/members?limit=200`,
      )
      return data
    },
    enabled: Boolean(selectedCompanyId),
  })

  const invitationsQuery = useQuery<CompanyInvitation[]>({
    queryKey: ['company-invitations', selectedCompanyId],
    queryFn: async () => {
      const { data } = await apiClient.get(
        `/companies/${selectedCompanyId}/invitations?limit=200`,
      )
      return data
    },
    enabled: Boolean(selectedCompanyId),
  })

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['company-members', selectedCompanyId] })
    queryClient.invalidateQueries({ queryKey: ['company-invitations', selectedCompanyId] })
  }

  const [inviteEmail, setInviteEmail] = useState('')
  const [inviteRole, setInviteRole] = useState<Role>('VIEWER')
  const [inviteError, setInviteError] = useState<string | null>(null)

  const inviteMutation = useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post(`/companies/${selectedCompanyId}/invitations`, {
        email: inviteEmail,
        role: inviteRole,
      })
      return data
    },
    onSuccess: () => {
      setInviteEmail('')
      setInviteError(null)
      refresh()
    },
    onError: (error) => {
      setInviteError(apiErrorMessage(error))
    },
  })

  const updateMutation = useMutation({
    mutationFn: async ({ id, role, status }: { id: string; role?: Role; status?: string }) => {
      const { data } = await apiClient.patch(`/companies/${selectedCompanyId}/members/${id}`, {
        role,
        status,
      })
      return data
    },
    onSuccess: refresh,
    onError: (error) => {
      alert(apiErrorMessage(error))
    },
  })

  const removeMutation = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/companies/${selectedCompanyId}/members/${id}`)
    },
    onSuccess: refresh,
    onError: (error) => {
      alert(apiErrorMessage(error))
    },
  })

  const cancelInvitationMutation = useMutation({
    mutationFn: async (id: string) => {
      await apiClient.delete(`/companies/${selectedCompanyId}/invitations/${id}`)
    },
    onSuccess: refresh,
    onError: (error) => {
      alert(apiErrorMessage(error))
    },
  })

  useEffect(() => {
    queryClient.invalidateQueries({ queryKey: ['company-members'] })
    queryClient.invalidateQueries({ queryKey: ['company-invitations'] })
  }, [selectedCompanyId, queryClient])

  const isLoading = membersQuery.isLoading || invitationsQuery.isLoading
  const queryError = apiErrorMessage(membersQuery.error ?? invitationsQuery.error)

  const activeMembers = membersQuery.data?.filter((member) => member.status === 'active') ?? []
  const pendingInvites =
    invitationsQuery.data?.filter(
      (invite) => invite.status === 'pending' || invite.status === 'expired',
    ) ?? []

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1">
        <Header />
        <main className="p-6">
          <h2 className="text-2xl font-bold mb-6">Team Members</h2>

          <div className="bg-white rounded-lg shadow p-6 mb-6">
            <h3 className="text-lg font-semibold mb-3">Invite Member</h3>
            <div className="flex flex-wrap items-end gap-3">
              <div className="flex-1 min-w-[200px]">
                <label className="block text-sm font-medium mb-1">Email</label>
                <input
                  type="email"
                  value={inviteEmail}
                  onChange={(event) => setInviteEmail(event.target.value)}
                  placeholder="teammate@example.com"
                  className="w-full border rounded px-3 py-2 text-sm"
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Role</label>
                <select
                  value={inviteRole}
                  onChange={(event) => setInviteRole(event.target.value as Role)}
                  className="border rounded px-3 py-2 text-sm"
                >
                  {ROLES.filter((role) => role !== 'OWNER').map((role) => (
                    <option key={role} value={role}>
                      {role}
                    </option>
                  ))}
                </select>
              </div>
              <button
                onClick={() => inviteMutation.mutate()}
                disabled={
                  !inviteEmail.trim() ||
                  inviteMutation.isPending ||
                  !selectedCompanyId
                }
                className="bg-brand-600 text-white px-6 py-2 rounded text-sm disabled:opacity-50"
              >
                {inviteMutation.isPending ? 'Inviting...' : 'Send Invitation'}
              </button>
            </div>
            {inviteError && <p className="text-red-600 text-sm mt-2">{inviteError}</p>}
            {inviteMutation.isSuccess && (
              <p className="text-green-600 text-sm mt-2">Invitation sent</p>
            )}
          </div>

          {isLoading ? (
            <div className="bg-white rounded-lg shadow p-6">
              <p className="text-gray-500 text-sm">Loading members...</p>
            </div>
          ) : queryError ? (
            <div className="bg-white rounded-lg shadow p-6">
              <p className="text-red-600 text-sm">{queryError}</p>
            </div>
          ) : activeMembers.length === 0 && pendingInvites.length === 0 ? (
            <div className="bg-white rounded-lg shadow p-6">
              <p className="text-gray-500 text-sm">
                No members yet. Invite your first teammate above.
              </p>
            </div>
          ) : (
            <>
              <div className="bg-white rounded-lg shadow mb-6">
                <div className="border-b px-6 py-3">
                  <h3 className="font-semibold">Members</h3>
                </div>
                {activeMembers.length === 0 ? (
                  <p className="text-gray-500 text-sm px-6 py-4">No active members.</p>
                ) : (
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-500 border-b">
                        <th className="px-6 py-2">Name</th>
                        <th className="px-6 py-2">Email</th>
                        <th className="px-6 py-2">Role</th>
                        <th className="px-6 py-2">Status</th>
                        <th className="px-6 py-2 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {activeMembers.map((member) => (
                        <tr key={member.id} className="border-b last:border-0">
                          <td className="px-6 py-3">{member.name}</td>
                          <td className="px-6 py-3">{member.email}</td>
                          <td className="px-6 py-3">
                            <select
                              value={member.role}
                              onChange={(event) =>
                                updateMutation.mutate({
                                  id: member.id,
                                  role: event.target.value as Role,
                                })
                              }
                              className="border rounded px-2 py-1 text-sm"
                            >
                              {ROLES.map((role) => (
                                <option key={role} value={role}>
                                  {role}
                                </option>
                              ))}
                            </select>
                          </td>
                          <td className="px-6 py-3">
                            <span
                              className={`px-2 py-1 rounded text-xs ${
                                member.status === 'active'
                                  ? 'bg-green-100 text-green-700'
                                  : 'bg-gray-100 text-gray-500'
                              }`}
                            >
                              {member.status}
                            </span>
                          </td>
                          <td className="px-6 py-3 text-right">
                            <button
                              onClick={() => {
                                if (
                                  window.confirm(
                                    `Remove ${member.name} from this company?`,
                                  )
                                ) {
                                  removeMutation.mutate(member.id)
                                }
                              }}
                              disabled={removeMutation.isPending}
                              className="text-red-600 hover:text-red-800 text-sm disabled:opacity-50"
                            >
                              Remove
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              {pendingInvites.length > 0 && (
                <div className="bg-white rounded-lg shadow">
                  <div className="border-b px-6 py-3">
                    <h3 className="font-semibold">Pending Invitations</h3>
                  </div>
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-500 border-b">
                        <th className="px-6 py-2">Email</th>
                        <th className="px-6 py-2">Role</th>
                        <th className="px-6 py-2">Status</th>
                        <th className="px-6 py-2 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pendingInvites.map((invite) => (
                        <tr key={invite.id} className="border-b last:border-0">
                          <td className="px-6 py-3">{invite.email}</td>
                          <td className="px-6 py-3">{invite.role}</td>
                          <td className="px-6 py-3">
                            <span
                              className={`px-2 py-1 rounded text-xs ${
                                invite.status === 'pending'
                                  ? 'bg-yellow-100 text-yellow-700'
                                  : 'bg-gray-100 text-gray-500'
                              }`}
                            >
                              {invite.status}
                            </span>
                          </td>
                          <td className="px-6 py-3 text-right">
                            {invite.status === 'pending' && (
                              <button
                                onClick={() => {
                                  if (
                                    window.confirm(
                                      `Cancel the invitation for ${invite.email}?`,
                                    )
                                  ) {
                                    cancelInvitationMutation.mutate(invite.id)
                                  }
                                }}
                                disabled={cancelInvitationMutation.isPending}
                                className="text-red-600 hover:text-red-800 text-sm disabled:opacity-50"
                              >
                                Cancel
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  )
}