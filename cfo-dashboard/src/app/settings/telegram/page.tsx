'use client'

import { useEffect, useState } from 'react'
import Sidebar from '@/components/layout/Sidebar'
import Header from '@/components/layout/Header'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import apiClient from '@/lib/api-client'
import { useCompany } from '@/contexts/CompanyContext'
import type { TelegramStatus, TelegramBotConfig } from '@/lib/types'

const POLL_INTERVAL_MS = 5000

export default function TelegramSettingsPage() {
  const queryClient = useQueryClient()
  const { selectedCompanyId } = useCompany()
  const [pendingPairing, setPendingPairing] = useState(false)
  const [copied, setCopied] = useState(false)
  const [countdown, setCountdown] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [token, setToken] = useState('')
  const [username, setUsername] = useState('')

  const { data: status } = useQuery<TelegramStatus>({
    queryKey: ['telegram-status', selectedCompanyId],
    queryFn: async () => {
      const { data } = await apiClient.get('/integrations/telegram/status')
      return data
    },
    enabled: Boolean(selectedCompanyId),
    refetchInterval: pendingPairing ? POLL_INTERVAL_MS : false,
  })

  const { data: botConfig } = useQuery<TelegramBotConfig>({
    queryKey: ['telegram-bot-config'],
    queryFn: async () => {
      const { data } = await apiClient.get('/integrations/telegram/bot-config')
      return data
    },
  })

  const saveConfigMutation = useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.put<TelegramBotConfig>(
        '/integrations/telegram/bot-config',
        { bot_token: token, bot_username: username },
      )
      return data
    },
    onSuccess: (data) => {
      setToken('')
      setUsername('')
      setEditing(false)
      queryClient.invalidateQueries({ queryKey: ['telegram-bot-config'] })
      if (data.verified_username && data.bot_username !== data.verified_username) {
        alert(
          `Note: Telegram reports this bot as @${data.verified_username}, but you saved @${data.bot_username}.`,
        )
      }
    },
  })

  const connectMutation = useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post<TelegramStatus>('/integrations/telegram/connect')
      return data
    },
    onSuccess: (data) => {
      setCopied(false)
      setPendingPairing(data.connected === false)
      queryClient.invalidateQueries({ queryKey: ['telegram-status'] })
    },
  })

  const disconnectMutation = useMutation({
    mutationFn: async () => {
      await apiClient.delete('/integrations/telegram/disconnect')
    },
    onSuccess: () => {
      setPendingPairing(false)
      queryClient.invalidateQueries({ queryKey: ['telegram-status'] })
    },
  })

  useEffect(() => {
    if (status?.connected && pendingPairing) {
      setPendingPairing(false)
    }
  }, [status?.connected, pendingPairing])

  useEffect(() => {
    if (!pendingPairing || !connectMutation.data?.pairing_expires_at) {
      setCountdown(null)
      return
    }
    const update = () => {
      const remaining =
        new Date(connectMutation.data.pairing_expires_at as string).getTime() - Date.now()
      if (remaining <= 0) {
        setCountdown('expired')
        return
      }
      const minutes = Math.floor(remaining / 60000)
      const seconds = Math.floor((remaining % 60000) / 1000)
      setCountdown(`${minutes}:${String(seconds).padStart(2, '0')}`)
    }
    update()
    const timer = setInterval(update, 1000)
    return () => clearInterval(timer)
  }, [pendingPairing, connectMutation.data?.pairing_expires_at])

  const pairing = connectMutation.data
  const pairingActive = pendingPairing && pairing?.pairing_link

  const copyCode = async () => {
    if (!pairing?.pairing_code) return
    await navigator.clipboard.writeText(`/start ${pairing.pairing_code}`)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1">
        <Header />
        <main className="p-6">
          <h2 className="text-2xl font-bold mb-6">Telegram Settings</h2>

          <div className="bg-white rounded-lg shadow p-6 max-w-lg mb-6">
            <h3 className="text-lg font-semibold mb-1">Bot Setup</h3>
            <p className="text-sm text-gray-500 mb-4">
              Paste your bot token (from @BotFather) and optionally the bot username. The token is
              validated with Telegram and stored encrypted.
            </p>
            {!editing ? (
              <div className="flex items-center justify-between">
                <div className="text-sm">
                  {botConfig?.configured ? (
                    <p>
                      <strong>Bot:</strong> @{botConfig.bot_username}
                    </p>
                  ) : (
                    <p className="text-gray-500">No bot configured yet.</p>
                  )}
                </div>
                <button
                  onClick={() => {
                    setEditing(true)
                    setUsername(botConfig?.bot_username ?? '')
                  }}
                  className="border border-blue-600 text-blue-700 px-3 py-1.5 rounded text-xs font-medium hover:bg-blue-50"
                >
                  {botConfig?.configured ? 'Edit' : 'Set up'}
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Bot token (from @BotFather)
                  </label>
                  <input
                    type="password"
                    value={token}
                    onChange={(e) => setToken(e.target.value)}
                    placeholder="123456789:AA..."
                    className="w-full border rounded px-3 py-2 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-600 mb-1">
                    Bot username (without @) — optional, auto-detected from the token
                  </label>
                  <input
                    type="text"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="YourChatBot"
                    className="w-full border rounded px-3 py-2 text-sm"
                  />
                </div>
                {saveConfigMutation.isError && (
                  <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                    {(saveConfigMutation.error as { response?: { data?: { detail?: string } } })
                      ?.response?.data?.detail ?? 'Could not save the bot configuration.'}
                  </div>
                )}
                <div className="flex gap-2">
                  <button
                    onClick={() => saveConfigMutation.mutate()}
                    disabled={saveConfigMutation.isPending || !token.trim()}
                    className="bg-blue-600 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
                  >
                    {saveConfigMutation.isPending ? 'Saving...' : 'Save bot'}
                  </button>
                  <button
                    onClick={() => {
                      setEditing(false)
                      setToken('')
                      setUsername('')
                    }}
                    className="text-gray-600 text-sm underline"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>

          <div className="bg-white rounded-lg shadow p-6 max-w-lg">
            <div className="flex items-center gap-3 mb-6">
              <span className={`w-3 h-3 rounded-full ${status?.connected ? 'bg-green-500' : 'bg-gray-300'}`} />
              <span className="font-medium">
                {status?.connected ? 'Connected' : pendingPairing ? 'Waiting for connection...' : 'Not Connected'}
              </span>
            </div>

            {status?.connected ? (
              <div className="space-y-4">
                <div className="text-sm">
                  <p><strong>Bot:</strong> @{status.bot_username}</p>
                  <p><strong>Chat ID:</strong> {status.chat_id}</p>
                </div>
                <div className="rounded border border-green-200 bg-green-50 p-3 text-sm text-green-700">
                  The bot is linked to this company. Send a receipt or expense description to the bot on Telegram.
                </div>
                <button
                  onClick={() => disconnectMutation.mutate()}
                  disabled={disconnectMutation.isPending}
                  className="bg-red-600 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
                >
                  Disconnect
                </button>
              </div>
            ) : pairingActive ? (
              <div className="space-y-4">
                <p className="text-sm text-gray-500">
                  Open the bot on Telegram, press Start, and this page will update automatically.
                </p>
                <a
                  href={pairing.pairing_link ?? '#'}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold px-6 py-3 rounded text-center"
                >
                  Open Telegram
                </a>
                <div className="rounded border border-blue-200 bg-blue-50 p-4 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <p className="font-medium">One-time pairing code</p>
                    {countdown === 'expired' ? (
                      <span className="text-red-600 text-xs font-semibold">Expired</span>
                    ) : countdown ? (
                      <span className="text-gray-500 text-xs">Expires in {countdown}</span>
                    ) : null}
                  </div>
                  <div className="mt-2 flex items-center gap-2">
                    <code className="flex-1 break-all rounded bg-white p-2">
                      {pairing.pairing_code}
                    </code>
                    <button
                      onClick={copyCode}
                      className="shrink-0 border border-blue-600 text-blue-700 px-3 py-1.5 rounded text-xs font-medium hover:bg-blue-50"
                    >
                      {copied ? 'Copied!' : 'Copy'}
                    </button>
                  </div>
                  <ol className="mt-3 list-decimal pl-5 space-y-1 text-gray-600">
                    <li>Press <strong>Open Telegram</strong> above.</li>
                    <li>Press <strong>Start</strong> in the chat with @{pairing.bot_username}.</li>
                    <li>Wait for the &quot;Connected!&quot; message — this page updates automatically.</li>
                  </ol>
                </div>
                <button
                  onClick={() => connectMutation.mutate()}
                  disabled={connectMutation.isPending}
                  className="text-blue-700 text-sm underline disabled:opacity-50"
                >
                  Generate a new pairing link
                </button>
              </div>
            ) : (
              <div className="space-y-4">
                <p className="text-sm text-gray-500">
                  Connect your Telegram bot to process expenses and receipts from chat messages.
                </p>
                {!botConfig?.configured && (
                  <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded p-3">
                    Set up the bot above first, then connect it to this company.
                  </p>
                )}
                <button
                  onClick={() => connectMutation.mutate()}
                  disabled={connectMutation.isPending || !botConfig?.configured}
                  className="bg-blue-600 text-white px-4 py-2 rounded text-sm disabled:opacity-50"
                >
                  {connectMutation.isPending ? 'Connecting...' : 'Connect Telegram Bot'}
                </button>
                {connectMutation.isError && (
                  <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                    {(connectMutation.error as { response?: { data?: { detail?: string } } })
                      ?.response?.data?.detail ??
                      'Could not connect. Please try again.'}
                  </div>
                )}
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}
