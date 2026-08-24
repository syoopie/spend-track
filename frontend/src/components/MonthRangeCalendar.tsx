import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import type { MonthlyTotal } from '../api/types'
import { currentMonthKey, fmtCompact } from '../lib/format'

function normalize(a: string, b: string): { from: string; to: string } {
  return a <= b ? { from: a, to: b } : { from: b, to: a }
}

export function MonthRangeCalendar({
  monthlyTotals,
  value,
  onChange,
}: {
  monthlyTotals: MonthlyTotal[]
  value: { from: string; to: string }
  onChange: (range: { from: string; to: string }) => void
}) {
  const totalsByMonth = useMemo(() => {
    const m = new Map<string, MonthlyTotal>()
    for (const t of monthlyTotals) m.set(t.month, t)
    return m
  }, [monthlyTotals])

  const currentKey = currentMonthKey()
  const currentYear = Number(currentKey.slice(0, 4))
  // Earliest year with any recorded data - paging further back than this
  // would only ever show a grid of unreachable months, so the "previous
  // year" arrow stops here rather than letting the user wander into empty
  // years indefinitely.
  const earliestYear = useMemo(() => {
    if (monthlyTotals.length === 0) return currentYear
    return Math.min(...monthlyTotals.map((t) => Number(t.month.slice(0, 4))))
  }, [monthlyTotals, currentYear])

  // DASH-8 in UI Review.dc.html: this used to always show the trailing 12
  // months ending at the current month regardless of how much history
  // existed, so anything older than a year back was reachable only through
  // the "All time" shortcut. A full calendar-year grid, paged by year, can
  // reach any month with data.
  const [displayYear, setDisplayYear] = useState(() => Number(value.to.slice(0, 4)))

  const months = useMemo(() => {
    const out: string[] = []
    for (let m = 1; m <= 12; m++) out.push(`${displayYear}-${String(m).padStart(2, '0')}`)
    return out
  }, [displayYear])

  const [dragStart, setDragStart] = useState<string | null>(null)
  const [hoverMonth, setHoverMonth] = useState<string | null>(null)
  const dragging = dragStart != null

  const displayRange = dragging && hoverMonth ? normalize(dragStart, hoverMonth) : value

  useEffect(() => {
    if (!dragging) return
    function onMouseUp() {
      if (dragStart && hoverMonth) onChange(normalize(dragStart, hoverMonth))
      setDragStart(null)
      setHoverMonth(null)
    }
    window.addEventListener('mouseup', onMouseUp)
    return () => window.removeEventListener('mouseup', onMouseUp)
  }, [dragging, dragStart, hoverMonth, onChange])

  return (
    <div className="select-none">
      <div className="flex items-center justify-between mb-2.5">
        <button
          type="button"
          onClick={() => setDisplayYear((y) => y - 1)}
          disabled={displayYear <= earliestYear}
          aria-label="Previous year"
          className="p-1 rounded-md border-none bg-transparent text-muted hover:text-text cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <ChevronLeft size={15} />
        </button>
        <div className="text-sm font-semibold font-display">{displayYear}</div>
        <button
          type="button"
          onClick={() => setDisplayYear((y) => y + 1)}
          disabled={displayYear >= currentYear}
          aria-label="Next year"
          className="p-1 rounded-md border-none bg-transparent text-muted hover:text-text cursor-pointer disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <ChevronRight size={15} />
        </button>
      </div>
      <div className="grid grid-cols-4 gap-2.5">
        {months.map((key) => {
          const [y, m] = key.split('-')
          const label = new Date(Number(y), Number(m) - 1, 1).toLocaleDateString('en-US', { month: 'short' })
          const totals = totalsByMonth.get(key)
          const selected = key >= displayRange.from && key <= displayRange.to
          const isFuture = key > currentKey
          // Dimmed rather than functionally `disabled` (DASH-8's "disable
          // months that have no data") - a disabled native <button> stops
          // receiving mouseenter in some browsers, which would break
          // dragging a range across a month with genuinely zero activity in
          // the middle of it. Future months are truly disabled instead,
          // since they can never become selectable no matter what.
          const hasData = !!totals && (totals.inflow > 0 || totals.outflow > 0)
          return (
            <button
              key={key}
              type="button"
              disabled={isFuture}
              onMouseDown={() => {
                if (isFuture) return
                setDragStart(key)
                setHoverMonth(key)
              }}
              onMouseEnter={() => dragging && !isFuture && setHoverMonth(key)}
              className={`text-left px-3 py-2.5 rounded-md border ${
                isFuture ? 'cursor-not-allowed opacity-30' : 'cursor-pointer'
              } ${
                selected ? 'border-accent bg-accent/15' : 'border-border bg-input hover:border-muted-2'
              } ${!isFuture && !hasData ? 'opacity-50' : ''}`}
            >
              <div className={`text-title-sm font-semibold ${selected ? 'text-text' : 'text-muted'}`}>
                {label} <span className="text-muted-2 font-normal">'{y.slice(2)}</span>
              </div>
              <div className="text-xs font-mono text-success leading-tight mt-0.5">
                {totals && totals.inflow > 0 ? fmtCompact(totals.inflow) : ' '}
              </div>
              <div className="text-xs font-mono text-danger-text leading-tight">
                {totals && totals.outflow > 0 ? fmtCompact(totals.outflow) : ' '}
              </div>
            </button>
          )
        })}
      </div>
      <div className="text-xs text-muted-2 mt-3 pt-2.5 border-t border-border">
        Click a month, or click and drag across months to select a range. Faded months have no recorded activity.
      </div>
    </div>
  )
}
