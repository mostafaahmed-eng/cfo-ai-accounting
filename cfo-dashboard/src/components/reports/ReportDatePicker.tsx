'use client'

interface DateRangePickerProps {
  startDate: string
  endDate: string
  onStartDateChange: (value: string) => void
  onEndDateChange: (value: string) => void
}

interface AsOfDatePickerProps {
  asOf: string
  onChange: (value: string) => void
}

function displayDate(value: string): string {
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(`${value}T00:00:00Z`))
}

export function DateRangePicker({
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
}: DateRangePickerProps) {
  const valid = startDate <= endDate

  return (
    <div className="mb-6 rounded-lg border bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-end gap-4">
        <label className="text-sm font-medium text-gray-700">
          Start date
          <input
            type="date"
            value={startDate}
            max={endDate}
            onChange={event => onStartDateChange(event.target.value)}
            className="mt-1 block rounded-md border border-gray-300 px-3 py-2"
          />
        </label>
        <label className="text-sm font-medium text-gray-700">
          End date
          <input
            type="date"
            value={endDate}
            min={startDate}
            onChange={event => onEndDateChange(event.target.value)}
            className="mt-1 block rounded-md border border-gray-300 px-3 py-2"
          />
        </label>
        <p className="pb-2 text-sm text-gray-600" aria-live="polite">
          {valid
            ? `${displayDate(startDate)} – ${displayDate(endDate)}`
            : 'Start date must not be after end date'}
        </p>
      </div>
    </div>
  )
}

export function AsOfDatePicker({ asOf, onChange }: AsOfDatePickerProps) {
  return (
    <div className="mb-6 rounded-lg border bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-end gap-4">
        <label className="text-sm font-medium text-gray-700">
          As of
          <input
            type="date"
            value={asOf}
            onChange={event => onChange(event.target.value)}
            className="mt-1 block rounded-md border border-gray-300 px-3 py-2"
          />
        </label>
        <p className="pb-2 text-sm text-gray-600" aria-live="polite">
          As of {displayDate(asOf)}
        </p>
      </div>
    </div>
  )
}
