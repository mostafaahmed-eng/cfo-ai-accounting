'use client'

export default function RecentTransactions({ transactions }: { transactions: Record<string, unknown>[] }) {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold mb-4">Recent Transactions</h3>
      {transactions.length === 0 ? (
        <p className="text-gray-500 text-sm">No recent transactions</p>
      ) : (
        <div className="space-y-3">
          {transactions.slice(0, 5).map((t, i) => (
            <div key={i} className="flex justify-between items-center border-b pb-2">
              <div>
                <p className="font-medium text-sm">{String(t.description)}</p>
                <p className="text-xs text-gray-500">{String(t.date)}</p>
              </div>
              <span className={`font-semibold ${Number(t.amount) < 0 ? 'text-red-600' : 'text-green-600'}`}>
                ${Number(t.amount).toLocaleString()}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
