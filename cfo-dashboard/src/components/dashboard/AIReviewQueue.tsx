'use client'

import type { DraftTransaction } from '@/lib/types'

export default function AIReviewQueue({ items }: { items: DraftTransaction[] }) {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-semibold mb-4">AI Review Queue</h3>
      {items.length === 0 ? (
        <p className="text-gray-500 text-sm">No items awaiting review</p>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div key={item.id} className="border rounded p-3 flex justify-between items-center">
              <div>
                <p className="font-medium text-sm">{item.description}</p>
                <p className="text-xs text-gray-500">{item.transaction_date} &middot; {item.currency}</p>
              </div>
              <div className="text-right">
                <p className="font-semibold">{item.currency} {item.amount.toLocaleString()}</p>
                {item.ai_confidence != null && (
                  <p className="text-xs text-gray-500">AI: {(item.ai_confidence * 100).toFixed(0)}%</p>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
