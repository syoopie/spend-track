import { useEffect, useRef, useState } from 'react'
import type { MonthlyTotal } from '../api/types'
import { currentMonthKey, fmtMonthRangeLabel, shiftMonth } from '../lib/format'
import { MonthRangeCalendar } from './MonthRangeCalendar'

export function DateRangePicker({
  value,
  onChange,
  monthlyTotals,
}: {
  value: { from: string; to: string }
  onChange: (range: { from: string; to: string }) => void
  monthlyTotals: MonthlyTotal[]
}) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) setOpen(false)
    }
    window.addEventListener('mousedown', onClickOutside)
    return () => window.removeEventListener('mousedown', onClickOutside)
  }, [open])

  const allMonths = monthlyTotals.map((t) => t.month)
  const earliest = allMonths.length ? allMonths.reduce((a, b) => (a < b ? a : b)) : value.from
  const latest = allMonths.length ? allMonths.reduce((a, b) => (a > b ? a : b)) : value.to

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        // DASH-8 in UI Review.dc.html: "Jun – Aug 2026" would wrap to two
        // lines and change the header row's height - a fixed min-width and
        // whitespace-nowrap keep the trigger a stable single line.
        className="text-md px-3 py-2 rounded-lg border border-border bg-input text-text cursor-pointer flex items-center gap-1.5 whitespace-nowrap min-w-[168px] justify-between"
      >
        {fmtMonthRangeLabel(value.from, value.to)}
        <span className="text-muted-2 text-[10px]">▾</span>
      </button>
      {open && (
        <div className="absolute left-0 top-[calc(100%+6px)] z-40 bg-card border border-border rounded-xl p-4 shadow-xl w-[400px] max-w-[90vw]">
          <MonthRangeCalendar
            monthlyTotals={monthlyTotals}
            value={value}
            onChange={(range) => {
              onChange(range)
              setOpen(false)
            }}
          />
          <div className="flex gap-3 mt-2.5 pt-2.5 border-t border-border flex-wrap">
            <button
              type="button"
              onClick={() => {
                onChange({ from: latest, to: latest })
                setOpen(false)
              }}
              className="text-xs text-accent hover:text-accent-hover bg-transparent border-none cursor-pointer p-0"
            >
              Latest month
            </button>
            <button
              type="button"
              onClick={() => {
                onChange({ from: shiftMonth(latest, -2), to: latest })
                setOpen(false)
              }}
              className="text-xs text-accent hover:text-accent-hover bg-transparent border-none cursor-pointer p-0"
            >
              Last 3 months
            </button>
            <button
              type="button"
              onClick={() => {
                onChange({ from: `${currentMonthKey().slice(0, 4)}-01`, to: latest })
                setOpen(false)
              }}
              className="text-xs text-accent hover:text-accent-hover bg-transparent border-none cursor-pointer p-0"
            >
              Year to date
            </button>
            <button
              type="button"
              onClick={() => {
                onChange({ from: earliest, to: latest })
                setOpen(false)
              }}
              className="text-xs text-accent hover:text-accent-hover bg-transparent border-none cursor-pointer p-0"
            >
              All time
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
