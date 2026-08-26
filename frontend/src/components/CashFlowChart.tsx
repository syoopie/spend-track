import { useState } from 'react'
import type { CashFlowMonth, MonthlyTotal } from '../api/types'
import { Card } from './Card'
import { fmtMonthLabel, fmtPlain } from '../lib/format'

const MIN_MONTHS = 6
const MAX_MONTHS = 12

// Exposed so Dashboard.tsx can render this on the shared Tabs row's right
// edge instead of as a second heading inside the card (DASH-3 in
// UI Review.dc.html - the tab already reads "Cash Flow", so the panel
// heading below it repeating "Cash Flow — ..." was a literal duplicate).
// null means there's nothing to add beyond what the tab label already says.
export function cashFlowQualifier(data: CashFlowMonth[], trend: MonthlyTotal[] | undefined): string | null {
  const padded = data.length < MIN_MONTHS && !!trend && trend.length > 0
  if (padded) return 'recent trend'
  if (data.length > MAX_MONTHS) return 'most recent 12 months'
  return null
}

export function CashFlowChart({
  data,
  trend,
  rangeFrom,
  rangeTo,
  bare = false,
}: {
  data: CashFlowMonth[]
  trend?: MonthlyTotal[]
  rangeFrom: string
  rangeTo: string
  bare?: boolean
}) {
  const [hovered, setHovered] = useState<string | null>(null)

  const padded = data.length < MIN_MONTHS && !!trend && trend.length > 0
  const chartData = padded
    ? trend!.filter((m) => m.month <= rangeTo).slice(-MIN_MONTHS)
    : data.length > MAX_MONTHS
      ? data.slice(-MAX_MONTHS)
      : data

  const max = Math.max(1, ...chartData.flatMap((d) => [d.inflow, d.outflow]))
  const hoveredMonth = chartData.find((m) => m.month === hovered) ?? null

  // Bars used to sit in flex-1 columns with a fixed 36px min-width, which
  // forced a horizontal scrollbar once 9+ months didn't fit that width in a
  // narrower card. Scaling the bar/gap sizes down as the month count grows
  // (instead of holding size fixed and letting the row overflow) means the
  // full range always fits in whatever width the card actually has.
  const n = chartData.length
  // Bars grow with the column they sit in and are only *capped* per month
  // count, rather than being pinned to a fixed width. Fixed widths meant a
  // wide card stretched the columns but not the bars, so a 6-month range on
  // a large screen drew two 14px slivers marooned in a 150px column.
  const barMaxW = n > 9 ? 'max-w-3' : n > 6 ? 'max-w-4.5' : 'max-w-7'
  const barGap = n > 9 ? 'gap-0.5' : 'gap-1'
  const colGap = n > 9 ? 'gap-1' : n > 6 ? 'gap-2' : 'gap-3.5'

  const content = (
    <>
      {!bare && <div className="text-md font-semibold mb-4">Cash Flow</div>}
      {/* DASH-4: a per-bar value label above all 24 bars at 12 months was a
          wall of grey micro-text over 8px-wide bars. Now only the hovered
          month's figures show, in a floating tooltip - the same "hover for
          detail" contract VelocityChart already uses in the same card. */}
      <div className={`flex items-end ${colGap} h-[150px] px-1.5`}>
        {chartData.map((m) => {
          const isSelected = !padded || (m.month >= rangeFrom && m.month <= rangeTo)
          return (
            <div
              key={m.month}
              onMouseEnter={() => setHovered(m.month)}
              onMouseLeave={() => setHovered((h) => (h === m.month ? null : h))}
              className={`relative flex flex-col items-center gap-1.5 flex-1 min-w-0 ${isSelected ? '' : 'opacity-45'}`}
            >
              {hoveredMonth?.month === m.month && (
                <div className="absolute bottom-full mb-1.5 left-1/2 -translate-x-1/2 pointer-events-none bg-card border border-border rounded-lg shadow-xl px-2.5 py-2 text-2xs whitespace-nowrap z-10">
                  <div className="font-semibold text-text mb-1">{fmtMonthLabel(m.month)}</div>
                  <div className="flex items-center gap-1.5 text-success">
                    <span className="w-1.5 h-1.5 rounded-full bg-success shrink-0" />
                    Inflow: <span className="font-mono text-text">{fmtPlain(m.inflow)}</span>
                  </div>
                  <div className="flex items-center gap-1.5" style={{ color: isSelected ? 'var(--color-accent)' : 'var(--color-dim)' }}>
                    <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ background: isSelected ? 'var(--color-accent)' : 'var(--color-dim)' }} />
                    Outflow: <span className="font-mono text-text">{fmtPlain(m.outflow)}</span>
                  </div>
                </div>
              )}
              <div className={`flex items-end justify-center w-full ${barGap} h-[120px]`}>
                <div
                  className={`flex-1 min-w-[6px] ${barMaxW} rounded-t-[3px] bg-success transition-opacity ${hovered && !hoveredMonth ? '' : hovered && hovered !== m.month ? 'opacity-60' : ''}`}
                  style={{ height: `${Math.max(1, (m.inflow / max) * 120)}px` }}
                />
                <div
                  className={`flex-1 min-w-[6px] ${barMaxW} rounded-t-[3px] transition-opacity ${hovered && hovered !== m.month ? 'opacity-60' : ''}`}
                  style={{ height: `${Math.max(1, (m.outflow / max) * 120)}px`, background: isSelected ? 'var(--color-accent)' : 'var(--color-dim)' }}
                />
              </div>
              <div className={`text-2xs text-center ${isSelected ? 'text-text font-semibold' : 'text-muted-2'}`}>
                {fmtMonthLabel(m.month)}
              </div>
            </div>
          )
        })}
      </div>
      <div className="flex gap-4 text-2xs text-muted mt-1.5">
        <span>
          <span className="text-success">■</span> Inflow
        </span>
        <span>
          <span className={padded ? 'text-accent' : 'text-dim'}>■</span> Outflow{padded ? ' (selected range)' : ''}
        </span>
        {padded && (
          <span>
            <span className="text-dim">■</span> Outflow (prior months)
          </span>
        )}
      </div>
    </>
  )

  if (bare) return content
  return <Card>{content}</Card>
}
