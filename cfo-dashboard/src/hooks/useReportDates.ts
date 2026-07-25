'use client'

import { useCallback, useEffect, useMemo, useState } from 'react'

export interface DateRange {
  startDate: string
  endDate: string
}

function toIsoDate(date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function defaultReportRange(): DateRange {
  const now = new Date()
  return {
    startDate: toIsoDate(new Date(now.getFullYear(), now.getMonth(), 1)),
    endDate: toIsoDate(new Date(now.getFullYear(), now.getMonth() + 1, 0)),
  }
}

function replaceQueryParams(updates: Record<string, string>) {
  const params = new URLSearchParams(window.location.search)
  Object.entries(updates).forEach(([key, value]) => params.set(key, value))
  window.history.replaceState(
    null,
    '',
    `${window.location.pathname}?${params.toString()}${window.location.hash}`,
  )
}

export function useReportDateRange() {
  const [range, setRange] = useState<DateRange>(defaultReportRange)

  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const startDate = params.get('start_date')
    const endDate = params.get('end_date')
    if (startDate && endDate) {
      setRange({ startDate, endDate })
    }
  }, [])

  const updateRange = useCallback((next: DateRange) => {
    setRange(next)
    replaceQueryParams({
      start_date: next.startDate,
      end_date: next.endDate,
    })
  }, [])

  return {
    ...range,
    isValid: range.startDate <= range.endDate,
    setStartDate: (startDate: string) => updateRange({ ...range, startDate }),
    setEndDate: (endDate: string) => updateRange({ ...range, endDate }),
  }
}

export function useReportAsOfDate() {
  const defaultAsOf = useMemo(() => toIsoDate(new Date()), [])
  const [asOf, setAsOfState] = useState(defaultAsOf)

  useEffect(() => {
    const value = new URLSearchParams(window.location.search).get('as_of')
    if (value) {
      setAsOfState(value)
    }
  }, [])

  const setAsOf = useCallback((value: string) => {
    setAsOfState(value)
    replaceQueryParams({ as_of: value })
  }, [])

  return { asOf, setAsOf }
}
