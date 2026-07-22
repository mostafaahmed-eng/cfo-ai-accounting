'use client'

export default function BudgetWarnings({ warnings }: { warnings: Record<string, unknown>[] }) {
  if (warnings.length === 0) return null

  return (
    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-6">
      <h3 className="text-lg font-semibold mb-4 text-yellow-800">Budget Warnings</h3>
      <div className="space-y-2">
        {warnings.map((w, i) => (
          <div key={i} className="flex items-center gap-2 text-sm text-yellow-700">
            <span className="font-medium">{String(w.category)}</span>
            <span>- {String(w.message)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
