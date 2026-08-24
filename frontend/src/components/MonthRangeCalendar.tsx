import { useEffect, useMemo, useState } from 'react'
import type { MonthlyTotal } from '../api/types'
import { currentMonthKey, fmtCompact, shiftMonth } from '../lib/format'

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

  // The most recent 12 months, ending at the current month - selection never
  // extends into the future.
  const months = useMemo(() => {
    const current = currentMonthKey()
    const out: string[] = []
    for (let i = 11; i >= 0; i--) out.push(shiftMonth(current, -i))
    return out
  }, [])

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
      <div className="grid grid-cols-4 gap-2.5">
        {months.map((key) => {
          const [y, m] = key.split('-')
          const label = new Date(Number(y), Number(m) - 1, 1).toLocaleDateString('en-US', { month: 'short' })
          const totals = totalsByMonth.get(key)
          const selected = key >= displayRange.from && key <= displayRange.to
          return (
            <button
              key={key}
              type="button"
              onMouseDown={() => {
                setDragStart(key)
                setHoverMonth(key)
              }}
              onMouseEnter={() => dragging && setHoverMonth(key)}
              className={`text-left px-3 py-2.5 rounded-md border cursor-pointer ${
                selected ? 'border-accent bg-accent/15' : 'border-border bg-input hover:border-muted-2'
              }`}
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
        Click a month, or click and drag across months to select a range.
      </div>
    </div>
  )
}
