import { useState } from 'react'
import type { CashFlowMonth, MonthlyTotal } from '../api/types'
import { fmtCompact, fmtMonthLabel, fmtMonthRangeLabel, fmtPlain } from '../lib/format'

const MIN_MONTHS = 6
const MAX_MONTHS = 12

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
  const [hoveredMonth, setHoveredMonth] = useState<string | null>(null)

  const padded = data.length < MIN_MONTHS && !!trend && trend.length > 0
  const chartData = padded
    ? trend!.filter((m) => m.month <= rangeTo).slice(-MIN_MONTHS)
    : data.length > MAX_MONTHS
      ? data.slice(-MAX_MONTHS)
      : data
  const truncated = !padded && data.length > MAX_MONTHS

  const max = Math.max(1, ...chartData.flatMap((d) => [d.inflow, d.outflow]))
  const title = padded
    ? `Cash Flow — Trend into ${fmtMonthRangeLabel(rangeFrom, rangeTo)}`
    : `Cash Flow — Inflow vs Outflow${truncated ? ' (most recent 12 months)' : ''}`

  const hovered = chartData.find((m) => m.month === hoveredMonth)

  const content = (
    <>
      <div className="text-[13px] font-semibold mb-4">{title}</div>
      <div className="flex items-end gap-3.5 h-[150px] px-1.5 overflow-x-auto overflow-y-visible">
        {chartData.map((m) => {
          const isSelected = !padded || (m.month >= rangeFrom && m.month <= rangeTo)
          const isHovered = m.month === hoveredMonth
          return (
            <div
              key={m.month}
              onMouseEnter={() => setHoveredMonth(m.month)}
              onMouseLeave={() => setHoveredMonth(null)}
              className={`relative flex flex-col items-center gap-1.5 flex-1 min-w-[36px] rounded-md transition-colors cursor-default
                ${isSelected ? '' : 'opacity-45'} ${isHovered ? 'bg-input' : ''}`}
            >
              {isHovered && (
                <div
                  className="absolute bottom-full mb-1.5 left-1/2 -translate-x-1/2 pointer-events-none bg-card border border-border rounded-lg shadow-xl px-2.5 py-2 text-[11px] whitespace-nowrap z-10"
                >
                  <div className="font-semibold text-text mb-1">{fmtMonthLabel(m.month)}</div>
                  <div className="flex items-center gap-1.5 text-success">
                    <span className="w-1.5 h-1.5 rounded-full bg-success shrink-0" />
                    Inflow: <span className="font-mono text-text">{fmtPlain(m.inflow)}</span>
                  </div>
                  <div className="flex items-center gap-1.5 text-accent">
                    <span className="w-1.5 h-1.5 rounded-full bg-accent shrink-0" />
                    Outflow: <span className="font-mono text-text">{fmtPlain(m.outflow)}</span>
                  </div>
                  <div className="text-muted-2 mt-0.5">Net: <span className="font-mono text-text">{fmtPlain(m.inflow - m.outflow)}</span></div>
                </div>
              )}
              <div className="flex items-end gap-1 h-[120px] pt-1.5">
                <div className="flex flex-col items-center justify-end h-full">
                  {m.inflow > 0 && <div className="text-[10px] font-mono text-muted-2 mb-0.5">{fmtCompact(m.inflow)}</div>}
                  <div
                    className={`w-3.5 rounded-t-[3px] bg-success transition-transform origin-bottom ${isHovered ? 'scale-x-125' : ''}`}
                    style={{ height: `${Math.max(1, (m.inflow / max) * 120)}px` }}
                  />
                </div>
                <div className="flex flex-col items-center justify-end h-full">
                  {m.outflow > 0 && <div className="text-[10px] font-mono text-muted-2 mb-0.5">{fmtCompact(m.outflow)}</div>}
                  <div
                    className={`w-3.5 rounded-t-[3px] transition-transform origin-bottom ${isHovered ? 'scale-x-125' : ''}`}
                    style={{ height: `${Math.max(1, (m.outflow / max) * 120)}px`, background: isSelected ? 'var(--color-accent)' : 'var(--color-dim)' }}
                  />
                </div>
              </div>
              <div className={`text-[11px] pb-0.5 ${isSelected || isHovered ? 'text-text font-semibold' : 'text-muted-2'}`}>
                {fmtMonthLabel(m.month)}
              </div>
            </div>
          )
        })}
      </div>
      <div className="flex gap-4 text-[11px] text-muted mt-1.5">
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
        {hovered && <span className="ml-auto text-muted-2">Net: <span className="font-mono text-text">{fmtPlain(hovered.inflow - hovered.outflow)}</span></span>}
      </div>
    </>
  )

  if (bare) return content
  return <div className="bg-card border border-border rounded-xl p-5">{content}</div>
}
