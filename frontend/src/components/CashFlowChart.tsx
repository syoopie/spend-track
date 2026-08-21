import type { CashFlowMonth, MonthlyTotal } from '../api/types'
import { fmtCompact, fmtMonthLabel, fmtMonthRangeLabel } from '../lib/format'

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

  const content = (
    <>
      <div className="text-[13px] font-semibold mb-4">{title}</div>
      <div className="flex items-end gap-3.5 h-[150px] px-1.5 overflow-x-auto">
        {chartData.map((m) => {
          const isSelected = !padded || (m.month >= rangeFrom && m.month <= rangeTo)
          return (
            <div key={m.month} className={`flex flex-col items-center gap-1.5 flex-1 min-w-[36px] ${isSelected ? '' : 'opacity-45'}`}>
              <div className="flex items-end gap-1 h-[120px]">
                <div className="flex flex-col items-center justify-end h-full">
                  {m.inflow > 0 && <div className="text-[10px] font-mono text-muted-2 mb-0.5">{fmtCompact(m.inflow)}</div>}
                  <div
                    className="w-3.5 rounded-t-[3px] bg-success"
                    style={{ height: `${Math.max(1, (m.inflow / max) * 120)}px` }}
                  />
                </div>
                <div className="flex flex-col items-center justify-end h-full">
                  {m.outflow > 0 && <div className="text-[10px] font-mono text-muted-2 mb-0.5">{fmtCompact(m.outflow)}</div>}
                  <div
                    className="w-3.5 rounded-t-[3px]"
                    style={{ height: `${Math.max(1, (m.outflow / max) * 120)}px`, background: isSelected ? 'var(--color-accent)' : '#3a3b48' }}
                  />
                </div>
              </div>
              <div className={`text-[11px] ${isSelected ? 'text-text font-semibold' : 'text-muted-2'}`}>
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
          <span className={padded ? 'text-accent' : 'text-[#3a3b48]'}>■</span> Outflow{padded ? ' (selected range)' : ''}
        </span>
        {padded && (
          <span>
            <span className="text-[#3a3b48]">■</span> Outflow (prior months)
          </span>
        )}
      </div>
    </>
  )

  if (bare) return content
  return <div className="bg-card border border-border rounded-xl p-5">{content}</div>
}
